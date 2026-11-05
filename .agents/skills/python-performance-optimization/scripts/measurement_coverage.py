"""Offline observation coverage; never grants research adoption or start permission."""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path


def clock(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError('Timezone-aware observation and stage clocks required')
    return result


def cpu(row, pid, created):
    matches = [p for p in row.get('processes', []) if p.get('pid') == pid]
    if len(matches) != 1:
        return None
    process = matches[0]
    try:
        if clock(process['created']) != created:
            return None
    except (KeyError, ValueError, TypeError):
        return None
    value = process.get('cpu_sec')
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def coverage(datasets, stage):
    start, end, created = (clock(stage[k]) for k in ('start', 'end', 'created'))
    pid = stage['pid']
    if type(pid) is not int or pid <= 0 or end <= start or created > start:
        raise ValueError('Positive actual PID and ordered, bound stage clocks required')
    intervals = []
    rejected = {'failed_sample': 0, 'clock_or_gap': 0, 'identity_or_cpu': 0}
    for rows in datasets:
        for before, after in zip(rows, rows[1:]):
            if 'error' in before or 'error' in after:
                rejected['failed_sample'] += 1
                continue
            try:
                a, b = clock(before['observed_at']), clock(after['observed_at'])
            except (KeyError, ValueError, TypeError):
                rejected['clock_or_gap'] += 1
                continue
            if not 0 < (b-a).total_seconds() <= 120:
                rejected['clock_or_gap'] += 1
                continue
            old, new = cpu(before, pid, created), cpu(after, pid, created)
            if old is None or new is None or new < old:
                rejected['identity_or_cpu'] += 1
                continue
            left, right = max(start, a), min(end, b)
            if left < right:
                intervals.append((left, right))
    merged = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    duration = (end-start).total_seconds()
    covered = sum((b-a).total_seconds() for a, b in merged)
    return {'name': stage['name'], 'pid': pid, 'created': stage['created'],
            'start': stage['start'], 'end': stage['end'], 'duration_seconds': duration,
            'covered_seconds': covered, 'missing_seconds': duration-covered,
            'coverage_fraction': covered/duration, 'at_least_95pct': covered/duration >= .95,
            'merged_intervals': [[a.isoformat(), b.isoformat()] for a, b in merged],
            'rejected_adjacent_pairs': rejected}


def load(raw):
    return json.loads(raw.decode('utf-8-sig'))


def run(root, directories, stage_file, output):
    root, output, stage_file = root.resolve(), output.resolve(), stage_file.resolve()
    allowed = (root/'07_監視システム/verification', root/'06_研究結果/jdrt/goal_20261017')
    if not any(output.is_relative_to(p) and output != p for p in allowed):
        raise ValueError('New output directory must be in project operational evidence, never research runs')
    if not stage_file.is_relative_to(root):
        raise ValueError('Stage definitions must be project-local evidence')
    output.mkdir(parents=True, exist_ok=False)
    raw = stage_file.read_bytes()
    (output/'stage_definitions.json').write_bytes(raw)
    definitions = load(raw)
    if definitions.get('schema') != 'pipeline_stage_definitions_v1' or not definitions.get('stages'):
        raise ValueError('Explicit bound stage definitions required')
    evidence = definitions.get('evidence', {})
    if not evidence:
        raise ValueError('Stage provenance references required; interpretation remains caller responsibility')
    for name, expected in evidence.items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Stage provenance file missing or changed')
    datasets, sources = [], []
    for index, directory in enumerate(directories):
        snapshot = output/str(index)
        snapshot.mkdir()
        bindings = {}
        for name in ('state.json', 'samples.jsonl'):
            raw = (directory/name).read_bytes()
            (snapshot/name).write_bytes(raw)
            bindings[name] = sha256(raw).hexdigest()
        state = load((snapshot/'state.json').read_bytes())
        if state.get('schema') != 'pipeline_measurement_v1':
            raise ValueError('Unknown measurement schema')
        rows = [json.loads(line) for line in (snapshot/'samples.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        datasets.append(rows)
        walls = sorted(r['collection_wall_sec'] for r in rows if type(r.get('collection_wall_sec')) in (int, float)
                       and math.isfinite(r['collection_wall_sec']) and r['collection_wall_sec'] >= 0)
        sources.append({'source': str(directory.resolve()), 'snapshot_sha256': bindings,
                        'collector_source_sha256': state.get('source_sha256'),
                        'samples': len(rows), 'failed_samples': sum('error' in r for r in rows),
                        'collection_wall_seconds_p95_nearest_rank': walls[math.ceil(.95*len(walls))-1] if walls else None,
                        'state_sample_count_is_not_snapshot_consistency_proof': True})
    report = {'schema': 'measurement_interval_coverage_v1', 'status': 'OBSERVATION_COVERAGE_ONLY',
              'at_jst': datetime.now().astimezone().isoformat(),
              'run_id': definitions['run_id'], 'registration_id': definitions['registration_id'],
              'helper_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'stage_definitions_sha256': sha256((output/'stage_definitions.json').read_bytes()).hexdigest(),
              'stage_provenance_sha256': evidence, 'sources': sources,
              'stages': [coverage(datasets, stage) for stage in definitions['stages']],
              'limitations': ['Sampling intervals use observed_at; CPU query occurs within collection_wall_sec',
                             'Only same PID+creation endpoints with finite nondecreasing CPU and <=120sec intervals count',
                             'Stage definitions and their semantic primary-evidence bindings require caller review',
                             'Coverage is not scientific acceptance, stage-B completion, causality, exact memory peak or efficiency improvement',
                             'Snapshots of live append-only sources are point observations; state and samples are not an atomic pair']}
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--measurement-dir', type=Path, action='append', required=True)
    parser.add_argument('--stages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.project_root, args.measurement_dir, args.stages, args.output)
    print(json.dumps({'status': result['status'], 'stages': [
        {k: stage[k] for k in ('name','coverage_fraction','at_least_95pct')} for stage in result['stages']]}, ensure_ascii=False))
