"""Pure rules for the preregistered realtime_choice_v1 series only."""
import hashlib
import math
from decimal import Decimal

import networkx as nx


def hash_number(seed, key, role):
    return int.from_bytes(hashlib.sha256(f'{seed}|{role}|{key}'.encode()).digest(), 'big')


def select_intents(people, seed, fraction):
    if not 0 <= fraction <= 1:
        raise ValueError('Intent fraction outside [0, 1]')
    selected = set()
    for typ in ('type3', 'type4'):
        candidates = sorted(
            (p['person_id'] for p in people if p['person_type'] == typ),
            key=lambda pid: (hash_number(seed, pid, 'uptake'), pid),
        )
        selected.update(candidates[:math.floor(len(candidates) * fraction + .5)])
    return selected


def lex_shortest_path(graph, start, target, distances):
    """Reconstruct the lexicographically first shortest path; weights must be positive."""
    if start not in distances:
        return []
    path = [start]
    while path[-1] != target:
        node = path[-1]
        choices = []
        for neighbor, data in graph[node].items():
            weight = Decimal(str(data['length']))
            if not math.isfinite(weight) or weight <= 0:
                raise ValueError('Destination graph requires finite positive lengths')
            if neighbor in distances and weight + distances[neighbor] == distances[node]:
                choices.append(neighbor)
        if not choices:
            raise ValueError('Shortest-path distances cannot be reconstructed')
        chosen = min(choices)
        if chosen in path:
            raise ValueError('Cycle in positive-length shortest path')
        path.append(chosen)
    return path


def facility_first_destinations(origins, graphs, terminals):
    """Initial current graphs only. Do not pass a future hazard table here."""
    priorities = [('facility', 'passenger'), ('facility', 'pedestrian'),
                  ('boundary_exit', 'passenger'), ('boundary_exit', 'pedestrian')]
    distances = {}
    for mode, graph in graphs.items():
        if any(not math.isfinite(d['length']) or d['length'] <= 0
               for _, _, d in graph.edges(data=True)):
            raise ValueError('Destination graph requires finite positive lengths')
        reverse = graph.reverse(copy=False) if graph.is_directed() else graph
        for terminal in terminals:
            edge = terminal['edge_id']
            if edge in graph:
                distances[mode, terminal['terminal_id']] = nx.single_source_dijkstra_path_length(
                    reverse, edge, weight=lambda u, v, d: Decimal(str(d['length'])))
    result = []
    for origin in sorted(origins, key=lambda row: row['origin_id']):
        start = origin['edge_id']
        chosen = None
        for stage, (kind, mode) in enumerate(priorities, 1):
            candidates = [(distances[mode, t['terminal_id']][start], t['terminal_id'], t)
                          for t in terminals if t['kind'] == kind
                          and start in distances.get((mode, t['terminal_id']), {})]
            if candidates:
                distance, terminal_id, terminal = min(candidates, key=lambda x: (x[0], x[1]))
                chosen = (stage, distance, terminal_id, terminal)
                break
        row = {'origin_id': origin['origin_id'], 'edge_id': start, 'terminal_id': '',
               'selection_stage': '', 'selection_distance_m': '', 'selection_distance_exact_m': '',
               'car_route': [], 'walk_route': [], 'walk_length_m': ''}
        if chosen:
            stage, distance, terminal_id, terminal = chosen
            row.update(terminal_id=terminal_id, selection_stage=stage,
                       selection_distance_m=float(distance), selection_distance_exact_m=str(distance))
            for mode, field in [('passenger', 'car_route'), ('pedestrian', 'walk_route')]:
                graph = graphs[mode]
                route = lex_shortest_path(graph, start, terminal['edge_id'],
                                          distances.get((mode, terminal_id), {}))
                row[field] = route
                if mode == 'pedestrian' and route:
                    row['walk_length_m'] = sum(graph.nodes[n]['length'] for n in route)
        result.append(row)
    return result


def unboarded_expired(person_status, now, deadline):
    return person_status in ('waiting_origin', 'assigned_origin') and now >= deadline


def candidate_checks(now, pickup_sec, delivery_sec, deadline, horizon,
                     boarding_sec, alighting_sec, margin_sec,
                     forecast_remaining_sec=None):
    if any(math.isnan(v) or v < 0 for v in (pickup_sec, delivery_sec)):
        raise ValueError('Invalid travel estimate')
    pickup_route = math.isfinite(pickup_sec)
    delivery_route = math.isfinite(delivery_sec)
    pickup_deadline = now + pickup_sec < deadline
    completion = now + pickup_sec + boarding_sec + delivery_sec + alighting_sec <= horizon
    required = pickup_sec + boarding_sec + delivery_sec + alighting_sec + margin_sec
    forecast_pass = (required < forecast_remaining_sec
                     if forecast_remaining_sec is not None else None)
    checks = [('no_pickup_route', pickup_route), ('no_delivery_route', delivery_route),
              ('pickup_deadline', pickup_deadline), ('horizon', completion)]
    if forecast_remaining_sec is not None:
        if math.isnan(forecast_remaining_sec):
            raise ValueError('Missing forecast remaining time')
        checks.append(('forecast_gate', forecast_pass))
    return {'pickup_route': pickup_route, 'delivery_route': delivery_route,
            'pickup_before_deadline': pickup_deadline, 'completion_within_horizon': completion,
            'required_sec': required, 'forecast_gate_pass': forecast_pass,
            'forecast_gate_applicable': forecast_remaining_sec is not None
                                        and math.isfinite(forecast_remaining_sec),
            'reason': next((reason for reason, passed in checks if not passed), 'eligible')}


def request_transition(status, event):
    transitions = {
        ('none', 'received'): 'pending',
        ('pending', 'invalid_input'): 'rejected_input',
        ('pending', 'accepted'): 'accepted',
        ('accepted', 'boarding_started'): 'boarding',
        ('boarding', 'boarded'): 'onboard',
        ('onboard', 'alighting_started'): 'alighting',
        ('alighting', 'alighted'): 'served',
        ('pending', 'timeout'): 'cancelled_timeout',
        ('accepted', 'timeout'): 'cancelled_timeout',
        ('accepted', 'vehicle_failed'): 'cancelled_vehicle_failure',
        ('boarding', 'vehicle_failed'): 'failed_after_boarding',
        ('onboard', 'vehicle_failed'): 'failed_after_boarding',
        ('alighting', 'vehicle_failed'): 'failed_after_boarding',
    }
    if event == 'horizon' and status in ('pending', 'accepted', 'boarding', 'onboard', 'alighting'):
        return 'time_limit'
    try:
        return transitions[status, event]
    except KeyError as exc:
        raise ValueError(f'Invalid request transition: {status} -> {event}') from exc
