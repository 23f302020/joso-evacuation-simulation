"""Reconstruct candidate paths, gates and choices without importing dispatcher code."""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
import argparse
import csv
import gzip
import hashlib
import json
import math
import networkx as nx

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else Path.open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def number(row, prefix):
    kind = row[prefix + '_kind']
    if kind == 'finite' and row[prefix + '_sec'] != '':
        value = float(row[prefix + '_sec'])
        if math.isfinite(value):
            return value
    elif kind == 'infinite' and row[prefix + '_sec'] == '':
        return math.inf
    elif kind == 'not_applicable' and row[prefix + '_sec'] == '':
        return None
    raise ValueError('Invalid numeric/missingness pair')


def audit(run_id):
    cfg = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    folder = ROOT / cfg['workspace'] / 'smoke' / run_id
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    directory = ROOT / manifest['input_directory']
    errors = defaultdict(list)
    people = {p['person_id']: p for p in rows(folder / 'common_realization.csv')}
    origins = {p['origin_id']: p for p in rows(directory / 'origins.csv')}
    destinations = {p['origin_id']: p for p in rows(directory / ('destinations_' + manifest['destination_policy'] + '.csv'))}
    terms = {p['terminal_id']: p for p in rows(directory / 'terminals.csv')}
    positions = {(p['kind'], p['place_id']): p for p in rows(directory / 'place_positions.csv')}
    raw = json.loads((directory / 'graphs.json').read_text(encoding='utf-8'))['passenger']
    graph = nx.DiGraph()
    graph.add_nodes_from(raw['nodes'])
    graph.add_edges_from((a, b) for a, b, attributes in raw['edges'])
    closures = {p['edge_id']: float(p['closure_sec']) for p in rows(directory / 'hazard.csv')
                if p['mode'] == 'passenger' and p['closure_sec'] != ''}
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    states = [e for e in events if e['event'] == 'request_state']
    accepts = {(e['cycle'], e['stage']): (e['person_id'], e['vehicle_id'])
               for e in events if e['event'] == 'request_accepted'}
    frames = {(float(p['time_sec']), p['actor_id']): p for p in rows(folder / 'actor_observations.csv.gz')
              if p['kind'] == 'drt'}
    speeds = defaultdict(lambda: defaultdict(lambda: [0., 0]))
    for p in rows(folder / 'edge_observations.csv.gz'):
        frame = speeds[float(p['time_sec'])]
        if p['mode'] in ('car', 'drt') and int(p['traffic_count']):
            count = int(p['traffic_count'])
            frame[p['edge_id']][0] += count * float(p['traffic_mean_speed_mps'])
            frame[p['edge_id']][1] += count
    candidates = defaultdict(list)
    for row in rows(folder / 'candidates.csv.gz'):
        candidates[int(row['cycle']), int(row['stage'])].append(row)
    cycles = {int(row['cycle']): row for row in rows(folder / 'dispatch_cycles.csv.gz')}
    distance_cache = {}
    row_count = 0
    for key, group in sorted(candidates.items()):
        cycle, stage = key
        now = float(group[0]['time_sec'])
        pending = {}
        for e in states:
            if e['time_sec'] > now:
                break
            if e.get('trigger') == 'accepted' and e.get('cycle') == cycle and e.get('stage', 0) >= stage:
                continue
            pending[e['person_id']] = e['after']
        expected_people = {pid for pid, state in pending.items() if state == 'pending'}
        persons, vehicles = {p['person_id'] for p in group}, {p['vehicle_id'] for p in group}
        pairs = {(p['person_id'], p['vehicle_id']) for p in group}
        if persons != expected_people or len(group) != len(pairs) or pairs != {(p, v) for p in persons for v in vehicles}:
            errors['candidate_matrix'].append(key)
        if len(vehicles) != int(cycles[cycle]['free_start']) - (stage - 1):
            errors['candidate_free_stage_count'].append(key)
        open_graph = nx.subgraph_view(graph, filter_node=lambda n: closures.get(n, math.inf) > now + manifest['step_sec'])
        previous = [at for at in speeds if at < now]
        observed = speeds[max(previous)] if previous else {}

        def edge_time(edge, mode):
            total, count = observed.get(edge, (0, 0)) if mode == 'pickup' else (0, 0)
            return raw['nodes'][edge]['length'] / max(total / count, .1) if count else raw['nodes'][edge]['free_sec']

        def optimal(start, target, start_pos, target_pos, mode, minimum=0):
            if start not in open_graph or target not in open_graph:
                return math.inf
            first, last = raw['nodes'][start]['length'], raw['nodes'][target]['length']
            if start == target and target_pos - start_pos >= minimum:
                return edge_time(start, mode) * (target_pos - start_pos) / first
            cache_key = now, mode, target
            if cache_key not in distance_cache:
                # Reverse search gives distance-to-target, independent of producer's forward trees.
                distance_cache[cache_key] = nx.single_source_dijkstra_path_length(
                    open_graph.reverse(copy=False), target, weight=lambda u, v, data: edge_time(u, mode))
            distance = distance_cache[cache_key]
            if start == target:
                cost = min((edge_time(n, mode) + distance[n] for n in open_graph.successors(start)
                            if n in distance), default=math.inf)
            else:
                cost = distance.get(start, math.inf)
            return cost + edge_time(start, mode) * (1 - start_pos / first) - edge_time(target, mode) * (1 - target_pos / last)

        expected_scores, eligible = {}, []
        for row in group:
            row_count += 1
            pid, vid = row['person_id'], row['vehicle_id']
            person = people[pid]
            origin = origins[person['origin_id']]['edge_id']
            terminal_id = destinations[person['origin_id']]['terminal_id']
            target = terms[terminal_id]['edge_id']
            op = float(positions['origin', person['origin_id']]['car_pos_m'])
            tp = float(positions['terminal', terminal_id]['car_pos_m'])
            frame = frames.get((now, vid))
            if not frame or row['source_edge'] != frame['road_id'] or not math.isclose(float(row['source_pos_m']), float(frame['lane_position_m']), abs_tol=1e-8):
                errors['candidate_source_observation'].append((key, vid))
            if not math.isclose(float(row['pickup_pos_m']), op, abs_tol=1e-8) or not math.isclose(float(row['terminal_pos_m']), tp, abs_tol=1e-8):
                errors['candidate_registered_positions'].append((key, pid))
            paths = {mode: json.loads(row[mode + '_path']) for mode in ('pickup', 'delivery')}
            for mode, start, end, position, arrival in [('pickup', row['source_edge'], origin, float(row['source_pos_m']), op),
                                                      ('delivery', origin, target, op, tp)]:
                expected = optimal(start, end, position, arrival, mode, float(row['minimum_advance_m']) if mode == 'pickup' else 0)
                value = number(row, mode)
                equal = value == expected if not math.isfinite(expected) else value is not None and math.isclose(value, expected, abs_tol=1e-7)
                if not equal:
                    errors['candidate_shortest_time'].append((key, pid, mode, value, expected))
                path = paths[mode]
                if path and (path[0] != start or path[-1] != end or any(n not in open_graph for n in path)
                             or not all(open_graph.has_edge(a, b) for a, b in zip(path, path[1:]))):
                    errors['candidate_open_path'].append((key, pid, mode))
            pickup, delivery = number(row, 'pickup'), number(row, 'delivery')
            deadline = float(person['ready_sec']) + cfg['request_policy']['max_unboarded_wait_sec']
            required = pickup + delivery + cfg['operation']['boarding_sec'] + cfg['operation']['alighting_sec'] + cfg['operation']['margin_sec']
            forecasting = manifest['scenario'].startswith('R2')
            remaining = (min((closures.get(n, math.inf) + cfg['forecast'][manifest['scenario']]['scheduled_time_error_sec'] - now
                              for n in paths['pickup'] + paths['delivery']), default=math.inf) if forecasting else None)
            predicates = [('no_pickup_route', math.isfinite(pickup)), ('no_delivery_route', math.isfinite(delivery)),
                          ('pickup_deadline', now + pickup < deadline),
                          ('horizon', now + required - cfg['operation']['margin_sec'] <= manifest['end_sec'])]
            if forecasting:
                predicates.append(('forecast_gate', required < remaining))
            reason = next((name for name, value in predicates if not value), 'eligible')
            expected_bool = {'pickup_route': predicates[0][1], 'delivery_route': predicates[1][1],
                             'pickup_before_deadline': predicates[2][1], 'completion_within_horizon': predicates[3][1],
                             'gate_applicable': forecasting and math.isfinite(remaining),
                             'gate_pass': required < remaining if forecasting else None}
            if any(row[name] != (str(value) if value is not None else '') for name, value in expected_bool.items()) or row['reason'] != reason:
                errors['candidate_gate_components'].append((key, pid, reason))
            expected_remaining = number(row, 'forecast_remaining')
            recorded_required = number(row, 'required')
            same_required = (recorded_required == required if not math.isfinite(required)
                             else recorded_required is not None and math.isclose(recorded_required, required, rel_tol=0, abs_tol=1e-9))
            if expected_remaining != remaining or not same_required:
                errors['candidate_forecast_required'].append((key, pid))
            waiting, vulnerable = now - float(person['ready_sec']), int(person['person_type'] == 'type4')
            urgency = 1 / max(remaining, 1) if remaining is not None and math.isfinite(remaining) else 0
            if float(row['waiting_sec']) != waiting or int(row['vulnerability']) != vulnerable or not math.isclose(float(row['urgency']), urgency, abs_tol=1e-12):
                errors['candidate_score_components'].append((key, pid))
            if reason == 'eligible':
                eligible.append((row, waiting, vulnerable, pickup, urgency))
            elif row['score'] != '':
                errors['candidate_ineligible_score'].append(key)
        maxima = [max((values[index] for values in eligible), default=0) for index in (1, 3, 4)]
        weights = cfg['dispatch_weights']
        for row, waiting, vulnerability, pickup, urgency in eligible:
            score = (weights['waiting'] * waiting / maxima[0] if maxima[0] else 0) + weights['vulnerability'] * vulnerability
            score -= weights['pickup'] * pickup / maxima[1] if maxima[1] else 0
            if manifest['scenario'].startswith('R2'):
                score += weights['flood'] * urgency / maxima[2] if maxima[2] else 0
            expected_scores[row['person_id'], row['vehicle_id']] = score
            if row['score'] == '' or not math.isclose(float(row['score']), score, abs_tol=1e-10):
                errors['candidate_score'].append((key, row['person_id']))
        chosen = min(expected_scores, key=lambda pair: (-expected_scores[pair], pair), default=None)
        selected = [(row['person_id'], row['vehicle_id']) for row in group if row['decision'] == 'selected']
        if selected != ([chosen] if chosen else []) or accepts.get(key) != chosen:
            errors['candidate_choice_and_acceptance'].append(key)
    for cycle, row in cycles.items():
        groups = [group for (c, s), group in candidates.items() if c == cycle]
        if len(groups) != int(row['stages']) or sum(map(len, groups)) != int(row['candidate_rows']):
            errors['cycle_primary_counts'].append(cycle)
    checks = {name: not errors[name] for name in ('candidate_matrix', 'candidate_free_stage_count',
        'candidate_source_observation', 'candidate_registered_positions', 'candidate_shortest_time',
        'candidate_open_path', 'candidate_gate_components', 'candidate_forecast_required',
        'candidate_score_components', 'candidate_ineligible_score', 'candidate_score',
        'candidate_choice_and_acceptance', 'cycle_primary_counts')}
    return {'run_id': run_id, 'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
            'scope': 'partial_candidate_smoke_audit_not_formal_core_acceptance',
            'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'candidate_rows': row_count, 'candidate_stages': len(candidates), 'cycles': len(cycles),
            'numeric_sum_tolerance_sec': 1e-9,
            'tolerance_scope': 'addition-order numerical agreement only; strict Gate boolean outcomes checked separately',
            'errors': {k: v[:20] for k, v in errors.items() if v}, 'core_adoption_permitted': False,
            'auditor_sha256': sha(Path(__file__)), 'manifest_sha256': sha(folder / 'manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    report = audit(args.run_id)
    (Path(__file__).parent / (args.run_id + '_候補選択独立監査.json')).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
