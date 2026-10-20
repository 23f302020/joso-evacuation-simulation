"""Pure registered-secondary components; no simulation or research-result discovery."""
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
from pathlib import Path


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def rows(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def number(value):
    value = float(value)
    require(math.isfinite(value) and value >= 0, 'Invalid nonnegative measurement')
    return value


def boolean(value):
    require(value in ('True', 'False'), 'Missing or invalid boolean')
    return value == 'True'


def vehicle_summary(vehicles):
    vehicles = list(vehicles)
    require(len({v['vehicle_id'] for v in vehicles}) == len(vehicles), 'Duplicate vehicle')
    require(all(v['kind'] in ('car', 'drt') for v in vehicles), 'Unknown vehicle kind')
    output = []
    for kind in ('car', 'drt'):
        selected = [v for v in vehicles if v['kind'] == kind]
        native = [number(v['distance_m']) for v in selected if v['distance_m'] != '']
        total = sum(number(v['observed_distance_m']) for v in selected)
        empty = sum(number(v['observed_empty_distance_m']) for v in selected)
        require(empty <= total + 1e-6, 'Empty distance exceeds observed total')
        output.append({'kind': kind, 'vehicles': len(selected), 'native_distance_observed_vehicles': len(native),
            'native_distance_missing_vehicles': len(selected) - len(native),
            'native_distance_known_sum_m': sum(native) if native or not selected else None,
            'native_distance_complete_sum_m': sum(native) if len(native) == len(selected) else None,
            'observed_distance_sum_m': total, 'observed_empty_distance_sum_m': empty,
            'final_status_counts': json.dumps(Counter(v['status'] for v in selected), sort_keys=True)})
    return output


def candidate_summary(candidates, cycles, scenario):
    cycle_rows = list(cycles)
    indexed = {r['cycle']: r for r in cycle_rows}
    require(len(indexed) == len(cycle_rows), 'Duplicate dispatch cycle')
    counts, reasons, decisions, flags = Counter(), defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    names = ('pickup_route', 'delivery_route', 'pickup_before_deadline', 'completion_within_horizon',
             'gate_applicable', 'gate_pass')
    for row in candidates:
        key = (row['cycle'], int(row['stage']))
        require(key[0] in indexed and 1 <= key[1] <= int(indexed[key[0]]['stages']), 'Unknown candidate cycle/stage')
        require(row['decision'] in ('selected', 'not_selected'), 'Unknown candidate decision')
        require(row['decision'] != 'selected' or row['reason'] == 'eligible', 'Selected rejected candidate')
        counts[key] += 1
        reasons[key][row['reason']] += 1
        decisions[key][row['decision']] += 1
        for name in names:
            flags[key][name + '=' + str(boolean(row[name]))] += 1
    stage_rows = []
    for cycle in cycle_rows:
        keys = [(cycle['cycle'], stage) for stage in range(1, int(cycle['stages']) + 1)]
        require(sum(counts[k] for k in keys) == int(cycle['candidate_rows']), 'Cycle candidate accounting differs')
        require(sum(decisions[k]['selected'] for k in keys) == int(cycle['accepted']), 'Cycle selected accounting differs')
        for key in keys:
            expected = (int(cycle['free_start']) - key[1] + 1) * (int(cycle['pending_start']) - key[1] + 1)
            require(expected > 0 and counts[key] == expected, 'Missing vehicle-by-request stage candidates')
            stage_rows.append({'cycle': key[0], 'stage': key[1], 'candidate_rows': counts[key],
                'selected': decisions[key]['selected'], 'exclusive_reason_counts': json.dumps(reasons[key], sort_keys=True),
                'boolean_counts': json.dumps(flags[key], sort_keys=True)})
    require(scenario != 'R0' or not cycle_rows and not counts, 'R0 has dispatch candidates/cycles')
    summary = {'dispatch_cycles': len(cycle_rows), 'zero_candidate_cycles': sum(int(r['candidate_rows']) == 0 for r in cycle_rows),
               'candidate_rows': sum(counts.values()), 'selected': sum(v['selected'] for v in decisions.values())}
    return summary, cycle_rows, stage_rows


def road_summary(observations, transitions):
    grouped = defaultdict(Counter)
    for row in observations:
        key = (row['time_sec'], row['mode'], boolean(row['closed']))
        require(row['mode'] in ('car', 'drt', 'walk'), 'Unknown road mode')
        group = grouped[key]
        group['road_rows'] += 1
        for name in ('count', 'traffic_count', 'halting_count', 'traffic_halting_count', 'parked_count',
                     'reentry_pending_count', 'unplaced_reentry_count'):
            value = number(row[name]); require(value.is_integer(), 'Fractional actor count')
            group[name + '_sum'] += int(value)
        group['zero_raw_count_rows'] += int(row['count'] == '0')
        group['zero_traffic_count_rows'] += int(row['traffic_count'] == '0')
        for prefix, count_name, speed_name in [('raw', 'count', 'mean_speed_mps'),
                                              ('traffic', 'traffic_count', 'traffic_mean_speed_mps')]:
            count = int(row[count_name])
            if row[speed_name] == '':
                group[prefix + '_speed_missing_rows'] += 1
            else:
                require(count > 0, 'Speed supplied for zero actors')
                group[prefix + '_speed_observed_actor_samples'] += count
                group[prefix + '_speed_actor_weighted_sum_mps'] += count * number(row[speed_name])
    road = []
    fields = ['road_rows', 'count_sum', 'traffic_count_sum', 'halting_count_sum', 'traffic_halting_count_sum',
              'parked_count_sum', 'reentry_pending_count_sum', 'unplaced_reentry_count_sum', 'zero_raw_count_rows',
              'zero_traffic_count_rows', 'raw_speed_missing_rows', 'traffic_speed_missing_rows',
              'raw_speed_observed_actor_samples', 'traffic_speed_observed_actor_samples',
              'raw_speed_actor_weighted_sum_mps', 'traffic_speed_actor_weighted_sum_mps']
    for (time, mode, closed), group in sorted(grouped.items()):
        road.append({'time_sec': time, 'mode': mode, 'closed': closed, **{k: group[k] for k in fields}})
    entries = Counter()
    for row in transitions:
        require(row['mode'] in ('passenger', 'pedestrian') and row['kind'] in ('transition', 'closed_entry'),
                'Unknown transition mode/kind')
        entries[row['mode'], row['kind'], boolean(row['ambiguous'])] += 1
    transition_rows = [{'mode': mode, 'kind': kind, 'ambiguous': ambiguous, 'count': entries[mode, kind, ambiguous]}
        for mode in ('passenger', 'pedestrian') for kind in ('transition', 'closed_entry') for ambiguous in (False, True)]
    return road, transition_rows


def structural_bounds(people, destinations, terminals, walk_limit):
    indexed = {r['origin_id']: r for r in destinations}
    require(len(indexed) == len(destinations), 'Duplicate destination origin')
    counts = defaultdict(Counter)
    for person in people:
        if person['person_type'] != 'type4':
            continue
        row = indexed[person['origin_id']]
        tid = row['terminal_id']
        if tid == '':
            require(not json.loads(row['car_route']) and not json.loads(row['walk_route']),
                    'Missing terminal has a registered route')
            continue  # Retained in the primary Type4 denominator, not a fixed facility assignment.
        require(tid in terminals, 'Unknown fixed terminal')
        if terminals[tid]['kind'] != 'facility':
            continue
        counts[tid]['type4_fixed'] += 1
        car = bool(json.loads(row['car_route']))
        walk = bool(json.loads(row['walk_route']))
        within_limit = walk and row['walk_length_m'] != '' and number(row['walk_length_m']) <= walk_limit
        counts[tid]['registered_passenger_route_present'] += int(car)
        counts[tid]['registered_walk_route_present'] += int(walk)
        counts[tid]['registered_walk_route_within_limit'] += int(within_limit)
    output = []
    for tid, terminal in sorted(terminals.items()):
        if terminal['kind'] == 'facility':
            capacity = int(terminal['capacity'])
            output.append({'terminal_id': tid, 'capacity_all_modes_shared': capacity,
                **{k: counts[tid][k] for k in ('type4_fixed', 'registered_passenger_route_present',
                    'registered_walk_route_present', 'registered_walk_route_within_limit')},
                'fixed_assignment_capacity_upper': min(capacity, counts[tid]['type4_fixed'])})
    require(bool(output), 'No registered facility capacities')
    output.append({'terminal_id': 'all_facilities', **{name: sum(r[name] for r in output)
        for name in output[0] if name != 'terminal_id'}})
    denominator = sum(p['person_type'] == 'type4' for p in people)
    for row in output:
        row['type4_population_denominator'] = denominator
        row['type4_without_fixed_facility'] = denominator - output[-1]['type4_fixed']
    return output


def workload(realization, demand, cfg):
    operation = cfg['operation']; horizon = cfg['simulation']['duration_sec']
    count = sum(boolean(p['intent_' + demand]) for p in realization)
    service = operation['boarding_sec'] + operation['alighting_sec']
    return {'demand_level': demand, 'intended_requests': count, 'fleet_count': operation['fleet_count'],
        'horizon_sec': horizon, 'boarding_sec': operation['boarding_sec'], 'alighting_sec': operation['alighting_sec'],
        'rho_service_only': count * service / (operation['fleet_count'] * horizon)}


def service_bound(horizon, available_from, boarding, alighting, *, initially_empty, serial_one_person):
    require(initially_empty and serial_one_person, 'Service upper-bound assumptions are not established')
    require(horizon > 0 and boarding > 0 and alighting > 0 and available_from, 'Invalid service-bound parameters')
    require(all(0 <= t <= horizon for t in available_from), 'Availability outside counted horizon')
    return sum(math.floor((horizon - t) / (boarding + alighting)) for t in available_from)


def direct_service_accounting(requests, people, cfg, scenario, proof):
    conditions = proof['conditions']
    require(not cfg['operation']['pooling'] and set(conditions) == {'initially_empty', 'serial_one_person',
        'all_available_at_zero', 'full_processing_times', 'no_vehicle_time_reset'} and all(conditions.values()),
        'Unestablished frozen serial-service contract')
    operation = cfg['operation']; horizon = cfg['simulation']['duration_sec']
    bound = 0 if scenario == 'R0' else service_bound(horizon, [0] * operation['fleet_count'],
        operation['boarding_sec'], operation['alighting_sec'], initially_empty=conditions['initially_empty'],
        serial_one_person=conditions['serial_one_person'])
    persons = {p['person_id']: p for p in people}
    served = [q for q in requests if q['status'] == 'served']
    intervals = defaultdict(list)
    for q in served:
        times = [number(q[k]) for k in ('boarding_started_sec', 'boarded_sec', 'alighting_started_sec', 'alighted_sec')]
        require(times[0] < number(q['deadline_sec']) and times[0] <= times[1] <= times[2] <= times[3] <= horizon,
                'Served service outside valid observation/deadline order')
        require(times[1] - times[0] >= operation['boarding_sec'] and times[3] - times[2] >= operation['alighting_sec'],
                'Served service lacks full processing time')
        require(q['vehicle_id'] != '', 'Served service lacks vehicle identity')
        intervals[q['vehicle_id']].append((times[0], times[3]))
    require(len(intervals) <= operation['fleet_count'], 'More successful service vehicles than fleet')
    for service_intervals in intervals.values():
        ordered = sorted(service_intervals)
        require(all(left[1] <= right[0] for left, right in zip(ordered, ordered[1:])),
                'Successful intervals overlap on one vehicle')
    admitted = sum(persons[q['person_id']]['status'] == 'admitted' for q in served)
    direct = [p for p in people if p['mode'] == 'drt' and p['status'] == 'admitted']
    require({p['person_id'] for p in direct} == {q['person_id'] for q in served if persons[q['person_id']]['status'] == 'admitted'},
            'Direct DRT admissions and served requests differ')
    require(admitted <= len(served) <= bound, 'Serial DRT service upper bound exceeded')
    return {'successful_drt_services': len(served), 'direct_drt_admitted': admitted,
        'direct_drt_type4_admitted': sum(p['person_type'] == 'type4' for p in direct),
        'service_only_completion_upper': bound,
        'scope': 'DRT_direct_completion_only_not_all_person_or_Type4_improvement_difference'}
