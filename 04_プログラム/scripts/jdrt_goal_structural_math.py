"""Derived necessary bounds and paired accounting for the frozen boundary series.

No SUMO runs or input mutations. Bounds are optimistic necessary conditions;
they are not predicted achievable throughput or empirical disaster demand.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from fractions import Fraction
import csv
import hashlib
import html
import json
import math
import networkx as nx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '06_研究結果/jdrt/goal_20261017'
P = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_b_boundary_v2.json').read_text(encoding='utf-8'))
W = ROOT / P['workspace']
I = W / P['input_directory']
SOURCES = {}


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def rows(path):
    SOURCES[path.relative_to(ROOT).as_posix()] = sha(path)
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def js(path):
    SOURCES[path.relative_to(ROOT).as_posix()] = sha(path)
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    now = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    OUT.mkdir(exist_ok=True)
    assert js(ROOT / '04_プログラム/config/jdrt_realtime_b_boundary_v2.json') == P
    SOURCES[P['pap']] = sha(ROOT / P['pap'])
    ledger_path = ROOT / '05_タスク管理/jdrt/JDRT-実時間B境界整合_セル検証台帳.jsonl'
    SOURCES[ledger_path.relative_to(ROOT).as_posix()] = sha(ledger_path)
    ledger = [json.loads(x) for x in ledger_path.read_text(encoding='utf-8').splitlines() if x.strip()]
    assert {(r['seed'], r['scenario']) for r in ledger} == {(seed, s) for seed in P['seeds'] for s in P['scenarios']}
    terminals = {r['terminal_id']: r for r in rows(I / 'terminals.csv')}
    population = rows(I / 'people.csv')
    origins = {r['origin_id']: r for r in rows(I / 'origins.csv')}
    raw = js(I / 'graphs.json')
    inputs = js(I / 'manifest.json')
    hazard = rows(I / 'hazard.csv')
    graphs = {}
    reverse_reach = {}
    for mode, data in raw.items():
        g = nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from(data['nodes'])
        g.add_edges_from((a, b) for a, b, _ in data['edges'])
        g.remove_nodes_from(r['edge_id'] for r in hazard if r['mode'] == mode and r['closure_sec'] != '' and float(r['closure_sec']) == 0)
        graphs[mode] = g
        rg = g.reverse(copy=False) if g.is_directed() else g
        reverse_reach[mode] = {tid: (nx.descendants(rg, r['edge_id']) | {r['edge_id']}) if r['edge_id'] in g else set()
                               for tid, r in terminals.items() if r['kind'] == 'facility'}
    g = graphs['passenger']
    depot = inputs['depot_edge']
    depot_reach = (nx.descendants(g, depot) | {depot}) if depot in g else set()
    fixed = Counter()
    for p in population:
        terminal = origins[p['origin_id']]['terminal_id']
        fixed[(p['person_type'], terminal, terminals.get(terminal, {}).get('kind', 'unassigned'))] += 1
    t4 = [p for p in population if p['person_type'] == P['evaluation']['primary_type']]
    target4 = sum(n for (typ, _, kind), n in fixed.items() if typ == P['evaluation']['primary_type'] and kind == 'facility')
    facilities = []
    for tid, r in terminals.items():
        if r['kind'] == 'facility':
            demand = sum(n for (_, t, _), n in fixed.items() if t == tid)
            facilities.append({'terminal_id': tid, 'capacity': int(r['capacity']), 'fixed_target_people': demand,
                               'admission_upper_fixed_targets': min(int(r['capacity']), demand)})
    service = P['operation']['boarding_sec'] + P['operation']['alighting_sec']
    horizon = P['simulation']['duration_sec']
    fleet = P['operation']['fleet_count']
    assert not P['operation']['pooling'] and service > 0
    processing_upper = fleet * (horizon // service)
    result = []
    by_seed = defaultdict(dict)
    for record in ledger:
        directory = W / 'runs' / record['run_id']
        manifest = js(directory / 'manifest.json')
        people = rows(directory / 'person_results.csv')
        vehicles = rows(directory / 'vehicle_results.csv')
        requests = rows(directory / 'request_results.csv')
        assert manifest['status'] == 'COMPLETED'
        for file in ['person_results.csv', 'vehicle_results.csv', 'request_results.csv', 'events.jsonl']:
            assert sha(directory / file) == manifest['output_sha256'][file]
        by_seed[record['seed']][record['scenario']] = {p['person_id']: p for p in people}
        drt_vehicles = {v['vehicle_id']: v for v in vehicles if v['kind'] == 'drt'}
        removals = {}
        starts = defaultdict(dict)
        completed = defaultdict(list)
        board_complete = {}
        alight_start = {}
        SOURCES[(directory / 'events.jsonl').relative_to(ROOT).as_posix()] = sha(directory / 'events.jsonl')
        with (directory / 'events.jsonl').open(encoding='utf-8') as f:
            for line in f:
                e = json.loads(line)
                if e['event'] == 'actor_removed' and e['actor_id'] in drt_vehicles:
                    removals[e['actor_id']] = min(removals.get(e['actor_id'], horizon), e['time_sec'])
                if e['event'] == 'boarding_started':
                    starts[e['vehicle_id']][e['person_id']] = e['time_sec']
                if e['event'] == 'drt_boarded':
                    board_complete[e['person_id']] = e['time_sec']
                if e['event'] == 'alighting_started':
                    alight_start[e['person_id']] = e['time_sec']
                if e['event'] == 'drt_alighted':
                    vid, pid = e['vehicle_id'], e['person_id']
                    begin = starts[vid][pid]
                    assert board_complete[pid] - begin == P['operation']['boarding_sec']
                    assert e['time_sec'] - alight_start[pid] == P['operation']['alighting_sec']
                    assert e['time_sec'] - begin >= service
                    completed[vid].append((begin, e['time_sec']))
        vehicle_bounds = []
        for vid in drt_vehicles:
            ordered = sorted(completed[vid])
            assert all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:]))
            available = removals.get(vid, horizon)
            upper = math.floor(available / service)
            assert len(ordered) <= upper
            vehicle_bounds.append({'vehicle_id': vid, 'available_upper_sec': available, 'processing_upper': upper,
                                   'completed_services': len(ordered), 'maximum_onboard': int(drt_vehicles[vid]['maximum_onboard'])})
        feasible_walk = feasible_drt = 0
        for p in people:
            if p['person_type'] != P['evaluation']['primary_type'] or p['terminal_id'] not in reverse_reach['passenger']:
                continue
            edge = origins[p['origin_id']]['edge_id']
            if p['mode'] == 'walk':
                feasible_walk += edge in reverse_reach['pedestrian'][p['terminal_id']]
            elif p['mode'] == 'drt':
                feasible_drt += edge in depot_reach and edge in reverse_reach['passenger'][p['terminal_id']]
        actual4 = sum(p['person_type'] == P['evaluation']['primary_type'] and p['status'] == P['evaluation']['primary_status'] for p in people)
        connectivity_upper = min(target4, feasible_walk + min(feasible_drt, processing_upper))
        assert actual4 <= connectivity_upper
        result.append({'run_id': record['run_id'], 'seed': record['seed'], 'scenario': record['scenario'],
                       'request_people': len(requests), 'processing_only_upper': processing_upper if drt_vehicles else 0,
                       'throughput_upper_fraction_of_requests': float(Fraction(processing_upper, len(requests))) if requests else None,
                       'required_processing_vehicle_hours': len(requests) * service / 3600,
                       'available_vehicle_hours': fleet * horizon / 3600 if drt_vehicles else 0,
                       'workload_ratio_lower_bound': float(Fraction(len(requests) * service, fleet * horizon)) if requests else None,
                       'per_vehicle': vehicle_bounds, 'type4_fixed_facility_people': target4, 'type4_all': len(t4),
                       'type4_initial_walk_feasible': feasible_walk, 'type4_initial_drt_feasible': feasible_drt,
                       'type4_loose_admission_upper': connectivity_upper, 'type4_actual_admitted': actual4})
    decomposition = []
    for seed, scenarios in by_seed.items():
        for a, b in [('R0', 'R1'), ('R1', 'R2')]:
            for metric, statuses in [('admitted', {'admitted'}), ('terminal_arrived', {'admitted', 'boundary_exit', 'capacity_rejected'}), ('boundary_exit', {'boundary_exit'})]:
                sums = Counter()
                for pid, pa in scenarios[a].items():
                    pb = scenarios[b][pid]
                    if pa['person_type'] != P['evaluation']['primary_type']:
                        continue
                    assert pa['selected_jdrt'] == pb['selected_jdrt']
                    delta = int(pb['status'] in statuses) - int(pa['status'] in statuses)
                    sums['selected' if pa['selected_jdrt'] == 'True' else 'not_selected'] += delta
                    sums['total'] += delta
                assert sums['selected'] + sums['not_selected'] == sums['total']
                decomposition.append({'seed': seed, 'comparison': b + '−' + a, 'metric': metric, 'denominator': len(t4), **dict(sums)})
    payload = {'at_jst': now, 'protocol': P['protocol'], 'basis': 'postanalysis necessary bounds, not new primary estimates',
               'fixed_type4': {'all': len(t4), 'facility_target': target4, 'rate_upper': float(Fraction(target4, len(t4)))},
               'facilities': facilities, 'effective_capacity_upper': sum(r['admission_upper_fixed_targets'] for r in facilities),
               'processing_only': {'service_lower_sec': service, 'fleet': fleet, 'horizon_sec': horizon, 'upper': processing_upper},
               'cells': result, 'paired_selected_decomposition': decomposition,
               'checks': {'no_service_overlap': True, 'processing_durations': True, 'actuals_under_necessary_bounds': True, 'paired_algebra_identity': True}}
    (OUT / '数理構造診断.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    for path, digest in SOURCES.items():
        assert sha(ROOT / path) == digest, path
    provenance = {'at_jst': now, 'script_sha256': sha(Path(__file__)), 'source_sha256': SOURCES,
                  'output_sha256': {'数理構造診断.json': sha(OUT / '数理構造診断.json')}}
    (OUT / '数理構造診断_生成根拠.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    with (OUT / 'operations.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'at_jst': now, 'action': 'mathematical_diagnosis_complete', 'source_files': len(SOURCES), 'checks': payload['checks']}, ensure_ascii=False) + '\n')
    print(json.dumps({k: payload[k] for k in ['fixed_type4', 'facilities', 'effective_capacity_upper', 'processing_only']}, ensure_ascii=False))
    print(json.dumps([{k: r[k] for k in ['seed', 'scenario', 'request_people', 'type4_loose_admission_upper', 'type4_actual_admitted', 'workload_ratio_lower_bound']} for r in result], ensure_ascii=False))


if __name__ == '__main__':
    main()
