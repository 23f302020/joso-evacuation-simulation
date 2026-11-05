"""All-cell-gated registered analysis components, not the final report.

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
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
CONFIG = '04_プログラム/config/jdrt_realtime_choice_v1.json'
REQUEST_SOURCE = Path(__file__).with_name('G6_要求待ち・打切り_集計.py')
SECONDARY_SOURCE = Path(__file__).with_name('G6_副指標・理論上限_集計.py')
SECONDARY_PROOF = Path(__file__).with_name('G6_副指標・理論上限_実装証跡.json')
METRICS = ['admitted', 'admitted_rate', 'normalized_unadmitted_time', 'boundary_exit']


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


def jsonlines(path):
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def load_request_component():
    """Execute precisely the bytes whose hash is recorded, without a pyc cache."""
    source = REQUEST_SOURCE.read_bytes()
    module = ModuleType('choice_request_analysis')
    exec(compile(source, str(REQUEST_SOURCE), 'exec'), module.__dict__)
    return module, sha256(source).hexdigest()


def load_secondary_component(root):
    source = SECONDARY_SOURCE.read_bytes()
    module = ModuleType('choice_secondary_analysis')
    exec(compile(source, str(SECONDARY_SOURCE), 'exec'), module.__dict__)
    proof_bytes = SECONDARY_PROOF.read_bytes()
    proof = json.loads(proof_bytes.decode('utf-8-sig'))
    require(proof['implementation_sha256'] and all(digest(local(root, name)) == value
        for name, value in proof['implementation_sha256'].items()), 'Frozen service-contract source changed; audit required')
    return module, sha256(source).hexdigest(), proof, sha256(proof_bytes).hexdigest()


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
                    row.update({key + '_difference': a[key] - b[key] for key in METRICS})
                    row['admitted_percentage_point_difference'] = 100 * row['admitted_rate_difference']
                    output.append(row)
    return output


def diagnostic_contrasts(cells, cfg):
    """Registered D/u differences and their D-by-u interaction, paired by seed.

    R0 has no demand coordinate: D1-D0 occurs once; u and D-by-u are inapplicable.
    The interaction is not an additional scenario/forecast treatment contrast.
    """
    require(set(cfg['analysis']['diagnostic_contrasts']) == {
        'facility_first-fixed_reference', 'u50-u05', 'difference_in_differences'},
        'Unsupported registered diagnostic definitions')
    indexed = {(x['destination_policy'], x['demand_level'], x['scenario'], x['seed']): x for x in cells}
    require(len(indexed) == len(cells), 'Ambiguous diagnostic metric identities')
    destinations = ['fixed_reference', 'facility_first']
    demands = ['u05', 'u50']
    scenarios = list(dict.fromkeys(c['scenario'] for c in cfg['cells']))
    require({c['destination_policy'] for c in cfg['cells']} == set(destinations)
            and {c['demand_level'] for c in cfg['cells'] if c['demand_level'] is not None} == set(demands),
            'Unsupported registered D/u axes')
    output = []

    def difference(kind, destination, demand, scenario, seed, expression, terms):
        values = [(coefficient, indexed[(d, u, scenario, seed)]) for coefficient, d, u in terms]
        require(len({x['denominator'] for _, x in values}) == 1, 'Paired diagnostic denominators differ')
        row = {'diagnostic': kind, 'destination_policy': destination, 'demand_level': demand,
               'scenario': scenario, 'seed': seed, 'expression': expression,
               'cell_terms': json.dumps([{'coefficient': k, 'run_id': x['run_id'],
                   'destination_policy': x['destination_policy'], 'demand_level': x['demand_level'],
                   'scenario': scenario, 'seed': seed} for k, x in values], ensure_ascii=False),
               'denominator': values[0][1]['denominator'], 'R0_reused_reference': scenario == 'R0'}
        row.update({key + '_difference': sum(k * x[key] for k, x in values) for key in METRICS})
        row['admitted_percentage_point_difference'] = 100 * row['admitted_rate_difference']
        output.append(row)

    for seed in cfg['seeds']:
        for scenario in scenarios:
            for demand in [None] if scenario == 'R0' else demands:
                difference('D1-D0', None, demand, scenario, seed, 'D1-D0',
                           [(1, destinations[1], demand), (-1, destinations[0], demand)])
            if scenario == 'R0':
                continue
            for destination in destinations:
                difference('u50-u05', destination, None, scenario, seed, 'u50-u05',
                           [(1, destination, demands[1]), (-1, destination, demands[0])])
            difference('D_by_u_difference_in_differences', None, None, scenario, seed,
                       '(D1_u50-D0_u50)-(D1_u05-D0_u05)',
                       [(1, destinations[1], demands[1]), (-1, destinations[0], demands[1]),
                        (-1, destinations[1], demands[0]), (1, destinations[0], demands[0])])
    return output


def descriptive_summaries(rows, cfg, axes):
    groups = {}
    for row in rows:
        key = tuple(row[name] for name in axes)
        groups.setdefault(key, []).append(row)
    summaries = []
    for key, group in groups.items():
        require(len(group) == len(cfg['seeds']) and {x['seed'] for x in group} == set(cfg['seeds']),
                'Incomplete or duplicate paired seeds')
        for metric in [k for k in group[0] if k.endswith('_difference')]:
            values = [x[metric] for x in group]
            summaries.append({**dict(zip(axes, key)), 'metric': metric, 'seeds': len(values),
                              'mean': mean(values), 'min': min(values), 'max': max(values)})
    return summaries


def write_table(path, rows, fields=None):
    require(bool(rows) or bool(fields), 'Refuse empty analysis table without explicit columns')
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def analyze(root):
    root = root.resolve()
    analysis_sha = digest(Path(__file__))
    cfg = json.loads(local(root, CONFIG).read_text(encoding='utf-8'))
    verified = complete_records(root, cfg)  # Must succeed before output directory creation.
    request_component, request_sha = load_request_component()
    secondary, secondary_sha, service_proof, service_proof_sha = load_secondary_component(root)
    primary, outcomes, reasons, provenance = [], [], [], []
    request_details, request_summaries, request_distributions = [], [], []
    vehicle_totals, cycle_totals, cycle_details, candidate_stages = [], [], [], []
    road_totals, transition_totals, direct_bounds, facility_bounds, workloads = [], [], [], [], []
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
        people = table(folder / 'person_results.csv')
        metrics, states, facilities = person_metrics(people, source, terminals, m['end_sec'])
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
        requests = table(folder / 'request_results.csv')
        details, summaries, distributions = request_component.request_summary(
            requests, people, jsonlines(folder / 'events.jsonl'), m['end_sec'])
        require(row['scenario'] != 'R0' or not details, 'R0 must have zero requests')
        for value in summaries:
            selected_requests = [x for x in details if value['group'] == 'all' or x['person_type'] == value['group']]
            for mode in ['ped', 'vehicle']:
                name = 'origin_' + mode + '_closed_unboarded_including_boarding_sec'
                value[name + '_sum'] = sum(x[name] for x in selected_requests)
        request_details.extend({**identity, **value} for value in details)
        request_summaries.extend({**identity, **value} for value in summaries)
        request_distributions.extend({**identity, **value} for value in distributions)
        vehicle_totals.extend({**identity, **value} for value in secondary.vehicle_summary(table(folder / 'vehicle_results.csv')))
        cycles, cycle_rows, stages = secondary.candidate_summary(secondary.rows(folder / 'candidates.csv.gz'),
            secondary.rows(folder / 'dispatch_cycles.csv.gz'), row['scenario'])
        cycle_totals.append({**identity, **cycles})
        cycle_details.extend({**identity, **value} for value in cycle_rows)
        candidate_stages.extend({**identity, **value} for value in stages)
        roads, transitions = secondary.road_summary(secondary.rows(folder / 'edge_observations.csv.gz'),
            secondary.rows(folder / 'transitions.csv.gz'))
        road_totals.extend({**identity, **value} for value in roads)
        transition_totals.extend({**identity, **value} for value in transitions)
        direct_bounds.append({**identity, **secondary.direct_service_accounting(requests, people, cfg, row['scenario'], service_proof)})
        if row['scenario'] == 'R0':
            bounds = secondary.structural_bounds(list(source.values()),
                table(inputs / ('destinations_' + row['destination_policy'] + '.csv')),
                terminals, cfg['population']['walk_limit_m'])
            facility_bounds.extend({**identity, **value} for value in bounds)
            realization = table(inputs / ('common_realization_seed' + str(row['seed']) + '.csv'))
            for demand in cfg['demand_levels']:
                workloads.append({'destination_policy': row['destination_policy'], 'seed': row['seed'],
                    'input_manifest_sha256': m['input_manifest_sha256'],
                    **secondary.workload(realization, demand, cfg)})
        require(all(digest(p) == expected for p, expected in bound.items()), 'Primary source bytes changed during aggregation')
        provenance.append({'run_id': row['run_id'], 'manifest_sha256': row['manifest_sha256'],
                           'validation_report': row['validation_report'], 'bound_files_verified': len(bound)})
    require(len(input_sha) == 1, 'Different input versions')
    contrasts = paired_contrasts(primary, cfg)
    summaries = descriptive_summaries(contrasts, cfg, ['destination_policy', 'demand_level', 'contrast'])
    diagnostics = diagnostic_contrasts(primary, cfg)
    diagnostic_summaries = descriptive_summaries(diagnostics, cfg,
        ['diagnostic', 'destination_policy', 'demand_level', 'scenario', 'expression'])
    require(digest(REQUEST_SOURCE) == request_sha, 'Request analysis source changed during aggregation')
    require(digest(SECONDARY_SOURCE) == secondary_sha and digest(SECONDARY_PROOF) == service_proof_sha,
            'Secondary helper or service-contract proof changed during aggregation')
    require(all(digest(local(root, name)) == value for name, value in service_proof['implementation_sha256'].items()),
            'Frozen service-contract source changed during aggregation')
    require(digest(Path(__file__)) == analysis_sha, 'Primary analysis source changed during aggregation')
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%dT%H%M%S%f')
    target = root / '06_研究結果/jdrt/goal_20261017' / ('主指標集計_' + stamp)
    target.mkdir(parents=True, exist_ok=False)
    for name, data in [('全セル主指標.csv', primary), ('全Type受入・退出・積分.csv', outcomes),
                       ('理由別全員会計.csv', reasons), ('PAP主差分_全seed.csv', contrasts), ('PAP主差分_記述集計.csv', summaries),
                       ('PAP診断差分_全seed.csv', diagnostics), ('PAP診断差分_記述集計.csv', diagnostic_summaries),
                       ('全要求_待ち段階明細.csv', request_details), ('全セル要求_段階待ち会計.csv', request_summaries),
                       ('全要求_終端別観測待ち分布.csv', request_distributions)]:
        write_table(target / name, data)
    for name, data, fields in [
        ('全車両_距離状態会計.csv', vehicle_totals, None), ('全セル配車_周期会計.csv', cycle_totals, None),
        ('全配車cycle_0候補込み.csv', cycle_details, list(identity) + ['cycle', 'time_sec', 'free_start', 'pending_start', 'stages', 'candidate_rows', 'accepted']),
        ('全候補cycle_stage_理由boolean会計.csv', candidate_stages, list(identity) + ['cycle', 'stage', 'candidate_rows', 'selected', 'exclusive_reason_counts', 'boolean_counts']),
        ('全道路_0台込み時刻mode閉鎖会計.csv', road_totals, None), ('全遷移_閉鎖進入曖昧会計.csv', transition_totals, None),
        ('全セル_DRT直接完了上限.csv', direct_bounds, None), ('D別seed_施設固定割当上限.csv', facility_bounds, None),
        ('D別seed_u_提供需要仕事量.csv', workloads, None)]:
        write_table(target / name, data, fields)
    manifest = {'scope': 'preregistered_primary_analysis_component_not_final_report', 'status': 'COMPLETED',
                'protocol': cfg['protocol'], 'registered_cell_count': len(cfg['cells']), 'accepted_cell_count': len(verified),
                'config_sha256': digest(local(root, CONFIG)), 'analysis_source_sha256': analysis_sha,
                'request_analysis_source': REQUEST_SOURCE.name, 'request_analysis_source_sha256': request_sha,
                'secondary_analysis_source': SECONDARY_SOURCE.name, 'secondary_analysis_source_sha256': secondary_sha,
                'service_contract_proof': SECONDARY_PROOF.name, 'service_contract_proof_sha256': service_proof_sha,
                'frozen_service_contract_implementation_sha256': service_proof['implementation_sha256'],
                'provenance': provenance, 'population_inference': False, 'R0_is_shared_not_independent_replication': True,
                'diagnostic_definition': {'source': 'PAP v1 section 7 and Registry analysis.diagnostic_contrasts',
                    'D1': 'facility_first', 'D0': 'fixed_reference', 'u_high': 'u50', 'u_low': 'u05',
                    'difference_in_differences': '(D1_u50-D0_u50)-(D1_u05-D0_u05)',
                    'pairing': 'same registered seed and scenario; all paired Type4 denominators equal',
                    'R0_demand_difference_and_D_by_u': 'not_applicable; no demand coordinate; no synthetic duplicate',
                    'percentage_points': '100 times admitted_rate difference',
                    'normalized_unadmitted_time': 'smaller means earlier/more facility admission; exits remain H'},
                'request_wait_definition': 'all requests; boarding start/cancellation/input rejection observed endpoints; only preboarding H is right-censored',
                'request_zero_denominator': 'R0 retains type3/type4/all summaries with requests=0 and empty mean; no fictitious detail/distribution rows',
                'secondary_definitions': {'roads': 'All edge rows retained in time/mode/closed aggregates including zero actors; raw and traffic speeds have separate weighted sums and observed denominators. Formal validator supplies same-phase actor-to-edge independent audit.',
                    'capacity': 'Sum min(shared facility capacity, all fixed Type4 assignments); route-presence counts do not remove people from the optimistic bound; no attainable or real-world guarantee.',
                    'workload': 'Input-mask quantities by D/seed/u, with no R0 demand outcome rows. All intended/offered requests N including rejected connections; rho=N*(boarding+alighting)/(fleet*H), not realized utilization.',
                    'service_upper': 'Direct DRT admitted <= served <= sum_v floor(H/(b+a)), initially empty serial single-person service available from 0; every successful service interval is within [0,H] and nonoverlapping per vehicle. Not a population improvement bound.',
                    'native_vehicle_missing': 'Blank native distance remains missing; known subtotal and completeness are separate.'},
                'remaining': ['joint_interpretation_and_complete_limitations', 'full_final_report_and_completion_audit',
                              'real_all70_execution_and_performance_unverified'],
                'output_sha256': {p.name: digest(p) for p in target.iterdir() if p.is_file()}}
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'COMPLETED_COMPONENT', 'path': target.relative_to(root).as_posix()}, ensure_ascii=False))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    analyze(parser.parse_args().project_root)


if __name__ == '__main__':
    main()
