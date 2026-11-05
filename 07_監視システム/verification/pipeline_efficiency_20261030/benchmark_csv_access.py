"""Isolated CSV access benchmark; no validator or research execution."""
import argparse
import csv
from datetime import datetime
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import time


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def scan(stream, indexed):
    reader = csv.reader(stream) if indexed else csv.DictReader(stream)
    header = next(reader, []) if indexed else reader.fieldnames
    if not header or len(header) != len(set(header)) or not {'time_sec', 'count'} <= set(header):
        raise ValueError('Unique header with time_sec and count required')
    time_key, count_key = (header.index('time_sec'), header.index('count')) if indexed else ('time_sec', 'count')
    rows, count_sum, time_sum = 0, 0, 0.0
    for row in reader:
        if indexed and not row:
            continue
        if len(row) != len(header) or (not indexed and (None in row or None in row.values())):
            raise ValueError('Ragged row')
        at = float(row[time_key])
        if not math.isfinite(at):
            raise ValueError('Nonfinite time')
        time_sum += at
        count_sum += int(row[count_key])
        rows += 1
    return {'rows': rows, 'count_sum': count_sum, 'time_sum': time_sum}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, manifest, output = args.project_root.resolve(), args.manifest.resolve(), args.output.resolve()
    if not output.is_relative_to(root / '07_監視システム/verification'):
        parser.error('New output directory under 07 verification required')
    if not manifest.is_relative_to(root / '04_プログラム/output'):
        parser.error('Existing archived research manifest required')
    raw = manifest.read_bytes()
    m = json.loads(raw)
    if m.get('purpose') != 'core' or m.get('status') != 'COMPLETED':
        parser.error('Completed core artifact required; this does not re-adopt it')
    artifact = 'edge_observations.csv.gz'
    source = manifest.parent / artifact
    expected = m['output_sha256'][artifact]
    if digest(source) != expected:
        parser.error('Archived artifact SHA mismatch')
    output.mkdir(parents=True, exist_ok=False)
    state = {'status': 'RUNNING', 'scope': 'CSV_ACCESS_MICROBENCH_ONLY',
             'started_at': datetime.now().astimezone().isoformat(), 'run_id': m['run_id'],
             'registration_id': m['registration_id'], 'manifest_sha256': sha256(raw).hexdigest(),
             'artifact_sha256': expected, 'script_sha256': digest(Path(__file__)), 'trials': [],
             'production_code_changed': False, 'core_adoption_permitted': False,
             'limits': ['Sequential warm-cache-sensitive trials; not a full validator or production speed comparison.',
                        'Equality covers complete row count and time/count aggregates only, not every research field.',
                        'Fixture-only experiment; indexed access is not installed in the frozen validator.']}
    def save():
        (output / 'result.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save()
    try:
        for indexed in (False, True):
            wall, cpu = time.perf_counter(), time.process_time()
            with gzip.open(source, 'rt', encoding='utf-8-sig', newline='') as stream:
                summary = scan(stream, indexed)
            state['trials'].append({'method': 'indexed' if indexed else 'dictionary',
                                    'wall_sec': time.perf_counter() - wall,
                                    'cpu_sec': time.process_time() - cpu, 'summary': summary})
            save()
        if state['trials'][0]['summary'] != state['trials'][1]['summary']:
            raise ValueError('CSV summary mismatch')
        if digest(source) != expected or manifest.read_bytes() != raw:
            raise ValueError('Source changed during measurement')
        state.update(status='COMPONENT_EXPERIMENT_COMPLETED', source_unchanged=True,
                     aggregate_equality=True, finished_at=datetime.now().astimezone().isoformat())
    except Exception as error:
        state.update(status='FAILED_PRESERVED', error=type(error).__name__)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
