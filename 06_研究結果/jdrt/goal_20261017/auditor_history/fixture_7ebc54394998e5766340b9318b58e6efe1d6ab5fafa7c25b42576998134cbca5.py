"""Recalculate synthetic integration evidence from immutable primary artifacts."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = {'walk_reroute', 'walk_reroute_limit', 'walk_budget', 'walk_reverse',
            'pickup_closure', 'boarding_closure', 'alighting_closure', 'forecast_r1', 'forecast_p0',
            'forecast_p900', 'forecast_reroute', 'shared_capacity', 'horizon_alighting',
            'car_backward_cycle', 'car_backward_no_cycle', 'car_reroute'}
candidate_file = Path(__file__).parent / 'G4_候補選択独立監査.py'
candidate_spec = importlib.util.spec_from_file_location('fixture_independent_candidates', candidate_file)
candidate_auditor = importlib.util.module_from_spec(candidate_spec)
candidate_spec.loader.exec_module(candidate_auditor)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else Path.open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def audit_case(folder):
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    inputs = ROOT / m['input_directory']
    cfg = json.loads((ROOT / m['parameter_path']).read_text(encoding='utf-8'))
    source = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
    checks = {'fixture_only': m['protocol'] == source['protocol'] == cfg['protocol'] == 'realtime_choice_fixture_v1'
              and m['purpose'] == 'fixture' and m['research_adoption_permitted'] is source['research_adoption_permitted'] is False,
              'completed': m['status'] == 'COMPLETED',
              'parameters_input_artifacts_bound': sha(ROOT / m['parameter_path']) == m['parameter_sha256']
                 and sha(inputs / 'manifest.json') == m['input_manifest_sha256']
                 and all(sha(inputs / p) == value for p, value in source['artifacts'].items()),
              'input_sources_current': all(sha(ROOT / p) == value for p, value in source['source_sha256'].items()),
              'outputs_bound': all(sha(folder / p) == value for p, value in m['output_sha256'].items()),
              'current_code_and_archives': all(sha(ROOT / p) == sha(folder / 'implementation' / p) == value
                                             for p, value in m['implementation_sha256'].items())}
    people = {p['person_id']: p for p in rows(folder / 'person_results.csv')}
    common = {p['person_id']: p for p in rows(folder / 'common_realization.csv')}
    original = {p['person_id']: p for p in rows(inputs / f'common_realization_seed{m["seed"]}.csv')}
    vehicles = {p['vehicle_id']: p for p in rows(folder / 'vehicle_results.csv')}
    requests = {p['person_id']: p for p in rows(folder / 'request_results.csv')}
    checks['input_people_and_request_sets'] = (set(people) == set(common) == set(original)
        and requests.keys() == {pid for pid, p in common.items() if p['selected_jdrt'] == 'True'}
        and all(all(common[pid][key] == value for key, value in p.items()) for pid, p in original.items()))
    events = [json.loads(s) for s in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    person_states = {pid: 'not_ready' for pid in people}
    request_states = {pid: 'none' for pid in requests}
    state_ok = True
    for e in events:
        if e['event'] in ('person_state', 'request_state'):
            state = person_states if e['event'] == 'person_state' else request_states
            state_ok &= state[e['person_id']] == e['before']
            state[e['person_id']] = e['after']
    checks['state_event_chains_and_complete_denominator'] = (state_ok
        and person_states == {pid: p['status'] for pid, p in people.items()}
        and request_states == {pid: p['status'] for pid, p in requests.items()})
    service_time_ok = True
    for pid, request in requests.items():
        for start, finish, expected in [('boarding_started_sec', 'boarded_sec', cfg['operation']['boarding_sec']),
                                         ('alighting_started_sec', 'alighted_sec', cfg['operation']['alighting_sec'])]:
            if request[finish] != '':
                service_time_ok &= request[start] != '' and float(request[finish]) - float(request[start]) == expected
        if request['boarding_started_sec'] != '':
            service_time_ok &= float(request['boarding_started_sec']) < float(request['deadline_sec'])
    checks['strict_deadline_and_service_durations'] = service_time_ok
    native = {(p['edge_id'], p['mode']): float(p['closure_sec']) for p in rows(inputs / 'hazard.csv') if p['closure_sec'] != ''}
    applied = [e for e in events if e['event'] == 'closure_applied']
    expected = {(edge, mode) for (edge, mode), at in native.items() if at <= m['end_sec']}
    checks['all_closures_and_three_clocks'] = (len(applied) == len(expected)
        and {(e['edge_id'], e['mode']) for e in applied} == expected
        and all(e['scheduled_sec'] == e['observation_upper_sec'] == native[e['edge_id'], e['mode']]
                and e['time_sec'] == e['control_call_sec'] == max(0, e['scheduled_sec'] - m['step_sec'])
                and e['control_lead_sec'] == e['scheduled_sec'] - e['time_sec'] for e in applied))
    routes = defaultdict(dict)
    for vid, v in vehicles.items():
        if v['kind'] == 'drt':
            routes[vid][0] = [source['depot_edge']]
    for e in events:
        if e['event'] == 'private_departure_requested':
            routes[e['vehicle_id']][0] = e['route']
        elif e['event'] in ('drt_route', 'cancel_wait_route', 'private_reroute'):
            routes[e['vehicle_id']][e['route_version']] = e['route']
    speed_integral, distance, empty, last_vehicle = defaultdict(float), defaultdict(float), defaultdict(float), {}
    duplicate, invalid_speed, unexplained, bad_index, closed_actor = [], [], [], [], []
    last_time, active, actor_rows, kinds = None, set(), 0, Counter()
    observations = defaultdict(dict)
    for row in rows(folder / 'actor_observations.csv.gz'):
        actor_rows += 1
        now, actor = float(row['time_sec']), row['actor_id']
        if now != last_time:
            last_time, active = now, set()
        members = json.loads(row['members'])
        if active.intersection(members):
            duplicate.append((now, actor))
        active.update(members)
        state, speed = row['observation_kind'], float(row['speed_mps'])
        if row['phase'] != 'after_step_before_control':
            unexplained.append((now, actor, 'wrong_actor_phase'))
        kinds[state] += 1
        if state not in ('onroad', 'parked', 'departure_pending', 'reentry_pending'):
            unexplained.append((now, actor))
        if row['kind'] == 'walk':
            if not 0 <= speed <= cfg['population']['walk_mps'][people[actor]['person_type']] + 1e-6:
                invalid_speed.append((now, actor))
            speed_integral[actor] += speed * m['step_sec']
            observations[actor][now] = row
        elif state != 'departure_pending':
            value = float(row['distance_m'])
            if value >= 0:
                increment = value - distance[actor]
                if increment < -1e-8:
                    unexplained.append((now, actor, 'odometer_decrease'))
                distance[actor] = max(value, distance[actor])
                if not members:
                    empty[actor] += max(0, increment)
                last_vehicle[actor] = row
            if state == 'onroad':
                index = int(row['route_index'])
                path = routes[actor].get(int(row['route_version']), [])
                if not 0 <= index < len(path) or (not row['road_id'].startswith(':') and path[index] != row['road_id']):
                    bad_index.append((now, actor))
        mode = 'pedestrian' if row['kind'] == 'walk' else 'passenger'
        if row['road_id'] and not row['road_id'].startswith(':') and now >= native.get((row['road_id'], mode), math.inf):
            closed_actor.append((now, actor))
    checks['no_duplicate_active_mode'] = not duplicate
    checks['walking_speed_and_independent_integral'] = not invalid_speed and all(
        math.isclose(float(p['walk_speed_integral_m']), speed_integral[pid], abs_tol=1e-7)
        and speed_integral[pid] <= cfg['population']['walk_limit_m'] for pid, p in people.items())
    checks['observed_vehicle_empty_distances'] = not unexplained and all(
        math.isclose(float(v['observed_distance_m']), distance[vid], abs_tol=1e-7)
        and math.isclose(float(v['observed_empty_distance_m']), empty[vid], abs_tol=1e-7) for vid, v in vehicles.items())
    checks['actual_route_index_and_version'] = not bad_index
    checks['no_actor_observed_on_closed_external_edge'] = not closed_actor
    graphs = json.loads((inputs / 'graphs.json').read_text(encoding='utf-8'))
    road_nodes = {mode: set(graphs[mode]['nodes']) for mode in graphs}
    associated, moving = defaultdict(list), defaultdict(list)
    parked, reentry, unplaced = Counter(), Counter(), Counter()
    snapshot_rows, snapshot_ok, native_membership_ok = 0, True, True
    for row in rows(folder / 'snapshot_actor_observations.csv.gz'):
        snapshot_rows += 1
        time, kind, edge, state = float(row['time_sec']), row['kind'], row['road_id'], row['observation_kind']
        snapshot_ok &= row['phase'] == 'after_control_before_step'
        physical = 'pedestrian' if kind == 'walk' else 'passenger'
        if edge in road_nodes[physical]:
            key = time, edge, kind
            associated[key].append(float(row['speed_mps']))
            if state == 'onroad':
                moving[key].append(float(row['speed_mps']))
            elif state == 'parked':
                parked[key] += 1
            elif state == 'reentry_pending':
                reentry[key] += 1
            else:
                snapshot_ok = False
            if kind != 'walk':
                native_membership_ok &= row['native_edge_contains_vehicle'] == str(state == 'onroad')
        elif state == 'reentry_pending':
            unplaced[time, row['reentry_source_edge'], kind] += 1
    seen = set()
    for row in rows(folder / 'edge_observations.csv.gz'):
        key = float(row['time_sec']), row['edge_id'], row['mode']
        raw_speeds, traffic_speeds = associated[key], moving[key]
        valid = all(math.isfinite(s) and s >= 0 for s in raw_speeds)
        expected_mean = sum(raw_speeds) / len(raw_speeds) if raw_speeds and valid else None
        traffic_mean = sum(traffic_speeds) / len(traffic_speeds) if traffic_speeds else None
        means = all(row[field] == '' if value is None else row[field] != '' and math.isclose(float(row[field]), value, abs_tol=1e-9)
                    for field, value in [('mean_speed_mps', expected_mean), ('traffic_mean_speed_mps', traffic_mean)])
        snapshot_ok &= (key not in seen and int(row['count']) == len(raw_speeds)
            and int(row['traffic_count']) == len(traffic_speeds) and means
            and int(row['parked_count']) == parked[key] and int(row['reentry_pending_count']) == reentry[key]
            and int(row['unplaced_reentry_count']) == unplaced[key]
            and int(row['halting_count']) == sum(0 <= speed < cfg['simulation']['stop_speed_mps'] for speed in raw_speeds)
            and int(row['traffic_halting_count']) == sum(speed < cfg['simulation']['stop_speed_mps'] for speed in traffic_speeds))
        seen.add(key)
    expected_keys = {(float(time), edge, kind) for time in range(0, int(m['end_sec']) + 1, m['snapshot_sec'])
                     for kind, physical in [('car', 'passenger'), ('drt', 'passenger'), ('walk', 'pedestrian')]
                     for edge in road_nodes[physical]}
    checks['post_control_snapshot_full_zero_inclusive_reaggregation'] = (snapshot_ok and seen == expected_keys
        and snapshot_rows == m['summary']['counts']['snapshot_actor_rows'])
    checks['parking_traffic_filter_matches_native_edge_vehicle_ids'] = native_membership_ok
    transitions = list(rows(folder / 'transitions.csv.gz'))
    checks['transition_recount_no_closed_entry'] = len(transitions) == m['summary']['counts']['transition_rows'] and all(
        p['ambiguous'] == 'False' and float(p['time_upper_sec']) < native.get((p['to_edge'], p['mode']), math.inf)
        for p in transitions)
    terminal = {p['terminal_id']: p for p in rows(inputs / 'terminals.csv')}
    occupancy = Counter(p['terminal_id'] for p in people.values() if p['status'] == 'admitted')
    facility = {p['terminal_id']: p for p in rows(folder / 'facility_results.csv')}
    checks['shared_facility_capacity_exit_separate'] = (all(terminal[key]['kind'] == 'facility'
        and value <= int(terminal[key]['capacity']) for key, value in occupancy.items())
        and all(int(p['admitted']) == occupancy[key] for key, p in facility.items())
        and all(terminal[p['terminal_id']]['kind'] == 'boundary_exit' for p in people.values() if p['status'] == 'boundary_exit'))
    budget_events = [e for e in events if e['event'] == 'walk_budget_pre_step_stop']
    checks['pre_step_budget_rule'] = all(
        0 <= e['remaining_budget_m'] < e['max_next_step_m']
        and math.isclose(e['remaining_budget_m'] + e['spent_m'], cfg['population']['walk_limit_m'], abs_tol=1e-7)
        and e['max_next_step_m'] == cfg['population']['walk_mps'][people[e['person_id']]['person_type']] * m['step_sec']
        and max(observations[e['person_id']], default=0) <= e['time_sec'] for e in budget_events)
    reroutes = [e for e in events if e['event'] == 'walk_plan' and e['stage'] == 'reroute']
    reroute_ok = True
    for e in reroutes:
        p = people[e['person_id']]
        before = observations[e['person_id']][e['time_sec']]
        origin = next(row for row in rows(inputs / 'place_positions.csv') if row['kind'] == 'origin' and row['place_id'] == p['origin_id'])
        straight_passed = float(before['lane_position_m']) - float(origin['pedestrian_pos_m'])
        reroute_ok &= math.isclose(e['previous_plan_m'] - e['old_remaining_m'], straight_passed, abs_tol=1e-7)
        reroute_ok &= math.isclose(e['model_passed_m'], e['speed_integral_m'], abs_tol=1e-7)
        after = observations[e['person_id']].get(e['time_sec'] + m['step_sec'])
        if after:
            reroute_ok &= math.dist((float(before['x']), float(before['y'])), (float(after['x']), float(after['y']))) <= cfg['population']['walk_mps'][p['person_type']] * m['step_sec'] + 1e-7
    checks['reroute_progress_and_position_continuity'] = reroute_ok
    trips = {p.attrib['id']: p.attrib for p in ET.parse(folder / 'tripinfo.xml').getroot().findall('tripinfo')}
    vkt_differences, vkt_ok = {}, True
    for vid, v in vehicles.items():
        if vid not in trips:
            vkt_ok &= distance[vid] == 0 and v['distance_m'] == ''
            continue
        trip, last = trips[vid], last_vehicle[vid]
        tail = float(trip['arrivalPos']) - float(last['lane_position_m']) if v['status'] == 'arrived' else 0
        if v['status'] == 'arrived':
            path = routes[vid][int(last['route_version'])]
            vkt_ok &= last['road_id'] == path[-1] and int(last['route_index']) == len(path) - 1 and tail >= 0
        # SUMO rounds both arrivalPos and routeLength; derive their quanta from the strings.
        quanta = [float(Decimal(1).scaleb(Decimal(trip[key]).as_tuple().exponent)) for key in ('arrivalPos', 'routeLength')]
        tolerance = .5 * sum(quanta) + 1e-7
        difference = float(trip['routeLength']) - distance[vid] - tail
        vkt_differences[vid] = {'backend_minus_last_observation_m': float(trip['routeLength']) - distance[vid],
                              'arrival_tail_m': tail, 'residual_m': difference, 'rounding_bound_m': tolerance}
        vkt_ok &= abs(difference) <= tolerance and float(v['distance_m']) == float(trip['routeLength'])
    checks['backend_vkt_with_arrival_tail_and_rounding'] = vkt_ok
    warning_lines = [line for line in (folder / 'sumo_errors.log').read_text(encoding='utf-8').splitlines() if line.startswith('Warning:')]
    checks['warnings_classified'] = all(source['fixture_case'] in ('pickup_closure', 'boarding_closure', 'alighting_closure')
        and ('skips stop on lane' in line or 'aborts stop.' in line) for line in warning_lines)
    candidate_report = candidate_auditor.audit(m['run_id'], execution_directory=folder)
    checks['candidate_shortest_paths_all_gates_scores_and_choices'] = candidate_report['status'] == 'PASS'
    # Prove each named branch occurred; a vacuous generic PASS is insufficient.
    case = source['fixture_case']
    outcomes = Counter(p['status'] for p in people.values())
    fallbacks = [e for e in events if e['event'] == 'fallback_attempt']
    candidates = list(rows(folder / 'candidates.csv.gz'))
    one_state = lambda name: outcomes == Counter({name: len(original)})
    if case == 'walk_reroute':
        checks['named_branch_exercised'] = bool(reroutes) and one_state('admitted')
    elif case == 'walk_reroute_limit':
        checks['named_branch_exercised'] = one_state('walk_limit') and any(
            max(e['model_passed_m'], e['speed_integral_m']) + e['sumo_plan_length_m'] > cfg['population']['walk_limit_m']
            for e in reroutes)
    elif case == 'walk_budget':
        checks['named_branch_exercised'] = bool(budget_events) and one_state('walk_limit')
    elif case == 'walk_reverse':
        origin_point = next(p for p in rows(inputs / 'place_positions.csv') if p['kind'] == 'origin')
        end_point = next(p for p in rows(inputs / 'place_positions.csv') if p['kind'] == 'terminal')
        reverse_length = float(origin_point['pedestrian_pos_m']) - float(end_point['pedestrian_pos_m'])
        checks['named_branch_exercised'] = reverse_length > 0 and one_state('admitted') and any(
            e['event'] == 'walk_plan' and e['sumo_plan_length_m'] == reverse_length for e in events)
    elif case == 'pickup_closure':
        checks['named_branch_exercised'] = len(fallbacks) == len(requests) and all(
            q['status'] == 'cancelled_vehicle_failure' and q['boarding_started_sec'] == '' for q in requests.values())
    elif case in ('boarding_closure', 'alighting_closure'):
        started = 'boarding_started_sec' if case == 'boarding_closure' else 'alighting_started_sec'
        checks['named_branch_exercised'] = one_state('stranded_drt') and not fallbacks and all(
            q[started] != '' and q['status'] == 'failed_after_boarding' for q in requests.values())
    elif case == 'forecast_p0':
        checks['named_branch_exercised'] = any(p['reason'] == 'forecast_gate' and all(
            p[key] == 'True' for key in ('pickup_route', 'delivery_route', 'pickup_before_deadline', 'completion_within_horizon'))
            for p in candidates) and len(fallbacks) == len(requests) and all(
                q['accepted_sec'] == '' and q['status'] == 'cancelled_timeout' for q in requests.values())
    elif case in ('forecast_r1', 'forecast_p900'):
        checks['named_branch_exercised'] = all(q['status'] == 'served' for q in requests.values()) and any(
            p['forecast_remaining_kind'] == ('not_applicable' if case == 'forecast_r1' else 'finite') for p in candidates)
    elif case == 'forecast_reroute':
        selected = [p for p in candidates if p['decision'] == 'selected']
        blocked = {edge for (edge, mode) in native if mode == 'passenger'}
        checks['named_branch_exercised'] = (any(p['reason'] == 'forecast_gate' for p in candidates)
            and bool(selected) and all(q['status'] == 'served' for q in requests.values())
            and all(not blocked.intersection(json.loads(p['delivery_path']))
                    and float(p['time_sec']) > min(native[edge, 'passenger'] for edge in blocked) for p in selected))
    elif case == 'shared_capacity':
        assigned = Counter(p['terminal_id'] for p in people.values())
        expected_outcomes = Counter()
        for key, number in assigned.items():
            if terminal[key]['kind'] == 'boundary_exit':
                expected_outcomes['boundary_exit'] += number
            else:
                accepted = min(number, int(terminal[key]['capacity']))
                expected_outcomes['admitted'] += accepted
                expected_outcomes['capacity_rejected'] += number - accepted
        checks['named_branch_exercised'] = outcomes == +expected_outcomes
    elif case == 'horizon_alighting':
        checks['named_branch_exercised'] = one_state('time_limit') and all(q['status'] == 'time_limit' for q in requests.values()) and any(
            e['event'] == 'horizon_finalize' and e['previous_status'] in ('boarding', 'onboard', 'alighting') for e in events)
    elif case == 'car_backward_cycle':
        departures = [e for e in events if e['event'] == 'private_departure_requested']
        checks['named_branch_exercised'] = one_state('admitted') and bool(departures) and all(
            e['depart_pos'] > e['arrival_pos'] and len(e['route']) > 1 and e['route'][0] == e['route'][-1] for e in departures)
    elif case == 'car_backward_no_cycle':
        checks['named_branch_exercised'] = one_state('no_route') and not any(e['event'] == 'private_departure_requested' for e in events)
    elif case == 'car_reroute':
        checks['named_branch_exercised'] = one_state('admitted') and any(e['event'] == 'private_reroute'
            and e['route_version'] > 0 for e in events)
    return {'case': source['fixture_case'], 'run_id': m['run_id'], 'status': 'PASS' if all(checks.values()) else 'FAIL',
            'checks': checks, 'actor_rows': actor_rows, 'actor_kinds': dict(kinds), 'reroute_events': len(reroutes),
            'snapshot_actor_rows': snapshot_rows,
            'budget_stop_events': len(budget_events), 'transition_rows': len(transitions),
            'vkt': vkt_differences, 'warnings': warning_lines,
            'independent_candidates': candidate_report,
            'errors': {'duplicate': duplicate[:10], 'invalid_speed': invalid_speed[:10], 'unexplained': unexplained[:10],
                       'bad_route_index': bad_index[:10], 'closed_actor': closed_actor[:10]},
            'manifest_sha256': sha(folder / 'manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', required=True)
    args = parser.parse_args()
    params = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    technical = ROOT / params['workspace'] / 'technical'
    parent = technical / args.suite
    suite = json.loads((parent / 'manifest.json').read_text(encoding='utf-8'))
    reports = [audit_case(technical / case['child_run_id'] / 'execution') for case in suite['cases']]
    checks = {'complete_suite': suite['status'] == 'COMPLETED' and len(reports) == len(REQUIRED)
              and {p['case'] for p in reports} == REQUIRED,
              'factory_archive_bound': sha(parent / 'factory.py') == suite['factory_sha256'],
              'all_case_primary_audits': all(p['status'] == 'PASS' for p in reports)}
    report = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(), 'suite': args.suite,
              'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'cases': reports,
              'scope': 'independent_synthetic_fixture_primary_audit_not_core_acceptance',
              'core_adoption_permitted': False, 'auditor_sha256': sha(Path(__file__)),
              'candidate_auditor_sha256': sha(candidate_file),
              'suite_manifest_sha256': sha(parent / 'manifest.json')}
    history = Path(__file__).parent / 'auditor_history'
    history.mkdir(exist_ok=True)
    report['auditor_archives'] = {}
    for label, source_file in [('fixture', Path(__file__)), ('candidate', candidate_file)]:
        archived = history / (label + '_' + sha(source_file) + '.py')
        if not archived.exists():
            archived.write_bytes(source_file.read_bytes())
        if sha(archived) != sha(source_file):
            raise ValueError('Auditor archive mismatch')
        report['auditor_archives'][label] = archived.relative_to(ROOT).as_posix()
    target = Path(__file__).parent / (args.suite + '_統合fixture独立監査.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**{k: v for k, v in report.items() if k != 'cases'},
        'case_status': [{'case': p['case'], 'status': p['status'],
                         'failed_checks': [k for k, value in p['checks'].items() if not value],
                         'candidate_rows': p['independent_candidates']['candidate_rows']} for p in reports]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
