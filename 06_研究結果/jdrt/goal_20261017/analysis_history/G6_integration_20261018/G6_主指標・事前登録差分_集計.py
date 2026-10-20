"""All-cell-gated primary analysis. This is one component, not the final report.

No simulation imports or execution. No partial-set override. R0 is reused only as
the registered paired reference; reused rows are never independent replicates.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
CONFIG = '04_プログラム/config/jdrt_realtime_choice_v1.json'


def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def table(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def local(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), 'Evidence path outside project')
    return path


def complete_records(root, cfg):
    """Stop before any result output or population reading on an incomplete set."""
    ledger_path = local(root, cfg['record_files'][-1])
    require(ledger_path.is_file(), 'Not ready: no formally recorded core ledger')
    records = [json.loads(line) for line in ledger_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    expected = {c['cell_id']: c for c in cfg['cells']}
    require(len(expected) == len(cfg['cells']), 'Duplicate registered cells')
    require(len(records) == len(expected), 'Not ready: complete registered set required')
    require(len({x['run_id'] for x in records}) == len(records), 'Duplicate accepted run')
    require(len({x['cell_id'] for x in records}) == len(records), 'Duplicate accepted cell')
    require({x['cell_id'] for x in records} == set(expected), 'Accepted and registered cell sets differ')
    for row in records:
        require(row['protocol'] == cfg['protocol'] and row['purpose'] == 'core'
                and row['validation_status'] == 'PASS', 'Foreign or unaccepted record')
        cell = expected[row['cell_id']]
        require(all(row[k] == cell[k] for k in cell), 'Recorded cell attributes differ')
        marker = '<!-- choice_record:' + row['run_id'] + ' -->'
        for name in cfg['record_files'][:-1]:
            path = local(root, name)
            require(path.is_file(), 'Missing record document: ' + name)
            text = path.read_text(encoding='utf-8')
            if path.name == 'context.md':
                text = text.split('\n<!-- AGENT_CURRENT_END -->')[0]
            require(marker in text, 'Partial six-file record: ' + row['run_id'])
    workspace = local(root, cfg['workspace'])
    for path in (workspace / 'record_transactions').glob('*/journal.json'):
        require(json.loads(path.read_text(encoding='utf-8'))['status'] != 'PREPARED', 'Unresolved record transaction')
    current = {name: digest(local(root, name)) for name in cfg['execution']['implementation_files']}
    accepted_ids = {row['run_id'] for row in records}
    for path in (workspace / 'runs').glob('*/manifest.json'):
        extra = json.loads(path.read_text(encoding='utf-8'))
        require(extra['status'] != 'RUNNING', 'A core is still running')
        if extra['run_id'] not in accepted_ids:
            require(extra['status'] in ('FAILED', 'INVALID') and
                    (workspace / 'driver_logs' / (extra['run_id'] + '.diagnosis.json')).is_file(),
                    'Unrecorded or undiagnosed core remains')
    verified = []
    for row in records:
        folder = workspace / 'runs' / row['run_id']
        mp = folder / 'manifest.json'
        require(digest(mp) == row['manifest_sha256'], 'Accepted manifest changed')
        m = json.loads(mp.read_text(encoding='utf-8'))
        require(m['purpose'] == 'core' and m['status'] == 'COMPLETED' and m['protocol'] == cfg['protocol'], 'Not a completed core')
        require(m['run_id'] == row['run_id'] and m['cell_id'] == row['cell_id'], 'Run identity differs')
        require(all(m[k] == expected[row['cell_id']][k] for k in expected[row['cell_id']]),
                'Manifest registered attributes differ')
        require(m['implementation_sha256'] == row['implementation_sha256'] == current, 'Mixed implementation set')
        require(m['parameter_sha256'] == digest(local(root, CONFIG)), 'Registered configuration changed')
        require(m['end_sec'] == cfg['simulation']['duration_sec'], 'Not the registered full horizon')
        proof_path = local(root, row['validation_report'])
        require(digest(proof_path) == row['validation_report_sha256'], 'Recorded validation changed')
        proof = json.loads(proof_path.read_text(encoding='utf-8'))
        require(proof['status'] == 'PASS' and proof['purpose'] == 'core'
                and proof['core_adoption_permitted'] is True and proof['pending'] == [], 'No formal core proof')
        require(proof['manifest_sha256'] == row['manifest_sha256'] and proof['run_id'] == row['run_id'], 'Validation identity differs')
        require(proof['implementation_sha256'] == current and proof['checks'] and all(proof['checks'].values()),
                'Incomplete validation metadata or checks')
        components = {'person_tables', 'candidate_tables', 'road_snapshots', 'actor_stream',
                      'movement_events', 'native_logs', 'native_fixture_boundaries'}
        require(set(proof['components']) == components and
                all(c['status'] == 'PASS' for c in proof['components'].values()), 'Missing validation component')
        verified.append((row, m, folder, proof))
    return verified


def person_metrics(people, source, terminals, horizon):
    by_id = {p['person_id']: p for p in people}
    require(len(by_id) == len(people) and set(by_id) == set(source), 'Population missing or duplicated')
    facility_counts = Counter()
    results, reasons = [], []
    for p in people:
        require(p['person_type'] == source[p['person_id']]['person_type'], 'Person type changed')
        admitted = p['status'] == 'admitted'
        require(admitted == (p['admitted_sec'] != ''), 'Admission status/time disagreement')
        if admitted:
            require(terminals[p['terminal_id']]['kind'] == 'facility', 'Exit counted as admission')
            require(0 <= float(p['admitted_sec']) <= horizon, 'Admission outside horizon')
            facility_counts[p['terminal_id']] += 1
    for tid, count in facility_counts.items():
        require(count <= int(terminals[tid]['capacity']), 'Shared facility capacity exceeded')
    for group in sorted({p['person_type'] for p in people}) + ['all']:
        selected = [p for p in people if group == 'all' or p['person_type'] == group]
        n = len(selected)
        admitted = sum(p['status'] == 'admitted' for p in selected)
        # Numeric zero is a valid arrival time. Exits and all other nonadmissions use H.
        integral = sum(min(float(p['admitted_sec']), horizon) if p['admitted_sec'] != '' else horizon for p in selected)
        results.append({'group': group, 'denominator': n, 'admitted': admitted,
                        'admitted_rate': admitted / n if n else None,
                        'boundary_exit': sum(p['status'] == 'boundary_exit' for p in selected),
                        'terminal_arrivals': sum(p['arrival_sec'] != '' for p in selected),
                        'unadmitted_time_person_sec': integral,
                        'normalized_unadmitted_time': integral / (horizon * n) if n else None})
        reasons.extend({'group': group, 'status': status, 'count': count}
                       for status, count in sorted(Counter(p['status'] for p in selected).items()))
    return results, reasons, facility_counts


def paired_contrasts(cells, cfg):
    indexed = {(x['destination_policy'], x['demand_level'], x['scenario'], x['seed']): x for x in cells}
    require(len(indexed) == len(cells), 'Ambiguous primary metric identities')
    destinations = list(dict.fromkeys(c['destination_policy'] for c in cfg['cells']))
    demands = list(dict.fromkeys(c['demand_level'] for c in cfg['cells'] if c['demand_level'] is not None))
    output = []
    metrics = ['admitted', 'admitted_rate', 'normalized_unadmitted_time', 'boundary_exit']
    for destination in destinations:
        for demand in demands:
            for seed in cfg['seeds']:
                for contrast in cfg['analysis']['primary_contrasts']:
                    left, right = contrast.split('-')
                    a = indexed[(destination, None if left == 'R0' else demand, left, seed)]
                    b = indexed[(destination, None if right == 'R0' else demand, right, seed)]
                    require(a['denominator'] == b['denominator'], 'Paired primary denominators differ')
                    row = {'contrast': contrast, 'destination_policy': destination, 'demand_level': demand,
                           'seed': seed, 'left_run_id': a['run_id'], 'right_run_id': b['run_id'],
                           'denominator': a['denominator'], 'R0_reused_reference': left == 'R0' or right == 'R0'}
                    row.update({key + '_difference': a[key] - b[key] for key in metrics})
                    row['admitted_percentage_point_difference'] = 100 * row['admitted_rate_difference']
                    output.append(row)
    return output


def write_table(path, rows):
    require(bool(rows), 'Refuse empty analysis table')
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    cfg = json.loads(local(root, CONFIG).read_text(encoding='utf-8'))
    verified = complete_records(root, cfg)  # Must succeed before output directory creation.
    primary, outcomes, reasons, provenance = [], [], [], []
    input_sha = set()
    for row, m, folder, proof in verified:
        inputs = local(root, m['input_directory'])
        im_path = inputs / 'manifest.json'
        require(digest(im_path) == m['input_manifest_sha256'] == row['input_manifest_sha256'], 'Input manifest changed')
        im = json.loads(im_path.read_text(encoding='utf-8'))
        bound = {im_path: m['input_manifest_sha256'], folder / 'manifest.json': row['manifest_sha256']}
        bound.update({local(root, name): value for name, value in im['source_sha256'].items()})
        bound.update({inputs / name: value for name, value in im['artifacts'].items()})
        bound.update({folder / name: value for name, value in m['output_sha256'].items()})
        bound.update({folder / 'implementation' / name: value for name, value in m['implementation_sha256'].items()})
        bound[folder / 'preflight_ready.json'] = m['preflight_ready_sha256']
        require(all(digest(p) == expected for p, expected in bound.items()), 'Primary source bytes changed before aggregation')
        input_sha.add(m['input_manifest_sha256'])
        source = {p['person_id']: p for p in table(inputs / 'people.csv')}
        terminals = {t['terminal_id']: t for t in table(inputs / 'terminals.csv')}
        metrics, states, facilities = person_metrics(table(folder / 'person_results.csv'), source, terminals, m['end_sec'])
        facility_rows = table(folder / 'facility_results.csv')
        require({p['terminal_id']: int(p['admitted']) for p in facility_rows} ==
                {tid: facilities[tid] for tid, t in terminals.items() if t['kind'] == 'facility'}, 'Facility/person admission accounting differs')
        identity = {k: row[k] for k in ['run_id', 'cell_id', 'destination_policy', 'demand_level', 'scenario', 'seed']}
        outcomes.extend({**identity, **value} for value in metrics)
        reasons.extend({**identity, **value} for value in states)
        selected = next(v for v in metrics if v['group'] == 'type4')
        require(selected['admitted'] == proof['components']['person_tables']['primary_admitted']
                and selected['denominator'] == proof['components']['person_tables']['primary_denominator'], 'Independent primary reaggregation disagrees')
        primary.append({**identity, **selected})
        require(all(digest(p) == expected for p, expected in bound.items()), 'Primary source bytes changed during aggregation')
        provenance.append({'run_id': row['run_id'], 'manifest_sha256': row['manifest_sha256'],
                           'validation_report': row['validation_report'], 'bound_files_verified': len(bound)})
    require(len(input_sha) == 1, 'Different input versions')
    contrasts = paired_contrasts(primary, cfg)
    summaries = []
    for key in sorted({(x['destination_policy'], x['demand_level'], x['contrast']) for x in contrasts}):
        group = [x for x in contrasts if (x['destination_policy'], x['demand_level'], x['contrast']) == key]
        require({x['seed'] for x in group} == set(cfg['seeds']), 'Incomplete paired seeds')
        for metric in [k for k in group[0] if k.endswith('_difference')]:
            values = [x[metric] for x in group]
            summaries.append({'destination_policy': key[0], 'demand_level': key[1], 'contrast': key[2],
                              'metric': metric, 'seeds': len(values), 'mean': mean(values), 'min': min(values), 'max': max(values)})
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%dT%H%M%S%f')
    target = root / '06_研究結果/jdrt/goal_20261017' / ('主指標集計_' + stamp)
    target.mkdir(exist_ok=False)
    for name, data in [('全セル主指標.csv', primary), ('全Type受入・退出・積分.csv', outcomes),
                       ('理由別全員会計.csv', reasons), ('PAP主差分_全seed.csv', contrasts), ('PAP主差分_記述集計.csv', summaries)]:
        write_table(target / name, data)
    manifest = {'scope': 'preregistered_primary_analysis_component_not_final_report', 'status': 'COMPLETED',
                'protocol': cfg['protocol'], 'registered_cell_count': len(cfg['cells']), 'accepted_cell_count': len(verified),
                'config_sha256': digest(local(root, CONFIG)), 'analysis_source_sha256': digest(Path(__file__)),
                'provenance': provenance, 'population_inference': False, 'R0_is_shared_not_independent_replication': True,
                'remaining': ['diagnostic_destination_demand_and_difference_in_differences', 'all_request_wait_censoring_and_lifecycle',
                              'candidate_road_movement_vehicle_secondary_tables', 'structural_bounds_workload_and_joint_interpretation',
                              'full_final_report_and_completion_audit'],
                'output_sha256': {p.name: digest(p) for p in target.iterdir() if p.is_file()}}
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'COMPLETED_COMPONENT', 'path': target.relative_to(root).as_posix()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
