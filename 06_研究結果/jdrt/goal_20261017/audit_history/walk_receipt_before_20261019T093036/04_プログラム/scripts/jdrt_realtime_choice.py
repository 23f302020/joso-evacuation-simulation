"""Physical vehicle controls for realtime_choice_v1. Core runner is not ready yet."""

def clear_vehicle_stops(connection, vehicle_id):
    """Release an active stop and remove all scheduled stops without teleporting."""
    if connection.vehicle.isStopped(vehicle_id):
        connection.vehicle.resume(vehicle_id)
    while connection.vehicle.getStops(vehicle_id):
        connection.vehicle.replaceStop(vehicle_id, 0, '', teleport=0)


def set_vehicle_route(connection, vehicle_id, path, lane_info, duration, stop_pos=None):
    from traci.constants import STOP_PARKING
    current = connection.vehicle.getRoadID(vehicle_id)
    if not path or current.startswith(':') or path[0] != current:
        raise ValueError('Route update must start on current external edge')
    target = path[-1]
    lane, length = lane_info[target]
    stop_pos = length - 1 if stop_pos is None else stop_pos
    if not 0 <= stop_pos <= length:
        raise ValueError('Stop position outside target lane')
    clear_vehicle_stops(connection, vehicle_id)
    connection.vehicle.setRoute(vehicle_id, path)
    connection.vehicle.setStop(vehicle_id, target, pos=stop_pos,
                               laneIndex=lane, duration=duration,
                               flags=STOP_PARKING)
    return list(connection.vehicle.getRoute(vehicle_id))


def cancel_vehicle_to_wait(connection, vehicle_id, lane_info, duration, step_sec):
    """Return None while inside a junction or lacking braking room; retain physical position."""
    current = connection.vehicle.getRoadID(vehicle_id)
    if not current or current.startswith(':'):
        return None
    lane, length = lane_info[current]
    position = connection.vehicle.getLanePosition(vehicle_id)
    speed = connection.vehicle.getSpeed(vehicle_id)
    deceleration = connection.vehicle.getDecel(vehicle_id)
    if not connection.vehicle.isStopped(vehicle_id):
        braking_room = speed * speed / (2 * deceleration) + speed * step_sec + 1
        if length - 1 - position < braking_room:
            return None
    if length - 1 < position:
        return None
    if connection.vehicle.isStopped(vehicle_id):
        from traci.constants import STOP_PARKING
        stops = connection.vehicle.getStops(vehicle_id)
        if not stops or stops[0].lane.rsplit('_', 1)[0] != current:
            raise ValueError('Stopped vehicle lacks its current stop')
        for index in reversed(range(1, len(stops))):
            connection.vehicle.replaceStop(vehicle_id, index, '', teleport=0)
        connection.vehicle.setRoute(vehicle_id, [current])
        connection.vehicle.setStop(vehicle_id, current, pos=stops[0].endPos,
                                   laneIndex=int(stops[0].lane.rsplit('_', 1)[1]),
                                   duration=duration, flags=STOP_PARKING)
        return list(connection.vehicle.getRoute(vehicle_id))
    return set_vehicle_route(connection, vehicle_id, [current], lane_info, duration)


def traffic_observation_state(stop_state, position_valid, reentry_expected, departure_pending=False):
    if stop_state & 2:
        return 'parked'
    if not position_valid:
        if departure_pending:
            return 'departure_pending'
        return 'reentry_pending' if reentry_expected else 'missing'
    return 'onroad'

from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
import os
import time
import traceback
import xml.etree.ElementTree as ET
import networkx as nx
from scripts.jdrt.smoke import resolve_sumo_binary, load_traci
from scripts.jdrt.full_run import summarize_sumo_error_log
from scripts.jdrt_realtime_choice_inputs import read_csv, sha
from scripts.jdrt_choice_policy import candidate_checks, request_transition, unboarded_expired
ROOT = Path(__file__).resolve().parents[2]
PARAM = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'
FINAL = {'admitted','boundary_exit','capacity_rejected','no_origin_connection','no_route','walk_limit','initial_or_current_closed','route_cut','stranded_drt','time_limit'}


def stamp():return datetime.now(timezone(timedelta(hours=9))).isoformat()

def atomic_json(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for attempt in range(6):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.2)

def load_graphs(directory):
    raw=json.loads((directory/'graphs.json').read_text(encoding='utf-8'));graphs={}
    for mode,data in raw.items():
        g=nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from((n,a) for n,a in data['nodes'].items());g.add_edges_from((a,b,d) for a,b,d in data['edges']);graphs[mode]=g
    return graphs

def route(graph,start,end,weight='length'):
    try:return nx.shortest_path(graph,start,end,weight=weight)
    except (nx.NodeNotFound,nx.NetworkXNoPath):return []

def positioned_car_route(graph, start, target, start_pos, target_pos, weight='free_sec',
                         minimum_advance=0, source_tree=None, first_successors=None):
    """Forward motion only, including a cycle for a target behind the current front."""
    if start not in graph or target not in graph:
        return [], math.inf
    length_start, length_target = graph.nodes[start]['length'], graph.nodes[target]['length']
    if not (0 <= start_pos <= length_start and 0 <= target_pos <= length_target):
        raise ValueError('Car position outside edge')
    node_time = lambda n: graph.nodes[n][weight]
    edge_time = lambda a, b, data: node_time(b)
    if start == target and target_pos - start_pos >= minimum_advance:
        return [start], node_time(start) * (target_pos - start_pos) / length_start
    if start == target or first_successors is not None:
        candidates = []
        for following in sorted(graph.successors(start)):
            if first_successors is not None and following not in first_successors:
                continue
            try:
                cost, path = nx.single_source_dijkstra(graph, following, target, weight=edge_time)
                candidates.append((node_time(following) + cost, [start] + path))
            except nx.NetworkXNoPath:
                continue
        if not candidates:
            return [], math.inf
        cost, path = min(candidates, key=lambda item: (item[0], item[1]))
    else:
        if source_tree is None:
            try:
                cost, path = nx.single_source_dijkstra(graph, start, target, weight=edge_time)
            except nx.NetworkXNoPath:
                return [], math.inf
        else:
            distances, paths = source_tree
            if target not in paths:
                return [], math.inf
            cost, path = distances[target], paths[target]
    time_sec = (cost + node_time(start) * (length_start - start_pos) / length_start
                - node_time(target) * (length_target - target_pos) / length_target)
    if time_sec < -1e-8:
        raise ValueError('Negative position-adjusted travel time')
    return path, max(0, time_sec)


def lane_constrained_car_route(graph, start, target, start_pos, target_pos,
                               lane_length, lane_successors, speed, deceleration,
                               step_sec, stopped=False, weight='free_sec'):
    """Avoid a new non-native first turn when normal braking room is exhausted."""
    braking = speed * speed / (2 * deceleration) + speed * step_sec + 1 if not stopped else 0
    remaining = lane_length - start_pos
    constrained = remaining < braking
    successors = sorted(set(lane_successors) & set(graph.successors(start))) if start in graph else []
    path, travel = positioned_car_route(graph, start, target, start_pos, target_pos,
        weight, minimum_advance=braking, first_successors=successors if constrained else None)
    receipt = {'source_edge': start, 'source_lane_position_m': start_pos,
               'source_lane_length_m': lane_length, 'remaining_lane_m': remaining,
               'source_speed_mps': speed, 'source_decel_mps2': deceleration,
               'step_sec': step_sec, 'stopped': stopped, 'braking_room_m': braking,
               'first_turn_constrained': constrained, 'open_lane_successors': successors,
               'requested_remaining_route': path}
    return path, travel, receipt


def native_parking_stop(connection, vehicle_id):
    stops = connection.vehicle.getStops(vehicle_id, limit=1)
    if not stops:
        raise ValueError('Parked vehicle lacks its native current stop')
    stop = stops[0]
    return {'lane_id': stop.lane, 'start_pos_m': stop.startPos,
            'end_pos_m': stop.endPos, 'flags': stop.stopFlags}


def vehicle_path_source(connection, vehicle_id, net):
    """Keep an empty native lane distinct from a parked stop's reference lane."""
    vehicle = connection.vehicle
    raw = {'road_id': vehicle.getRoadID(vehicle_id), 'lane_id': vehicle.getLaneID(vehicle_id),
           'lane_position_m': vehicle.getLanePosition(vehicle_id), 'speed_mps': vehicle.getSpeed(vehicle_id),
           'decel_mps2': vehicle.getDecel(vehicle_id), 'stop_state': vehicle.getStopState(vehicle_id),
           'route': list(vehicle.getRoute(vehicle_id)), 'route_index': vehicle.getRouteIndex(vehicle_id)}
    reference = raw['lane_id']
    kind, stop = 'onroad_lane', None
    if not reference:
        if raw['stop_state'] & 3 != 3 or raw['speed_mps'] != 0:
            raise ValueError('Empty vehicle lane lacks native stopped parking state')
        stop = native_parking_stop(connection, vehicle_id)
        reference, kind = stop['lane_id'], 'parked_stop'
    lane = net.getLane(reference)
    position, index = raw['lane_position_m'], raw['route_index']
    if (lane.getEdge().getID() != raw['road_id'] or not lane.allows('passenger')
            or not math.isfinite(position) or not 0 <= position <= lane.getLength()
            or not 0 <= index < len(raw['route']) or raw['route'][index] != raw['road_id']
            or not all(math.isfinite(raw[k]) for k in ('speed_mps', 'decel_mps2'))
            or raw['speed_mps'] < 0 or raw['decel_mps2'] <= 0):
        raise ValueError('Vehicle native source contradicts lane, route or position')
    if stop and (not stop['flags'] & 1 or not 0 <= stop['start_pos_m'] <= position <= stop['end_pos_m'] <= lane.getLength()
                 or raw['route'][-1] != raw['road_id']):
        raise ValueError('Parked vehicle position contradicts its native current stop')
    return lane, {'source_kind': kind, 'source_reference_lane_id': reference,
                  'native_source': raw, 'native_parking_stop': stop}


def replace_walk_stage_receipt(connection, person_id, index, stage, purpose):
    """Capture native position/stage bytes around one unchanged replaceStage call."""
    def snapshot():
        actual = connection.person.getStage(person_id, index)
        return {'edge_id': connection.person.getRoadID(person_id),
                'lane_position_m': connection.person.getLanePosition(person_id),
                'xy': list(connection.person.getPosition(person_id)),
                'stage_edges': list(actual.edges), 'stage_arrival_pos_m': actual.arrivalPos,
                'stage_length_m': actual.length}
    receipt = {'purpose': purpose, 'stage_index': index, 'requested_edges': list(stage.edges),
               'requested_depart_pos_m': stage.departPos,
               'requested_arrival_pos_m': stage.arrivalPos, 'before': snapshot()}
    connection.person.replaceStage(person_id, index, stage)
    receipt['after'] = snapshot()
    for key in ('edge_id', 'lane_position_m', 'xy'):
        if receipt['before'][key] != receipt['after'][key]:
            raise RuntimeError('Walking stage replacement moved the person')
    return receipt


def pedestrian_endpoint_topology(net, eligible):
    """Undirected lane endpoints retain direction and partial-edge distances."""
    topology = nx.Graph()
    for edge in net.getEdges(withInternal=True):
        name = edge.getID()
        if (name in eligible or name.startswith(':')) and edge.allows('pedestrian'):
            lane = next(l for l in edge.getLanes() if l.allows('pedestrian'))
            topology.add_edge((name, 0), (name, 1), length=lane.getLength())
    for edge in net.getEdges(withInternal=True):
        if (edge.getID(), 0) not in topology:
            continue
        for other, connections in edge.getAllowedOutgoing('pedestrian').items():
            internal, _ = net.getInternalPath(connections)
            chain = [edge] + (internal or []) + [other]
            if all((item.getID(), 0) in topology for item in chain):
                for a, b in zip(chain, chain[1:]):
                    topology.add_edge((a.getID(), 1), (b.getID(), 0), length=0.)
    return topology


def positioned_walk_route(topology, start, target, start_pos, target_pos):
    if (start, 0) not in topology or (target, 0) not in topology:
        return [], math.inf
    start_length = topology[start, 0][start, 1]['length']
    target_length = topology[target, 0][target, 1]['length']
    if not (0 <= start_pos <= start_length and 0 <= target_pos <= target_length):
        raise ValueError('Pedestrian position outside lane')
    a, b = ('__position_start__', 0), ('__position_target__', 0)
    try:
        for point, edge, pos, length in [(a, start, start_pos, start_length),
                                        (b, target, target_pos, target_length)]:
            topology.add_edge(point, (edge, 0), length=pos)
            topology.add_edge(point, (edge, 1), length=length - pos)
        if start == target:
            topology.add_edge(a, b, length=abs(target_pos - start_pos))
        distance, nodes = nx.single_source_dijkstra(topology, a, b, weight='length')
        path = [start]
        for edge, _ in nodes[1:-1]:
            if not edge.startswith(':') and path[-1] != edge:
                path.append(edge)
        if path[-1] != target:
            path.append(target)
        return path, distance
    except nx.NetworkXNoPath:
        return [], math.inf
    finally:
        topology.remove_nodes_from([a, b])


def allocate_arrivals(arrivals,people,terminals,occupancy,now):
    """One shared capacity account across all modes; deterministic same-tick ties."""
    for pid in sorted(set(arrivals)):
        person=people[pid];terminal=terminals[person['terminal_id']]
        person['arrival_sec']=now
        if terminal['kind']=='boundary_exit':person['status']='boundary_exit'
        elif occupancy[terminal['terminal_id']]<int(terminal['capacity']):
            occupancy[terminal['terminal_id']]+=1;person['status']='admitted';person['admitted_sec']=now
        else:person['status']='capacity_rejected'

def rank_candidates(candidates,forecast_enabled,weights=None):
    weights=weights or {'waiting':1,'vulnerability':1,'pickup':1,'flood':1}
    feasible=[c for c in candidates if c['reason']=='eligible']
    max_wait=max((c['waiting_sec'] for c in feasible),default=0)
    max_pickup=max((c['pickup_sec'] for c in feasible),default=0)
    max_urgency=max((c['urgency'] for c in feasible),default=0)
    for c in feasible:
        c['score']=weights['waiting']*(c['waiting_sec']/max_wait if max_wait else 0)+weights['vulnerability']*c['vulnerability']-weights['pickup']*(c['pickup_sec']/max_pickup if max_pickup else 0)
        if forecast_enabled:c['score']+=weights['flood']*(c['urgency']/max_urgency if max_urgency else 0)
    return min(feasible,key=lambda c:(-c['score'],c['person_id'],c['vehicle_id']),default=None)

def remove_sumo_actor(connection,actor,mode):
    domain=connection.person if mode=='pedestrian' else connection.vehicle
    domain.unsubscribe(actor)
    domain.remove(actor)

def apply_remaining_route(connection,actor,path,route_id):
    if not path or connection.vehicle.getRoadID(actor)!=path[0]:
        raise ValueError('Remaining route must begin at the current external edge')
    stopped=connection.vehicle.isStopped(actor)
    connection.route.add(route_id,path)
    connection.vehicle.setRouteID(actor,route_id)
    if stopped:connection.vehicle.resume(actor)

def pedestrian_closure_action(path,current,previous_external,closed):
    if not current:return 'defer',''
    internal=current.startswith(':')
    reference=previous_external or path[0] if internal else current
    index=path.index(reference)
    remaining=path[index+1:] if internal else path[index:]
    if not set(remaining)&closed:return 'clear',''
    if not internal:return ('remove_current' if current in closed else 'reroute'),''
    next_external=remaining[0]
    return ('remove_junction' if next_external in closed else 'defer'),next_external

def vehicle_closure_action(path,current,route_index,closed):
    if not current:return 'defer',''
    if not 0<=route_index<len(path):raise ValueError('Vehicle route index outside controlled path')
    internal=current.startswith(':')
    if not internal and path[route_index]!=current:raise ValueError('Vehicle route index and current edge disagree')
    remaining=path[route_index+1:] if internal else path[route_index:]
    if not set(remaining)&closed:return 'clear',''
    if not internal:return ('remove_current' if current in closed else 'reroute'),''
    next_external=remaining[0]
    return ('remove_junction' if next_external in closed else 'defer'),next_external

def closure_timing(scheduled_sec,step_sec):
    if not math.isfinite(scheduled_sec) or scheduled_sec<0 or step_sec<=0:
        raise ValueError('Invalid closure clock')
    if not math.isclose(scheduled_sec/step_sec,round(scheduled_sec/step_sec),abs_tol=1e-9):
        raise ValueError('Closure must be on the simulation grid')
    call_sec=max(0,scheduled_sec-step_sec)
    return {'scheduled_sec':scheduled_sec,'control_call_sec':call_sec,
            'observation_upper_sec':scheduled_sec,'control_lead_sec':scheduled_sec-call_sec,
            'phase':'initial_before_observation' if scheduled_sec==0 else 'before_step_ending_at_closure'}


def write_csv(path, rows, fields=None):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def dispatch_forecast(scenario, hazard, parameters):
    if not scenario.startswith('R2'):
        return None
    error = parameters['forecast'][scenario]['scheduled_time_error_sec']
    return {row['edge_id']: int(row['closure_sec']) + error for row in hazard
            if row['mode'] == 'passenger' and row['closure_sec'] != ''}


def load_inputs():
    parameters = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / parameters['workspace'] / parameters['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for path, expected in manifest['source_sha256'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('Input source SHA mismatch: ' + path)
    for path, expected in manifest['artifacts'].items():
        if sha(directory / path) != expected:
            raise ValueError('Input artifact SHA mismatch: ' + path)
    return parameters, directory, manifest


def technical_ready_times(people):
    """Shorten smoke readiness without separating a private vehicle's crew."""
    groups = {}
    result = {}
    for index, person in enumerate(people):
        key = ('vehicle', person['vehicle_id']) if person['vehicle_id'] else ('person', person['person_id'])
        groups.setdefault(key, index % 10)
        result[person['person_id']] = groups[key]
    return result


def run(cell_id, run_id, purpose='core', smoke_end=1800, fixture_directory=None):
    parameters, directory, input_manifest = load_inputs()
    parameter_path = PARAM
    if purpose == 'fixture':
        expected = ROOT / parameters['workspace'] / 'technical' / run_id / 'fixture_inputs'
        if fixture_directory is None or Path(fixture_directory).resolve() != expected.resolve():
            raise ValueError('Fixture inputs must be isolated under their unique technical run ID')
        directory = expected
        parameter_path = directory / 'fixture_parameters.json'
        fixture_parameters = json.loads(parameter_path.read_text(encoding='utf-8'))
        if (fixture_parameters['protocol'] != 'realtime_choice_fixture_v1'
                or fixture_parameters['workspace'] != parameters['workspace']
                or fixture_parameters['execution'] != parameters['execution']):
            raise ValueError('Invalid technical fixture protocol/workspace/implementation set')
        parameters = fixture_parameters
        input_manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if input_manifest['research_adoption_permitted'] is not False:
            raise ValueError('Technical fixture must forbid research adoption')
        for name, expected_sha in input_manifest['source_sha256'].items():
            if sha(ROOT / name) != expected_sha:
                raise ValueError('Fixture source SHA mismatch: ' + name)
        for name, expected_sha in input_manifest['artifacts'].items():
            if sha(directory / name) != expected_sha:
                raise ValueError('Fixture artifact SHA mismatch: ' + name)
    elif fixture_directory is not None:
        raise ValueError('Fixture inputs cannot enter core or smoke runs')
    cell = next((c for c in parameters['cells'] if c['cell_id'] == cell_id), None)
    if cell is None or purpose not in ('core', 'smoke', 'fixture'):
        raise ValueError('Unregistered cell or purpose')
    workspace = ROOT / parameters['workspace']
    implementation = {name: sha(ROOT / name) for name in parameters['execution']['implementation_files']}
    if purpose == 'core':
        receipt_path = workspace / 'preflight_ready.json'
        if not receipt_path.is_file():
            raise RuntimeError('Current registered preflight READY receipt required')
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes.decode('utf-8'))
        required_checks = set(parameters.get('acceptance_gates', {})) | {'unit_tests', 'six_file_record_transaction', 'storage_and_single_writer'}
        if (receipt['status'] != 'READY' or not required_checks <= set(receipt['checks'])
                or not all(value is True for value in receipt['checks'].values())
                or receipt['implementation_sha256'] != implementation
                or receipt['parameter_sha256'] != sha(PARAM)
                or receipt['input_manifest_sha256'] != sha(directory / 'manifest.json')):
            raise RuntimeError('Current registered preflight READY receipt required')
        from scripts.jdrt_realtime_choice_validate import verify_preflight_receipt
        if not all(verify_preflight_receipt(receipt, parameters).values()):
            raise RuntimeError('Preflight primary evidence or verifier dependencies changed')
    run_dir = (workspace / 'technical' / run_id / 'execution' if purpose == 'fixture'
               else workspace / ('runs' if purpose == 'core' else 'smoke') / run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    scenario, seed = cell['scenario'], cell['seed']
    end = parameters['simulation']['duration_sec'] if purpose in ('core', 'fixture') else smoke_end
    manifest = {'protocol': parameters['protocol'], 'run_id': run_id, **cell, 'purpose': purpose,
                'pid': os.getpid(), 'status': 'RUNNING', 'started_at_jst': stamp(),
                'parameter_sha256': sha(parameter_path),
                'parameter_path': parameter_path.relative_to(ROOT).as_posix(),
                'input_manifest_sha256': sha(directory / 'manifest.json'),
                'input_directory': directory.relative_to(ROOT).as_posix(),
                'implementation_sha256': implementation, 'execution_contract': parameters['execution'],
                'end_sec': end, 'step_sec': parameters['simulation']['step_sec'],
                'snapshot_sec': parameters['simulation']['snapshot_sec']}
    if purpose == 'fixture':
        manifest.update(research_adoption_permitted=False, fixture_case=input_manifest['fixture_case'])
    atomic_json(run_dir / 'manifest.json', manifest)
    connection, handles = None, []
    try:
        if purpose == 'core':
            (run_dir / 'preflight_ready.json').write_bytes(receipt_bytes)
            manifest['preflight_ready_sha256'] = sha(run_dir / 'preflight_ready.json')
            if manifest['preflight_ready_sha256'] != sha(receipt_path):
                raise RuntimeError('Preflight receipt changed while being archived')
        manifest['implementation_archive_sha256'] = {}
        for name, expected in implementation.items():
            archived = run_dir / 'implementation' / name
            archived.parent.mkdir(parents=True, exist_ok=True)
            archived.write_bytes((ROOT / name).read_bytes())
            if sha(archived) != expected:
                raise ValueError('Implementation changed during source archival: ' + name)
            manifest['implementation_archive_sha256'][name] = sha(archived)
        atomic_json(run_dir / 'manifest.json', manifest)
        origins = {r['origin_id']: r for r in read_csv(directory / 'origins.csv')}
        destinations = {r['origin_id']: r for r in read_csv(directory / ('destinations_' + cell['destination_policy'] + '.csv'))}
        terminals = {r['terminal_id']: r for r in read_csv(directory / 'terminals.csv')}
        positions = {(r['kind'], r['place_id']): r for r in read_csv(directory / 'place_positions.csv')}
        hazards = read_csv(directory / 'hazard.csv')
        realized = read_csv(directory / f'common_realization_seed{seed}.csv')
        for p in realized:
            p['ready_sec'] = int(p['ready_sec'])
            p['terminal_id'] = destinations[p['origin_id']]['terminal_id']
            p['selected_jdrt'] = scenario != 'R0' and p['intent_' + str(cell['demand_level'])] == 'True'
        if purpose == 'smoke':
            eligible = [p for p in realized if p['terminal_id']
                        and destinations[p['origin_id']]['car_route'] != '[]'
                        and destinations[p['origin_id']]['walk_route'] != '[]']
            eligible.sort(key=lambda p: (float(destinations[p['origin_id']]['walk_length_m'] or math.inf), p['person_id']))
            vehicle_ids = sorted({p['vehicle_id'] for p in eligible if p['base_mode'] == 'car'})[:3]
            chosen = {p['person_id'] for p in realized if p['vehicle_id'] in vehicle_ids and p['vehicle_id']}
            for typ in ('type3', 'type4'):
                for column in ('intent_u05', 'intent_u50'):
                    chosen.update(p['person_id'] for p in [p for p in eligible
                                  if p['person_type'] == typ and p[column] == 'True'][:3])
                chosen.update(p['person_id'] for p in [p for p in eligible if p['person_type'] == typ][:3])
            future = {r['edge_id']: int(r['closure_sec']) for r in hazards
                      if r['mode'] == 'passenger' and r['closure_sec'] != '' and int(r['closure_sec']) > 0}
            # A technical cohort must exercise finite forecast branches, not only dry short walks.
            future_cases = []
            for typ in ('type3', 'type4'):
                for column in ('intent_u05', 'intent_u50'):
                    affected = []
                    for p in eligible:
                        if p['person_type'] != typ or p[column] != 'True':
                            continue
                        at = min((future.get(n, math.inf) for n in json.loads(
                            destinations[p['origin_id']]['car_route'])), default=math.inf)
                        if math.isfinite(at):
                            affected.append((at, p['person_id']))
                    selected = sorted(affected)[:2]
                    chosen.update(pid for at, pid in selected)
                    future_cases.append({'person_type': typ, 'intent_column': column,
                                         'available': len(affected), 'selected': selected})
            realized = [p for p in realized if p['person_id'] in chosen]
            smoke_ready = technical_ready_times(realized)
            for p in realized:
                p['ready_sec'] = smoke_ready[p['person_id']]
            manifest['smoke_fixture'] = {'basis': 'complete_private_crews_short_walks_and_future_closure_requests',
                'future_closure_cases': future_cases, 'people': len(realized),
                'readiness_override': 'first_group_index_mod_10_shared_private_crew_technical_only', 'core_adoption_permitted': False}
        write_csv(run_dir / 'common_realization.csv', realized)
        time_fields = ['received_sec', 'accepted_sec', 'boarding_started_sec', 'boarded_sec',
                       'alighting_started_sec', 'alighted_sec', 'cancel_sec', 'fallback_sec',
                       'depart_sec', 'arrival_sec', 'admitted_sec']
        people = {}
        for p in realized:
            mode = 'drt' if p['selected_jdrt'] else p['base_mode']
            people[p['person_id']] = {**p, 'initial_mode': mode, 'mode': mode, 'status': 'not_ready',
                **{key: '' for key in time_fields}, 'cancel_reason': '', 'fallback_reason': '',
                'deadline_sec': p['ready_sec'] + parameters['request_policy']['max_unboarded_wait_sec'] if p['selected_jdrt'] else '',
                'origin_ped_closed_wait_sec': 0., 'origin_vehicle_closed_wait_sec': 0.,
                'walk_model_passed_m': 0., 'walk_plan_length_m': 0.,
                'walk_speed_integral_m': 0., 'walk_budget_lead_m': 0.}
        graphs = load_graphs(directory)
        for node, attrs in graphs['passenger'].nodes(data=True):
            attrs['travel_sec'] = attrs['free_sec']
        original_nodes = {mode: set(g) for mode, g in graphs.items()}
        true_times = {(r['edge_id'], r['mode']): int(r['closure_sec']) for r in hazards if r['closure_sec'] != ''}
        closure_events = defaultdict(lambda: defaultdict(set))
        for (edge, mode), at in true_times.items():
            closure_events[at][mode].add(edge)
        control_times = {at: closure_timing(at, manifest['step_sec']) for at in closure_events}
        forecast = dispatch_forecast(scenario, hazards, parameters)
        crews = defaultdict(list)
        for pid, p in people.items():
            if p['mode'] == 'car':
                crews[p['vehicle_id']].append(pid)
        vehicles = {vid: {'kind': 'car', 'members': members, 'origin_id': people[members[0]]['origin_id'],
            'terminal_id': people[members[0]]['terminal_id'], 'ready_sec': people[members[0]]['ready_sec'],
            'status': 'not_ready', 'route': [], 'distance_m': 0., 'empty_distance_m': 0.,
            'route_version': 0, 'active_person': '', 'reentry_expected': False} for vid, members in crews.items()}
        for i in range(parameters['operation']['fleet_count'] if scenario != 'R0' else 0):
            vehicles[f'choice_drt_{i}'] = {'kind': 'drt', 'members': [], 'origin_id': '', 'terminal_id': '',
                'ready_sec': 0, 'status': 'pending_idle', 'route': [input_manifest['depot_edge']],
                'distance_m': 0., 'empty_distance_m': 0., 'route_version': 0, 'active_person': '', 'reentry_expected': False}
        binary = resolve_sumo_binary()
        traci = load_traci(binary)
        tc = traci.constants
        manifest['runtime_sha256'] = {'sumo_binary': sha(binary), 'traci_init': sha(Path(traci.__file__)),
            'traci_vehicle': sha(Path(traci.__file__).parent / '_vehicle.py'),
            'shared_smoke': sha(ROOT / '04_プログラム/scripts/jdrt/smoke.py'),
            'shared_log_parser': sha(ROOT / '04_プログラム/scripts/jdrt/full_run.py')}
        if purpose == 'core' and receipt['runtime_sha256'] != manifest['runtime_sha256']:
            raise RuntimeError('Runtime dependencies differ from preflight')
        atomic_json(run_dir / 'manifest.json', manifest)
        route_xml = ET.Element('routes')
        ET.SubElement(route_xml, 'vType', id='car', vClass='passenger',
                      length=str(parameters['operation']['vehicle_length_m']), minGap=str(parameters['operation']['min_gap_m']))
        ET.SubElement(route_xml, 'vType', id='drt', vClass='passenger',
                      length=str(parameters['operation']['vehicle_length_m']), minGap=str(parameters['operation']['min_gap_m']),
                      personCapacity=str(parameters['operation']['passenger_capacity']))
        for typ, speed in parameters['population']['walk_mps'].items():
            attributes = {'id': 'walk_' + typ, 'vClass': 'pedestrian', 'maxSpeed': str(speed)}
            if purpose == 'fixture' and 'technical_walk_speed_factors' in parameters:
                attributes['speedFactor'] = str(parameters['technical_walk_speed_factors'][typ])
                attributes['speedDev'] = '0'
            ET.SubElement(route_xml, 'vType', **attributes)
        ET.ElementTree(route_xml).write(run_dir / 'types.rou.xml', encoding='utf-8', xml_declaration=True)
        command = [str(binary), '--net-file', os.path.relpath(directory / 'bounded.net.xml', run_dir),
            '--route-files', 'types.rou.xml', '--step-length', str(manifest['step_sec']), '--seed', str(seed),
            '--begin', '0', '--end', str(end + 1), '--time-to-teleport', '-1', '--collision.action', 'teleport',
            '--no-step-log', 'true', '--duration-log.disable', 'true', '--error-log', 'sumo_errors.log',
            '--log', 'sumo.log', '--tripinfo-output', 'tripinfo.xml', '--tripinfo-output.write-unfinished', 'true']
        previous_directory = Path.cwd()
        try:
            os.chdir(run_dir)
            traci.start(command, label=run_id, doSwitch=False, verbose=False)
            connection = traci.getConnection(run_id)
        finally:
            os.chdir(previous_directory)
        t = connection
        manifest['sumo_version'] = list(t.getVersion())
        import sumolib
        net = sumolib.net.readNet(str(directory / 'bounded.net.xml'), withInternal=True)
        walk_topology = pedestrian_endpoint_topology(net, original_nodes['pedestrian'])
        lane_info, lanes_by_edge = {}, defaultdict(list)
        for edge in net.getEdges():
            name = edge.getID()
            if name.startswith(':'):
                continue
            for lane in edge.getLanes():
                lanes_by_edge[name].append(lane.getID())
                if lane.allows('passenger') and name not in lane_info:
                    lane_info[name] = (int(lane.getID().rsplit('_', 1)[1]), lane.getLength())
            if name not in original_nodes['passenger'] and name not in original_nodes['pedestrian']:
                for lane in lanes_by_edge[name]:
                    t.lane.setDisallowed(lane, sorted(set(t.lane.getDisallowed(lane)) | {'passenger'}))
        vehicle_vars = [tc.VAR_ROAD_ID, tc.VAR_LANE_ID, tc.VAR_SPEED, tc.VAR_DECEL, tc.VAR_DISTANCE, tc.VAR_ROUTE_INDEX,
                        tc.VAR_POSITION, tc.VAR_LANEPOSITION, tc.VAR_STOPSTATE]
        person_vars = [tc.VAR_ROAD_ID, tc.VAR_SPEED, tc.VAR_POSITION, tc.VAR_LANEPOSITION]
        for vid, vehicle in vehicles.items():
            if vehicle['kind'] == 'drt':
                depot = input_manifest['depot_edge']
                t.route.add('initial_' + vid, [depot])
                t.vehicle.add(vid, 'initial_' + vid, typeID='drt', depart='now')
                lane, length = lane_info[depot]
                t.vehicle.setStop(vid, depot, pos=length - 1, laneIndex=lane, duration=end + 1, flags=tc.STOP_PARKING)
                t.vehicle.subscribe(vid, vehicle_vars)
        def gz_writer(name, fields):
            stream = gzip.open(run_dir / name, 'wt', encoding='utf-8', newline='', compresslevel=1)
            handles.append(stream)
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            return writer
        roads = gz_writer('edge_observations.csv.gz', ['time_sec', 'edge_id', 'mode', 'count',
            'mean_speed_mps', 'halting_count', 'traffic_count', 'traffic_mean_speed_mps',
            'traffic_halting_count', 'parked_count', 'reentry_pending_count', 'unplaced_reentry_count',
            'closed', 'observation_status'])
        actors = gz_writer('actor_observations.csv.gz', ['time_sec', 'phase', 'actor_id', 'kind', 'road_id', 'lane_id',
            'lane_position_m', 'x', 'y', 'speed_mps', 'decel_mps2', 'distance_m', 'route_index', 'route_version', 'stop_state', 'status',
            'active_person', 'members', 'observation_kind', 'reentry_source_edge',
            'native_stop_lane_id', 'native_stop_start_pos_m', 'native_stop_end_pos_m', 'native_stop_flags'])
        snapshot_actors = gz_writer('snapshot_actor_observations.csv.gz', ['time_sec', 'phase', 'actor_id',
            'kind', 'road_id', 'speed_mps', 'observation_kind', 'stop_state',
            'reentry_source_edge', 'native_edge_contains_vehicle'])
        transitions = gz_writer('transitions.csv.gz', ['time_lower_sec', 'time_upper_sec', 'actor_id',
            'mode', 'from_edge', 'to_edge', 'kind', 'closure_sec', 'ambiguous'])
        candidate_fields = ['cycle', 'stage', 'time_sec', 'vehicle_id', 'person_id', 'pickup_sec', 'delivery_sec',
            'waiting_sec', 'vulnerability', 'forecast_remaining_sec', 'required_sec', 'pickup_kind', 'delivery_kind',
            'forecast_remaining_kind', 'required_kind', 'pickup_route', 'delivery_route',
            'source_edge', 'source_pos_m', 'source_speed_mps', 'source_decel_mps2', 'minimum_advance_m',
            'pickup_pos_m', 'terminal_pos_m', 'pickup_path', 'delivery_path',
            'pickup_before_deadline',
            'completion_within_horizon', 'gate_applicable', 'gate_pass', 'urgency', 'score', 'decision', 'reason']
        candidates_writer = gz_writer('candidates.csv.gz', candidate_fields)
        cycles = gz_writer('dispatch_cycles.csv.gz', ['cycle', 'time_sec', 'free_start', 'pending_start', 'stages', 'candidate_rows', 'accepted'])
        events = (run_dir / 'events.jsonl').open('w', encoding='utf-8')
        handles.append(events)
        def event(now, kind, **data):
            events.write(json.dumps({'time_sec': now, 'event': kind, **data}, ensure_ascii=False) + '\n')
        def person_state(pid, state, now, reason=''):
            old_state = people[pid]['status']
            if old_state != state:
                event(now, 'person_state', person_id=pid, before=old_state, after=state, reason=reason)
                people[pid]['status'] = state
        requests, waiting = {}, set()
        closed = {mode: set() for mode in graphs}
        applied, occupancy, last, walking_routes, route_cache = set(), Counter(), {}, {}, {}
        latest_v, latest_p, pending_arrivals = {}, {}, []
        cycle, route_counter = 0, 0
        counts = {key: 0 for key in ['steps', 'controller_ticks', 'snapshots', 'teleports', 'collisions',
            'transition_rows', 'closed_entry_rows', 'ambiguous_transitions', 'candidate_rows', 'dispatch_cycles',
            'missing_vehicle_subscriptions', 'missing_person_subscriptions', 'reentry_pending_frames',
            'departure_pending_frames', 'snapshot_actor_rows']}
        def destination(pid):
            return terminals[people[pid]['terminal_id']]['edge_id']
        def point(kind, identifier, mode):
            return float(positions[kind, identifier]['car_pos_m' if mode == 'passenger' else 'pedestrian_pos_m'])
        def walking_path(start, target, position, target_position):
            return positioned_walk_route(walk_topology, start, target, position, target_position)
        def vehicle_path(vid, target, target_position, weight='free_sec'):
            lane, source_receipt = vehicle_path_source(t, vid, net)
            raw = source_receipt['native_source']
            current, position, speed = raw['road_id'], raw['lane_position_m'], raw['speed_mps']
            successors = [link.getToLane().getEdge().getID() for link in lane.getOutgoing()
                          if link.getToLane().allows('passenger')]
            path, travel, receipt = lane_constrained_car_route(graphs['passenger'], current,
                target, position, target_position, lane.getLength(), successors, speed,
                raw['decel_mps2'], manifest['step_sec'], bool(raw['stop_state'] & 1), weight)
            event(now, 'vehicle_route_feasibility', vehicle_id=vid, source_lane_id=raw['lane_id'],
                  target_edge=target, target_position_m=target_position, **source_receipt, **receipt)
            return path, travel
        def current_walk_stage(pid):
            for index in range(t.person.getRemainingStages(pid)):
                stage = t.person.getStage(pid, index)
                if stage.type == tc.STAGE_WALKING:
                    return index, stage
            raise RuntimeError('Active walker lacks a walking stage')
        def request_event(pid, trigger, now, **data):
            q = requests[pid]
            previous = q['status']
            q['status'] = request_transition(previous, trigger)
            event(now, 'request_state', person_id=pid, request_id=q['request_id'], before=previous,
                  after=q['status'], trigger=trigger, **data)
        def start_walk(pid, now, fallback=False):
            p = people[pid]
            origin = origins[p['origin_id']]['edge_id']
            if fallback:
                p['fallback_sec'] = now
                p['mode'] = 'walk'
                person_state(pid, 'fallback_pending', now)
                event(now, 'fallback_attempt', person_id=pid, origin_edge=origin, terminal_id=p['terminal_id'])
            origin_position = point('origin', p['origin_id'], 'pedestrian') if origin else 0
            target_position = point('terminal', p['terminal_id'], 'pedestrian') if p['terminal_id'] else 0
            path, estimate = walking_path(origin, destination(pid), origin_position, target_position) if origin and p['terminal_id'] else ([], math.inf)
            reason = ('no_origin_connection' if not origin else 'no_route' if not p['terminal_id']
                      else 'initial_or_current_closed' if origin in closed['pedestrian'] else 'no_route' if not path else '')
            if reason:
                p['fallback_reason'] = reason if fallback else ''
                person_state(pid, reason, now)
                return
            if pid in t.person.getIDList():
                raise RuntimeError('Duplicate walking actor: ' + pid)
            t.person.add(pid, origin, pos=origin_position, typeID='walk_' + p['person_type'])
            t.person.appendWalkingStage(pid, path, arrivalPos=target_position,
                                        speed=parameters['population']['walk_mps'][p['person_type']])
            t.person.setSpeed(pid, parameters['population']['walk_mps'][p['person_type']])
            _, stage = current_walk_stage(pid)
            length = stage.length
            event(now, 'walk_plan', person_id=pid, stage='initial', route=path, depart_pos=origin_position,
                  arrival_pos=target_position, endpoint_estimate_m=estimate, sumo_plan_length_m=length,
                  model_passed_m=p['walk_model_passed_m'], speed_integral_m=p['walk_speed_integral_m'],
                  enforced_stage_speed_mps=parameters['population']['walk_mps'][p['person_type']],
                  person_type_id=t.person.getTypeID(pid),
                  person_type_max_mps=t.vehicletype.getMaxSpeed(t.person.getTypeID(pid)),
                  person_max_mps=t.person.getMaxSpeed(pid), person_speed_factor=t.person.getSpeedFactor(pid))
            if not math.isfinite(length) or length < 0:
                raise RuntimeError('Invalid SUMO planned walking distance')
            if length > parameters['population']['walk_limit_m']:
                t.person.remove(pid)
                p['fallback_reason'] = 'walk_limit' if fallback else ''
                person_state(pid, 'walk_limit', now)
                return
            p['walk_plan_length_m'] = length
            t.person.subscribe(pid, person_vars)
            walking_routes[pid] = path
            p['depart_sec'] = now
            person_state(pid, 'travelling_walk', now)
            event(now, 'walk_departure', person_id=pid, fallback=fallback, route=path, length_m=length)
        def cancel_request(pid, now, trigger, vehicle_id='', park=True):
            p, q = people[pid], requests[pid]
            request_event(pid, trigger, now, vehicle_id=vehicle_id)
            q['cancel_sec'] = p['cancel_sec'] = now
            q['cancel_reason'] = p['cancel_reason'] = trigger
            waiting.discard(pid)
            event(now, 'request_cancelled', person_id=pid, vehicle_id=vehicle_id, reason=trigger)
            if vehicle_id:
                v = vehicles[vehicle_id]
                v['active_person'] = ''
                v['members'] = []
                if park:
                    v['status'] = 'cancel_pending'
            start_walk(pid, now, fallback=True)
        def remove_actor(actor, mode, reason, now):
            event(now, 'actor_removed', actor_id=actor, mode=mode, reason=reason)
            remove_sumo_actor(t, actor, mode)
            if mode == 'pedestrian':
                person_state(actor, reason, now)
                walking_routes.pop(actor, None)
            else:
                v = vehicles[actor]
                pid = v['active_person']
                if pid:
                    if people[pid]['status'] == 'assigned_origin':
                        cancel_request(pid, now, 'vehicle_failed', actor, park=False)
                    else:
                        request_event(pid, 'vehicle_failed', now, vehicle_id=actor)
                        person_state(pid, 'stranded_drt', now, reason)
                for member in v['members']:
                    person_state(member, reason if v['kind'] == 'car' else 'stranded_drt', now)
                v.update(status='stranded', members=[], active_person='')
            last.pop(actor, None)
        def bus_route(vid, path, now, target_position):
            v = vehicles[vid]
            current = t.vehicle.getRoadID(vid)
            position = t.vehicle.getLanePosition(vid)
            distance = t.vehicle.getDistance(vid)
            actual_path = set_vehicle_route(t, vid, path, lane_info, end + 1, stop_pos=target_position)
            v['route'], v['route_version'] = actual_path, v['route_version'] + 1
            v['reentry_expected'] = t.vehicle.getPosition(vid)[0] == tc.INVALID_DOUBLE_VALUE
            v['reentry_source_edge'], v['target_position_m'] = current, target_position
            source_index = len(actual_path) - len(path)
            if source_index < 0 or actual_path[source_index:] != path:
                raise RuntimeError('Native route does not retain the requested remaining suffix')
            last[vid] = (current, now, source_index)
            event(now, 'drt_route', vehicle_id=vid, route=actual_path, requested_remaining_route=path, source_edge=current,
                  source_lane_position=position, source_distance_m=distance, target_position_m=target_position,
                  route_version=v['route_version'], source_route_index=source_index,
                  reentry_expected=v['reentry_expected'])
        def observe_transition(actor, mode, edge, now, path):
            prior = last.get(actor)
            index = (int(latest_v.get(actor, {}).get(tc.VAR_ROUTE_INDEX, len(path) - 1))
                     if mode == 'passenger' else path.index(edge))
            if mode == 'passenger' and actor in vehicles and vehicles[actor]['status'] == 'arrived':
                index = len(path) - 1
            if prior and (prior[0] != edge or index > prior[2]):
                try:
                    lo, hi = (prior[2], index) if mode == 'passenger' else (path.index(prior[0]), index)
                    entered, ambiguous = (path[lo + 1:hi + 1] if hi > lo else [edge]), hi <= lo
                except ValueError:
                    entered, ambiguous = [edge], True
                for target in entered:
                    at = true_times.get((target, mode))
                    violation = at is not None and now >= at
                    transitions.writerow({'time_lower_sec': prior[1], 'time_upper_sec': now, 'actor_id': actor,
                        'mode': mode, 'from_edge': prior[0], 'to_edge': target, 'kind': 'closed_entry' if violation else 'transition',
                        'closure_sec': at if at is not None else '', 'ambiguous': ambiguous})
                    counts['transition_rows'] += 1
                    counts['closed_entry_rows'] += int(violation)
                    counts['ambiguous_transitions'] += int(ambiguous)
            last[actor] = (edge, now, index)
        wall_start = time.monotonic()
        while True:
            now = float(t.simulation.getTime())
            controller_tick = now % parameters['simulation']['controller_sec'] == 0
            if controller_tick:
                counts['controller_ticks'] += 1
            for pid in t.simulation.getArrivedPersonIDList():
                if pid in people and people[pid]['status'] not in FINAL:
                    people[pid]['walk_model_passed_m'] += people[pid]['walk_plan_length_m']
                    people[pid]['walk_plan_length_m'] = 0.
                    path = walking_routes.pop(pid, [])
                    if path:
                        observe_transition(pid, 'pedestrian', path[-1], now, path)
                    pending_arrivals.append(pid)
                    last.pop(pid, None)
            for vid in t.simulation.getArrivedIDList():
                if vid in vehicles:
                    v = vehicles[vid]
                    if v['kind'] == 'drt' and v['status'] != 'stranded':
                        raise RuntimeError('DRT vehicle left controlled service: ' + vid)
                    if v['kind'] == 'car' and v['status'] not in ('stranded', 'arrived'):
                        observe_transition(vid, 'passenger', v['route'][-1], now, v['route'])
                        pending_arrivals.extend(v['members'])
                        v['status'] = 'arrived'
                        last.pop(vid, None)
            due = [at for at in sorted(closure_events) if at <= end
                   and control_times[at]['control_call_sec'] <= now and at not in applied]
            for at in due:
                for mode, names in closure_events[at].items():
                    closed[mode].update(names)
                    graphs[mode].remove_nodes_from(names)
                    for name in sorted(names):
                        if mode == 'passenger':
                            for lane in lanes_by_edge[name]:
                                t.lane.setDisallowed(lane, sorted(set(t.lane.getDisallowed(lane)) | {'passenger'}))
                        elif (name, 0) in walk_topology:
                            walk_topology.remove_nodes_from([(name, 0), (name, 1)])
                        event(now, 'closure_applied', edge_id=name, mode=mode, **control_times[at])
                applied.add(at)
            if due:
                route_cache.clear()
            for vid, v in vehicles.items():
                if v['status'] in ('not_ready', 'arrived', 'stranded'):
                    continue
                data = latest_v.get(vid, {})
                current = data.get(tc.VAR_ROAD_ID, '')
                if not current and v['reentry_expected'] and v['reentry_source_edge'] in closed['passenger']:
                    remove_actor(vid, 'passenger', 'initial_or_current_closed', now)
                    continue
                action, next_external = vehicle_closure_action(v['route'], current,
                    int(data.get(tc.VAR_ROUTE_INDEX, -1)), closed['passenger'])
                if action in ('clear', 'defer'):
                    continue
                if action in ('remove_current', 'remove_junction'):
                    remove_actor(vid, 'passenger', 'initial_or_current_closed' if action == 'remove_current' else 'route_cut', now)
                    continue
                target_position = (v['target_position_m'] if v['kind'] == 'drt'
                                   else point('terminal', v['terminal_id'], 'passenger'))
                replacement, _ = vehicle_path(vid, v['route'][-1], target_position)
                if not replacement:
                    remove_actor(vid, 'passenger', 'route_cut', now)
                elif v['kind'] == 'drt':
                    bus_route(vid, replacement, now, target_position)
                else:
                    apply_remaining_route(t, vid, replacement, 'reroute_' + vid + '_' + str(v['route_version'] + 1))
                    v['route'], v['route_version'] = list(t.vehicle.getRoute(vid)), v['route_version'] + 1
                    event(now, 'private_reroute', vehicle_id=vid, route=v['route'],
                          requested_remaining_route=replacement, source_edge=current,
                          source_lane_position=t.vehicle.getLanePosition(vid),
                          target_position_m=target_position, route_version=v['route_version'])
                    source_index = len(v['route']) - len(replacement)
                    if source_index < 0 or v['route'][source_index:] != replacement:
                        raise RuntimeError('Private route does not retain its remaining suffix')
                    last[vid] = (current, now, source_index)
            for pid, path in list(walking_routes.items()):
                current = latest_p.get(pid, {}).get(tc.VAR_ROAD_ID, '')
                action, next_external = pedestrian_closure_action(path, current, last.get(pid, ('', 0))[0], closed['pedestrian'])
                if action in ('clear', 'defer'):
                    continue
                if action in ('remove_current', 'remove_junction'):
                    remove_actor(pid, 'pedestrian', 'initial_or_current_closed' if action == 'remove_current' else 'route_cut', now)
                    continue
                position = t.person.getLanePosition(pid)
                p = people[pid]
                target_position = point('terminal', p['terminal_id'], 'pedestrian')
                replacement, estimate = walking_path(current, destination(pid), position, target_position)
                if not replacement:
                    remove_actor(pid, 'pedestrian', 'route_cut', now)
                else:
                    index, stage = current_walk_stage(pid)
                    before_xy = t.person.getPosition(pid)
                    previous_plan = p['walk_plan_length_m']
                    stage.edges, stage.departPos = path[path.index(current):], position
                    stage.arrivalPos = target_position
                    replacement_receipts = [replace_walk_stage_receipt(t, pid, index, stage, 'old_remaining')]
                    _, remaining_stage = current_walk_stage(pid)
                    old_remaining = remaining_stage.length
                    passed = previous_plan - old_remaining
                    p['walk_model_passed_m'] += max(0, passed)
                    remaining_stage.edges, remaining_stage.departPos = replacement, position
                    replacement_receipts.append(replace_walk_stage_receipt(t, pid, index, remaining_stage, 'new_route'))
                    # Stage serialization has no walking-speed field; preserve the registered bound.
                    t.person.setSpeed(pid, parameters['population']['walk_mps'][p['person_type']])
                    _, new_stage = current_walk_stage(pid)
                    if t.person.getPosition(pid) != before_xy or t.person.getLanePosition(pid) != position:
                        raise RuntimeError('Walking stage replacement moved the person')
                    p['walk_plan_length_m'] = new_stage.length
                    spent = max(p['walk_model_passed_m'], p['walk_speed_integral_m'])
                    event(now, 'walk_plan', person_id=pid, stage='reroute', route=replacement,
                          depart_pos=position, arrival_pos=target_position, endpoint_estimate_m=estimate,
                          previous_plan_m=previous_plan, old_remaining_m=old_remaining,
                          signed_progress_m=passed, model_passed_m=p['walk_model_passed_m'],
                          speed_integral_m=p['walk_speed_integral_m'], sumo_plan_length_m=new_stage.length,
                          enforced_stage_speed_mps=parameters['population']['walk_mps'][p['person_type']],
                          replacement_receipts=replacement_receipts,
                          person_type_id=t.person.getTypeID(pid),
                          person_type_max_mps=t.vehicletype.getMaxSpeed(t.person.getTypeID(pid)),
                          person_max_mps=t.person.getMaxSpeed(pid), person_speed_factor=t.person.getSpeedFactor(pid))
                    if not math.isfinite(new_stage.length) or new_stage.length < 0:
                        raise RuntimeError('Invalid SUMO rerouted walking distance')
                    if spent + new_stage.length > parameters['population']['walk_limit_m']:
                        remove_actor(pid, 'pedestrian', 'walk_limit', now)
                        continue
                    walking_routes[pid] = replacement
                    last[pid] = (current, now, 0)
                    event(now, 'walk_reroute', person_id=pid, route=replacement, depart_pos=position)
            if controller_tick:
                for pid, p in people.items():
                    if unboarded_expired(p['status'], now, p['deadline_sec'] if p['deadline_sec'] != '' else math.inf):
                        cancel_request(pid, now, 'timeout', requests[pid]['vehicle_id'])
            for vid, v in vehicles.items():
                if v['kind'] != 'car' or v['status'] != 'not_ready' or v['ready_sec'] > now:
                    continue
                origin = origins[v['origin_id']]['edge_id']
                origin_position = point('origin', v['origin_id'], 'passenger') if origin else 0
                target_position = point('terminal', v['terminal_id'], 'passenger') if v['terminal_id'] else 0
                path, _ = (positioned_car_route(graphs['passenger'], origin, terminals[v['terminal_id']]['edge_id'],
                            origin_position, target_position) if origin and v['terminal_id'] else ([], math.inf))
                if not path:
                    reason = 'no_origin_connection' if not origin else 'initial_or_current_closed' if origin in closed['passenger'] else 'no_route'
                    for pid in v['members']:
                        person_state(pid, reason, now)
                    v['status'] = 'stranded'
                    continue
                route_counter += 1
                rid = 'private_' + str(route_counter)
                t.route.add(rid, path)
                t.vehicle.add(vid, rid, typeID='car', depart='now', departLane='best',
                              departPos=str(origin_position), arrivalPos=str(target_position))
                t.vehicle.subscribe(vid, vehicle_vars)
                v.update(route=path, status='pending')
                for pid in v['members']:
                    people[pid]['depart_sec'] = now
                    person_state(pid, 'travelling_car', now)
                event(now, 'private_departure_requested', vehicle_id=vid, members=v['members'], route=path, route_version=0,
                      depart_pos=origin_position, arrival_pos=target_position)
            for pid, p in people.items():
                if p['mode'] == 'car' or p['status'] != 'not_ready' or p['ready_sec'] > now:
                    continue
                event(now, 'person_ready', person_id=pid)
                if p['mode'] == 'walk':
                    start_walk(pid, now)
                    continue
                q = {'request_id': 'request_' + pid, 'person_id': pid, 'status': 'none', 'vehicle_id': '',
                     'terminal_id': p['terminal_id'], 'deadline_sec': p['deadline_sec'],
                     **{field: '' for field in time_fields}, 'cancel_reason': ''}
                requests[pid] = q
                request_event(pid, 'received', now)
                q['received_sec'] = p['received_sec'] = now
                event(now, 'request_received', person_id=pid, deadline_sec=p['deadline_sec'])
                if not origins[p['origin_id']]['edge_id'] or not p['terminal_id']:
                    request_event(pid, 'invalid_input', now)
                    person_state(pid, 'no_origin_connection' if not origins[p['origin_id']]['edge_id'] else 'no_route', now)
                else:
                    person_state(pid, 'waiting_origin', now)
                    waiting.add(pid)
            active_ids = set(t.vehicle.getIDList())
            for vid, v in vehicles.items():
                if v['kind'] != 'drt' or vid not in active_ids or v['status'] == 'stranded':
                    continue
                if v['status'] == 'cancel_pending':
                    path = cancel_vehicle_to_wait(t, vid, lane_info, end + 1, manifest['step_sec'])
                    if path:
                        v.update(route=path, status='cancel_wait', route_version=v['route_version'] + 1)
                        source = path[-1]
                        last[vid] = (source, now, len(path) - 1)
                        event(now, 'cancel_wait_route', vehicle_id=vid, route=path, route_version=v['route_version'],
                              requested_remaining_route=[source], source_edge=source,
                              source_lane_position=t.vehicle.getLanePosition(vid))
                    continue
                if not controller_tick:
                    continue
                current = t.vehicle.getRoadID(vid)
                stopped = t.vehicle.isStopped(vid)
                if v['status'] in ('pending_idle', 'cancel_wait') and stopped:
                    v['status'] = 'idle'
                elif v['status'] in ('pickup', 'delivery') and stopped and current == v['route'][-1]:
                    pid = v['active_person']
                    boarding = v['status'] == 'pickup'
                    trigger = 'boarding_started' if boarding else 'alighting_started'
                    if boarding and not now < people[pid]['deadline_sec']:
                        raise RuntimeError('Deadline cancellation did not precede boarding')
                    request_event(pid, trigger, now, vehicle_id=vid)
                    requests[pid][trigger + '_sec'] = people[pid][trigger + '_sec'] = now
                    person_state(pid, 'boarding' if boarding else 'alighting', now)
                    v.update(status='boarding' if boarding else 'alighting', until_sec=now + parameters['operation']['boarding_sec' if boarding else 'alighting_sec'])
                    event(now, trigger, person_id=pid, vehicle_id=vid)
                elif v['status'] == 'boarding' and now >= v['until_sec']:
                    pid = v['active_person']
                    target_position = point('terminal', people[pid]['terminal_id'], 'passenger')
                    path, _ = vehicle_path(vid, destination(pid), target_position)
                    if not path:
                        remove_actor(vid, 'passenger', 'stranded_drt', now)
                        continue
                    request_event(pid, 'boarded', now, vehicle_id=vid)
                    requests[pid]['boarded_sec'] = people[pid]['boarded_sec'] = now
                    v['members'], v['maximum_onboard'] = [pid], 1
                    person_state(pid, 'onboard', now)
                    bus_route(vid, path, now, target_position)
                    v['status'] = 'delivery'
                    event(now, 'drt_boarded', person_id=pid, vehicle_id=vid, onboard_count=1)
                elif v['status'] == 'alighting' and now >= v['until_sec']:
                    pid = v['active_person']
                    request_event(pid, 'alighted', now, vehicle_id=vid)
                    requests[pid]['alighted_sec'] = people[pid]['alighted_sec'] = now
                    pending_arrivals.append(pid)
                    v.update(members=[], active_person='', status='idle')
                    event(now, 'drt_alighted', person_id=pid, vehicle_id=vid, onboard_count=0)
            if pending_arrivals:
                previous = {pid: people[pid]['status'] for pid in set(pending_arrivals)}
                allocate_arrivals(pending_arrivals, people, terminals, occupancy, now)
                for pid in sorted(previous):
                    event(now, 'person_state', person_id=pid, before=previous[pid], after=people[pid]['status'], reason='terminal')
                    event(now, 'person_terminal', person_id=pid, status=people[pid]['status'], terminal_id=people[pid]['terminal_id'])
                pending_arrivals = []
            if scenario != 'R0' and now % parameters['simulation']['dispatch_sec'] == 0:
                cycle += 1
                counts['dispatch_cycles'] += 1
                free = sorted(vid for vid, v in vehicles.items() if v['kind'] == 'drt' and v['status'] == 'idle')
                cycle_info = {'cycle': cycle, 'time_sec': now, 'free_start': len(free), 'pending_start': len(waiting),
                              'stages': 0, 'candidate_rows': 0, 'accepted': 0}
                while free and waiting:
                    cycle_info['stages'] += 1
                    candidates = []
                    for vid in free:
                        if not t.vehicle.isStopped(vid):
                            raise RuntimeError('Idle dispatch vehicle is not physically stopped')
                        current = t.vehicle.getRoadID(vid)
                        if current not in graphs['passenger']:
                            raise RuntimeError('Idle vehicle is not on an observed open edge')
                        start_position = t.vehicle.getLanePosition(vid)
                        source_speed = t.vehicle.getSpeed(vid)
                        source_decel = t.vehicle.getDecel(vid)
                        minimum_advance = (source_speed * source_speed / (2 * source_decel)
                            + source_speed * manifest['step_sec'] + 1 if not t.vehicle.isStopped(vid) else 0)
                        source_tree = nx.single_source_dijkstra(graphs['passenger'], current,
                            weight=lambda a, b, data: graphs['passenger'].nodes[b]['travel_sec'])
                        for pid in sorted(waiting):
                            p = people[pid]
                            origin = origins[p['origin_id']]['edge_id']
                            pickup_position = point('origin', p['origin_id'], 'passenger')
                            target_position = point('terminal', p['terminal_id'], 'passenger')
                            pickup_path, pickup = positioned_car_route(graphs['passenger'], current, origin,
                                start_position, pickup_position, 'travel_sec', minimum_advance, source_tree)
                            key = ('delivery', origin, destination(pid), pickup_position, target_position,
                                   len(closed['passenger']))
                            if key not in route_cache:
                                route_cache[key] = positioned_car_route(graphs['passenger'], origin,
                                    destination(pid), pickup_position, target_position)
                            delivery_path, delivery = route_cache[key]
                            remaining = min((forecast.get(n, math.inf) - now for n in pickup_path + delivery_path), default=math.inf) if forecast is not None else None
                            check = candidate_checks(now, pickup, delivery, p['deadline_sec'], end,
                                parameters['operation']['boarding_sec'], parameters['operation']['alighting_sec'],
                                parameters['operation']['margin_sec'], remaining)
                            c = {'cycle': cycle, 'stage': cycle_info['stages'], 'time_sec': now, 'vehicle_id': vid,
                                'person_id': pid, 'pickup_sec': pickup, 'delivery_sec': delivery,
                                'waiting_sec': now - p['ready_sec'], 'vulnerability': int(p['person_type'] == 'type4'),
                                'forecast_remaining_sec': remaining, 'required_sec': check['required_sec'],
                                'gate_applicable': check['forecast_gate_applicable'], 'gate_pass': check['forecast_gate_pass'],
                                'pickup_route': check['pickup_route'], 'delivery_route': check['delivery_route'],
                                'pickup_before_deadline': check['pickup_before_deadline'], 'completion_within_horizon': check['completion_within_horizon'],
                                'urgency': 1 / max(remaining, 1) if remaining is not None and math.isfinite(remaining) else 0,
                                'score': '', 'decision': 'not_selected', 'reason': check['reason'], '_pickup_path': pickup_path}
                            c.update(source_edge=current, source_pos_m=start_position, source_speed_mps=source_speed,
                                     source_decel_mps2=source_decel,
                                     minimum_advance_m=minimum_advance, pickup_pos_m=pickup_position,
                                     terminal_pos_m=target_position, pickup_path=json.dumps(pickup_path),
                                     delivery_path=json.dumps(delivery_path))
                            candidates.append(c)
                    chosen = rank_candidates(candidates, forecast is not None, parameters['dispatch_weights'])
                    if chosen:
                        chosen['decision'] = 'selected'
                    for c in candidates:
                        record = {key: value for key, value in c.items() if not key.startswith('_')}
                        for field in ('pickup_sec', 'delivery_sec', 'forecast_remaining_sec', 'required_sec'):
                            value = record[field]
                            kind = 'not_applicable' if value is None else 'finite' if math.isfinite(value) else 'infinite'
                            record[field.replace('_sec', '_kind')] = kind
                            if kind != 'finite':
                                record[field] = ''
                        candidates_writer.writerow(record)
                        counts['candidate_rows'] += 1
                        cycle_info['candidate_rows'] += 1
                    if chosen is None:
                        break
                    vid, pid = chosen['vehicle_id'], chosen['person_id']
                    bus_route(vid, chosen['_pickup_path'], now, chosen['pickup_pos_m'])
                    vehicles[vid].update(status='pickup', active_person=pid)
                    requests[pid]['vehicle_id'] = vid
                    request_event(pid, 'accepted', now, vehicle_id=vid, cycle=cycle, stage=cycle_info['stages'])
                    requests[pid]['accepted_sec'] = people[pid]['accepted_sec'] = now
                    person_state(pid, 'assigned_origin', now)
                    waiting.remove(pid)
                    free.remove(vid)
                    cycle_info['accepted'] += 1
                    event(now, 'request_accepted', person_id=pid, vehicle_id=vid, cycle=cycle, stage=cycle_info['stages'])
                cycles.writerow(cycle_info)
            if now % manifest['snapshot_sec'] == 0:
                grouped = defaultdict(list)
                traffic, parked, reentry, unplaced = defaultdict(list), Counter(), Counter(), Counter()
                native_edge_vehicles = {}
                for vid in t.vehicle.getIDList():
                    if vid in vehicles and vehicles[vid]['status'] not in ('stranded', 'arrived'):
                        v = vehicles[vid]
                        edge, xy = t.vehicle.getRoadID(vid), t.vehicle.getPosition(vid)
                        valid = all(math.isfinite(value) and value != tc.INVALID_DOUBLE_VALUE for value in xy)
                        state = traffic_observation_state(t.vehicle.getStopState(vid), valid, v['reentry_expected'])
                        if state == 'missing':
                            raise RuntimeError('Unexplained snapshot vehicle position missing: ' + vid)
                        speed = t.vehicle.getSpeed(vid)
                        native_contains = ''
                        if edge in original_nodes['passenger']:
                            if edge not in native_edge_vehicles:
                                native_edge_vehicles[edge] = set(t.edge.getLastStepVehicleIDs(edge))
                            native_contains = vid in native_edge_vehicles[edge]
                        snapshot_actors.writerow({'time_sec': now, 'phase': 'after_control_before_step',
                            'actor_id': vid, 'kind': v['kind'], 'road_id': edge, 'speed_mps': speed,
                            'observation_kind': state, 'stop_state': t.vehicle.getStopState(vid),
                            'reentry_source_edge': v.get('reentry_source_edge', ''),
                            'native_edge_contains_vehicle': native_contains})
                        counts['snapshot_actor_rows'] += 1
                        if edge in original_nodes['passenger']:
                            key = edge, v['kind']
                            grouped[key].append(speed)
                            if state == 'onroad':
                                traffic[key].append(speed)
                            elif state == 'parked':
                                parked[key] += 1
                            else:
                                reentry[key] += 1
                        elif state == 'reentry_pending':
                            unplaced[v['reentry_source_edge'], v['kind']] += 1
                for pid in t.person.getIDList():
                    edge = t.person.getRoadID(pid)
                    if pid in walking_routes:
                        speed = t.person.getSpeed(pid)
                        position = t.person.getPosition(pid)
                        valid = all(math.isfinite(value) and value != tc.INVALID_DOUBLE_VALUE for value in position)
                        snapshot_actors.writerow({'time_sec': now, 'phase': 'after_control_before_step',
                            'actor_id': pid, 'kind': 'walk', 'road_id': edge, 'speed_mps': speed,
                            'observation_kind': 'onroad' if valid else 'missing'})
                        counts['snapshot_actor_rows'] += 1
                        if not valid or not math.isfinite(speed) or speed < 0:
                            raise RuntimeError('Unexplained snapshot pedestrian observation missing: ' + pid)
                        if edge in original_nodes['pedestrian']:
                            grouped[edge, 'walk'].append(speed)
                            traffic[edge, 'walk'].append(speed)
                for mode, physical in [('car', 'passenger'), ('drt', 'passenger'), ('walk', 'pedestrian')]:
                    for edge in sorted(original_nodes[physical]):
                        speeds = grouped.get((edge, mode), [])
                        moving = traffic.get((edge, mode), [])
                        valid_speeds = all(math.isfinite(s) and s >= 0 for s in speeds)
                        roads.writerow({'time_sec': now, 'edge_id': edge, 'mode': mode, 'count': len(speeds),
                            'mean_speed_mps': sum(speeds) / len(speeds) if speeds and valid_speeds else '',
                            'halting_count': sum(0 <= s < parameters['simulation']['stop_speed_mps'] for s in speeds),
                            'traffic_count': len(moving),
                            'traffic_mean_speed_mps': sum(moving) / len(moving) if moving else '',
                            'traffic_halting_count': sum(s < parameters['simulation']['stop_speed_mps'] for s in moving),
                            'parked_count': parked[edge, mode], 'reentry_pending_count': reentry[edge, mode],
                            'unplaced_reentry_count': unplaced[edge, mode], 'closed': edge in closed[physical],
                            'observation_status': 'observed' if valid_speeds else 'partial_reentry_speed'})
                counts['snapshots'] += 1
                atomic_json(run_dir / 'progress.json', {'at_jst': stamp(), 'run_id': run_id, 'time_sec': now,
                    'end_sec': end, 'wall_sec': time.monotonic() - wall_start, 'counts': counts.copy(),
                    'people_states': dict(Counter(p['status'] for p in people.values())),
                    'request_states': dict(Counter(q['status'] for q in requests.values()))})
                events.flush()
                for edge, attrs in graphs['passenger'].nodes(data=True):
                    speeds = traffic.get((edge, 'car'), []) + traffic.get((edge, 'drt'), [])
                    attrs['travel_sec'] = attrs['length'] / max(sum(speeds) / len(speeds), .1) if speeds else attrs['free_sec']
                for a, b, data in graphs['passenger'].edges(data=True):
                    data['travel_sec'] = graphs['passenger'].nodes[b]['travel_sec']
            if now >= end:
                break
            for pid in list(walking_routes):
                p = people[pid]
                spent = max(p['walk_model_passed_m'], p['walk_speed_integral_m'])
                step_bound = parameters['population']['walk_mps'][p['person_type']] * manifest['step_sec']
                if spent + step_bound > parameters['population']['walk_limit_m']:
                    p['walk_budget_lead_m'] = max(0, parameters['population']['walk_limit_m'] - spent)
                    event(now, 'walk_budget_pre_step_stop', person_id=pid, spent_m=spent,
                          remaining_budget_m=p['walk_budget_lead_m'], max_next_step_m=step_bound)
                    remove_actor(pid, 'pedestrian', 'walk_limit', now)
            for p in people.values():
                if p['status'] in ('waiting_origin', 'assigned_origin', 'boarding'):
                    origin = origins[p['origin_id']]['edge_id']
                    p['origin_ped_closed_wait_sec'] += manifest['step_sec'] * (origin in closed['pedestrian'])
                    p['origin_vehicle_closed_wait_sec'] += manifest['step_sec'] * (origin in closed['passenger'])
            t.simulationStep()
            upper = float(t.simulation.getTime())
            counts['steps'] += 1
            teleported = t.simulation.getStartingTeleportIDList()
            colliding = t.simulation.getCollidingVehiclesIDList()
            counts['teleports'] += len(teleported)
            counts['collisions'] += len(colliding)
            for kind, actor_ids in [('teleport_started', teleported), ('collision_observed', colliding)]:
                for actor_id in actor_ids:
                    event(upper, kind, actor_id=actor_id)
            latest_v, latest_p = t.vehicle.getAllSubscriptionResults(), t.person.getAllSubscriptionResults()
            pending_insertion = set(t.simulation.getPendingVehicles())
            onroad_ids = set(t.vehicle.getIDList())
            counts['missing_vehicle_subscriptions'] += len(set(t.vehicle.getIDList()) - set(latest_v))
            counts['missing_person_subscriptions'] += len(set(t.person.getIDList()) - set(latest_p))
            for mode, observed in [('passenger', latest_v), ('pedestrian', latest_p)]:
                for actor, data in observed.items():
                    edge = data.get(tc.VAR_ROAD_ID, '')
                    xy = data.get(tc.VAR_POSITION, (tc.INVALID_DOUBLE_VALUE, tc.INVALID_DOUBLE_VALUE))
                    valid = all(math.isfinite(value) and value != tc.INVALID_DOUBLE_VALUE for value in xy)
                    speed = float(data.get(tc.VAR_SPEED, tc.INVALID_DOUBLE_VALUE))
                    if mode == 'passenger' and actor in vehicles:
                        v = vehicles[actor]
                        initial_pending = (actor in pending_insertion and actor not in onroad_ids
                                           and v['status'] in ('pending', 'pending_idle') and v['route_version'] == 0)
                        observed_state = traffic_observation_state(int(data[tc.VAR_STOPSTATE]), valid,
                                                                   v['reentry_expected'], initial_pending)
                        native_stop = native_parking_stop(t, actor) if observed_state == 'parked' else None
                        actors.writerow({'time_sec': upper, 'phase': 'after_step_before_control',
                            'actor_id': actor, 'kind': v['kind'], 'road_id': edge,
                            'lane_id': data[tc.VAR_LANE_ID],
                            'lane_position_m': data[tc.VAR_LANEPOSITION], 'x': xy[0], 'y': xy[1], 'speed_mps': speed,
                            'decel_mps2': data[tc.VAR_DECEL],
                            'distance_m': data[tc.VAR_DISTANCE], 'stop_state': data[tc.VAR_STOPSTATE],
                            'route_index': data[tc.VAR_ROUTE_INDEX], 'route_version': v['route_version'],
                            'status': v['status'], 'active_person': v['active_person'], 'members': json.dumps(v['members']),
                            'observation_kind': observed_state, 'reentry_source_edge': v.get('reentry_source_edge', ''),
                            'native_stop_lane_id': native_stop['lane_id'] if native_stop else '',
                            'native_stop_start_pos_m': native_stop['start_pos_m'] if native_stop else '',
                            'native_stop_end_pos_m': native_stop['end_pos_m'] if native_stop else '',
                            'native_stop_flags': native_stop['flags'] if native_stop else ''})
                        if observed_state == 'missing' or (observed_state == 'onroad' and (not math.isfinite(speed) or speed < 0)):
                            raise RuntimeError('Unexplained vehicle observation missing: ' + actor)
                        if observed_state == 'departure_pending':
                            counts['departure_pending_frames'] += 1
                            continue
                        distance = float(data.get(tc.VAR_DISTANCE, 0))
                        increment = max(0, distance - v['distance_m'])
                        if not v['members']:
                            v['empty_distance_m'] += increment
                        v['distance_m'] = max(v['distance_m'], distance)
                        if v['status'] == 'pending':
                            v['status'] = 'travelling'
                        if observed_state == 'reentry_pending':
                            counts['reentry_pending_frames'] += 1
                            event(upper, 'vehicle_reentry_pending', vehicle_id=actor, source_edge=v['reentry_source_edge'], observed_distance_m=distance)
                        elif valid and edge and v['reentry_expected']:
                            event(upper, 'vehicle_reentry_observed', vehicle_id=actor, edge_id=edge, observed_distance_m=distance)
                            v['reentry_expected'] = False
                    elif mode == 'pedestrian' and actor in walking_routes:
                        p = people[actor]
                        actors.writerow({'time_sec': upper, 'phase': 'after_step_before_control',
                            'actor_id': actor, 'kind': 'walk', 'road_id': edge,
                            'lane_position_m': data[tc.VAR_LANEPOSITION], 'x': xy[0], 'y': xy[1], 'speed_mps': speed,
                            'status': p['status'], 'members': json.dumps([actor]),
                            'observation_kind': 'onroad' if valid else 'missing'})
                        if not valid or not math.isfinite(speed) or speed < 0:
                            raise RuntimeError('Unexplained pedestrian observation missing: ' + actor)
                        maximum = parameters['population']['walk_mps'][p['person_type']]
                        if speed > maximum + 1e-6:
                            raise RuntimeError('Pedestrian speed exceeds registered maximum: ' + actor)
                        p['walk_speed_integral_m'] += speed * manifest['step_sec']
                    if not edge or edge.startswith(':'):
                        continue
                    path = vehicles[actor]['route'] if mode == 'passenger' else walking_routes.get(actor, [])
                    observe_transition(actor, mode, edge, upper, path)
        for pid, p in people.items():
            if p['status'] not in FINAL:
                event(end, 'horizon_finalize', person_id=pid, previous_status=p['status'])
                person_state(pid, 'time_limit', end)
        for pid, q in requests.items():
            if q['status'] in ('pending', 'accepted', 'boarding', 'onboard', 'alighting'):
                request_event(pid, 'horizon', end)
            q['person_final_status'] = people[pid]['status']
            q['person_final_mode'] = people[pid]['mode']
            for field in ('fallback_sec', 'depart_sec', 'arrival_sec', 'admitted_sec'):
                q[field] = people[pid][field]
        for stream in handles:
            stream.close()
        handles = []
        t.close()
        connection = None
        distances = {trip.attrib['id']: float(trip.attrib['routeLength'])
                     for trip in ET.parse(run_dir / 'tripinfo.xml').getroot().findall('tripinfo')}
        write_csv(run_dir / 'person_results.csv', list(people.values()))
        request_fields = ['request_id', 'person_id', 'status', 'vehicle_id', 'terminal_id', 'deadline_sec',
                          *time_fields, 'cancel_reason', 'person_final_status', 'person_final_mode']
        write_csv(run_dir / 'request_results.csv', [requests[pid] for pid in sorted(requests)], request_fields)
        write_csv(run_dir / 'vehicle_results.csv', [{'vehicle_id': vid, 'kind': v['kind'], 'status': v['status'],
            'distance_m': distances.get(vid, ''), 'observed_distance_m': v['distance_m'],
            'observed_empty_distance_m': v['empty_distance_m'], 'maximum_onboard': v.get('maximum_onboard', 0),
            'passenger_capacity': parameters['operation']['passenger_capacity'] if v['kind'] == 'drt' else ''}
            for vid, v in sorted(vehicles.items())],
            ['vehicle_id', 'kind', 'status', 'distance_m', 'observed_distance_m',
             'observed_empty_distance_m', 'maximum_onboard', 'passenger_capacity'])
        write_csv(run_dir / 'facility_results.csv', [{'terminal_id': key, 'capacity': r['capacity'], 'admitted': occupancy[key]}
            for key, r in terminals.items() if r['kind'] == 'facility'])
        counts['closures_applied'] = sum(len(names) for at in applied for names in closure_events[at].values())
        manifest.update(status='COMPLETED', finished_at_jst=stamp(), summary={
            'people': len(people), 'states': dict(Counter(p['status'] for p in people.values())),
            'request_states': dict(Counter(q['status'] for q in requests.values())),
            'type_counts': dict(Counter(p['person_type'] for p in people.values())), 'counts': counts,
            'sumo_errors': summarize_sumo_error_log(run_dir / 'sumo_errors.log')},
            output_sha256={p.name: sha(p) for p in run_dir.iterdir() if p.is_file() and p.name != 'manifest.json'})
        atomic_json(run_dir / 'manifest.json', manifest)
        return manifest
    except BaseException as error:
        if connection is not None:
            debug = {'time_sec': locals().get('now'), 'vehicles': {}}
            try:
                for debug_id in connection.vehicle.getIDList():
                    if debug_id in locals().get('vehicles', {}):
                        debug['vehicles'][debug_id] = {
                            'controlled': vehicles[debug_id], 'road': connection.vehicle.getRoadID(debug_id),
                            'route_index': connection.vehicle.getRouteIndex(debug_id),
                            'route': connection.vehicle.getRoute(debug_id),
                            'subscription': locals().get('latest_v', {}).get(debug_id, {})}
            except Exception as diagnostic_error:
                debug['diagnostic_error'] = str(diagnostic_error)
            atomic_json(run_dir / 'runtime_debug.json', debug)
            try:
                connection.close()
            except Exception as close_error:
                manifest['connection_close_error'] = str(close_error)
        for stream in handles:
            stream.close()
        (run_dir / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        manifest.update(status='FAILED', finished_at_jst=stamp(), error_type=type(error).__name__, error=str(error))
        atomic_json(run_dir / 'manifest.json', manifest)
        raise
