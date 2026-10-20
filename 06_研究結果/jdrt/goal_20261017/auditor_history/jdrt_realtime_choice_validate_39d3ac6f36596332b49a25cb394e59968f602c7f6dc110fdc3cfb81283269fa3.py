"""Independent input and run-table checks; full core acceptance is not ready yet."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import csv
import gzip
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET

import h5py
import networkx as nx
import numpy as np
import rasterio
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from pyproj import Transformer
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
PARAM = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def stream_rows(path):
    opener = gzip.open if path.suffix == '.gz' else Path.open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


class IndependentCarTimes:
    """CSR node-cost shortest paths, independent of the dispatcher's NetworkX trees.

    Construct once per dispatch cycle. Only requested source/target distance arrays
    are retained, never all-pairs or arrays for all historical cycles.
    """

    def __init__(self, graph, closed, observed, pickup_sources, delivery_targets):
        self.nodes = graph['nodes']
        self.names = sorted(self.nodes)
        self.index = {name: i for i, name in enumerate(self.names)}
        self.closed = set(closed)
        self.successors = defaultdict(list)
        arcs = set()
        for a, b, _ in graph['edges']:
            if a not in self.closed and b not in self.closed:
                arcs.add((self.index[a], self.index[b]))
                self.successors[a].append(b)
        ordered = sorted(arcs)
        rid = np.array([a for a, b in ordered], dtype=np.int32)
        col = np.array([b for a, b in ordered], dtype=np.int32)
        n = len(self.names)
        self.times = {}
        self.forward, self.reverse = {}, {}
        self.pickup_sources = sorted((set(pickup_sources) - self.closed) & self.index.keys())
        self.delivery_targets = sorted((set(delivery_targets) - self.closed) & self.index.keys())
        for mode in ('pickup', 'delivery'):
            weights = []
            for name in self.names:
                total, count = observed.get(name, (0., 0)) if mode == 'pickup' else (0., 0)
                attrs = self.nodes[name]
                value = float(attrs['length']) / max(total / count, .1) if count else float(attrs['free_sec'])
                if not math.isfinite(value) or value < 0 or float(attrs['length']) <= 0:
                    raise ValueError('Invalid registered edge length/time')
                weights.append(value)
            self.times[mode] = np.array(weights)
            matrix = csr_matrix((self.times[mode][col], (rid, col)), shape=(n, n))
            targets = self.pickup_sources if mode == 'pickup' else self.delivery_targets
            if targets:
                distances = dijkstra(matrix.T.tocsr(), directed=True,
                                     indices=[self.index[x] for x in targets])
                self.reverse[mode] = dict(zip(targets, distances))
            else:
                self.reverse[mode] = {}
            if mode == 'pickup' and self.pickup_sources:
                distances = dijkstra(matrix, directed=True,
                                     indices=[self.index[x] for x in self.pickup_sources])
                self.forward[mode] = dict(zip(self.pickup_sources, distances))

    def optimal(self, start, target, start_pos, target_pos, mode, minimum=0):
        if start not in self.index or target not in self.index or {start, target} & self.closed:
            return math.inf
        first, last = float(self.nodes[start]['length']), float(self.nodes[target]['length'])
        if not all(math.isfinite(x) for x in (start_pos, target_pos, minimum)) or not (
                0 <= start_pos <= first and 0 <= target_pos <= last and minimum >= 0):
            raise ValueError('Invalid partial-edge position')
        weights = self.times[mode]
        si, ti = self.index[start], self.index[target]
        if start == target and target_pos - start_pos >= minimum:
            return float(weights[si] * (target_pos - start_pos) / first)
        if start == target:
            reverse = self.reverse[mode][target]
            cost = min((weights[self.index[n]] + reverse[self.index[n]]
                        for n in self.successors[start]), default=math.inf)
        elif mode == 'pickup':
            cost = self.forward[mode][start][ti]
        else:
            cost = self.reverse[mode][target][si]
        return float(cost + weights[si] * (1 - start_pos / first)
                     - weights[ti] * (1 - target_pos / last))


def independent_number(row, prefix):
    kind, value = row[prefix + '_kind'], row[prefix + '_sec']
    if kind == 'finite' and value != '' and math.isfinite(float(value)):
        return float(value)
    if kind == 'infinite' and value == '':
        return math.inf
    if kind == 'not_applicable' and value == '':
        return None
    raise ValueError('Invalid numeric/missingness pair: ' + prefix)


def audit_candidates(folder, manifest, cfg, events):
    """Stream candidate stages; retain observations only at dispatch timestamps."""
    inputs = ROOT / manifest['input_directory']
    graph = json.loads((inputs / 'graphs.json').read_text(encoding='utf-8'))['passenger']
    arcs = {(a, b) for a, b, _ in graph['edges']}
    common = {r['person_id']: r for r in rows(folder / 'common_realization.csv')}
    origins = {r['origin_id']: r for r in rows(inputs / 'origins.csv')}
    dest = {r['origin_id']: r for r in rows(inputs / ('destinations_' + manifest['destination_policy'] + '.csv'))}
    terms = {r['terminal_id']: r for r in rows(inputs / 'terminals.csv')}
    places = {(r['kind'], r['place_id']): r for r in rows(inputs / 'place_positions.csv')}
    closures = {r['edge_id']: float(r['closure_sec']) for r in rows(inputs / 'hazard.csv')
                if r['mode'] == 'passenger' and r['closure_sec'] != ''}
    cycles_list = list(stream_rows(folder / 'dispatch_cycles.csv.gz'))
    cycles = {int(r['cycle']): r for r in cycles_list}
    errors = Counter()
    details = defaultdict(list)

    def fail(name, detail):
        errors[name] += 1
        if len(details[name]) < 10:
            details[name].append(detail)

    expected_times = (list(range(0, int(manifest['end_sec']) + 1, cfg['simulation']['dispatch_sec']))
                      if manifest['scenario'] != 'R0' else [])
    if (len(cycles) != len(cycles_list) or sorted(cycles) != list(range(1, len(expected_times) + 1))
            or [float(cycles[c]['time_sec']) for c in sorted(cycles)] != expected_times):
        fail('dispatch_grid', 'duplicate/missing/off-grid cycle')
    cycle_times = {float(r['time_sec']) for r in cycles_list}
    frames = {}
    for r in stream_rows(folder / 'actor_observations.csv.gz'):
        if r['kind'] == 'drt' and float(r['time_sec']) in cycle_times:
            key = float(r['time_sec']), r['actor_id']
            if key in frames:
                fail('candidate_source', ['duplicate', *key])
            frames[key] = r
    speeds = defaultdict(lambda: defaultdict(lambda: [0., 0]))
    # Unlike the old probe auditor this does not reread the dense all-edge CSV.
    for r in stream_rows(folder / 'snapshot_actor_observations.csv.gz'):
        at = float(r['time_sec'])
        speeds[at]  # Empty-traffic snapshots still replace older observations.
        if r['kind'] != 'walk' and r['observation_kind'] == 'onroad' and r['road_id'] in graph['nodes']:
            pair = speeds[at][r['road_id']]
            pair[0] += float(r['speed_mps'])
            pair[1] += 1
    # Also include entirely empty snapshot frames, which have no actor rows.
    for at in range(0, int(manifest['end_sec']) + 1, manifest['snapshot_sec']):
        speeds[float(at)]
    accepts = {(int(e['cycle']), int(e['stage'])): (e['person_id'], e['vehicle_id'])
               for e in events if e['event'] == 'request_accepted'}
    state_events = [e for e in events if e['event'] == 'request_state']
    event_times = defaultdict(list)
    for e in events:
        event_times[e['time_sec']].append(e)
    fleet = {r['vehicle_id'] for r in rows(folder / 'vehicle_results.csv') if r['kind'] == 'drt'}
    free_by_cycle = {}
    for cycle, row in cycles.items():
        now = float(row['time_sec'])
        statuses = {}
        for vid in fleet:
            frame = frames.get((now, vid))
            status = frame['status'] if frame else 'pending_idle'
            if frame and status in ('pending_idle', 'cancel_wait') and int(frame['stop_state']) & 1:
                status = 'idle'
            statuses[vid] = status
        for e in event_times[now]:
            vid = e.get('vehicle_id', e.get('actor_id'))
            if vid in fleet:
                change = {'request_cancelled': 'cancel_pending', 'actor_removed': 'stranded',
                          'drt_alighted': 'idle', 'drt_boarded': 'delivery',
                          'boarding_started': 'boarding', 'alighting_started': 'alighting',
                          'cancel_wait_route': 'cancel_wait'}.get(e['event'])
                if change:
                    statuses[vid] = change
        free_by_cycle[cycle] = {vid for vid, status in statuses.items() if status == 'idle'}
        pending = {}
        for e in state_events:
            if e['time_sec'] > now:
                break
            if e.get('trigger') == 'accepted' and e.get('cycle') == cycle:
                continue
            pending[e['person_id']] = e['after']
        number_pending = sum(state == 'pending' for state in pending.values())
        if len(free_by_cycle[cycle]) != int(row['free_start']) or number_pending != int(row['pending_start']):
            fail('cycle_availability', cycle)
        if bool(int(row['stages'])) != bool(free_by_cycle[cycle] and number_pending):
            fail('cycle_availability', [cycle, 'missing/extra_stages'])
    seen_accepts, stage_counts, row_counts = set(), Counter(), Counter()
    row_total, last_key, active_cycle, engine = 0, (0, 0), None, None
    keyfn = lambda r: (int(r['cycle']), int(r['stage']))
    for key, iterator in itertools.groupby(stream_rows(folder / 'candidates.csv.gz'), keyfn):
        group = list(iterator)
        cycle, stage = key
        if key <= last_key or cycle not in cycles:
            raise ValueError('Candidate stages are duplicated, unordered or unknown')
        last_key = key
        now = float(cycles[cycle]['time_sec'])
        stage_counts[cycle] += 1
        row_counts[cycle] += len(group)
        row_total += len(group)
        pending = {}
        for e in state_events:
            if e['time_sec'] > now:
                break
            if e.get('trigger') == 'accepted' and e.get('cycle') == cycle and e.get('stage', 0) >= stage:
                continue
            pending[e['person_id']] = e['after']
        persons = {pid for pid, state in pending.items() if state == 'pending'}
        vehicles = {r['vehicle_id'] for r in group}
        expected_vehicles = free_by_cycle[cycle] - {v for (c, s), (p, v) in accepts.items() if c == cycle and s < stage}
        pairs = {(r['person_id'], r['vehicle_id']) for r in group}
        if pairs != {(p, v) for p in persons for v in vehicles} or len(pairs) != len(group):
            fail('candidate_matrix', key)
        if (stage != stage_counts[cycle] or len(vehicles) != int(cycles[cycle]['free_start']) - stage + 1
                or vehicles != expected_vehicles):
            fail('candidate_free_stages', key)
        closed = {n for n, at in closures.items() if max(0, at - manifest['step_sec']) <= now}
        if active_cycle != cycle:
            previous = max((at for at in speeds if at < now), default=None)
            sources = {r['source_edge'] for r in group}
            targets = {t['edge_id'] for t in terms.values()}
            engine = IndependentCarTimes(graph, closed, speeds[previous] if previous is not None else {}, sources, targets)
            active_cycle = cycle
        eligible = []
        for r in group:
            pid, vid = r['person_id'], r['vehicle_id']
            for field in ('time_sec', 'source_pos_m', 'source_speed_mps', 'source_decel_mps2', 'minimum_advance_m',
                          'pickup_pos_m', 'terminal_pos_m', 'waiting_sec', 'urgency'):
                if not math.isfinite(float(r[field])):
                    raise ValueError('Nonfinite candidate scalar: ' + field)
            p = common[pid]
            origin = origins[p['origin_id']]['edge_id']
            term = dest[p['origin_id']]['terminal_id']
            target = terms[term]['edge_id']
            op = float(places['origin', p['origin_id']]['car_pos_m'])
            tp = float(places['terminal', term]['car_pos_m'])
            frame = frames.get((now, vid))
            if (float(r['time_sec']) != now or not frame or r['source_edge'] != frame['road_id']
                    or abs(float(r['source_pos_m']) - float(frame['lane_position_m'])) > 1e-8
                    or abs(float(r['source_speed_mps']) - float(frame['speed_mps'])) > 1e-8):
                fail('candidate_source', [*key, pid, vid])
            if frame and int(frame['stop_state']) & 1 and float(r['minimum_advance_m']) != 0:
                fail('candidate_source', [*key, pid, vid, 'stopped_braking_bound'])
            if frame:
                decel = float(frame['decel_mps2'])
                if not math.isfinite(decel) or decel <= 0:
                    raise ValueError('Invalid native actor deceleration')
                speed = float(frame['speed_mps'])
                bound = 0 if int(frame['stop_state']) & 1 else speed * speed / (2 * decel) + speed * manifest['step_sec'] + 1
                if (float(r['source_decel_mps2']) != decel
                        or not math.isclose(float(r['minimum_advance_m']), bound, rel_tol=0, abs_tol=1e-9)):
                    fail('candidate_source', [*key, pid, vid, 'native_braking_bound'])
            if r['decision'] not in ('selected', 'not_selected'):
                fail('candidate_selection', [*key, pid, 'unknown_decision'])
            if abs(float(r['pickup_pos_m']) - op) > 1e-8 or abs(float(r['terminal_pos_m']) - tp) > 1e-8:
                fail('candidate_positions', [*key, pid])
            paths = {mode: json.loads(r[mode + '_path']) for mode in ('pickup', 'delivery')}
            for mode, start, end, begin, finish in [('pickup', r['source_edge'], origin, float(r['source_pos_m']), op),
                                                   ('delivery', origin, target, op, tp)]:
                expected = engine.optimal(start, end, begin, finish, mode,
                                          float(r['minimum_advance_m']) if mode == 'pickup' else 0)
                value = independent_number(r, mode)
                equal = value == expected if not math.isfinite(expected) else (
                    value is not None and math.isclose(value, expected, rel_tol=0, abs_tol=1e-7))
                path = paths[mode]
                path_valid = bool(path) == math.isfinite(expected)
                if path:
                    path_valid &= (path[0] == start and path[-1] == end and not set(path) & closed
                                   and all((a, b) in arcs for a, b in zip(path, path[1:])))
                    if path_valid:
                        weights = engine.times[mode]
                        actual = sum(weights[engine.index[n]] for n in path)
                        actual -= weights[engine.index[start]] * begin / float(graph['nodes'][start]['length'])
                        actual -= weights[engine.index[end]] * (1 - finish / float(graph['nodes'][end]['length']))
                        path_valid &= math.isclose(actual, expected, rel_tol=0, abs_tol=1e-7)
                if not equal or not path_valid:
                    fail('candidate_shortest_paths', [*key, pid, mode])
            pickup, delivery = independent_number(r, 'pickup'), independent_number(r, 'delivery')
            deadline = float(p['ready_sec']) + cfg['request_policy']['max_unboarded_wait_sec']
            required = pickup + delivery + sum(cfg['operation'][k] for k in ('boarding_sec', 'alighting_sec', 'margin_sec'))
            forecasting = manifest['scenario'].startswith('R2')
            remaining = min((closures.get(n, math.inf) + cfg['forecast'][manifest['scenario']]['scheduled_time_error_sec'] - now
                             for n in paths['pickup'] + paths['delivery']), default=math.inf) if forecasting else None
            predicates = [('no_pickup_route', math.isfinite(pickup)), ('no_delivery_route', math.isfinite(delivery)),
                          ('pickup_deadline', now + pickup < deadline),
                          ('horizon', now + required - cfg['operation']['margin_sec'] <= manifest['end_sec'])]
            if forecasting:
                predicates.append(('forecast_gate', required < remaining))
            reason = next((name for name, value in predicates if not value), 'eligible')
            booleans = dict(zip(('pickup_route', 'delivery_route', 'pickup_before_deadline', 'completion_within_horizon'),
                                [value for _, value in predicates[:4]]))
            booleans.update(gate_applicable=forecasting and math.isfinite(remaining),
                            gate_pass=required < remaining if forecasting else None)
            recorded = independent_number(r, 'required')
            same_required = recorded == required if not math.isfinite(required) else (
                recorded is not None and math.isclose(recorded, required, rel_tol=0, abs_tol=1e-9))
            if (r['reason'] != reason or any(r[k] != (str(v) if v is not None else '') for k, v in booleans.items())
                    or independent_number(r, 'forecast_remaining') != remaining or not same_required):
                fail('candidate_gates', [*key, pid])
            waiting, vulnerable = now - float(p['ready_sec']), int(p['person_type'] == 'type4')
            urgency = 1 / max(remaining, 1) if remaining is not None and math.isfinite(remaining) else 0
            if (float(r['waiting_sec']) != waiting or int(r['vulnerability']) != vulnerable
                    or not math.isclose(float(r['urgency']), urgency, rel_tol=0, abs_tol=1e-12)):
                fail('candidate_score_components', [*key, pid])
            if reason == 'eligible':
                eligible.append((r, waiting, vulnerable, pickup, urgency))
            elif r['score'] != '':
                fail('candidate_score', [*key, pid, 'ineligible_score'])
        maxima = [max((x[i] for x in eligible), default=0) for i in (1, 3, 4)]
        weights, scores = cfg['dispatch_weights'], {}
        for r, waiting, vulnerable, pickup, urgency in eligible:
            score = (weights['waiting'] * waiting / maxima[0] if maxima[0] else 0) + weights['vulnerability'] * vulnerable
            score -= weights['pickup'] * pickup / maxima[1] if maxima[1] else 0
            if manifest['scenario'].startswith('R2'):
                score += weights['flood'] * urgency / maxima[2] if maxima[2] else 0
            scores[r['person_id'], r['vehicle_id']] = score
            if r['score'] == '' or not math.isclose(float(r['score']), score, rel_tol=0, abs_tol=1e-10):
                fail('candidate_score', [*key, r['person_id']])
        chosen = min(scores, key=lambda pair: (-scores[pair], pair), default=None)
        selected = [(r['person_id'], r['vehicle_id']) for r in group if r['decision'] == 'selected']
        if selected != ([chosen] if chosen else []) or accepts.get(key) != chosen:
            fail('candidate_selection', key)
        if chosen:
            seen_accepts.add(key)
    if seen_accepts != set(accepts):
        fail('candidate_selection', 'acceptance_without_candidate_stage')
    for cycle, row in cycles.items():
        if (stage_counts[cycle] != int(row['stages']) or row_counts[cycle] != int(row['candidate_rows'])
                or int(row['accepted']) != sum(c == cycle for c, stage in accepts)):
            fail('cycle_counts', cycle)
    names = ('dispatch_grid', 'cycle_availability', 'candidate_matrix', 'candidate_free_stages', 'candidate_source',
             'candidate_positions', 'candidate_shortest_paths', 'candidate_gates',
             'candidate_score_components', 'candidate_score', 'candidate_selection', 'cycle_counts')
    return {'status': 'PASS' if not errors else 'INVALID', 'checks': {k: not errors[k] for k in names},
            'errors': dict(errors), 'examples': dict(details), 'candidate_rows': row_total,
            'cycles': len(cycles), 'method': 'scipy_CSR_forward_pickup_reverse_delivery_node_cost',
            'numeric_time_tolerance_sec': 1e-7, 'required_sum_tolerance_sec': 1e-9,
            'strict_gate_predicates_checked_separately': True, 'core_adoption_permitted': False}


def audit_person_tables(folder, manifest, cfg, events):
    """Reconstruct denominators, state/time chains and shared arrival capacity."""
    inputs = ROOT / manifest['input_directory']
    errors, examples = Counter(), defaultdict(list)

    def fail(name, detail):
        errors[name] += 1
        if len(examples[name]) < 10:
            examples[name].append(detail)

    def unique(path, key):
        data = rows(path)
        result = {r[key]: r for r in data}
        if len(result) != len(data):
            fail('unique_tables', path.name)
        return result

    people = unique(folder / 'person_results.csv', 'person_id')
    common = unique(folder / 'common_realization.csv', 'person_id')
    source = unique(inputs / f'common_realization_seed{manifest["seed"]}.csv', 'person_id')
    requests = unique(folder / 'request_results.csv', 'person_id')
    vehicles = unique(folder / 'vehicle_results.csv', 'vehicle_id')
    facilities = unique(folder / 'facility_results.csv', 'terminal_id')
    terminals = unique(inputs / 'terminals.csv', 'terminal_id')
    origins = unique(inputs / 'origins.csv', 'origin_id')
    destinations = unique(inputs / ('destinations_' + manifest['destination_policy'] + '.csv'), 'origin_id')
    if set(people) != set(common) or (manifest['purpose'] != 'smoke' and set(common) != set(source)):
        fail('complete_population', 'person/common/source IDs')
    if not set(common) <= set(source):
        fail('complete_population', 'unregistered person')
    for i, (pid, r) in enumerate(common.items()):
        p, original = people[pid], source[pid]
        expected_ready = i % 10 if manifest['purpose'] == 'smoke' else int(original['ready_sec'])
        if (any(r[k] != v for k, v in original.items() if k != 'ready_sec')
                or int(r['ready_sec']) != expected_ready
                or any(p[k] != v for k, v in r.items())):
            fail('common_realization_and_attributes', pid)
        selected = manifest['scenario'] != 'R0' and original['intent_' + str(manifest['demand_level'])] == 'True'
        terminal = destinations[r['origin_id']]['terminal_id']
        if (r['selected_jdrt'] != str(selected) or r['terminal_id'] != terminal
                or p['initial_mode'] != ('drt' if selected else original['base_mode'])
                or p['mode'] not in ('car', 'walk', 'drt')):
            fail('assigned_intent_mode_terminal', pid)
    if (len({q['request_id'] for q in requests.values()}) != len(requests)
            or set(requests) != {pid for pid, p in common.items() if p['selected_jdrt'] == 'True'}):
        fail('request_set', 'intent/request IDs')
    crews = defaultdict(list)
    for pid, p in people.items():
        if p['initial_mode'] == 'car':
            crews[p['vehicle_id']].append(pid)
    drt_ids = {f'choice_drt_{i}' for i in range(cfg['operation']['fleet_count'])} if manifest['scenario'] != 'R0' else set()
    if set(vehicles) != set(crews) | drt_ids:
        fail('vehicle_set', 'private crews/fleet IDs')
    for vid, v in vehicles.items():
        if v['kind'] != ('drt' if vid in drt_ids else 'car'):
            fail('vehicle_set', vid)
        if v['kind'] == 'drt' and (int(v['passenger_capacity']) != cfg['operation']['passenger_capacity']
                                   or not 0 <= int(v['maximum_onboard']) <= 1):
            fail('vehicle_set', [vid, 'nonpooling/capacity'])
    if manifest['purpose'] == 'smoke':
        # Cohort construction itself is technical, but it must not split private crews.
        for vid in crews:
            if set(crews[vid]) != {pid for pid, p in source.items() if p['vehicle_id'] == vid}:
                fail('complete_population', ['split_private_crew', vid])
    person_states = {pid: 'not_ready' for pid in people}
    request_states = {pid: 'none' for pid in requests}
    index = defaultdict(list)
    histories = defaultdict(list)
    allowed = {('none', 'pending'), ('pending', 'accepted'), ('pending', 'rejected_input'),
               ('pending', 'cancelled_timeout'), ('accepted', 'cancelled_timeout'),
               ('accepted', 'cancelled_vehicle_failure'), ('accepted', 'boarding'),
               ('boarding', 'onboard'), ('onboard', 'alighting'), ('alighting', 'served')}
    allowed |= {(s, 'failed_after_boarding') for s in ('boarding', 'onboard', 'alighting')}
    allowed |= {(s, 'time_limit') for s in ('pending', 'accepted', 'boarding', 'onboard', 'alighting')}
    last_time = -1
    final_states = {'admitted', 'boundary_exit', 'capacity_rejected', 'no_origin_connection', 'no_route',
                    'walk_limit', 'initial_or_current_closed', 'route_cut', 'stranded_drt', 'time_limit'}
    for e in events:
        at, pid = e['time_sec'], e.get('person_id')
        if not math.isfinite(at) or not last_time <= at <= manifest['end_sec'] or at % manifest['step_sec']:
            fail('event_clock', [e['event'], at])
        last_time = at
        index[pid, e['event']].append(e)
        if e['event'] in ('person_state', 'request_state'):
            states = person_states if e['event'] == 'person_state' else request_states
            if states.get(pid) != e['before']:
                fail('state_chains', [pid, e['event'], e['before']])
            if e['event'] == 'request_state' and (e['before'], e['after']) not in allowed:
                fail('request_fsm', [pid, e['before'], e['after']])
            if e['event'] == 'person_state':
                terminal_arrivals = {'admitted', 'boundary_exit', 'capacity_rejected'}
                failure = {'no_origin_connection', 'no_route', 'initial_or_current_closed'}
                person_allowed = {
                    'not_ready': ({'waiting_origin', 'no_origin_connection', 'no_route'} if people[pid]['initial_mode'] == 'drt'
                                  else failure | ({'travelling_car'} if people[pid]['initial_mode'] == 'car'
                                                  else {'travelling_walk', 'walk_limit'})),
                    'waiting_origin': {'assigned_origin', 'fallback_pending'},
                    'assigned_origin': {'boarding', 'fallback_pending'},
                    'fallback_pending': failure | {'travelling_walk', 'walk_limit'},
                    'boarding': {'onboard', 'stranded_drt'}, 'onboard': {'alighting', 'stranded_drt'},
                    'alighting': terminal_arrivals | {'stranded_drt'},
                    'travelling_car': terminal_arrivals | {'initial_or_current_closed', 'route_cut'},
                    'travelling_walk': terminal_arrivals | {'initial_or_current_closed', 'route_cut', 'walk_limit'}}
                if (e['after'] not in person_allowed.get(e['before'], set()) | {'time_limit'}
                        or (e['after'] == 'time_limit' and at != manifest['end_sec'])
                        or (at < float(people[pid]['ready_sec']) and e['after'] != 'time_limit')):
                    fail('person_fsm', [pid, e['before'], e['after'], at])
                if e['before'] in final_states:
                    fail('state_chains', [pid, 'left_final_state'])
                histories[pid].append(e)
            states[pid] = e['after']
    if person_states != {pid: p['status'] for pid, p in people.items()} or any(s not in final_states for s in person_states.values()):
        fail('state_chains', 'person final states')
    if request_states != {pid: p['status'] for pid, p in requests.items()}:
        fail('state_chains', 'request final states')
    for pid, q in requests.items():
        p = people[pid]
        deadline = float(p['ready_sec']) + cfg['request_policy']['max_unboarded_wait_sec']
        if (float(q['deadline_sec']) != deadline or float(p['deadline_sec']) != deadline
                or q['person_final_status'] != p['status'] or q['person_final_mode'] != p['mode']
                or q['terminal_id'] != p['terminal_id']):
            fail('request_lifecycle', [pid, 'person/deadline'])
        for field, event in [('received_sec', 'request_received'), ('accepted_sec', 'request_accepted'),
                             ('boarding_started_sec', 'boarding_started'), ('boarded_sec', 'drt_boarded'),
                             ('alighting_started_sec', 'alighting_started'), ('alighted_sec', 'drt_alighted'),
                             ('cancel_sec', 'request_cancelled'), ('fallback_sec', 'fallback_attempt')]:
            matches = index[pid, event]
            if (len(matches) != (1 if q[field] != '' else 0) or q[field] != p[field]
                    or (matches and float(q[field]) != matches[0]['time_sec'])):
                fail('request_lifecycle', [pid, field])
            for match in matches:
                if 'vehicle_id' in match and match['vehicle_id'] != q['vehicle_id']:
                    fail('request_lifecycle', [pid, event, 'vehicle_id'])
        if float(q['received_sec']) != float(p['ready_sec']):
            fail('request_lifecycle', [pid, 'received/readiness'])
        if q['boarding_started_sec'] != '' and not float(q['boarding_started_sec']) < deadline:
            fail('request_lifecycle', [pid, 'boarding_deadline'])
        for end, start, duration in [('boarded_sec', 'boarding_started_sec', cfg['operation']['boarding_sec']),
                                     ('alighted_sec', 'alighting_started_sec', cfg['operation']['alighting_sec'])]:
            if q[end] != '' and (q[start] == '' or float(q[end]) - float(q[start]) != duration):
                fail('request_lifecycle', [pid, end])
        fallback = index[pid, 'fallback_attempt']
        if q['status'].startswith('cancelled_'):
            if (len(fallback) != 1 or q['boarding_started_sec'] != '' or p['mode'] != 'walk'
                    or q['cancel_sec'] != q['fallback_sec']):
                fail('request_lifecycle', [pid, 'fallback'])
            if fallback and (fallback[0]['origin_edge'] != origins[p['origin_id']]['edge_id']
                             or fallback[0]['terminal_id'] != p['terminal_id']):
                fail('request_lifecycle', [pid, 'fallback_origin_terminal'])
        elif fallback:
            fail('request_lifecycle', [pid, 'unexpected_fallback'])
        if q['status'] == 'cancelled_timeout' and float(q['cancel_sec']) != deadline:
            fail('request_lifecycle', [pid, 'timeout'])
        if q['status'] == 'served' and q['alighted_sec'] == '':
            fail('request_lifecycle', [pid, 'served_without_alighting'])
        if q['status'] == 'failed_after_boarding' and q['boarding_started_sec'] == '':
            fail('request_lifecycle', [pid, 'failure_without_boarding'])
        if q['status'] == 'rejected_input' and origins[p['origin_id']]['edge_id'] and p['terminal_id']:
            fail('request_lifecycle', [pid, 'spurious_invalid_input'])
        for field in ('depart_sec', 'arrival_sec', 'admitted_sec'):
            if q[field] != p[field]:
                fail('request_lifecycle', [pid, field])
    occupancy = Counter()
    arrivals = sorted((float(p['arrival_sec']), pid) for pid, p in people.items() if p['arrival_sec'] != '')
    for at, pid in arrivals:
        p, terminal = people[pid], terminals[people[pid]['terminal_id']]
        status = ('boundary_exit' if terminal['kind'] == 'boundary_exit' else
                  'admitted' if occupancy[p['terminal_id']] < int(terminal['capacity']) else 'capacity_rejected')
        if status == 'admitted':
            occupancy[p['terminal_id']] += 1
        matched = index[pid, 'person_terminal']
        if (p['status'] != status or len(matched) != 1 or matched[0]['time_sec'] != at
                or matched[0]['status'] != status or matched[0]['terminal_id'] != p['terminal_id']
                or (p['admitted_sec'] != str(at) and status == 'admitted'
                    and (p['admitted_sec'] == '' or float(p['admitted_sec']) != at))
                or (status != 'admitted' and p['admitted_sec'] != '')):
            fail('shared_capacity_and_exit', pid)
    for pid, p in people.items():
        if (p['status'] in ('admitted', 'capacity_rejected', 'boundary_exit')) != (p['arrival_sec'] != ''):
            fail('shared_capacity_and_exit', [pid, 'arrival/status'])
    expected_facilities = {key for key, t in terminals.items() if t['kind'] == 'facility'}
    if set(facilities) != expected_facilities or any(
            int(f['capacity']) != int(terminals[key]['capacity']) or int(f['admitted']) != occupancy[key]
            for key, f in facilities.items()):
        fail('shared_capacity_and_exit', 'facility totals')
    hazard = {(r['edge_id'], r['mode']): float(r['closure_sec']) for r in rows(inputs / 'hazard.csv') if r['closure_sec'] != ''}
    closures = [e for e in events if e['event'] == 'closure_applied']
    expected = {(edge, mode, at) for (edge, mode), at in hazard.items() if at <= manifest['end_sec']}
    actual = [(e['edge_id'], e['mode'], e['scheduled_sec']) for e in closures]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        fail('closure_clocks', 'missing/duplicate closure')
    for e in closures:
        at = e['scheduled_sec']
        if not (e['time_sec'] == e['control_call_sec'] == max(0, at - manifest['step_sec'])
                and e['observation_upper_sec'] == at and e['control_lead_sec'] == at - e['time_sec']
                and e['phase'] == ('initial_before_observation' if at == 0 else 'before_step_ending_at_closure')):
            fail('closure_clocks', e)
    waiting_states = {'waiting_origin', 'assigned_origin', 'boarding'}
    for pid, p in people.items():
        for mode, field in [('pedestrian', 'origin_ped_closed_wait_sec'), ('passenger', 'origin_vehicle_closed_wait_sec')]:
            edge = origins[p['origin_id']]['edge_id']
            closed_at = hazard.get((edge, mode), math.inf)
            closed_at = max(0, closed_at - manifest['step_sec'])
            value = 0
            history = histories[pid]
            for i, e in enumerate(history):
                if e['after'] in waiting_states:
                    end = history[i + 1]['time_sec'] if i + 1 < len(history) else manifest['end_sec']
                    value += max(0, end - max(e['time_sec'], closed_at))
            if not math.isclose(float(p[field]), value, rel_tol=0, abs_tol=1e-7):
                fail('waiting_hazard_overlap', [pid, mode, value, p[field]])
    summary = manifest['summary']
    if (summary['people'] != len(people) or summary['states'] != dict(Counter(p['status'] for p in people.values()))
            or summary['type_counts'] != dict(Counter(p['person_type'] for p in people.values()))
            or summary['request_states'] != dict(Counter(q['status'] for q in requests.values()))):
        fail('summary_accounting', 'primary table/count mismatch')
    counts = summary['counts']
    if (counts['steps'] != manifest['end_sec'] / manifest['step_sec']
            or counts['controller_ticks'] != manifest['end_sec'] // cfg['simulation']['controller_sec'] + 1
            or counts['snapshots'] != manifest['end_sec'] // manifest['snapshot_sec'] + 1
            or counts['closures_applied'] != len(closures)):
        fail('summary_accounting', 'clock/closure counts')
    primary = [p for p in people.values() if p['person_type'] == cfg['evaluation']['primary_type']]
    names = ('unique_tables', 'complete_population', 'common_realization_and_attributes', 'assigned_intent_mode_terminal',
             'request_set', 'vehicle_set', 'event_clock', 'state_chains', 'person_fsm', 'request_fsm', 'request_lifecycle',
             'shared_capacity_and_exit', 'closure_clocks', 'waiting_hazard_overlap', 'summary_accounting')
    return {'status': 'PASS' if not errors else 'INVALID', 'checks': {k: not errors[k] for k in names},
            'errors': dict(errors), 'examples': dict(examples), 'people': len(people), 'requests': len(requests),
            'primary_denominator': len(primary), 'primary_admitted': sum(p['status'] == 'admitted' for p in primary),
            'primary_boundary_exit_separate': sum(p['status'] == 'boundary_exit' for p in primary),
            'primary_unaccepted_person_sec': sum(float(p['admitted_sec']) if p['status'] == 'admitted'
                                                 else manifest['end_sec'] for p in primary),
            'core_adoption_permitted': False}


def verifier_dependencies():
    import scipy
    from scipy.sparse.csgraph import _shortest_path
    from numpy._core import _multiarray_umath
    return {'numpy': np.__version__, 'scipy': scipy.__version__,
            'scipy_shortest_path_binary_sha256': file_sha(Path(_shortest_path.__file__)),
            'numpy_multiarray_binary_sha256': file_sha(Path(_multiarray_umath.__file__))}


def audit_actor_stream(folder, manifest, cfg, events):
    """Single-pass actor cadence, membership, integral, route-index and VKT checks."""
    inputs = ROOT / manifest['input_directory']
    people = {r['person_id']: r for r in rows(folder / 'person_results.csv')}
    vehicles = {r['vehicle_id']: r for r in rows(folder / 'vehicle_results.csv')}
    input_manifest = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
    crews = defaultdict(list)
    for pid, p in people.items():
        if p['initial_mode'] == 'car':
            crews[p['vehicle_id']].append(pid)
    expected_members = {vid: set(crews[vid]) for vid in vehicles}
    active_person = {vid: '' for vid in vehicles}
    reentry_expected = {vid: False for vid in vehicles}
    routes = defaultdict(dict)
    for vid, v in vehicles.items():
        if v['kind'] == 'drt':
            routes[vid][0] = [input_manifest['depot_edge']]
    starts = {vid: 0. for vid, v in vehicles.items() if v['kind'] == 'drt'}
    ends, removal_times = {}, set()
    reroute_times = set()
    for e in events:
        if e['event'] == 'private_departure_requested':
            starts[e['vehicle_id']] = e['time_sec']
        elif e['event'] == 'walk_departure':
            starts[e['person_id']] = e['time_sec']
        elif e['event'] == 'actor_removed':
            ends[e['actor_id']] = e['time_sec']
            removal_times.add((e['actor_id'], e['time_sec']))
        elif e['event'] == 'walk_plan' and e['stage'] == 'reroute':
            reroute_times.add((e['person_id'], e['time_sec']))
    trips_list = [r.attrib for r in ET.parse(folder / 'tripinfo.xml').getroot().findall('tripinfo')]
    trips = {r['id']: r for r in trips_list}
    for vid, v in vehicles.items():
        if v['status'] == 'arrived':
            # Native vehicle tripinfo uses the start of its final movement step;
            # the controller receives its arrived ID after that step finishes.
            ends[vid] = float(trips[vid]['arrival'])
    for pid, p in people.items():
        if p['mode'] == 'walk' and p['arrival_sec'] != '':
            ends[pid] = float(p['arrival_sec']) - manifest['step_sec']
    errors, examples = Counter(), defaultdict(list)

    def fail(name, detail):
        errors[name] += 1
        if len(examples[name]) < 10:
            examples[name].append(detail)

    if len(trips) != len(trips_list) or set(trips) - set(vehicles):
        fail('backend_vkt', 'duplicate/unknown tripinfo vehicle')
    for vid, v in vehicles.items():
        if v['status'] == 'arrived':
            expected = float(trips[vid]['arrival']) + manifest['step_sec']
            if any(people[pid]['arrival_sec'] == '' or float(people[pid]['arrival_sec']) != expected for pid in crews[vid]):
                fail('actor_arrival_clock', [vid, 'native_final_step/controller_arrival'])
    hazard = {(r['edge_id'], r['mode']): float(r['closure_sec']) for r in rows(inputs / 'hazard.csv') if r['closure_sec'] != ''}
    person_states = {pid: 'not_ready' for pid in people}
    last_actor, last_vehicle, removal_observations = {}, {}, {}
    counts, states = Counter(), Counter()
    integral, distance, empty = defaultdict(float), defaultdict(float), defaultdict(float)
    ever_valid = set()
    cursor, last_time, frame_actors, frame_members, actor_rows = 0, -1, set(), set(), 0
    for row in stream_rows(folder / 'actor_observations.csv.gz'):
        actor_rows += 1
        now, actor, kind = float(row['time_sec']), row['actor_id'], row['kind']
        if not math.isfinite(now) or now <= 0 or now > manifest['end_sec'] or now % manifest['step_sec']:
            raise ValueError('Actor row outside step grid')
        if now < last_time:
            fail('actor_grid_completeness', [now, 'unordered'])
        if now != last_time:
            last_time, frame_actors, frame_members = now, set(), set()
            while cursor < len(events) and events[cursor]['time_sec'] < now:
                e = events[cursor]
                cursor += 1
                vid, pid = e.get('vehicle_id'), e.get('person_id')
                if e['event'] in ('private_departure_requested', 'private_reroute', 'drt_route', 'cancel_wait_route'):
                    routes[vid][e['route_version']] = e['route']
                if e['event'] == 'drt_route':
                    reentry_expected[vid] = e['reentry_expected']
                elif e['event'] == 'vehicle_reentry_observed':
                    reentry_expected[vid] = False
                if e['event'] == 'person_state':
                    person_states[pid] = e['after']
                if vid in vehicles:
                    if e['event'] == 'request_accepted':
                        active_person[vid] = pid
                    elif e['event'] == 'drt_boarded':
                        expected_members[vid] = {pid}
                    elif e['event'] in ('drt_alighted', 'request_cancelled'):
                        active_person[vid], expected_members[vid] = '', set()
        if actor in frame_actors or row['phase'] != 'after_step_before_control':
            fail('actor_phase_unique_membership', [now, actor, 'duplicate/phase'])
        frame_actors.add(actor)
        members = json.loads(row['members'])
        if len(set(members)) != len(members) or frame_members.intersection(members) or set(members) - people.keys():
            fail('actor_phase_unique_membership', [now, actor, 'overlapping/unknown_members'])
        frame_members.update(members)
        if actor not in starts or now < starts[actor] + manifest['step_sec'] or now > ends.get(actor, manifest['end_sec']):
            fail('actor_grid_completeness', [now, actor, 'outside_lifetime'])
        previous = last_actor.get(actor)
        if (actor, now) in removal_times:
            removal_observations[actor] = {key: row[key] for key in (
                'time_sec', 'road_id', 'observation_kind', 'reentry_source_edge', 'status')}
        if previous and now != float(previous['time_sec']) + manifest['step_sec']:
            fail('actor_grid_completeness', [now, actor, 'missing_step'])
        counts[actor] += 1
        state = row['observation_kind']
        states[state] += 1
        if state not in ('onroad', 'parked', 'departure_pending', 'reentry_pending'):
            fail('actor_observation_state', [now, actor, state])
        speed = float(row['speed_mps'])
        edge = row['road_id']
        if kind == 'walk':
            maximum = cfg['population']['walk_mps'][people[actor]['person_type']]
            if (members != [actor] or person_states[actor] != row['status'] or row['status'] != 'travelling_walk' or state != 'onroad'
                    or not math.isfinite(speed) or not 0 <= speed <= maximum + 1e-6):
                fail('actor_walk_integral_and_speed', [now, actor])
            integral[actor] += speed * manifest['step_sec']
            if previous and (actor, float(previous['time_sec'])) in reroute_times:
                displacement = math.dist((float(previous['x']), float(previous['y'])), (float(row['x']), float(row['y'])))
                if displacement > maximum * manifest['step_sec'] + 1e-7:
                    fail('reroute_position_continuity', [now, actor, displacement])
        elif actor in vehicles and kind == vehicles[actor]['kind']:
            if not math.isfinite(float(row['decel_mps2'])) or float(row['decel_mps2']) <= 0:
                fail('actor_observation_state', [now, actor, 'invalid_deceleration'])
            if set(members) != expected_members[actor] or row['active_person'] != active_person[actor]:
                fail('actor_phase_unique_membership', [now, actor, 'control_membership'])
            version = int(row['route_version'])
            path = routes[actor].get(version, [])
            if not path:
                fail('actor_route_index', [now, actor, 'unknown_version'])
            if state == 'departure_pending':
                if actor in ever_valid or version != 0:
                    fail('actor_observation_state', [now, actor, 'late_departure_pending'])
            else:
                if state == 'reentry_pending' and not reentry_expected[actor]:
                    fail('actor_observation_state', [now, actor, 'unexplained_reentry'])
                value = float(row['distance_m'])
                if math.isfinite(value) and value >= 0:
                    increment = value - distance[actor]
                    if increment < -1e-8:
                        fail('actor_vehicle_distances', [now, actor, 'odometer_decrease'])
                    distance[actor] = max(value, distance[actor])
                    if not members:
                        empty[actor] += max(0, increment)
                    last_vehicle[actor] = row
                elif state != 'reentry_pending':
                    fail('actor_vehicle_distances', [now, actor, 'invalid_odometer'])
                if state == 'onroad':
                    ever_valid.add(actor)
                    index = int(row['route_index'])
                    if not 0 <= index < len(path) or (not edge.startswith(':') and path[index] != edge):
                        fail('actor_route_index', [now, actor, version, index])
                    if not math.isfinite(speed) or speed < 0:
                        fail('actor_observation_state', [now, actor, 'invalid_onroad_speed'])
                if bool(int(row['stop_state']) & 2) != (state == 'parked'):
                    fail('actor_observation_state', [now, actor, 'parking_bit'])
        else:
            fail('actor_observation_state', [now, actor, 'unknown_kind_or_id'])
        if state == 'onroad' and not all(math.isfinite(float(row[field])) for field in ('x', 'y', 'lane_position_m')):
            fail('actor_observation_state', [now, actor, 'invalid_position'])
        physical = 'pedestrian' if kind == 'walk' else 'passenger'
        if edge and not edge.startswith(':') and now >= hazard.get((edge, physical), math.inf):
            fail('actor_closed_external_edge', [now, actor, edge])
        last_actor[actor] = row
    for actor, start in starts.items():
        expected = max(0, round((ends.get(actor, manifest['end_sec']) - start) / manifest['step_sec']))
        if counts[actor] != expected:
            fail('actor_grid_completeness', [actor, counts[actor], expected])
    for pid, p in people.items():
        if (not math.isclose(float(p['walk_speed_integral_m']), integral[pid], rel_tol=0, abs_tol=1e-7)
                or integral[pid] > cfg['population']['walk_limit_m'] + 1e-7):
            fail('actor_walk_integral_and_speed', pid)
    vkt = {}
    for vid, v in vehicles.items():
        if (not math.isclose(float(v['observed_distance_m']), distance[vid], rel_tol=0, abs_tol=1e-7)
                or not math.isclose(float(v['observed_empty_distance_m']), empty[vid], rel_tol=0, abs_tol=1e-7)):
            fail('actor_vehicle_distances', vid)
        if vid not in trips:
            if distance[vid] != 0 or v['distance_m'] != '':
                fail('backend_vkt', [vid, 'trip_missing'])
            continue
        trip, last = trips[vid], last_vehicle.get(vid)
        if last is None:
            fail('backend_vkt', [vid, 'no_distance_observation'])
            continue
        tail = 0
        if v['status'] == 'arrived':
            path = routes[vid][int(last['route_version'])]
            if last['road_id'] != path[-1] or int(last['route_index']) != len(path) - 1:
                fail('backend_vkt', [vid, 'arrival_tail_not_provable_on_final_edge'])
                continue
            tail = float(trip['arrivalPos']) - float(last['lane_position_m'])
            if tail < 0:
                fail('backend_vkt', [vid, 'negative_tail'])
        quanta = [float(Decimal(1).scaleb(Decimal(trip[k]).as_tuple().exponent)) for k in ('arrivalPos', 'routeLength')]
        tolerance = .5 * sum(quanta) + 1e-7
        residual = float(trip['routeLength']) - distance[vid] - tail
        vkt[vid] = {'arrival_tail_m': tail, 'residual_m': residual, 'rounding_bound_m': tolerance}
        if abs(residual) > tolerance or v['distance_m'] == '' or float(v['distance_m']) != float(trip['routeLength']):
            fail('backend_vkt', [vid, residual])
    if (states['departure_pending'] != manifest['summary']['counts']['departure_pending_frames']
            or states['reentry_pending'] != manifest['summary']['counts']['reentry_pending_frames']):
        fail('actor_observation_state', 'summary pending-frame mismatch')
    names = ('actor_grid_completeness', 'actor_arrival_clock', 'actor_phase_unique_membership', 'actor_observation_state',
             'actor_walk_integral_and_speed', 'actor_vehicle_distances', 'actor_route_index',
             'actor_closed_external_edge', 'reroute_position_continuity', 'backend_vkt')
    return {'status': 'PASS' if not errors else 'INVALID', 'checks': {k: not errors[k] for k in names},
            'errors': dict(errors), 'examples': dict(examples), 'actor_rows': actor_rows,
            'actor_count': len(counts), 'vkt': vkt, 'removal_observations': removal_observations,
            'core_adoption_permitted': False}


def audit_movement_events(folder, manifest, cfg, events):
    """Rebuild every external entry and walk-budget decision on the step grid.

    At each frame, observations precede control events. Route changes preserve
    their physical source anchor. Only one frame's transition multiset is held.
    Native walking-stage lengths are observations; the registered recurrence and
    independent speed integral are recomputed, never stage-length totals.
    """
    inputs = ROOT / manifest['input_directory']
    people = {r['person_id']: r for r in rows(folder / 'person_results.csv')}
    vehicles = {r['vehicle_id']: r for r in rows(folder / 'vehicle_results.csv')}
    source = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
    hazards = {(r['edge_id'], r['mode']): float(r['closure_sec']) for r in rows(inputs / 'hazard.csv') if r['closure_sec'] != ''}
    errors, examples = Counter(), defaultdict(list)

    def fail(name, detail):
        errors[name] += 1
        if len(examples[name]) < 10:
            examples[name].append(detail)

    routes = {vid: [source['depot_edge']] for vid, v in vehicles.items() if v['kind'] == 'drt'}
    arrivals = defaultdict(list)
    crews = defaultdict(list)
    for pid, p in people.items():
        if p['initial_mode'] == 'car':
            crews[p['vehicle_id']].append(pid)
        if p['mode'] == 'walk' and p['arrival_sec'] != '':
            arrivals[float(p['arrival_sec'])].append((pid, 'pedestrian'))
    for vid, v in vehicles.items():
        if v['status'] == 'arrived':
            arrivals[float(people[crews[vid][0]]['arrival_sec'])].append((vid, 'passenger'))
    by_time = defaultdict(list)
    for e in events:
        by_time[e['time_sec']].append(e)
    actor_iterator = iter(stream_rows(folder / 'actor_observations.csv.gz'))
    transition_iterator = iter(stream_rows(folder / 'transitions.csv.gz'))
    actor_row = next(actor_iterator, None)
    transition_row = next(transition_iterator, None)
    anchors, latest = {}, {}
    plan, passed, speed_integral, budget_lead = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    active_walk, started_walk = set(), set()
    total_expected = total_actual = closed_entries = ambiguous = 0
    keys = ('time_lower_sec', 'time_upper_sec', 'actor_id', 'mode', 'from_edge', 'to_edge', 'kind', 'closure_sec', 'ambiguous')

    def transition_key(row):
        return tuple(float(row[k]) if k in ('time_lower_sec', 'time_upper_sec') else
                     float(row[k]) if k == 'closure_sec' and row[k] != '' else str(row[k]) for k in keys)

    def visit(actor, mode, edge, index, now, expected):
        path = routes.get(actor, [])
        if not 0 <= index < len(path) or path[index] != edge:
            fail('transition_route_reconstruction', [actor, now, edge, index])
            return
        previous = anchors.get(actor)
        if previous:
            old_edge, old_time, old_index = previous
            if edge != old_edge or index > old_index:
                if index <= old_index or old_index >= len(path) or path[old_index] != old_edge:
                    fail('transition_route_reconstruction', [actor, now, 'backward/unknown_anchor'])
                else:
                    for target in path[old_index + 1:index + 1]:
                        native = hazards.get((target, mode))
                        violation = native is not None and now >= native
                        expected.append(transition_key({'time_lower_sec': old_time, 'time_upper_sec': now,
                            'actor_id': actor, 'mode': mode, 'from_edge': old_edge, 'to_edge': target,
                            'kind': 'closed_entry' if violation else 'transition',
                            'closure_sec': '' if native is None else native, 'ambiguous': False}))
        anchors[actor] = edge, now, index

    dt, limit = manifest['step_sec'], cfg['population']['walk_limit_m']
    for tick in range(int(manifest['end_sec'] / dt) + 1):
        now = tick * dt
        expected, actual = [], []
        while actor_row is not None and float(actor_row['time_sec']) == now:
            row = actor_row
            actor_row = next(actor_iterator, None)
            actor, kind, edge = row['actor_id'], row['kind'], row['road_id']
            latest[actor] = row
            if kind == 'walk':
                speed_integral[actor] += float(row['speed_mps']) * dt
            if edge and not edge.startswith(':') and row['observation_kind'] != 'departure_pending':
                mode = 'pedestrian' if kind == 'walk' else 'passenger'
                path = routes.get(actor, [])
                if mode == 'pedestrian' and (len(path) != len(set(path)) or edge not in path):
                    fail('transition_route_reconstruction', [actor, now, 'ambiguous_walk_edge'])
                else:
                    index = path.index(edge) if mode == 'pedestrian' else int(row['route_index'])
                    visit(actor, mode, edge, index, now, expected)
        # Arrived actors no longer have a subscription row. Their final edge is
        # reconstructed from the still-active route before current control edits.
        for actor, mode in arrivals[now]:
            path = routes.get(actor, [])
            if not path:
                fail('transition_route_reconstruction', [actor, now, 'arrival_without_route'])
            else:
                visit(actor, mode, path[-1], len(path) - 1, now, expected)
            anchors.pop(actor, None)
            if mode == 'pedestrian':
                passed[actor] += plan[actor]
                plan[actor] = 0
                active_walk.discard(actor)
        while transition_row is not None and float(transition_row['time_upper_sec']) == now:
            row = transition_row
            transition_row = next(transition_iterator, None)
            actual.append(transition_key(row))
            native = hazards.get((row['to_edge'], row['mode']), math.inf)
            closed_entries += int(now >= native)
            ambiguous += int(row['ambiguous'] != 'False')
        if Counter(expected) != Counter(actual):
            fail('all_entries_primary_multiset', {'at': now, 'missing': list((Counter(expected) - Counter(actual)).elements())[:5],
                                                'extra': list((Counter(actual) - Counter(expected)).elements())[:5]})
        total_expected += len(expected)
        total_actual += len(actual)
        tick_events = by_time[now]
        budget_stops, over_budget_plans = set(), set()
        for e in tick_events:
            event, pid, vid = e['event'], e.get('person_id'), e.get('vehicle_id')
            if event == 'walk_plan':
                length = e['sumo_plan_length_m']
                if not math.isfinite(length) or length < 0 or not math.isclose(e['speed_integral_m'], speed_integral[pid], rel_tol=0, abs_tol=1e-7):
                    fail('walk_stage_budget_recurrence', [pid, now, 'length/integral'])
                if e['stage'] == 'initial':
                    if plan[pid] != 0 or passed[pid] != 0 or e['model_passed_m'] != 0:
                        fail('walk_stage_budget_recurrence', [pid, now, 'restarted_initial_plan'])
                elif e['stage'] == 'reroute':
                    row = latest.get(pid)
                    signed = plan[pid] - e['old_remaining_m']
                    if (not math.isclose(e['previous_plan_m'], plan[pid], rel_tol=0, abs_tol=1e-7)
                            or not math.isfinite(e['old_remaining_m']) or e['old_remaining_m'] < 0
                            or not math.isclose(e['signed_progress_m'], signed, rel_tol=0, abs_tol=1e-7)
                            or not row or float(row['time_sec']) != now
                            or abs(e['depart_pos'] - float(row['lane_position_m'])) > 1e-7
                            or e['route'][0] != row['road_id']):
                        fail('walk_stage_budget_recurrence', [pid, now, 'native_remaining/source'])
                    passed[pid] += max(0, signed)
                    maximum = cfg['population']['walk_mps'][people[pid]['person_type']]
                    if (e['enforced_stage_speed_mps'] != maximum or e['person_max_mps'] != maximum
                            or not math.isclose(e['model_passed_m'], passed[pid], rel_tol=0, abs_tol=1e-7)):
                        fail('walk_stage_budget_recurrence', [pid, now, 'passed/speed'])
                else:
                    fail('walk_stage_budget_recurrence', [pid, now, 'unknown_stage'])
                plan[pid] = length
                if max(passed[pid], speed_integral[pid]) + length > limit:
                    over_budget_plans.add(pid)
            elif event == 'walk_departure':
                if pid in started_walk or e['length_m'] != plan[pid] or plan[pid] > limit:
                    fail('walk_stage_budget_recurrence', [pid, now, 'invalid_departure'])
                started_walk.add(pid)
                active_walk.add(pid)
                routes[pid] = e['route']
            elif event == 'walk_reroute':
                if pid in over_budget_plans or max(passed[pid], speed_integral[pid]) + plan[pid] > limit:
                    fail('walk_stage_budget_recurrence', [pid, now, 'over_budget_reroute'])
                routes[pid] = e['route']
                anchors[pid] = e['route'][0], now, 0
            elif event == 'walk_budget_pre_step_stop':
                maximum = cfg['population']['walk_mps'][people[pid]['person_type']] * dt
                spent = max(passed[pid], speed_integral[pid])
                if (pid not in active_walk or e['spent_m'] != spent or e['max_next_step_m'] != maximum
                        or not 0 <= e['remaining_budget_m'] < maximum
                        or not math.isclose(e['remaining_budget_m'] + spent, limit, rel_tol=0, abs_tol=1e-7)):
                    fail('walk_pre_step_budget_stop', [pid, now])
                budget_stops.add(pid)
                budget_lead[pid] = e['remaining_budget_m']
            elif event == 'private_departure_requested':
                routes[vid] = e['route']
            elif event in ('private_reroute', 'drt_route', 'cancel_wait_route'):
                route, remaining = e['route'], e['requested_remaining_route']
                index = len(route) - len(remaining)
                row = latest.get(vid)
                if (index < 0 or route[index:] != remaining or not remaining or e['source_edge'] != remaining[0]
                        or not row or float(row['time_sec']) != now or row['road_id'] != e['source_edge']
                        or abs(float(row['lane_position_m']) - e['source_lane_position']) > 1e-7):
                    fail('route_change_source_continuity', [vid, now])
                routes[vid] = route
                anchors[vid] = remaining[0], now, index
            elif event == 'actor_removed':
                actor = e['actor_id']
                anchors.pop(actor, None)
                if e['mode'] == 'pedestrian':
                    if e['reason'] == 'walk_limit' and actor not in over_budget_plans | budget_stops:
                        fail('walk_pre_step_budget_stop', [actor, now, 'unexplained_limit_stop'])
                    active_walk.discard(actor)
        for pid in over_budget_plans:
            # The initial over-budget stage is removed before walking departure;
            # a replacement stage has an explicit actor_removed event.
            if pid in active_walk:
                fail('walk_stage_budget_recurrence', [pid, now, 'over_budget_actor_left_active'])
        if now < manifest['end_sec']:
            for pid in active_walk:
                maximum = cfg['population']['walk_mps'][people[pid]['person_type']] * dt
                if max(passed[pid], speed_integral[pid]) + maximum > limit:
                    fail('walk_pre_step_budget_stop', [pid, now, 'required_stop_missing'])
    if actor_row is not None or transition_row is not None:
        fail('all_entries_primary_multiset', 'unordered/off-grid/trailing rows')
    for pid, p in people.items():
        # An initial rejected plan never becomes the person's active plan.
        expected_plan = plan[pid] if pid in started_walk else 0
        if (not math.isclose(float(p['walk_model_passed_m']), passed[pid], rel_tol=0, abs_tol=1e-7)
                or not math.isclose(float(p['walk_plan_length_m']), expected_plan, rel_tol=0, abs_tol=1e-7)
                or not math.isclose(float(p['walk_budget_lead_m']), budget_lead[pid], rel_tol=0, abs_tol=1e-7)):
            fail('walk_stage_budget_recurrence', [pid, 'final_distance_fields'])
    counts = manifest['summary']['counts']
    if (total_actual != counts['transition_rows'] or closed_entries != counts['closed_entry_rows']
            or ambiguous != counts['ambiguous_transitions'] or closed_entries or ambiguous):
        fail('no_closed_or_ambiguous_entries', [total_actual, closed_entries, ambiguous])
    names = ('transition_route_reconstruction', 'all_entries_primary_multiset', 'route_change_source_continuity',
             'walk_stage_budget_recurrence', 'walk_pre_step_budget_stop', 'no_closed_or_ambiguous_entries')
    return {'status': 'PASS' if not errors else 'INVALID', 'checks': {k: not errors[k] for k in names},
            'errors': dict(errors), 'examples': dict(examples), 'expected_transition_rows': total_expected,
            'actual_transition_rows': total_actual, 'walkers': len(started_walk), 'core_adoption_permitted': False}


def audit_fixture_timing(folder, manifest, cfg, events):
    """Independently check native-derived artificial boundary inputs and branches."""
    if manifest['purpose'] != 'fixture':
        return {'status': 'PASS', 'applicable': False, 'core_adoption_permitted': False}
    inputs = ROOT / manifest['input_directory']
    source = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
    case = source['fixture_case']
    roles = {'pickup_deadline_equal', 'pickup_before_deadline', 'pickup_internal_calibration',
             'pickup_internal_timeout', 'pickup_internal_timeout_closed_next'}
    if case not in roles:
        return {'status': 'PASS', 'applicable': False, 'core_adoption_permitted': False}
    checks = {}
    requests = rows(folder / 'request_results.csv')
    if len(requests) != 1:
        raise ValueError('Native boundary fixture must have exactly one request')
    q = requests[0]

    def windows(directory, request):
        # Reverse scan is independent of the generator's forward suffix search.
        observations = [r for r in stream_rows(directory / 'actor_observations.csv.gz')
                        if r['actor_id'] == request['vehicle_id'] and r['status'] == 'pickup'
                        and float(r['time_sec']) >= float(request['accepted_sec'])]
        result, external = [], None
        for row in reversed(observations):
            at = float(row['time_sec'])
            if row['road_id'] and not row['road_id'].startswith(':'):
                external = row
            elif (row['road_id'].startswith(':') and at % cfg['simulation']['controller_sec'] == 0
                  and external is not None and float(external['time_sec']) - at >= 2 * manifest['step_sec']):
                result.append({'deadline_sec': at, 'internal_edge': row['road_id'],
                               'next_external_edge': external['road_id'],
                               'next_external_native_sec': float(external['time_sec'])})
        return list(reversed(result))

    if case == 'pickup_internal_calibration':
        checks['calibration_physically_served'] = q['status'] == 'served'
        checks['native_internal_integer_window_present'] = bool(windows(folder, q))
    else:
        timing = source['native_timing_reference']
        reference_id = timing['reference_run_id']
        if (reference_id.rsplit('_c', 1)[0] != manifest['run_id'].rsplit('_c', 1)[0]
                or not re.fullmatch(r'[a-zA-Z0-9_-]+_c[0-9]{2}', reference_id)):
            raise ValueError('Timing reference is not a prior sibling technical run')
        reference = ROOT / cfg['workspace'] / 'technical' / reference_id / 'execution'
        rm = json.loads((reference / 'manifest.json').read_text(encoding='utf-8'))
        rq = rows(reference / 'request_results.csv')
        expected_paths = [reference / name for name in ('manifest.json', 'request_results.csv', 'actor_observations.csv.gz')]
        expected_sources = {p.relative_to(ROOT).as_posix(): file_sha(p) for p in expected_paths}
        checks['timing_reference_primary_bytes'] = (timing['source_sha256'] == expected_sources
            and all(source['source_sha256'].get(k) == v for k, v in expected_sources.items())
            and all(rm['output_sha256'][p.name] == expected_sources[p.relative_to(ROOT).as_posix()] for p in expected_paths[1:])
            and rm['status'] == 'COMPLETED' and rm['purpose'] == 'fixture' and len(rq) == 1
            and int(reference_id.rsplit('_c', 1)[1]) < int(manifest['run_id'].rsplit('_c', 1)[1]))
        r = rq[0]
        checks['native_boarding_reference'] = (r['status'] == 'served'
            and timing['native_boarding_started_sec'] == float(r['boarding_started_sec'])
            and timing['native_accepted_sec'] == float(r['accepted_sec']))
        if case.startswith('pickup_internal'):
            eligible = windows(reference, r)
            checks['native_internal_reference'] = (rm['fixture_case'] == 'pickup_internal_calibration'
                and bool(eligible) and timing['internal_windows'] == eligible
                and timing['selected_internal_window'] == eligible[0])
            selected = eligible[0]
            deadline = selected['deadline_sec']
            prior_inputs = ROOT / rm['input_directory']
            before = json.loads((prior_inputs / 'graphs.json').read_text(encoding='utf-8'))['passenger']
            after = json.loads((inputs / 'graphs.json').read_text(encoding='utf-8'))['passenger']
            scale = timing['technical_free_time_scale']
            checks['explicit_artificial_underprediction_same_geometry'] = (0 < scale < 1
                and ET.tostring(ET.parse(prior_inputs / 'bounded.net.xml').getroot()) == ET.tostring(ET.parse(inputs / 'bounded.net.xml').getroot())
                and set(before['nodes']) == set(after['nodes'])
                and {(a, b) for a, b, _ in before['edges']} == {(a, b) for a, b, _ in after['edges']}
                and all(after['nodes'][n]['length'] == attr['length']
                        and after['nodes'][n]['free_sec'] == attr['free_sec'] * scale for n, attr in before['nodes'].items()))
            at_deadline = [p for p in stream_rows(folder / 'actor_observations.csv.gz')
                           if p['actor_id'] == q['vehicle_id'] and float(p['time_sec']) == deadline]
            checks['actual_internal_at_cancel'] = len(at_deadline) == 1 and at_deadline[0]['road_id'] == selected['internal_edge']
            if case == 'pickup_internal_timeout':
                checks['safe_external_wait_after_internal_cancel'] = any(e['event'] == 'cancel_wait_route'
                    and e['vehicle_id'] == q['vehicle_id'] and e['time_sec'] > deadline
                    and e['source_edge'] == selected['next_external_edge'] for e in events)
            else:
                native = math.floor(selected['next_external_native_sec'])
                hazard = rows(inputs / 'hazard.csv')
                checks['next_external_closure_and_removal'] = (any(p['edge_id'] == selected['next_external_edge']
                    and p['mode'] == 'passenger' and p['closure_sec'] != '' and float(p['closure_sec']) == native for p in hazard)
                    and any(e['event'] == 'actor_removed' and e['actor_id'] == q['vehicle_id']
                            and deadline < e['time_sec'] == max(0, native - manifest['step_sec']) for e in events))
        else:
            deadline = float(r['boarding_started_sec']) + (cfg['simulation']['controller_sec'] if case == 'pickup_before_deadline' else 0)
            checks['same_straight_pickup_reference'] = rm['fixture_case'] == 'forecast_r1'
        checks['derived_deadline_registered_only_in_fixture'] = (timing['derived_deadline_sec'] == deadline
            and cfg['request_policy']['max_unboarded_wait_sec'] == deadline and float(q['deadline_sec']) == deadline)
        if case == 'pickup_before_deadline':
            checks['boarding_strictly_before_then_continues'] = (q['status'] == 'served'
                and float(q['boarding_started_sec']) == float(r['boarding_started_sec']) < deadline < float(q['boarded_sec'])
                and not any(e['event'] == 'fallback_attempt' for e in events))
        else:
            checks['accepted_timeout_before_boarding_once_fallback'] = (q['status'] == 'cancelled_timeout'
                and q['accepted_sec'] != '' and float(q['accepted_sec']) < float(q['cancel_sec']) == deadline
                and q['boarding_started_sec'] == '' and sum(e['event'] == 'fallback_attempt' for e in events) == 1)
    return {'status': 'PASS' if all(checks.values()) else 'INVALID', 'applicable': True,
            'case': case, 'checks': checks, 'core_adoption_permitted': False}


def audit_native_logs(folder, manifest, events, actor_report):
    """Classify raw native diagnostics by closure/removal evidence, not fixture name."""
    inputs = ROOT / manifest['input_directory']
    hazard = {(r['edge_id'], r['mode']): float(r['closure_sec']) for r in rows(inputs / 'hazard.csv') if r['closure_sec'] != ''}
    removed = {e['actor_id']: e for e in events if e['event'] == 'actor_removed' and e['mode'] == 'passenger'}
    receipts = actor_report['removal_observations']
    errors, warnings, classified, unclassified = [], [], [], []
    text = (folder / 'sumo_errors.log').read_text(encoding='utf-8')
    used = set()
    for line in text.splitlines():
        if line.startswith('Error:'):
            errors.append(line)
        elif line.startswith('Warning:'):
            warnings.append(line)
            skip = re.fullmatch(r"Warning: Vehicle '([^']+)' skips stop on lane '([^']+)' time=([0-9]+(?:\.[0-9]+)?)\.", line)
            abort = re.fullmatch(r"Warning: Vehicle '([^']+)' aborts stop\.", line)
            actor = skip[1] if skip else abort[1] if abort else None
            event, raw = removed.get(actor), receipts.get(actor)
            valid = event is not None and raw is not None and actor not in used
            if valid:
                at = event['time_sec']
                edge = skip[2].rsplit('_', 1)[0] if skip else raw['road_id'] or raw['reentry_source_edge']
                native = hazard.get((edge, 'passenger'), math.inf)
                valid &= (float(raw['time_sec']) == at and max(0, native - manifest['step_sec']) <= at
                          and event['reason'] in ('initial_or_current_closed', 'route_cut', 'stranded_drt'))
                if skip:
                    valid &= float(skip[3]) == at
                else:
                    valid &= raw['status'] in ('boarding', 'alighting')
            if valid:
                classified.append({'raw': line, 'actor': actor, 'closure_native_sec': native,
                                   'removal_control_sec': event['time_sec'], 'evidence': raw})
                used.add(actor)
            else:
                unclassified.append(line)
        elif line.strip():
            unclassified.append(line)
    lowered = text.lower()
    observed_bad = [e for e in events if e['event'] in ('teleport_started', 'collision_observed')]
    counts = manifest['summary']['counts']
    summary = manifest['summary']['sumo_errors']
    checks = {'no_native_errors': not errors, 'all_warnings_evidence_classified': not unclassified,
              'no_teleports_or_collisions': not observed_bad and 'teleport' not in lowered and 'collision' not in lowered
                 and counts['teleports'] == counts['collisions'] == 0,
              'no_subscription_missing': counts['missing_vehicle_subscriptions'] == counts['missing_person_subscriptions'] == 0,
              'native_summary_recomputed': summary == {
                  'bytes': (folder / 'sumo_errors.log').stat().st_size, 'warning_count': len(warnings),
                  'error_count': len(errors), 'handled_route_rejection_count': 0,
                  'unhandled_error_count': len(errors), 'collision_teleport_count': 0, 'gridlock_teleport_count': 0}}
    return {'status': 'PASS' if all(checks.values()) else 'INVALID', 'checks': checks,
            'classified_warnings': classified, 'unknown': unclassified, 'errors': errors,
            'core_adoption_permitted': False}


def audit_road_snapshots(folder, manifest, cfg):
    """Sparse actor aggregates plus a dense boolean grid, not millions of dict rows."""
    inputs = ROOT / manifest['input_directory']
    graph = json.loads((inputs / 'graphs.json').read_text(encoding='utf-8'))
    pairs = [(kind, edge) for kind, mode in [('car', 'passenger'), ('drt', 'passenger'), ('walk', 'pedestrian')]
             for edge in sorted(graph[mode]['nodes'])]
    pair_index = {pair: i for i, pair in enumerate(pairs)}
    frames = int(manifest['end_sec'] // manifest['snapshot_sec']) + 1
    seen = np.zeros((frames, len(pairs)), dtype=bool)
    errors, examples = Counter(), defaultdict(list)

    def fail(name, detail):
        errors[name] += 1
        if len(examples[name]) < 10:
            examples[name].append(detail)

    def frame_number(at):
        if not math.isfinite(at) or not 0 <= at <= manifest['end_sec'] or at % manifest['snapshot_sec']:
            raise ValueError('Snapshot timestamp outside registered grid')
        return int(at // manifest['snapshot_sec'])

    # count, sum, raw halt, invalid raw, traffic count/sum/halt, parked, reentry, unplaced
    aggregates = defaultdict(lambda: [0, 0., 0, 0, 0, 0., 0, 0, 0, 0])
    actor_rows, last_time, actor_ids = 0, -1, set()
    stop_speed = cfg['simulation']['stop_speed_mps']
    for row in stream_rows(folder / 'snapshot_actor_observations.csv.gz'):
        actor_rows += 1
        at, actor = float(row['time_sec']), row['actor_id']
        frame = frame_number(at)
        if at < last_time:
            fail('snapshot_actor_identity_phase', ['unordered', at])
        if at != last_time:
            actor_ids, last_time = set(), at
        if actor in actor_ids or row['phase'] != 'after_control_before_step':
            fail('snapshot_actor_identity_phase', [at, actor])
        actor_ids.add(actor)
        kind, edge, state = row['kind'], row['road_id'], row['observation_kind']
        speed = float(row['speed_mps'])
        if kind not in ('car', 'drt', 'walk') or state not in ('onroad', 'parked', 'reentry_pending'):
            fail('snapshot_actor_states', [at, actor, state])
        if kind == 'walk' and (state != 'onroad' or not math.isfinite(speed) or speed < 0):
            fail('snapshot_actor_states', [at, actor, 'invalid_walk'])
        if kind != 'walk' and bool(int(row['stop_state']) & 2) != (state == 'parked'):
            fail('snapshot_actor_states', [at, actor, 'parking_bit'])
        if (kind, edge) in pair_index:
            values = aggregates[frame, pair_index[kind, edge]]
            valid = math.isfinite(speed) and speed >= 0
            values[0] += 1
            values[1] += speed if valid else 0
            values[2] += int(valid and speed < stop_speed)
            values[3] += int(not valid)
            if state == 'onroad':
                if not valid:
                    fail('snapshot_actor_states', [at, actor, 'invalid_traffic_speed'])
                values[4] += 1
                values[5] += speed if valid else 0
                values[6] += int(speed < stop_speed)
            elif state == 'parked':
                values[7] += 1
            elif state == 'reentry_pending':
                values[8] += 1
            if kind != 'walk' and row['native_edge_contains_vehicle'] != str(state == 'onroad'):
                fail('native_edge_membership', [at, actor])
        elif state == 'reentry_pending':
            source = kind, row['reentry_source_edge']
            if source not in pair_index:
                fail('snapshot_actor_states', [at, actor, 'unknown_reentry_source'])
            else:
                aggregates[frame, pair_index[source]][9] += 1
        elif not edge.startswith(':'):
            fail('snapshot_actor_states', [at, actor, 'unknown_external_edge'])
    hazards = {(r['edge_id'], r['mode']): float(r['closure_sec']) for r in rows(inputs / 'hazard.csv') if r['closure_sec'] != ''}
    road_rows = 0
    zero = [0] * 10
    for row in stream_rows(folder / 'edge_observations.csv.gz'):
        road_rows += 1
        at = float(row['time_sec'])
        frame = frame_number(at)
        pair = row['mode'], row['edge_id']
        if pair not in pair_index:
            fail('full_road_grid', [at, *pair, 'unknown'])
            continue
        index = pair_index[pair]
        if seen[frame, index]:
            fail('full_road_grid', [at, *pair, 'duplicate'])
        seen[frame, index] = True
        values = aggregates.get((frame, index), zero)
        fields = [('count', 0), ('halting_count', 2), ('traffic_count', 4), ('traffic_halting_count', 6),
                  ('parked_count', 7), ('reentry_pending_count', 8), ('unplaced_reentry_count', 9)]
        valid = all(int(row[field]) == values[i] for field, i in fields)
        for field, value in [('mean_speed_mps', values[1] / values[0] if values[0] and not values[3] else None),
                             ('traffic_mean_speed_mps', values[5] / values[4] if values[4] else None)]:
            valid &= (row[field] == '' if value is None else row[field] != '' and
                      math.isclose(float(row[field]), value, rel_tol=0, abs_tol=1e-9))
        physical = 'pedestrian' if pair[0] == 'walk' else 'passenger'
        closure = hazards.get((pair[1], physical), math.inf)
        valid &= (row['closed'] == str(max(0, closure - manifest['step_sec']) <= at)
                  and row['observation_status'] == ('partial_reentry_speed' if values[3] else 'observed'))
        if not valid:
            fail('snapshot_primary_reaggregation', [at, *pair])
    if road_rows != seen.size or not seen.all():
        fail('full_road_grid', ['expected', int(seen.size), 'actual', road_rows, 'missing', int(seen.size - seen.sum())])
    if actor_rows != manifest['summary']['counts']['snapshot_actor_rows']:
        fail('snapshot_actor_identity_phase', 'summary actor row count')
    names = ('snapshot_actor_identity_phase', 'snapshot_actor_states', 'native_edge_membership',
             'full_road_grid', 'snapshot_primary_reaggregation')
    return {'status': 'PASS' if not errors else 'INVALID', 'checks': {k: not errors[k] for k in names},
            'errors': dict(errors), 'examples': dict(examples), 'snapshot_actor_rows': actor_rows,
            'road_rows': road_rows, 'grid_bytes': seen.nbytes, 'sparse_occupied_keys': len(aggregates),
            'core_adoption_permitted': False}


def audit_run_tables(run_id, purpose='core', require_current=True):
    """Partial integration entrypoint. Never authorizes core adoption or READY.

    Historical mode is restricted to technical runs. It verifies their original
    archives but explicitly does not claim they match the current implementation.
    """
    canonical = json.loads(PARAM.read_text(encoding='utf-8'))
    if purpose not in ('core', 'smoke', 'fixture') or Path(run_id).name != run_id or run_id in ('', '.', '..'):
        raise ValueError('Invalid purpose/run ID')
    if purpose == 'core' and not require_current:
        raise ValueError('Historical diagnostics cannot validate research core')
    workspace = ROOT / canonical['workspace']
    folder = (workspace / 'technical' / run_id / 'execution' if purpose == 'fixture' else
              workspace / ('runs' if purpose == 'core' else 'smoke') / run_id)
    checks, components, fingerprints = {}, {}, {}
    report = {'run_id': run_id, 'purpose': purpose, 'scope': 'partial_run_tables_not_formal_acceptance',
              'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'core_adoption_permitted': False, 'technical_ready': False,
              'historical_diagnostic': not require_current, 'validator_sha256': file_sha(Path(__file__)),
              'verifier_dependencies': verifier_dependencies(),
              'pending': ['formal_adoption_and_preflight_transaction', 'current_complete_suite_and_all14_smokes']}
    try:
        manifest_path = folder / 'manifest.json'
        fingerprints[manifest_path] = file_sha(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        parameter = ROOT / manifest['parameter_path']
        cfg = json.loads(parameter.read_text(encoding='utf-8'))
        inputs = ROOT / manifest['input_directory']
        source = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
        fingerprints[parameter] = manifest['parameter_sha256']
        fingerprints[inputs / 'manifest.json'] = manifest['input_manifest_sha256']
        checks['terminal_completed_identity'] = (manifest['status'] == 'COMPLETED'
            and manifest['run_id'] == run_id and manifest['purpose'] == purpose
            and 'error' not in manifest and 'connection_close_error' not in manifest)
        checks['protocol_config_input_identity'] = (
            cfg['protocol'] == source['protocol'] == manifest['protocol']
            and cfg['workspace'] == canonical['workspace']
            and manifest['execution_contract'] == cfg['execution'] == canonical['execution'])
        if purpose == 'fixture':
            checks['isolated_technical_fixture'] = (inputs == workspace / 'technical' / run_id / 'fixture_inputs'
                and parameter == inputs / 'fixture_parameters.json'
                and manifest['protocol'] == 'realtime_choice_fixture_v1'
                and source['research_adoption_permitted'] is manifest['research_adoption_permitted'] is False)
        else:
            checks['registered_config_and_input'] = (parameter == PARAM
                and inputs == workspace / canonical['input_directory']
                and manifest['protocol'] == canonical['protocol'])
        cells = [c for c in cfg['cells'] if c['cell_id'] == manifest['cell_id']]
        checks['registered_cell'] = len(cells) == 1 and all(manifest[k] == value for k, value in cells[0].items())
        checks['registered_clocks'] = (manifest['step_sec'] == cfg['simulation']['step_sec']
            and manifest['snapshot_sec'] == cfg['simulation']['snapshot_sec']
            and manifest['end_sec'] > 0 and manifest['end_sec'] % manifest['step_sec'] == 0
            and (purpose == 'smoke' or manifest['end_sec'] == cfg['simulation']['duration_sec']))
        required = {'actor_observations.csv.gz', 'candidates.csv.gz', 'common_realization.csv',
                    'dispatch_cycles.csv.gz', 'edge_observations.csv.gz', 'events.jsonl',
                    'facility_results.csv', 'person_results.csv', 'progress.json', 'request_results.csv',
                    'snapshot_actor_observations.csv.gz', 'sumo.log', 'sumo_errors.log',
                    'transitions.csv.gz', 'tripinfo.xml', 'types.rou.xml', 'vehicle_results.csv'}
        checks['complete_output_file_set'] = (set(manifest['output_sha256']) == required
            and {p.name for p in folder.iterdir() if p.is_file()} == required | {'manifest.json'})
        for name, expected in manifest['output_sha256'].items():
            if Path(name).name != name:
                raise ValueError('Output name escapes run directory')
            fingerprints[folder / name] = expected
        checks['common_implementation_set'] = (set(manifest['implementation_sha256'])
            == set(manifest['implementation_archive_sha256']) == set(canonical['execution']['implementation_files']))
        for name, expected in manifest['implementation_sha256'].items():
            fingerprints[folder / 'implementation' / name] = expected
            if require_current:
                fingerprints[ROOT / name] = expected
        checks['implementation_archives_match_manifest'] = manifest['implementation_archive_sha256'] == manifest['implementation_sha256']
        for name, expected in source['source_sha256'].items():
            original = ROOT / name
            # The suite archives its exact factory before generating any case.
            # Historical diagnostics may read that byte-identical source only;
            # current/READY and all research sources still require current bytes.
            if (not require_current and purpose == 'fixture'
                    and name == '04_プログラム/scripts/jdrt_choice_fixtures.py'
                    and file_sha(original) != expected):
                parent = re.fullmatch(r'(.+)_c[0-9]{2}', run_id)
                archived = workspace / 'technical' / parent[1] / 'factory.py' if parent else None
                if archived is not None and archived.is_file() and file_sha(archived) == expected:
                    fingerprints[archived] = expected
                    report.setdefault('historical_source_archives', {})[name] = archived.relative_to(ROOT).as_posix()
                    continue
            fingerprints[original] = expected
        for name, expected in source['artifacts'].items():
            if not (inputs / name).resolve().is_relative_to(inputs.resolve()):
                raise ValueError('Input artifact escapes registered directory')
            fingerprints[inputs / name] = expected
        checks['all_bound_bytes_before'] = all(file_sha(p) == expected for p, expected in fingerprints.items())
        if require_current:
            # Location helpers only: no runtime decision function is imported.
            from scripts.jdrt.smoke import resolve_sumo_binary, load_traci
            binary = resolve_sumo_binary()
            traci = load_traci(binary)
            runtime = {'sumo_binary': file_sha(binary), 'traci_init': file_sha(Path(traci.__file__)),
                       'traci_vehicle': file_sha(Path(traci.__file__).parent / '_vehicle.py'),
                       'shared_smoke': file_sha(ROOT / '04_プログラム/scripts/jdrt/smoke.py'),
                       'shared_log_parser': file_sha(ROOT / '04_プログラム/scripts/jdrt/full_run.py')}
            checks['current_runtime_bytes'] = runtime == manifest['runtime_sha256']
        if not all(checks.values()):
            report['status'] = 'INVALID'
        else:
            events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
            components['person_tables'] = audit_person_tables(folder, manifest, cfg, events)
            components['candidate_tables'] = audit_candidates(folder, manifest, cfg, events)
            components['road_snapshots'] = audit_road_snapshots(folder, manifest, cfg)
            components['actor_stream'] = audit_actor_stream(folder, manifest, cfg, events)
            components['movement_events'] = audit_movement_events(folder, manifest, cfg, events)
            components['native_logs'] = audit_native_logs(folder, manifest, events, components['actor_stream'])
            components['native_fixture_boundaries'] = audit_fixture_timing(folder, manifest, cfg, events)
            checks['all_bound_bytes_after'] = all(file_sha(p) == expected for p, expected in fingerprints.items())
            report['status'] = ('INCOMPLETE' if all(checks.values())
                                and all(c['status'] == 'PASS' for c in components.values()) else 'INVALID')
    except (OSError, ValueError, KeyError, TypeError, IndexError, ET.ParseError) as error:
        report.update(status='INVALID', error_type=type(error).__name__, error=str(error))
    report.update(checks=checks, components=components, bound_files=len(fingerprints))
    target = workspace / 'validation_reports'
    target.mkdir(exist_ok=True)
    # Each invocation is preserved; reports never enter or rewrite an old run.
    name = 'tables_' + run_id + '_' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.json'
    with (target / name).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return report


def validate_choice_tables():
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    parent = ROOT / params['parent_input_manifest']
    prior = json.loads(parent.read_text(encoding='utf-8'))
    checks = {}
    checks['all_sources_current'] = all(file_sha(ROOT / path) == expected
                                       for path, expected in manifest['source_sha256'].items())
    checks['all_artifacts_current'] = all(file_sha(directory / path) == expected
                                         for path, expected in manifest['artifacts'].items())
    checks['physical_copy_exact'] = all(file_sha(directory / path) == expected
                                       for path, expected in prior['artifacts'].items())
    checks['lineage'] = (manifest['lineage']['parent_manifest_sha256'] == file_sha(parent)
                         and manifest['protocol'] == params['protocol'])
    checks['d0_byte_identical'] = file_sha(directory / 'destinations_fixed_reference.csv') == prior['artifacts']['origins.csv']
    raw = json.loads((directory / 'graphs.json').read_text(encoding='utf-8'))
    hazards = rows(directory / 'hazard.csv')
    graphs = {}
    for mode, data in raw.items():
        g = nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from(data['nodes'].items())
        g.add_edges_from(data['edges'])
        g.remove_nodes_from(row['edge_id'] for row in hazards
                            if row['mode'] == mode and row['closure_sec'] == '0')
        graphs[mode] = g
    origins = rows(directory / 'origins.csv')
    terms = {row['terminal_id']: row for row in rows(directory / 'terminals.csv')}
    derived = rows(directory / 'destinations_facility_first.csv')
    checks['d1_origins_exact'] = (len(derived) == len(origins)
                                 and {r['origin_id'] for r in derived} == {r['origin_id'] for r in origins})
    by_origin = {r['origin_id']: r for r in origins}
    mismatches = []
    for row in derived:
        start = by_origin[row['origin_id']]['edge_id']
        # Generator uses reverse Decimal distances. Audit uses forward rational distances.
        distance = {mode: nx.single_source_dijkstra_path_length(
                        graph, start, weight=lambda u, v, data: Fraction(str(data['length'])))
                    if start in graph else {} for mode, graph in graphs.items()}
        expected = None
        for stage, (kind, mode) in enumerate((('facility', 'passenger'), ('facility', 'pedestrian'),
                                              ('boundary_exit', 'passenger'), ('boundary_exit', 'pedestrian')), 1):
            choices = [(distance[mode][t['edge_id']], key)
                       for key, t in terms.items() if t['kind'] == kind and t['edge_id'] in distance[mode]]
            if choices:
                cost, key = min(choices)
                expected = (stage, cost, key)
                break
        if expected is None:
            valid = row['terminal_id'] == '' and row['selection_stage'] == ''
        else:
            stage, cost, key = expected
            valid = (row['terminal_id'] == key and int(row['selection_stage']) == stage
                     and Fraction(row['selection_distance_exact_m']) == cost)
        for mode, field in [('passenger', 'car_route'), ('pedestrian', 'walk_route')]:
            path = json.loads(row[field])
            target = terms[row['terminal_id']]['edge_id'] if row['terminal_id'] else None
            possible = target in distance[mode]
            valid &= bool(path) == possible
            if path and possible:
                valid &= path[0] == start and path[-1] == target and len(path) == len(set(path))
                valid &= all(graphs[mode].has_edge(a, b) for a, b in zip(path, path[1:]))
                if valid:
                    total = sum((Fraction(str(graphs[mode][a][b]['length']))
                                 for a, b in zip(path, path[1:])), Fraction(0))
                    valid &= total == distance[mode][target]
            if mode == 'pedestrian' and path:
                valid &= math.isclose(float(row['walk_length_m']),
                                      sum(graphs[mode].nodes[n]['length'] for n in path), abs_tol=1e-8)
        if not valid:
            mismatches.append(row['origin_id'])
    checks['d1_priority_distance_and_paths'] = not mismatches
    people = rows(directory / 'people.csv')
    base = {p['person_id']: p for p in people}
    checks['population_unique'] = len(base) == len(people) == manifest['people']
    realization_counts = {}
    realization_valid = True
    for seed in params['seeds']:
        common = rows(directory / f'common_realization_seed{seed}.csv')
        valid = len(common) == len(people) and {p['person_id'] for p in common} == set(base)
        expected_masks = {}
        for level, value in params['demand_levels'].items():
            mask = set()
            for typ in ('type3', 'type4'):
                candidates = [p['person_id'] for p in people if p['person_type'] == typ]
                candidates.sort(key=lambda pid: (hashlib.sha256(f'{seed}|uptake|{pid}'.encode()).digest(), pid))
                count = math.floor(len(candidates) * value['fraction'] + .5)
                mask.update(candidates[:count])
            expected_masks[level] = mask
        valid &= expected_masks['u05'] <= expected_masks['u50']
        low, high = params['population']['ready_interval_sec']
        for p in common:
            source = base[p['person_id']]
            valid &= all(p[k] == v for k, v in source.items())
            key = source['vehicle_id'] or p['person_id']
            ready = low + int.from_bytes(hashlib.sha256(f'{seed}|ready|{key}'.encode()).digest(), 'big') % (high - low + 1)
            valid &= int(p['ready_sec']) == ready
            for level, mask in expected_masks.items():
                valid &= p['intent_' + level] == str(p['person_id'] in mask)
        realization_counts[str(seed)] = {key: len(value) for key, value in expected_masks.items()}
        realization_valid &= valid
    checks['common_realization_independent'] = bool(realization_valid)
    cells = json.loads((directory / 'cells.json').read_text(encoding='utf-8'))
    expected_keys = set()
    for seed in params['seeds']:
        for policy in params['destination_policies']:
            expected_keys.add((policy, None, 'R0', seed))
            expected_keys.update((policy, level, scenario, seed)
                                 for level in params['demand_levels'] for scenario in ('R1', 'R2P900', 'R2P0'))
    keys = [(r['destination_policy'], r['demand_level'], r['scenario'], r['seed']) for r in cells]
    checks['cell_set_unique_and_exact'] = (cells == params['cells'] and len(keys) == len(set(keys))
                                          and set(keys) == expected_keys
                                          and len({r['cell_id'] for r in cells}) == len(cells))
    report = {
        'status': 'PASS' if all(checks.values()) else 'FAIL',
        'scope': 'derived_choice_tables_and_physical_byte_lineage_only',
        'technical_ready': False,
        'pending': ['raw_hdf_terrain_physical_recomputation', 'core_executor_and_validator',
                    'actual_sumo_cancellation_timing', 'all_14_setting_smoke', 'skill_cli_and_record'],
        'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'checks': checks, 'd1_mismatched_origins': mismatches,
        'realization_counts': realization_counts, 'registered_cells': len(cells),
        'd1_terminal_counts_origins': dict(Counter(row['terminal_id'] for row in derived)),
        'input_manifest_sha256': file_sha(directory / 'manifest.json'),
        'validator_sha256': file_sha(Path(__file__)),
    }
    target = ROOT / params['workspace'] / 'choice_table_validation.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def validate_physical_inputs():
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    checks = {'current_sources': all(file_sha(ROOT / p) == value
                                    for p, value in manifest['source_sha256'].items())}

    def source(suffix):
        matches = [ROOT / path for path in manifest['source_sha256'] if path.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError('Ambiguous primary source: ' + suffix)
        return matches[0]

    domain_data = json.loads(source('cells_utm54n.geojson').read_text(encoding='utf-8'))
    domain = unary_union([shape(feature['geometry']) for feature in domain_data['features']])
    transform = Transformer.from_crs(4326, 32654, always_xy=True)
    reference_origins = rows(source('scenario_c_agent_types.csv'))
    inside = {row['origin_id'] for row in reference_origins
              if domain.covers(Point(*transform.transform(float(row['lon']), float(row['lat']))))}
    reference_people = rows(source('scenario_c_mode_ledger.csv'))
    expected = {row['person_id']: row for row in reference_people if row['origin_id'] in inside}
    people, excluded = rows(directory / 'people.csv'), rows(directory / 'excluded_people.csv')
    checks['population_from_primary_domain'] = (len(people) == len(expected)
                                               and {p['source_person_id'] for p in people} == set(expected))
    checks['attributes_from_primary'] = all(p['person_type'] == expected[p['source_person_id']]['person_type']
                                            and p['base_mode'] == expected[p['source_person_id']]['assigned_mode']
                                            for p in people)
    checks['source_population_partition'] = (len(people) + len(excluded) == len(reference_people)
                                             and not {p['source_person_id'] for p in people}
                                             & {p['source_person_id'] for p in excluded})
    checks['origins_from_primary_domain'] = {o['origin_id'] for o in rows(directory / 'origins.csv')} == inside
    with np.load(directory / 'road_samples.npz') as archive:
        samples = {key: archive[key] for key in archive.files}
    with h5py.File(source('Calibrated/Calibrated.hdf'), 'r') as hydraulic:
        prefix = 'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
        dates = [datetime.strptime(value.decode(), '%d%b%Y %H:%M:%S')
                 for value in hydraulic[prefix + 'Time Date Stamp'][:]]
        start = datetime.fromisoformat(params['simulation']['start_jst']).replace(tzinfo=None)
        end = start + timedelta(seconds=params['simulation']['duration_sec'])
        indices = [i for i, value in enumerate(dates) if start <= value <= end]
        seconds = np.array([(dates[i] - start).total_seconds() for i in indices], dtype=int)
        surface = hydraulic[prefix + '2D Flow Areas/Joso Area/Water Surface'][indices, :]
    checks['native_times_from_hdf'] = (np.array_equal(seconds, samples['native_sec'])
                                      and seconds[0] == 0 and seconds[-1] == params['simulation']['duration_sec'])
    with rasterio.open(source('Terrain.kinugawa.tif')) as terrain:
        inverse = ~terrain.transform
        x, y = samples['xy'][:, 0], samples['xy'][:, 1]
        cols = np.floor(inverse.a * x + inverse.b * y + inverse.c).astype(int)
        rids = np.floor(inverse.d * x + inverse.e * y + inverse.f).astype(int)
        valid = (rids >= 0) & (rids < terrain.height) & (cols >= 0) & (cols < terrain.width)
        elevations = np.full(len(rids), terrain.nodata, dtype=float)
        grid = terrain.read(1)
        elevations[valid] = grid[rids[valid], cols[valid]]
    checks['elevation_from_primary_tif'] = np.array_equal(elevations, samples['elevation_m'])
    groups = defaultdict(list)
    for index, (edge, mode) in enumerate(zip(samples['edge_id'], samples['mode'])):
        groups[str(edge), str(mode)].append(index)
    hazard = rows(directory / 'hazard.csv')
    bad = []
    for row in hazard:
        indices = np.array(groups[row['edge_id'], row['mode']])
        if not np.all(samples['valid'][indices]):
            bad.append((row['edge_id'], row['mode']))
            continue
        cell_ids = samples['cell_id'][indices]
        depths = (surface[:, cell_ids] - elevations[indices]).clip(min=0).max(axis=1)
        threshold = params['hazard']['vehicle_depth_m' if row['mode'] == 'passenger' else 'pedestrian_depth_m']
        hits = np.nonzero(depths >= threshold)[0]
        hit = int(hits[0]) if len(hits) else None
        closure = str(int(seconds[hit])) if hit is not None else ''
        lower = str(int(seconds[max(0, hit - 1)])) if hit is not None else ''
        correct = (closure == row['closure_sec'] and closure == row['upper_sec']
                   and lower == row['lower_sec'] and float(row['threshold_m']) == threshold
                   and math.isclose(float(max(depths)), float(row['max_depth_m']), abs_tol=1e-6)
                   and math.isclose(float(depths[0]), float(row['initial_depth_m']), abs_tol=1e-6))
        if not correct:
            bad.append((row['edge_id'], row['mode']))
    checks['all_road_depths_threshold_intervals_from_hdf_tif'] = not bad
    tags = {row['edge_id']: row for row in rows(source('structure_tags_audit.csv'))}
    eligible = {row['edge_id'] for row in hazard}
    checks['unverified_structures_excluded'] = all(not tags[key]['bridge_tag'] and not tags[key]['tunnel_tag']
                                                  and tags[key]['way_match'] == 'True' for key in eligible)
    terms = rows(directory / 'terminals.csv')
    capacity = {r['shelter_id']: int(r['published_capacity_people'])
                for r in rows(source('既存9施設_公表容量照合_20261015.csv'))}
    checks['facility_capacity_primary'] = all(int(t['capacity']) == capacity[t['terminal_id']]
                                             for t in terms if t['kind'] == 'facility')
    by_hazard = {(r['edge_id'], r['mode']): r for r in hazard}
    checks['terminal_access_model_dry_window'] = all(by_hazard[t['edge_id'], mode]['closure_sec'] == ''
                                                    for t in terms for mode in ('passenger', 'pedestrian'))
    checks['exit_separate_from_facilities'] = all(t['terminal_id'].startswith('exit_') and t['capacity'] == ''
                                                 for t in terms if t['kind'] == 'boundary_exit')
    report = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'technical_ready': False,
              'scope': 'physical_primary_hdf_terrain_population_capacity_recomputation',
              'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'checks': {k: bool(value) for k, value in checks.items()},
              'hazard_rows_recomputed': len(hazard), 'mismatched_edge_modes': bad,
              'input_manifest_sha256': file_sha(directory / 'manifest.json'),
              'validator_sha256': file_sha(Path(__file__))}
    target = ROOT / params['workspace'] / 'physical_input_validation.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def validate_positions():
    """Independent XML/PROJ/Shapely audit; no producer or SUMO geometry imports."""
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    xml = ET.parse(directory / 'bounded.net.xml').getroot()
    location = xml.find('location').attrib
    offset = tuple(map(float, location['netOffset'].split(',')))
    transform = Transformer.from_crs('EPSG:4326', location['projParameter'], always_xy=True)
    edges = {e.attrib['id']: e for e in xml.findall('edge')}
    places = {(kind, r[identifier]): r for kind, name, identifier in
              [('origin', 'origins.csv', 'origin_id'), ('terminal', 'terminals.csv', 'terminal_id')]
              for r in rows(directory / name)}
    reference = {}
    for kind, suffix, identifier in [('origin', 'scenario_c_agent_types.csv', 'origin_id'),
                                     ('terminal', 'shelters_sumo.csv', 'shelter_id')]:
        source = [ROOT / p for p in manifest['source_sha256'] if p.endswith(suffix)]
        if len(source) != 1:
            raise ValueError('Ambiguous position reference')
        reference[kind] = {r[identifier]: r for r in rows(source[0])}
    positions = rows(directory / 'place_positions.csv')
    checks = {'places_unique_and_exact': len(positions) == len(places)
              and {(r['kind'], r['place_id']) for r in positions} == set(places)}
    errors, deviations = [], []

    def permitted(lane, mode):
        allowed = lane.attrib.get('allow')
        return (mode in allowed.split() or 'all' in allowed.split()) if allowed is not None else (
            mode not in lane.attrib.get('disallow', '').split()
            and 'all' not in lane.attrib.get('disallow', '').split())

    def close(actual, expected):
        error = abs(float(actual) - expected)
        deviations.append(error)
        return math.isfinite(float(actual)) and error <= 1e-7

    for row in positions:
        key = row['kind'], row['place_id']
        place = places[key]
        good = row['edge_id'] == place['edge_id']
        if not place['edge_id']:
            good &= row['status'] == 'no_origin_connection' and all(row[k] == '' for k in (
                'car_lane_id', 'pedestrian_lane_id', 'car_pos_m', 'pedestrian_pos_m'))
        else:
            lanes = edges[place['edge_id']].findall('lane')
            car = [lane for lane in lanes if permitted(lane, 'passenger')]
            foot = [lane for lane in lanes if permitted(lane, 'pedestrian')]
            good &= bool(car) and len(foot) == 1
            if not car or len(foot) != 1:
                errors.append(key)
                continue
            c, f = car[0].attrib, foot[0].attrib
            length, foot_length = float(c['length']), float(f['length'])
            line = LineString([tuple(map(float, p.split(','))) for p in c['shape'].split()])
            foot_line = LineString([tuple(map(float, p.split(','))) for p in f['shape'].split()])
            lower = params['position_contract']['minimum_front_pos_m']
            upper = length - params['position_contract']['end_buffer_m']
            good &= lower <= upper and all(float(l.attrib['length']) == length for l in car)
            is_exit = key[0] == 'terminal' and place['kind'] == 'boundary_exit'
            if is_exit:
                raw = upper
                ref = line.interpolate(raw / length * line.length)
                good &= row['source_kind'] == 'registered_exit_downstream_section'
                good &= row['reference_lon'] == row['reference_lat'] == ''
            else:
                source = reference[key[0]][key[1]]
                lon, lat = float(source['lon']), float(source['lat'])
                x, y = transform.transform(lon, lat)
                ref = Point(x + offset[0], y + offset[1])
                raw = line.project(ref) / line.length * length
                good &= close(row['reference_lon'], lon) and close(row['reference_lat'], lat)
                good &= row['source_kind'] == ('reference_origin_centroid' if key[0] == 'origin'
                                              else 'reference_facility_point_not_verified_entrance')
            pos = min(upper, max(lower, raw))
            car_point = line.interpolate(pos / length * line.length)
            foot_offset = foot_line.project(car_point)
            foot_pos = foot_offset / foot_line.length * foot_length
            foot_point = foot_line.interpolate(foot_offset)
            expected = {'reference_x': ref.x, 'reference_y': ref.y, 'car_lane_length_m': length,
                        'car_unclamped_pos_m': raw, 'car_pos_m': pos, 'clamp_shift_m': pos - raw,
                        'car_x': car_point.x, 'car_y': car_point.y,
                        'pedestrian_lane_length_m': foot_length, 'pedestrian_pos_m': foot_pos,
                        'pedestrian_x': foot_point.x, 'pedestrian_y': foot_point.y,
                        'lane_point_gap_m': car_point.distance(foot_point),
                        'reference_to_car_point_m': ref.distance(car_point)}
            good &= all(close(row[k], value) for k, value in expected.items())
            good &= (row['status'] == 'mapped' and row['car_lane_id'] == c['id']
                     and row['pedestrian_lane_id'] == f['id'] and 0 <= foot_pos <= foot_length)
        if not good:
            errors.append(key)
    checks['independent_positions_lanes_projection_ranges'] = not errors
    previous = ROOT / params['previous_choice_input_manifest']
    old = json.loads(previous.read_text(encoding='utf-8'))
    invariant = ['people.csv', 'origins.csv', 'terminals.csv', 'destinations_fixed_reference.csv',
                 'destinations_facility_first.csv', 'cells.json']
    invariant += [f'common_realization_seed{seed}.csv' for seed in params['seeds']]
    checks['people_destinations_masks_times_cells_unchanged'] = all(
        file_sha(directory / name) == old['artifacts'][name] for name in invariant)
    archive_path = ROOT / params['preregistration_archive']
    archive = json.loads(archive_path.read_text(encoding='utf-8'))
    checks['old_input_and_preregistration_preserved'] = (
        file_sha(previous) == archive['registered_input_manifest_sha256']
        and all(file_sha(archive_path.parent / p) == value for p, value in archive['archived_sha256'].items())
        and old['source_sha256'] == archive['registered01_source_sha256']
        and all(file_sha(archive_path.parent / p if p in archive['archived_sha256'] else ROOT / p) == value
                for p, value in old['source_sha256'].items()))
    checks['contracts_bound_to_registry'] = all(manifest[key] == params[key] for key in
        ('input_revision', 'position_contract', 'traffic_observation_contract', 'walking_distance_contract'))
    report = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'technical_ready': False,
              'scope': 'independent_position_geometry_and_old_choice_invariants',
              'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(), 'checks': checks,
              'places': len(positions), 'mismatches': errors,
              'max_numeric_error_m': max(deviations, default=0),
              'net_offset': offset, 'net_projection': location['projParameter'],
              'archival_manifest_sha256': file_sha(archive_path),
              'input_manifest_sha256': file_sha(directory / 'manifest.json'),
              'validator_sha256': file_sha(Path(__file__))}
    (ROOT / params['workspace'] / 'position_input_validation.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def validate_inputs():
    choice = validate_choice_tables()
    physical = validate_physical_inputs()
    positions = validate_positions()
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    still_current = (choice['input_manifest_sha256'] == physical['input_manifest_sha256']
                     == file_sha(directory / 'manifest.json')
                     and all(file_sha(ROOT / path) == expected
                             for path, expected in manifest['source_sha256'].items()))
    report = {
        'status': 'PASS' if choice['status'] == physical['status'] == positions['status'] == 'PASS' and still_current else 'FAIL',
        'scope': 'registered_physical_and_choice_inputs', 'technical_ready': False,
        'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'checks': {**{'choice_' + k: v for k, v in choice['checks'].items()},
                   **{'physical_' + k: v for k, v in physical['checks'].items()},
                   **{'position_' + k: v for k, v in positions['checks'].items()},
                   'sources_current_after_recomputation': still_current},
        'input_manifest_sha256': file_sha(directory / 'manifest.json'),
        'validator_sha256': file_sha(Path(__file__)),
        'component_reports_sha256': {name: file_sha(ROOT / params['workspace'] / name)
                                     for name in ('choice_table_validation.json', 'physical_input_validation.json',
                                                  'position_input_validation.json')},
        'pending': ['core_executor_and_run_validator', 'actual_sumo_cancellation_timing',
                    'all_14_setting_smoke', 'skill_cli_and_record'],
    }
    (ROOT / params['workspace'] / 'input_validation.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--physical', action='store_true')
    group.add_argument('--all', action='store_true')
    group.add_argument('--run-id')
    parser.add_argument('--purpose', choices=('core', 'smoke', 'fixture'), default='core')
    parser.add_argument('--historical-technical', action='store_true')
    arguments = parser.parse_args()
    if arguments.historical_technical and not arguments.run_id:
        parser.error('--historical-technical requires --run-id')
    result = (audit_run_tables(arguments.run_id, arguments.purpose, not arguments.historical_technical)
              if arguments.run_id else validate_inputs() if arguments.all else validate_physical_inputs()
              if arguments.physical else validate_choice_tables())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
