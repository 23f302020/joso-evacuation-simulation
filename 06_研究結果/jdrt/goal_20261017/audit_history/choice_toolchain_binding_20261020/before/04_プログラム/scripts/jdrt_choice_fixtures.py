"""Synthetic inputs run by the real choice controller. Never research observations."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import csv
import gzip
import json
import math
import os
import re
import subprocess
import traceback
import xml.etree.ElementTree as ET

import networkx as nx

from scripts.jdrt.smoke import load_traci, resolve_sumo_binary
from scripts.jdrt_realtime_choice import ROOT, PARAM, atomic_json, run, sha, stamp, write_csv

CASES = ('walk_reroute', 'walk_reroute_limit', 'walk_budget', 'walk_reverse',
         'pickup_closure', 'boarding_closure', 'alighting_closure',
         'forecast_r1', 'forecast_p0', 'forecast_p900', 'forecast_reroute',
         'shared_capacity', 'horizon_alighting', 'car_backward_cycle', 'car_backward_no_cycle', 'car_reroute',
         'pickup_deadline_equal', 'pickup_before_deadline', 'pickup_internal_calibration',
         'pickup_internal_timeout', 'pickup_internal_timeout_closed_next',
         'car_lane_calibration', 'car_lane_alternative', 'car_lane_cut',
         'walk_short_calibration', 'walk_short_repeated')


def car_lane_connections():
    # sidewalkWidth inserts pedestrian lane 0; passenger lanes start at 1.
    return [('g0', 'e0', 1, 1), ('g0', 'e0', 2, 2),
            ('e0', 'e1', 1, 1), ('e0', 'd0', 2, 1), ('e0', 's0', 1, 1),
            ('e1', 'e2', 1, 1), ('d0', 'd1', 1, 1), ('d1', 'd2', 1, 1),
            ('d2', 'e2', 1, 1), ('s0', 's1', 1, 1), ('s1', 'e2', 1, 1)]


def validate_car_lane_topology(net):
    """Require the artificial passenger turns in the actual converted net."""
    for first, second, source, target in car_lane_connections():
        lane, other = net.getLane(f'{first}_{source}'), net.getLane(f'{second}_{target}')
        if (not lane.allows('passenger') or not other.allows('passenger')
                or not any(link.getToLane().getID() == other.getID() for link in lane.getOutgoing())):
            raise ValueError('Converted car-lane fixture lacks a declared passenger connection')
    first = net.getLane('e0_1')
    successors = {link.getToLane().getEdge().getID() for link in first.getOutgoing()
                  if link.getToLane().allows('passenger')}
    if successors != {'e1', 's0'}:
        raise ValueError('Converted car-lane fixture changed its short-lane counterexample')


def native_walk_reference(folder, step_sec):
    """Find a shared native frame on a second short edge for a later reverse reroute."""
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    actors, results = folder / 'actor_observations.csv.gz', folder / 'person_results.csv'
    if manifest['status'] != 'COMPLETED' or manifest['purpose'] != 'fixture':
        raise ValueError('Completed technical walking calibration is required')
    for path in (actors, results):
        if sha(path) != manifest['output_sha256'][path.name]:
            raise ValueError('Walking calibration output SHA mismatch')
    with results.open(encoding='utf-8-sig', newline='') as stream:
        ids = {row['person_id'] for row in csv.DictReader(stream)}
    graph = json.loads((folder.parent / 'fixture_inputs/graphs.json').read_text(encoding='utf-8'))
    length = graph['pedestrian']['nodes']['d0']['length']
    frames = {}
    with gzip.open(actors, 'rt', encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            now, speed, position = float(row['time_sec']), float(row['speed_mps']), float(row['lane_position_m'])
            if (row['actor_id'] in ids and row['road_id'] == 'd0' and (now + step_sec) % 1 == 0
                    and 2 * speed * step_sec < position < length - 2 * speed * step_sec):
                frames.setdefault(now, {})[row['actor_id']] = row
    for now, rows in sorted(frames.items()):
        if set(rows) == ids:
            return {'reference_run_id': manifest['run_id'], 'source_time_sec': now,
                    'closure_sec': int(now + step_sec), 'source_edge': 'd0',
                    'source_frames': rows, 'source_lane_length_m': length,
                    'source_sha256': {path.relative_to(ROOT).as_posix(): sha(path)
                        for path in (folder / 'manifest.json', actors, results,
                                     folder.parent / 'fixture_inputs/graphs.json')}}
    raise ValueError('Calibration lacks a shared interior short-edge walking frame')


def native_lane_reference(folder, step_sec):
    """Find a native short-lane frame without injecting a lane or changing speed."""
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    actors = folder / 'actor_observations.csv.gz'
    if (manifest['status'] != 'COMPLETED' or manifest['purpose'] != 'fixture'
            or sha(actors) != manifest['output_sha256'][actors.name]):
        raise ValueError('Completed SHA-bound lane calibration is required')
    import sumolib
    net = sumolib.net.readNet(str(folder.parent / 'fixture_inputs/bounded.net.xml'), withInternal=True)
    with gzip.open(actors, 'rt', encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            now = float(row['time_sec'])
            if row['road_id'] != 'e0' or (now + step_sec) % 1 != 0:
                continue
            lane = net.getLane(row['lane_id'])
            remaining = lane.getLength() - float(row['lane_position_m'])
            speed, decel = float(row['speed_mps']), float(row['decel_mps2'])
            braking = speed * speed / (2 * decel) + speed * step_sec + 1
            successors = {link.getToLane().getEdge().getID() for link in lane.getOutgoing()}
            if remaining < braking and 'd0' not in successors and {'e1', 's0'} <= successors:
                return {'reference_run_id': manifest['run_id'], 'source_time_sec': now,
                        'closure_sec': int(now + step_sec), 'source_lane_id': row['lane_id'],
                        'source_lane_position_m': float(row['lane_position_m']),
                        'remaining_lane_m': remaining, 'braking_room_m': braking,
                        'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p)
                            for p in (folder / 'manifest.json', actors,
                                      folder.parent / 'fixture_inputs/bounded.net.xml')}}
    raise ValueError('Calibration did not expose the required native short-lane frame')


def native_pickup_reference(folder, controller_sec, step_sec):
    """Derive technical boundary times from a completed native run, not constants."""
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if m['status'] != 'COMPLETED' or m['purpose'] != 'fixture':
        raise ValueError('A completed technical reference run is required')
    paths = [folder / 'manifest.json', folder / 'request_results.csv', folder / 'actor_observations.csv.gz']
    if any(sha(p) != m['output_sha256'][p.name] for p in paths[1:]):
        raise ValueError('Native timing reference output SHA mismatch')
    with paths[1].open(encoding='utf-8-sig', newline='') as stream:
        requests = list(csv.DictReader(stream))
    if len(requests) != 1 or requests[0]['boarding_started_sec'] == '' or requests[0]['accepted_sec'] == '':
        raise ValueError('Timing reference must have one physically boarded request')
    q = requests[0]
    with gzip.open(paths[2], 'rt', encoding='utf-8-sig', newline='') as stream:
        pickup = [r for r in csv.DictReader(stream) if r['actor_id'] == q['vehicle_id']
                  and r['status'] == 'pickup' and float(r['time_sec']) >= float(q['accepted_sec'])]
    internal = []
    for i, row in enumerate(pickup):
        now = float(row['time_sec'])
        if row['road_id'].startswith(':') and now % controller_sec == 0:
            next_external = next((r for r in pickup[i + 1:] if r['road_id'] and not r['road_id'].startswith(':')), None)
            if next_external and float(next_external['time_sec']) - now >= 2 * step_sec:
                internal.append({'deadline_sec': now, 'internal_edge': row['road_id'],
                                 'next_external_edge': next_external['road_id'],
                                 'next_external_native_sec': float(next_external['time_sec'])})
    return {'reference_run_id': m['run_id'], 'native_boarding_started_sec': float(q['boarding_started_sec']),
            'native_accepted_sec': float(q['accepted_sec']), 'internal_windows': internal,
            'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}}


def prepare(case, run_id, params):
    directory = ROOT / params['workspace'] / 'technical' / run_id / 'fixture_inputs'
    directory.mkdir(parents=True, exist_ok=False)
    binary = resolve_sumo_binary()
    load_traci(binary)
    import sumolib
    nodes, edges = ET.Element('nodes'), ET.Element('edges')
    coordinates = [('G', -100, 0), ('A', 0, 0), ('B', 100, 0), ('C', 200, 0),
                   ('D', 100, 100), ('E', 200, 100), ('F', 300, 0),
                   ('L0', 0, -100), ('L1', 5000, -100)]
    if case == 'car_backward_cycle':
        coordinates.append(('R', 50, -150))
    if case.startswith('car_lane_'):
        coordinates = [(name, 35 if name in ('B', 'D') else x, y) for name, x, y in coordinates]
        coordinates.append(('S', 100, -100))
    if case.startswith('walk_short_'):
        coordinates = [(name, 30 if name in ('B', 'D') else x, 30 if name == 'D' else y)
                       for name, x, y in coordinates]
        coordinates.append(('W', -100, 150))
    for name, x, y in coordinates:
        attrs = {'id': name, 'x': str(x), 'y': str(y), 'type': 'priority'}
        if case.startswith('pickup_internal') and name == 'B':
            attrs['radius'] = '15'  # Artificial long turn exposes integer-controller internal frames.
        ET.SubElement(nodes, 'node', **attrs)
    links = [('g0', 'G', 'A'), ('e0', 'A', 'B'), ('e1', 'B', 'C'), ('e2', 'C', 'F'),
             ('d0', 'B', 'D'), ('d1', 'D', 'E'), ('d2', 'E', 'C'), ('long', 'L0', 'L1')]
    if case == 'car_backward_cycle':
        links.extend([('loop0', 'C', 'R'), ('loop1', 'R', 'A')])
    if case.startswith('car_lane_'):
        links.extend([('s0', 'B', 'S'), ('s1', 'S', 'C')])
    if case.startswith('walk_short_'):
        links.extend([('w0', 'A', 'W'), ('w1', 'W', 'E')])
    for name, a, b in links:
        attrs = {'id': name, 'from': a, 'to': b, 'speed': '5', 'numLanes': '1',
                 'allow': 'passenger', 'sidewalkWidth': '2'}
        if case.startswith('car_lane_'):
            attrs['speed'] = '15'
            if name in ('g0', 'e0'):
                attrs['numLanes'] = '2'
            if name == 's0':
                # Keep the native-lane detour longer than the adjacent-lane turn.
                attrs['shape'] = '35,0 140,0 140,-300 100,-300 100,-100'
        if name == 'd1' and case == 'walk_reroute_limit':
            attrs['shape'] = '100,100 100,2100 200,2100 200,100'
        ET.SubElement(edges, 'edge', **attrs)
    for name, tree in [('nodes.xml', nodes), ('edges.xml', edges)]:
        ET.ElementTree(tree).write(directory / name, encoding='utf-8', xml_declaration=True)
    connection_arguments = []
    if case.startswith('car_lane_'):
        connections = ET.Element('connections')
        for a, b, source, target in car_lane_connections():
            ET.SubElement(connections, 'connection', attrib={'from': a, 'to': b,
                          'fromLane': str(source), 'toLane': str(target)})
        ET.ElementTree(connections).write(directory / 'connections.xml', encoding='utf-8', xml_declaration=True)
        connection_arguments = ['--connection-files', 'connections.xml']
    result = subprocess.run([str(binary.parent / 'netconvert.exe'), '--node-files', 'nodes.xml',
        '--edge-files', 'edges.xml', '--output-file', 'bounded.net.xml', '--no-turnarounds', 'true',
        '--walkingareas', 'true', '--crossings.guess', 'true'] + connection_arguments,
        cwd=directory, capture_output=True, text=True)
    (directory / 'netconvert.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    result.check_returncode()
    net = sumolib.net.readNet(str(directory / 'bounded.net.xml'), withInternal=True)
    if case.startswith('car_lane_'):
        validate_car_lane_topology(net)
    data = {}
    for mode in ('passenger', 'pedestrian'):
        graph = nx.DiGraph() if mode == 'passenger' else nx.Graph()
        for edge in net.getEdges(withInternal=False):
            lane = next((lane for lane in edge.getLanes() if lane.allows(mode)), None)
            if lane is not None:
                speed = lane.getSpeed() if mode == 'passenger' else 1.
                graph.add_node(edge.getID(), length=lane.getLength(), free_sec=lane.getLength() / speed)
        for edge in net.getEdges(withInternal=False):
            if edge.getID() in graph:
                for other in edge.getAllowedOutgoing(mode):
                    if other.getID() in graph:
                        graph.add_edge(edge.getID(), other.getID(), length=graph.nodes[other.getID()]['length'],
                                       travel_sec=graph.nodes[other.getID()]['free_sec'])
        data[mode] = {'directed': graph.is_directed(), 'nodes': dict(graph.nodes(data=True)),
                      'edges': list(graph.edges(data=True))}
    drt = case in ('pickup_closure', 'boarding_closure', 'alighting_closure',
                   'forecast_r1', 'forecast_p0', 'forecast_p900', 'forecast_reroute', 'horizon_alighting') or case.startswith('pickup_')
    scenario = 'R2P0' if case in ('forecast_p0', 'forecast_reroute') else 'R2P900' if case == 'forecast_p900' else 'R1' if drt else 'R0'
    parameters = deepcopy(params)
    parameters['protocol'] = 'realtime_choice_fixture_v1'
    if case.startswith('walk_short_'):
        # Deliberate, fixture-only native getter/stage mismatch. No research input uses this key.
        parameters['technical_walk_speed_factors'] = {typ: .8 for typ in parameters['population']['walk_mps']}
    parameters['population']['ready_interval_sec'] = [0, 0]
    parameters['operation']['fleet_count'] = int(drt)
    parameters['simulation']['duration_sec'] = 5000 if case == 'walk_budget' else 2000 if drt else 1500
    parameters['cells'] = [{'cell_id': 'fixture_' + case, 'destination_policy': 'fixed_reference',
                             'demand_level': 'u50', 'scenario': scenario, 'seed': params['seeds'][0]}]
    timing = None
    if case == 'walk_short_repeated':
        prefix = run_id.rsplit('_c', 1)[0]
        reference_id = prefix + '_c' + str(CASES.index('walk_short_calibration') + 1).zfill(2)
        timing = native_walk_reference(ROOT / params['workspace'] / 'technical' / reference_id / 'execution',
                                       params['simulation']['step_sec'])
    if case in ('car_lane_alternative', 'car_lane_cut'):
        prefix = run_id.rsplit('_c', 1)[0]
        reference_id = prefix + '_c' + str(CASES.index('car_lane_calibration') + 1).zfill(2)
        timing = native_lane_reference(ROOT / params['workspace'] / 'technical' / reference_id / 'execution',
                                       params['simulation']['step_sec'])
    if case in ('pickup_deadline_equal', 'pickup_before_deadline', 'pickup_internal_timeout', 'pickup_internal_timeout_closed_next'):
        reference_case = 'pickup_internal_calibration' if case.startswith('pickup_internal') else 'forecast_r1'
        prefix = run_id.rsplit('_c', 1)[0]
        reference_id = prefix + '_c' + str(CASES.index(reference_case) + 1).zfill(2)
        reference = ROOT / params['workspace'] / 'technical' / reference_id / 'execution'
        timing = native_pickup_reference(reference, params['simulation']['controller_sec'], params['simulation']['step_sec'])
        if case.startswith('pickup_internal'):
            if not timing['internal_windows']:
                raise ValueError('Calibration has no native internal window with a later external step')
            timing['selected_internal_window'] = timing['internal_windows'][0]
            deadline = timing['selected_internal_window']['deadline_sec']
            # Deliberate technical underprediction permits acceptance before an
            # actual delay. Never used in registered research inputs or config.
            timing['technical_free_time_scale'] = .5
            for attrs in data['passenger']['nodes'].values():
                attrs['free_sec'] *= timing['technical_free_time_scale']
            for a, b, attrs in data['passenger']['edges']:
                attrs['travel_sec'] = data['passenger']['nodes'][b]['free_sec']
        else:
            deadline = timing['native_boarding_started_sec']
            if case == 'pickup_before_deadline':
                deadline += parameters['simulation']['controller_sec']
        if deadline % parameters['simulation']['controller_sec']:
            raise ValueError('Derived deadline is not on the controller grid')
        parameters['request_policy']['max_unboarded_wait_sec'] = int(deadline)
        timing['derived_deadline_sec'] = deadline
    atomic_json(directory / 'graphs.json', data)
    changes = {}
    if case in ('walk_reroute', 'walk_reroute_limit'):
        changes['e1', 'pedestrian'] = 40
    if case.startswith('walk_short_'):
        changes['e1', 'pedestrian'] = 1
        if case == 'walk_short_repeated':
            changes['d1', 'pedestrian'] = timing['closure_sec']
    if case == 'pickup_closure':
        changes['e0', 'passenger'] = 65
    if case == 'boarding_closure':
        changes['e0', 'passenger'] = 120
    if case == 'alighting_closure':
        changes['e2', 'passenger'] = 450
    if case == 'car_reroute':
        changes['e1', 'passenger'] = 10
    if case in ('car_lane_alternative', 'car_lane_cut'):
        changes['e1', 'passenger'] = timing['closure_sec']
    if case == 'car_lane_cut':
        changes['s0', 'passenger'] = 0
    if case.startswith('forecast_'):
        # P0's closure after the unboarded deadline forces the pure Gate/timeout case.
        # The separate 700s case allows a newly shortest detour before the deadline.
        changes['e1', 'passenger'] = 950 if case == 'forecast_p0' else 700
    if case == 'pickup_internal_timeout_closed_next':
        window = timing['selected_internal_window']
        changes[window['next_external_edge'], 'passenger'] = math.floor(window['next_external_native_sec'])
    hazard = [{'edge_id': edge, 'mode': mode, 'closure_sec': changes.get((edge, mode), '')}
              for mode, graph in data.items() for edge in sorted(graph['nodes'])]
    write_csv(directory / 'hazard.csv', hazard)
    origin_edge = ('g0' if case.startswith('car_lane_') else 'd0' if case.startswith('pickup_internal')
                   else 'long' if case == 'walk_budget' else 'e0')
    backward = case == 'walk_reverse' or case.startswith('car_backward_')
    terminal_edge = 'long' if case == 'walk_budget' else 'e0' if backward else 'e2'
    start_pos = 80 if backward else 20
    end_pos = 3020 if case == 'walk_budget' else 20 if backward else 50
    if case.startswith('walk_short_'):
        start_pos = data['pedestrian']['nodes']['e0']['length'] / 2
        if not all(end_pos > data['pedestrian']['nodes'][edge]['length'] for edge in ('e0', 'd0')):
            raise ValueError('Short-walk fixture requires terminal position longer than its source lane')
    if case == 'horizon_alighting':
        lengths = data['passenger']['nodes']
        estimate = (params['simulation']['dispatch_sec'] + 1 / 5 + start_pos / 5
                    + params['operation']['boarding_sec']
                    + (lengths['e0']['length'] - start_pos + lengths['e1']['length'] + end_pos) / 5
                    + params['operation']['alighting_sec'])
        parameters['simulation']['duration_sec'] = math.ceil(estimate)
    terms = [{'terminal_id': 'facility', 'kind': 'facility', 'edge_id': terminal_edge,
              'capacity': 1 if case == 'shared_capacity' else 10}]
    if case == 'shared_capacity':
        terms.append({'terminal_id': 'exit', 'kind': 'boundary_exit', 'edge_id': terminal_edge, 'capacity': ''})
    people, origins, positions = [], [], []
    for i in range(3 if case == 'shared_capacity' else 2 if case.startswith('walk_short_') else 1):
        origin, pid = 'origin_' + str(i), 'fixture_person_' + str(i)
        terminal = 'exit' if case == 'shared_capacity' and i == 2 else 'facility'
        people.append({'person_id': pid, 'source_person_id': pid, 'origin_id': origin,
                       'person_type': 'type4' if case.startswith('walk_short_') and i == 1 else 'type3',
                       'base_mode': 'car' if case.startswith('car_') else 'walk',
                       'vehicle_id': 'fixture_car' if case.startswith('car_') else '',
                       'ready_sec': 0, 'intent_u05': str(drt), 'intent_u50': str(drt)})
        path = (['d0', 'd1', 'd2', 'e2'] if case.startswith('pickup_internal') else
                ['g0', 'e0', 'e1', 'e2'] if case.startswith('car_lane_') else
                ['long'] if case == 'walk_budget' else ['e0'] if backward else ['e0', 'e1', 'e2'])
        origins.append({'origin_id': origin, 'edge_id': origin_edge, 'terminal_id': terminal,
                        'car_route': json.dumps(path), 'walk_route': json.dumps(path),
                        'walk_length_m': sum(data['pedestrian']['nodes'][n]['length'] for n in path)})
        person_start_pos = (data['pedestrian']['nodes']['e0']['length'] * (1 + 2 * i) / 4
                            if case.startswith('walk_short_') else start_pos)
        positions.append({'kind': 'origin', 'place_id': origin, 'car_pos_m': person_start_pos,
                          'pedestrian_pos_m': person_start_pos})
    positions.extend({'kind': 'terminal', 'place_id': term['terminal_id'], 'car_pos_m': end_pos,
                      'pedestrian_pos_m': end_pos} for term in terms)
    write_csv(directory / 'terminals.csv', terms)
    write_csv(directory / 'origins.csv', origins)
    write_csv(directory / 'destinations_fixed_reference.csv', origins)
    write_csv(directory / 'people.csv', people)
    write_csv(directory / f'common_realization_seed{params["seeds"][0]}.csv', people)
    write_csv(directory / 'place_positions.csv', positions)
    atomic_json(directory / 'fixture_parameters.json', parameters)
    manifest = {'protocol': parameters['protocol'], 'fixture_case': case, 'research_adoption_permitted': False,
                'depot_edge': 'g0', 'people': len(people), 'created_at_jst': stamp(),
                'base_parameter_sha256': sha(PARAM), 'synthetic_conditions': True,
                'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in (Path(__file__), PARAM)},
                'artifacts': {p.name: sha(p) for p in directory.iterdir() if p.is_file()}}
    if timing is not None:
        manifest['native_timing_reference'] = timing
        manifest['source_sha256'].update(timing['source_sha256'])
    atomic_json(directory / 'manifest.json', manifest)
    return directory


def evaluate(case, directory, result):
    def table(name):
        with (directory / name).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))
    people, requests = table('person_results.csv'), table('request_results.csv')
    events = [json.loads(line) for line in (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    outcomes = Counter(p['status'] for p in people)
    counts = result['summary']['counts']
    checks = {'same_real_controller_completed': result['status'] == 'COMPLETED',
              'technical_only': result['purpose'] == 'fixture' and result['protocol'] == 'realtime_choice_fixture_v1'
                                and result['research_adoption_permitted'] is False,
              'zero_physical_errors': all(counts[k] == 0 for k in ('teleports', 'collisions', 'closed_entry_rows',
                 'ambiguous_transitions', 'missing_vehicle_subscriptions', 'missing_person_subscriptions')),
              'sumo_error_zero': result['summary']['sumo_errors']['error_count'] == 0,
              'all_output_hashes': all(sha(directory / name) == expected for name, expected in result['output_sha256'].items())}
    if case == 'walk_reroute':
        checks['reroute_exercised'] = any(e['event'] == 'walk_reroute' for e in events)
        checks['admitted_after_reroute'] = outcomes == Counter(admitted=1)
    elif case == 'walk_reroute_limit':
        plans = [e for e in events if e['event'] == 'walk_plan' and e['stage'] == 'reroute']
        checks['reroute_plan_exceeds_cumulative_budget'] = any(
            max(e['model_passed_m'], e['speed_integral_m']) + e['sumo_plan_length_m'] > 3000 for e in plans)
        checks['walk_limit_preserves_person'] = outcomes == Counter(walk_limit=1)
    elif case == 'walk_budget':
        stops = [e for e in events if e['event'] == 'walk_budget_pre_step_stop']
        checks['budget_stop_exercised'] = bool(stops) and all(0 <= e['remaining_budget_m'] < e['max_next_step_m'] for e in stops)
        checks['walk_limit_no_overshoot'] = outcomes == Counter(walk_limit=1) and float(people[0]['walk_speed_integral_m']) <= 3000
    elif case == 'walk_reverse':
        checks['same_edge_reverse_arrived'] = outcomes == Counter(admitted=1)
        checks['reverse_plan_length'] = any(e['event'] == 'walk_plan' and e['sumo_plan_length_m'] == 60 for e in events)
    elif case == 'pickup_closure':
        checks['assigned_vehicle_failure_fallback_once'] = (requests[0]['status'] == 'cancelled_vehicle_failure'
            and sum(e['event'] == 'fallback_attempt' for e in events) == 1)
        checks['no_boarding'] = requests[0]['boarding_started_sec'] == ''
    elif case in ('pickup_deadline_equal', 'pickup_before_deadline', 'pickup_internal_calibration',
                  'pickup_internal_timeout', 'pickup_internal_timeout_closed_next'):
        q = requests[0]
        source = json.loads((directory.parent / 'fixture_inputs/manifest.json').read_text(encoding='utf-8'))
        if case == 'pickup_internal_calibration':
            cfg = json.loads((directory.parent / 'fixture_inputs/fixture_parameters.json').read_text(encoding='utf-8'))
            reference = native_pickup_reference(directory, cfg['simulation']['controller_sec'], cfg['simulation']['step_sec'])
            checks['native_internal_pickup_window_observed'] = bool(reference['internal_windows'])
            checks['calibration_service_completed'] = q['status'] == 'served'
        elif case == 'pickup_before_deadline':
            checks['boarding_before_deadline_then_continues'] = (q['status'] == 'served'
                and float(q['boarding_started_sec']) < float(q['deadline_sec']) < float(q['boarded_sec'])
                and float(q['boarding_started_sec']) == source['native_timing_reference']['native_boarding_started_sec'])
            checks['no_fallback_after_boarding'] = not any(e['event'] == 'fallback_attempt' for e in events)
        else:
            checks['accepted_then_deadline_cancel_without_boarding'] = (q['status'] == 'cancelled_timeout'
                and q['accepted_sec'] != '' and float(q['accepted_sec']) < float(q['cancel_sec']) == float(q['deadline_sec'])
                and q['boarding_started_sec'] == '')
            checks['one_fallback_same_origin_terminal'] = sum(e['event'] == 'fallback_attempt' for e in events) == 1
            if case == 'pickup_deadline_equal':
                checks['deadline_equals_native_boarding_reference'] = float(q['deadline_sec']) == source['native_timing_reference']['native_boarding_started_sec']
            else:
                with gzip.open(directory / 'actor_observations.csv.gz', 'rt', encoding='utf-8') as stream:
                    at_deadline = [r for r in csv.DictReader(stream) if r['actor_id'] == q['vehicle_id']
                                   and float(r['time_sec']) == float(q['deadline_sec'])]
                checks['cancellation_occurs_on_native_internal'] = len(at_deadline) == 1 and at_deadline[0]['road_id'].startswith(':')
                if case == 'pickup_internal_timeout':
                    checks['later_safe_external_wait_without_respawn'] = any(e['event'] == 'cancel_wait_route'
                        and e['vehicle_id'] == q['vehicle_id'] and e['time_sec'] > float(q['cancel_sec'])
                        and not e['source_edge'].startswith(':') for e in events)
                else:
                    checks['closed_next_external_removes_cancelled_vehicle'] = any(e['event'] == 'actor_removed'
                        and e['actor_id'] == q['vehicle_id'] and e['time_sec'] > float(q['cancel_sec']) for e in events)
    elif case in ('boarding_closure', 'alighting_closure'):
        field = 'boarding_started_sec' if case == 'boarding_closure' else 'alighting_started_sec'
        checks['failure_during_registered_service_phase'] = requests[0][field] != '' and requests[0]['status'] == 'failed_after_boarding'
        checks['no_origin_return_after_boarding'] = not any(e['event'] == 'fallback_attempt' for e in events)
        checks['stranded_account'] = outcomes == Counter(stranded_drt=1)
    elif case.startswith('forecast_'):
        with gzip.open(directory / 'candidates.csv.gz', 'rt', encoding='utf-8') as stream:
            candidates = list(csv.DictReader(stream))
        if case == 'forecast_p0':
            checks['forecast_only_rejection_exercised'] = any(p['reason'] == 'forecast_gate'
                and p['pickup_route'] == p['delivery_route'] == p['pickup_before_deadline']
                == p['completion_within_horizon'] == 'True' for p in candidates)
            checks['never_accepted_then_one_timeout_fallback'] = requests[0]['accepted_sec'] == '' and requests[0]['status'] == 'cancelled_timeout'
            checks['one_timeout_fallback'] = sum(e['event'] == 'fallback_attempt' for e in events) == 1
        elif case == 'forecast_reroute':
            checks['forecast_rejection_before_native_closure'] = any(p['reason'] == 'forecast_gate' for p in candidates)
            selected = [p for p in candidates if p['decision'] == 'selected']
            checks['postclosure_current_detour_accepted'] = (requests[0]['status'] == 'served' and bool(selected)
                and all(float(p['time_sec']) > 700 and 'e1' not in json.loads(p['delivery_path']) for p in selected))
        else:
            checks['service_accepted_and_completed'] = requests[0]['status'] == 'served'
            checks['forecast_mode_respected'] = any(p['forecast_remaining_kind'] == ('not_applicable'
                if case == 'forecast_r1' else 'finite') for p in candidates)
    elif case == 'shared_capacity':
        checks['single_shared_capacity_and_separate_exit'] = outcomes == Counter(admitted=1, capacity_rejected=1, boundary_exit=1)
        checks['facility_account'] = table('facility_results.csv')[0]['admitted'] == '1'
    elif case == 'horizon_alighting':
        phases = [e['previous_status'] for e in events if e['event'] == 'horizon_finalize']
        checks['active_service_at_horizon'] = len(phases) == 1 and phases[0] in ('boarding', 'onboard', 'alighting')
        checks['horizon_account_no_false_admission'] = requests[0]['status'] == 'time_limit' and outcomes == Counter(time_limit=1)
    elif case == 'car_backward_cycle':
        departures = [e for e in events if e['event'] == 'private_departure_requested']
        checks['forward_cycle_for_backward_target'] = (outcomes == Counter(admitted=1) and len(departures) == 1
            and departures[0]['route'][0] == departures[0]['route'][-1] == 'e0'
            and len(departures[0]['route']) > 1 and departures[0]['depart_pos'] > departures[0]['arrival_pos'])
    elif case == 'car_backward_no_cycle':
        checks['no_reverse_or_teleport_when_no_cycle'] = outcomes == Counter(no_route=1) and not any(
            e['event'] == 'private_departure_requested' for e in events)
    elif case == 'car_reroute':
        changes = [e for e in events if e['event'] == 'private_reroute']
        checks['private_detour_with_explicit_route_version'] = outcomes == Counter(admitted=1) and bool(changes) and all(
            e['route_version'] > 0 and 'e1' not in e['requested_remaining_route'] for e in changes)
    elif case.startswith('walk_short_'):
        with gzip.open(directory / 'actor_observations.csv.gz', 'rt', encoding='utf-8-sig', newline='') as stream:
            frames = {(row['actor_id'], float(row['time_sec'])): row for row in csv.DictReader(stream)}
        cfg = json.loads((directory.parent / 'fixture_inputs/fixture_parameters.json').read_text(encoding='utf-8'))
        topology = json.loads((directory.parent / 'fixture_inputs/graphs.json').read_text(encoding='utf-8'))
        expected_sources = ['e0', 'd0'] if case == 'walk_short_repeated' else ['e0']
        plans = [e for e in events if e['event'] == 'walk_plan' and e['stage'] == 'reroute']
        per_person, native_directions, receipts, speed_contract = [], [], [], []
        for person in people:
            pid = person['person_id']
            own = [e for e in plans if e['person_id'] == pid]
            per_person.append([e['route'][0] for e in own] == expected_sources)
            for index, plan in enumerate(own):
                before = frames.get((pid, plan['time_sec']))
                after = frames.get((pid, plan['time_sec'] + cfg['simulation']['step_sec']))
                native_directions.append(bool(before and after and before['road_id'] == after['road_id'] == plan['route'][0]
                    and (float(after['lane_position_m']) - float(before['lane_position_m'])) * (1 if index == 0 else -1) > 0))
                replacement = plan['replacement_receipts']
                receipts.append(len(replacement) == 2 and [r['purpose'] for r in replacement] == ['old_remaining', 'new_route']
                    and all(all(r['before'][key] == r['after'][key] for key in ('edge_id', 'lane_position_m', 'xy'))
                            for r in replacement)
                    and plan['arrival_pos'] > topology['pedestrian']['nodes'][plan['route'][0]]['length'])
                registered = cfg['population']['walk_mps'][person['person_type']]
                speed_contract.append(plan['enforced_stage_speed_mps'] == registered
                    and plan['person_speed_factor'] == cfg['technical_walk_speed_factors'][person['person_type']]
                    and plan['person_max_mps'] < registered)
        checks['both_type3_type4_fixture_people'] = {p['person_type'] for p in people} == {'type3', 'type4'}
        checks['all_people_short_edge_reroute_sequence'] = bool(per_person) and all(per_person)
        checks['native_forward_then_reverse_positions'] = bool(native_directions) and all(native_directions)
        checks['two_unchanged_native_replacement_receipts_per_plan'] = bool(receipts) and all(receipts)
        checks['both_types_getter_below_registered_stage_speed'] = bool(speed_contract) and all(speed_contract)
        native_log = (directory / 'sumo_errors.log').read_text(encoding='utf-8', errors='replace')
        checks['native_invalid_departpos_positive_exact_receipt_count'] = (
            len(re.findall(r'Invalid departPos', native_log)) == sum(len(e['replacement_receipts']) for e in plans) > 0)
        checks['all_fixture_walkers_reach_fixed_terminal'] = all(p['status'] == 'admitted' for p in people)
        if case == 'walk_short_calibration':
            reference = native_walk_reference(directory, cfg['simulation']['step_sec'])
            checks['shared_native_second_short_edge_frame'] = bool(reference['source_frames'])
    elif case.startswith('car_lane_'):
        native_log = (directory / 'sumo_errors.log').read_text(encoding='utf-8', errors='replace')
        checks['no_native_emergency_braking_or_stop'] = not re.search(
            r'emergency braking|emergency stop', native_log, re.IGNORECASE)
        if case == 'car_lane_calibration':
            cfg = json.loads((directory.parent / 'fixture_inputs/fixture_parameters.json').read_text(encoding='utf-8'))
            reference = native_lane_reference(directory, cfg['simulation']['step_sec'])
            checks['native_short_lane_counterexample_observed'] = reference['remaining_lane_m'] < reference['braking_room_m']
            checks['calibration_completes_without_controlled_reroute'] = (outcomes == Counter(admitted=1)
                and not any(e['event'] == 'private_reroute' for e in events))
        else:
            source = json.loads((directory.parent / 'fixture_inputs/manifest.json').read_text(encoding='utf-8'))
            reference = source['native_timing_reference']
            decisions = [e for e in events if e['event'] == 'vehicle_route_feasibility'
                         and e['vehicle_id'] == 'fixture_car' and e['time_sec'] == reference['source_time_sec']]
            checks['same_native_lane_and_braking_counterexample'] = (len(decisions) == 1
                and decisions[0]['source_lane_id'] == reference['source_lane_id']
                and decisions[0]['source_lane_position_m'] == reference['source_lane_position_m']
                and decisions[0]['first_turn_constrained']
                and 'd0' not in decisions[0]['open_lane_successors'])
            if case == 'car_lane_alternative':
                checks['native_connected_alternative_continues'] = (outcomes == Counter(admitted=1)
                    and len(decisions) == 1 and decisions[0]['requested_remaining_route'][1] == 's0'
                    and any(e['event'] == 'private_reroute' for e in events))
            else:
                checks['no_native_connection_preserves_route_cut'] = (outcomes == Counter(route_cut=1)
                    and len(decisions) == 1 and decisions[0]['requested_remaining_route'] == []
                    and not any(e['event'] == 'private_reroute' for e in events))
    return {'case': case, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'outcomes': dict(outcomes), 'request_states': dict(Counter(p['status'] for p in requests)),
            'event_counts': dict(Counter(e['event'] for e in events)),
            'sumo_log_summary': result['summary']['sumo_errors'],
            'execution_manifest_sha256': sha(directory / 'manifest.json')}


def run_suite(run_id, selected_case=None):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', run_id):
        raise ValueError('Use a new simple fixture suite ID up to 64 characters')
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    parent = ROOT / params['workspace'] / 'technical' / run_id
    parent.mkdir(parents=True, exist_ok=False)
    manifest = {'protocol': 'realtime_choice_fixture_suite_v1', 'purpose': 'technical_fixture_suite',
                'run_id': run_id, 'pid': os.getpid(), 'status': 'RUNNING', 'started_at_jst': stamp(),
                'research_adoption_permitted': False, 'factory_sha256': sha(Path(__file__)), 'cases': []}
    archived = parent / 'factory.py'
    archived.write_bytes(Path(__file__).read_bytes())
    atomic_json(parent / 'manifest.json', manifest)
    try:
        selected = (('walk_short_calibration', 'walk_short_repeated')
                    if selected_case == 'walk_short_repeated' else (selected_case,) if selected_case else CASES)
        for case in selected:
            if case not in CASES:
                raise ValueError('Unknown fixture case')
            child = run_id + '_c' + str(CASES.index(case) + 1).zfill(2)
            directory = prepare(case, child, params)
            result = run('fixture_' + case, child, purpose='fixture', fixture_directory=directory)
            report = evaluate(case, directory.parent / 'execution', result)
            report['child_run_id'] = child
            atomic_json(directory.parent / 'case_validation.json', report)
            manifest['cases'].append(report)
            atomic_json(parent / 'progress.json', {'at_jst': stamp(), 'completed_cases': len(manifest['cases']),
                                                  'last_case': case, 'last_status': report['status'], 'child_run_id': child})
            if report['status'] != 'PASS':
                raise RuntimeError('Integrated fixture failed: ' + case)
        manifest.update(status='COMPLETED', finished_at_jst=stamp())
        atomic_json(parent / 'manifest.json', manifest)
        return manifest
    except BaseException as error:
        (parent / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        manifest.update(status='FAILED', finished_at_jst=stamp(), error_type=type(error).__name__, error=str(error))
        atomic_json(parent / 'manifest.json', manifest)
        raise
