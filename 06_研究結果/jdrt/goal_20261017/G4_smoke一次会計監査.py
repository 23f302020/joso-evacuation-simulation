"""Independent first-smoke accounting audit; never a core acceptance gate."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import csv
import gzip
import hashlib
import json
import math

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def audit(run_id):
    parameters = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    folder = ROOT / parameters['workspace'] / 'smoke' / run_id
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    inputs = ROOT / manifest['input_directory']
    sources = {str(folder / name): expected for name, expected in manifest['output_sha256'].items()}
    sources[str(folder / 'manifest.json')] = sha(folder / 'manifest.json')
    checks = {'completed_smoke': manifest['status'] == 'COMPLETED' and manifest['purpose'] == 'smoke',
              'output_hashes': all(sha(Path(p)) == expected for p, expected in sources.items())}
    people = rows(folder / 'person_results.csv')
    by_person = {p['person_id']: p for p in people}
    common = rows(folder / 'common_realization.csv')
    requests = rows(folder / 'request_results.csv')
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    checks['people_unique_and_complete'] = len(people) == len(by_person) == len(common) and set(by_person) == {p['person_id'] for p in common}
    checks['type_account'] = dict(Counter(p['person_type'] for p in people)) == manifest['summary']['type_counts']
    checks['final_state_account'] = dict(Counter(p['status'] for p in people)) == manifest['summary']['states']
    expected_requests = {p['person_id'] for p in common if p['selected_jdrt'] == 'True'}
    checks['requests_exact_unique'] = len(requests) == len({q['person_id'] for q in requests}) and {q['person_id'] for q in requests} == expected_requests
    checks['request_state_account'] = dict(Counter(q['status'] for q in requests)) == manifest['summary']['request_states']
    request_state = {q['person_id']: 'none' for q in requests}
    person_state = {p['person_id']: 'not_ready' for p in people}
    allowed = {('none', 'pending'), ('pending', 'accepted'), ('pending', 'rejected_input'),
               ('pending', 'cancelled_timeout'), ('accepted', 'cancelled_timeout'),
               ('accepted', 'cancelled_vehicle_failure'), ('accepted', 'boarding'),
               ('boarding', 'onboard'), ('onboard', 'alighting'), ('alighting', 'served')}
    allowed.update((s, 'failed_after_boarding') for s in ('boarding', 'onboard', 'alighting'))
    allowed.update((s, 'time_limit') for s in ('pending', 'accepted', 'boarding', 'onboard', 'alighting'))
    request_events_valid = person_events_valid = True
    event_index = defaultdict(list)
    for event in events:
        pid = event.get('person_id')
        event_index[pid, event['event']].append(event)
        if event['event'] == 'request_state':
            request_events_valid &= request_state.get(pid) == event['before'] and (event['before'], event['after']) in allowed
            request_state[pid] = event['after']
        if event['event'] == 'person_state':
            person_events_valid &= person_state.get(pid) == event['before']
            person_state[pid] = event['after']
    checks['request_transition_chain'] = request_events_valid and all(request_state[q['person_id']] == q['status'] for q in requests)
    checks['person_event_chain'] = person_events_valid and all(person_state[p['person_id']] == p['status'] for p in people)
    lifecycle = True
    for q in requests:
        pid = q['person_id']
        p = by_person[pid]
        lifecycle &= q['person_final_status'] == p['status'] and q['person_final_mode'] == p['mode']
        for column, kind in [('received_sec', 'request_received'), ('accepted_sec', 'request_accepted'),
                             ('boarding_started_sec', 'boarding_started'), ('boarded_sec', 'drt_boarded'),
                             ('alighting_started_sec', 'alighting_started'), ('alighted_sec', 'drt_alighted')]:
            matched = event_index[pid, kind]
            lifecycle &= len(matched) == (1 if q[column] != '' else 0)
            if matched and q[column] != '':
                lifecycle &= float(q[column]) == matched[0]['time_sec'] == float(p[column])
        if q['boarding_started_sec'] != '':
            lifecycle &= float(q['boarding_started_sec']) < float(q['deadline_sec'])
        for end, start, duration in [('boarded_sec', 'boarding_started_sec', parameters['operation']['boarding_sec']),
                                     ('alighted_sec', 'alighting_started_sec', parameters['operation']['alighting_sec'])]:
            if q[end] != '':
                lifecycle &= float(q[end]) - float(q[start]) == duration
        if q['status'] == 'cancelled_timeout':
            lifecycle &= float(q['cancel_sec']) == float(q['deadline_sec']) and q['boarded_sec'] == ''
        fallback = event_index[pid, 'fallback_attempt']
        lifecycle &= len(fallback) <= 1
        if fallback:
            lifecycle &= q['status'].startswith('cancelled_') and p['boarding_started_sec'] == ''
            lifecycle &= fallback[0]['time_sec'] >= float(q['cancel_sec'])
        if q['status'] == 'served':
            lifecycle &= q['alighted_sec'] != ''
    checks['request_lifecycle_and_times'] = bool(lifecycle)
    admitted = Counter(p['terminal_id'] for p in people if p['status'] == 'admitted')
    facilities = rows(folder / 'facility_results.csv')
    terminal_kind = {t['terminal_id']: t['kind'] for t in rows(inputs / 'terminals.csv')}
    checks['shared_facility_capacity_account'] = all(int(f['admitted']) == admitted[f['terminal_id']] <= int(f['capacity']) for f in facilities)
    checks['admission_exit_separated'] = (all(terminal_kind[p['terminal_id']] == 'facility' for p in people if p['status'] == 'admitted')
        and all(terminal_kind[p['terminal_id']] == 'boundary_exit' for p in people if p['status'] == 'boundary_exit'))
    hazard = {(r['edge_id'], r['mode']): int(r['closure_sec']) for r in rows(inputs / 'hazard.csv') if r['closure_sec'] != ''}
    closure_events = [e for e in events if e['event'] == 'closure_applied']
    expected = {(edge, mode, at) for (edge, mode), at in hazard.items() if at <= manifest['end_sec']}
    actual = [(e['edge_id'], e['mode'], e['scheduled_sec']) for e in closure_events]
    checks['all_closures_once'] = len(actual) == len(set(actual)) and set(actual) == expected
    checks['three_clocks_and_phase'] = all(e['time_sec'] == e['control_call_sec'] == max(0, e['scheduled_sec'] - manifest['step_sec'])
        and e['observation_upper_sec'] == e['scheduled_sec'] and e['control_lead_sec'] == e['scheduled_sec'] - e['time_sec']
        and e['phase'] == ('initial_before_observation' if e['scheduled_sec'] == 0 else 'before_step_ending_at_closure') for e in closure_events)
    graph = json.loads((inputs / 'graphs.json').read_text(encoding='utf-8'))
    pairs = [(mode, edge) for mode, physical in [('car', 'passenger'), ('drt', 'passenger'), ('walk', 'pedestrian')]
             for edge in graph[physical]['nodes']]
    pair_index = {key: i for i, key in enumerate(pairs)}
    frames = int(manifest['end_sec'] // manifest['snapshot_sec']) + 1
    seen = np.zeros((frames, len(pairs)), dtype=bool)
    road_rows = duplicates = bad_road = 0
    with gzip.open(folder / 'edge_observations.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            road_rows += 1
            at = float(row['time_sec'])
            key = (row['mode'], row['edge_id'])
            if at % manifest['snapshot_sec'] or at < 0 or at > manifest['end_sec'] or key not in pair_index:
                bad_road += 1
                continue
            index, frame = pair_index[key], int(at // manifest['snapshot_sec'])
            duplicates += int(seen[frame, index])
            seen[frame, index] = True
            count, halted = int(row['count']), int(row['halting_count'])
            correct = 0 <= halted <= count and row['observation_status'] == 'observed'
            correct &= (row['mean_speed_mps'] == '') if count == 0 else math.isfinite(float(row['mean_speed_mps'])) and float(row['mean_speed_mps']) >= 0
            physical = 'pedestrian' if row['mode'] == 'walk' else 'passenger'
            closure = hazard.get((row['edge_id'], physical), math.inf)
            correct &= row['closed'] == str(max(0, closure - manifest['step_sec']) <= at)
            bad_road += int(not correct)
    checks['road_full_zero_inclusive_unique'] = bool(seen.all() and duplicates == 0 and bad_road == 0 and road_rows == seen.size)
    transition_rows = violations = ambiguous = 0
    with gzip.open(folder / 'transitions.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            transition_rows += 1
            at = hazard.get((row['to_edge'], row['mode']), math.inf)
            violation = float(row['time_upper_sec']) >= at
            violations += int(violation)
            ambiguous += int(row['ambiguous'] == 'True')
            if (row['kind'] == 'closed_entry') != violation:
                ambiguous += 1
    checks['transition_primary_recount'] = transition_rows == manifest['summary']['counts']['transition_rows'] and violations == ambiguous == 0
    checks['source_unchanged_after_audit'] = all(sha(Path(p)) == expected for p, expected in sources.items())
    return {'run_id': run_id, 'scope': 'first_smoke_primary_accounting_not_core_acceptance',
            'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'people': len(people), 'requests': len(requests), 'road_rows_read': road_rows,
            'closure_events': len(closure_events), 'transition_rows_read': transition_rows,
            'current_implementation_match': all(sha(ROOT / p) == expected for p, expected in manifest['implementation_sha256'].items()),
            'core_adoption_permitted': False,
            'pending_formal_validator': ['candidate_path_speed_score_independence', 'duplicate_active_mode_per_step',
                                         'full_core_common_realization', 'VKT', 'tamper_rejection_cases'],
            'source_sha256': {str(Path(p).relative_to(ROOT)): expected for p, expected in sources.items()}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    result = audit(args.run_id)
    target = Path(__file__).parent / (args.run_id + '_一次会計監査.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_sha256'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
