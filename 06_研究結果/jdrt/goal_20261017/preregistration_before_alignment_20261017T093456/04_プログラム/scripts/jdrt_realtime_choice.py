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


def traffic_observation_state(stop_state, position_valid, reentry_expected):
    if stop_state & 2:
        return 'parked'
    if not position_valid:
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
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def load_graphs(directory):
    raw=json.loads((directory/'graphs.json').read_text(encoding='utf-8'));graphs={}
    for mode,data in raw.items():
        g=nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from((n,a) for n,a in data['nodes'].items());g.add_edges_from((a,b,d) for a,b,d in data['edges']);graphs[mode]=g
    return graphs

def route(graph,start,end,weight='length'):
    try:return nx.shortest_path(graph,start,end,weight=weight)
    except (nx.NodeNotFound,nx.NetworkXNoPath):return []

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


def run(cell_id, run_id, purpose='core', smoke_end=1800):
    parameters, directory, input_manifest = load_inputs()
    cell = next((c for c in parameters['cells'] if c['cell_id'] == cell_id), None)
    if cell is None or purpose not in ('core', 'smoke'):
        raise ValueError('Unregistered cell or purpose')
    workspace = ROOT / parameters['workspace']
    implementation = {name: sha(ROOT / name) for name in parameters['execution']['implementation_files']}
    if purpose == 'core':
        receipt_path = workspace / 'preflight_ready.json'
        if not receipt_path.is_file():
            raise RuntimeError('Current registered preflight READY receipt required')
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        required_checks = set(parameters.get('acceptance_gates', {})) | {'unit_tests', 'six_file_record_transaction', 'storage_and_single_writer'}
        if (receipt['status'] != 'READY' or not required_checks <= set(receipt['checks'])
                or not all(value is True for value in receipt['checks'].values())
                or receipt['implementation_sha256'] != implementation
                or receipt['parameter_sha256'] != sha(PARAM)
                or receipt['input_manifest_sha256'] != sha(directory / 'manifest.json')):
            raise RuntimeError('Current registered preflight READY receipt required')
    run_dir = workspace / ('runs' if purpose == 'core' else 'smoke') / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    scenario, seed = cell['scenario'], cell['seed']
    end = parameters['simulation']['duration_sec'] if purpose == 'core' else smoke_end
    manifest = {'protocol': parameters['protocol'], 'run_id': run_id, **cell, 'purpose': purpose,
                'pid': os.getpid(), 'status': 'RUNNING', 'started_at_jst': stamp(),
                'parameter_sha256': sha(PARAM), 'input_manifest_sha256': sha(directory / 'manifest.json'),
                'input_directory': directory.relative_to(ROOT).as_posix(),
                'implementation_sha256': implementation, 'execution_contract': parameters['execution'],
                'end_sec': end, 'step_sec': parameters['simulation']['step_sec'],
                'snapshot_sec': parameters['simulation']['snapshot_sec']}
    atomic_json(run_dir / 'manifest.json', manifest)
    connection, handles = None, []
    try:
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
            realized = [p for p in realized if p['person_id'] in chosen]
            for i, p in enumerate(realized):
                p['ready_sec'] = i % 10
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
                'origin_ped_closed_wait_sec': 0., 'origin_vehicle_closed_wait_sec': 0.}
        graphs = load_graphs(directory)
        original_nodes = {mode: set(g) for mode, g in graphs.items()}
        hazards = read_csv(directory / 'hazard.csv')
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
        ET.SubElement(route_xml, 'vType', id='car', vClass='passenger', length='4.5', minGap='2.5')
        ET.SubElement(route_xml, 'vType', id='drt', vClass='passenger', length='4.5', minGap='2.5',
                      personCapacity=str(parameters['operation']['passenger_capacity']))
        for typ, speed in parameters['population']['walk_mps'].items():
            ET.SubElement(route_xml, 'vType', id='walk_' + typ, vClass='pedestrian', maxSpeed=str(speed))
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
        import sumolib
        net = sumolib.net.readNet(str(directory / 'bounded.net.xml'), withInternal=True)
        walk_topology = nx.Graph()
        for edge in net.getEdges(withInternal=True):
            name = edge.getID()
            if (name in original_nodes['pedestrian'] or name.startswith(':')) and edge.allows('pedestrian'):
                walk_topology.add_node(name, length=edge.getLength())
        for edge in net.getEdges(withInternal=True):
            if edge.getID() not in walk_topology:
                continue
            for other, connections in edge.getAllowedOutgoing('pedestrian').items():
                if other.getID() not in walk_topology:
                    continue
                internal, _ = net.getInternalPath(connections)
                chain = [edge] + (internal or []) + [other]
                if all(item.getID() in walk_topology for item in chain):
                    for a, b in zip(chain, chain[1:]):
                        walk_topology.add_edge(a.getID(), b.getID(), length=(a.getLength() + b.getLength()) / 2)
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
        vehicle_vars = [tc.VAR_ROAD_ID, tc.VAR_SPEED, tc.VAR_DISTANCE, tc.VAR_ROUTE_INDEX]
        person_vars = [tc.VAR_ROAD_ID, tc.VAR_SPEED]
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
            'mean_speed_mps', 'halting_count', 'closed', 'observation_status'])
        transitions = gz_writer('transitions.csv.gz', ['time_lower_sec', 'time_upper_sec', 'actor_id',
            'mode', 'from_edge', 'to_edge', 'kind', 'closure_sec', 'ambiguous'])
        candidate_fields = ['cycle', 'stage', 'time_sec', 'vehicle_id', 'person_id', 'pickup_sec', 'delivery_sec',
            'waiting_sec', 'vulnerability', 'forecast_remaining_sec', 'required_sec', 'pickup_kind', 'delivery_kind',
            'forecast_remaining_kind', 'required_kind', 'pickup_route', 'delivery_route', 'pickup_before_deadline',
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
            'missing_vehicle_subscriptions', 'missing_person_subscriptions', 'reentry_pending_frames']}
        def destination(pid):
            return terminals[people[pid]['terminal_id']]['edge_id']
        def cached_route(mode, start, target):
            key = (mode, start, target, len(closed[mode]))
            if key not in route_cache:
                route_cache[key] = route(graphs[mode], start, target)
            return route_cache[key]
        def walking_path(start, target, position=0):
            try:
                path = nx.shortest_path(walk_topology, start, target, weight='length')
                return [n for n in path if not n.startswith(':')], max(0, sum(walk_topology.nodes[n]['length'] for n in path) - position)
            except (nx.NodeNotFound, nx.NetworkXNoPath):
                return [], math.inf
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
            path, length = walking_path(origin, destination(pid)) if origin and p['terminal_id'] else ([], math.inf)
            reason = ('no_origin_connection' if not origin else 'no_route' if not p['terminal_id']
                      else 'initial_or_current_closed' if origin in closed['pedestrian'] else 'no_route' if not path
                      else 'walk_limit' if length > parameters['population']['walk_limit_m'] else '')
            if reason:
                p['fallback_reason'] = reason if fallback else ''
                person_state(pid, reason, now)
                return
            if pid in t.person.getIDList():
                raise RuntimeError('Duplicate walking actor: ' + pid)
            t.person.add(pid, origin, pos=0, typeID='walk_' + p['person_type'])
            t.person.appendWalkingStage(pid, path, arrivalPos=-1, speed=parameters['population']['walk_mps'][p['person_type']])
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
        def bus_route(vid, path, now):
            v = vehicles[vid]
            current = t.vehicle.getRoadID(vid)
            position = t.vehicle.getLanePosition(vid)
            distance = t.vehicle.getDistance(vid)
            actual_path = set_vehicle_route(t, vid, path, lane_info, end + 1)
            v['route'], v['route_version'] = actual_path, v['route_version'] + 1
            v['reentry_expected'] = t.vehicle.getPosition(vid)[0] == tc.INVALID_DOUBLE_VALUE
            last.pop(vid, None)
            event(now, 'drt_route', vehicle_id=vid, route=actual_path, requested_remaining_route=path, source_edge=current,
                  source_lane_position=position, source_distance_m=distance, reentry_expected=v['reentry_expected'])
        def observe_transition(actor, mode, edge, now, path):
            prior = last.get(actor)
            index = (int(latest_v.get(actor, {}).get(tc.VAR_ROUTE_INDEX, len(path) - 1))
                     if mode == 'passenger' else path.index(edge))
            if mode == 'passenger' and actor in vehicles and vehicles[actor]['status'] == 'arrived':
                index = len(path) - 1
            if prior and prior[0] != edge:
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
                        elif name in walk_topology:
                            walk_topology.remove_node(name)
                        event(now, 'closure_applied', edge_id=name, mode=mode, **control_times[at])
                applied.add(at)
            if due:
                route_cache.clear()
            for vid, v in vehicles.items():
                if v['status'] in ('not_ready', 'arrived', 'stranded'):
                    continue
                data = latest_v.get(vid, {})
                current = data.get(tc.VAR_ROAD_ID, '')
                if not current and v['reentry_expected'] and v['route'][0] in closed['passenger']:
                    remove_actor(vid, 'passenger', 'initial_or_current_closed', now)
                    continue
                action, next_external = vehicle_closure_action(v['route'], current,
                    int(data.get(tc.VAR_ROUTE_INDEX, -1)), closed['passenger'])
                if action in ('clear', 'defer'):
                    continue
                if action in ('remove_current', 'remove_junction'):
                    remove_actor(vid, 'passenger', 'initial_or_current_closed' if action == 'remove_current' else 'route_cut', now)
                    continue
                replacement = cached_route('passenger', current, v['route'][-1])
                if not replacement:
                    remove_actor(vid, 'passenger', 'route_cut', now)
                elif v['kind'] == 'drt':
                    bus_route(vid, replacement, now)
                else:
                    apply_remaining_route(t, vid, replacement, 'reroute_' + vid + '_' + str(v['route_version'] + 1))
                    v['route'], v['route_version'] = list(t.vehicle.getRoute(vid)), v['route_version'] + 1
                    last.pop(vid, None)
            for pid, path in list(walking_routes.items()):
                current = latest_p.get(pid, {}).get(tc.VAR_ROAD_ID, '')
                action, next_external = pedestrian_closure_action(path, current, last.get(pid, ('', 0))[0], closed['pedestrian'])
                if action in ('clear', 'defer'):
                    continue
                if action in ('remove_current', 'remove_junction'):
                    remove_actor(pid, 'pedestrian', 'initial_or_current_closed' if action == 'remove_current' else 'route_cut', now)
                    continue
                position = t.person.getLanePosition(pid)
                replacement, _ = walking_path(current, destination(pid), position)
                if not replacement:
                    remove_actor(pid, 'pedestrian', 'route_cut', now)
                else:
                    stage = t.person.getStage(pid)
                    stage.edges, stage.departPos = replacement, max(0, min(position, net.getEdge(current).getLength()))
                    t.person.replaceStage(pid, 0, stage)
                    walking_routes[pid] = replacement
                    last.pop(pid, None)
                    event(now, 'walk_reroute', person_id=pid, route=replacement, depart_pos=stage.departPos)
            if controller_tick:
                for pid, p in people.items():
                    if unboarded_expired(p['status'], now, p['deadline_sec'] if p['deadline_sec'] != '' else math.inf):
                        cancel_request(pid, now, 'timeout', requests[pid]['vehicle_id'])
            for vid, v in vehicles.items():
                if v['kind'] != 'car' or v['status'] != 'not_ready' or v['ready_sec'] > now:
                    continue
                origin = origins[v['origin_id']]['edge_id']
                path = cached_route('passenger', origin, terminals[v['terminal_id']]['edge_id']) if origin and v['terminal_id'] else []
                if not path:
                    reason = 'no_origin_connection' if not origin else 'initial_or_current_closed' if origin in closed['passenger'] else 'no_route'
                    for pid in v['members']:
                        person_state(pid, reason, now)
                    v['status'] = 'stranded'
                    continue
                route_counter += 1
                rid = 'private_' + str(route_counter)
                t.route.add(rid, path)
                t.vehicle.add(vid, rid, typeID='car', depart='now', departLane='best')
                t.vehicle.subscribe(vid, vehicle_vars)
                v.update(route=path, status='pending')
                for pid in v['members']:
                    people[pid]['depart_sec'] = now
                    person_state(pid, 'travelling_car', now)
                event(now, 'private_departure_requested', vehicle_id=vid, members=v['members'], route=path)
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
                        last.pop(vid, None)
                        event(now, 'cancel_wait_route', vehicle_id=vid, route=path)
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
                    path = cached_route('passenger', current, destination(pid))
                    if not path:
                        remove_actor(vid, 'passenger', 'stranded_drt', now)
                        continue
                    request_event(pid, 'boarded', now, vehicle_id=vid)
                    requests[pid]['boarded_sec'] = people[pid]['boarded_sec'] = now
                    v['members'], v['maximum_onboard'] = [pid], 1
                    person_state(pid, 'onboard', now)
                    bus_route(vid, path, now)
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
                        current = t.vehicle.getRoadID(vid)
                        if current not in graphs['passenger']:
                            raise RuntimeError('Idle vehicle is not on an observed open edge')
                        distances, paths = nx.single_source_dijkstra(graphs['passenger'], current, weight='travel_sec')
                        for pid in sorted(waiting):
                            p = people[pid]
                            origin = origins[p['origin_id']]['edge_id']
                            pickup_path = paths.get(origin, [])
                            delivery_path = cached_route('passenger', origin, destination(pid))
                            pickup = distances.get(origin, math.inf)
                            delivery = sum(graphs['passenger'].nodes[n]['free_sec'] for n in delivery_path) if delivery_path else math.inf
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
                    bus_route(vid, chosen['_pickup_path'], now)
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
                for vid, data in latest_v.items():
                    if vid in vehicles and vehicles[vid]['status'] not in ('stranded', 'arrived'):
                        edge = data.get(tc.VAR_ROAD_ID, '')
                        if edge in original_nodes['passenger']:
                            grouped[edge, vehicles[vid]['kind']].append(float(data[tc.VAR_SPEED]))
                for pid, data in latest_p.items():
                    edge = data.get(tc.VAR_ROAD_ID, '')
                    if pid in walking_routes and edge in original_nodes['pedestrian']:
                        grouped[edge, 'walk'].append(float(data[tc.VAR_SPEED]))
                for mode, physical in [('car', 'passenger'), ('drt', 'passenger'), ('walk', 'pedestrian')]:
                    for edge in sorted(original_nodes[physical]):
                        speeds = grouped.get((edge, mode), [])
                        roads.writerow({'time_sec': now, 'edge_id': edge, 'mode': mode, 'count': len(speeds),
                            'mean_speed_mps': sum(speeds) / len(speeds) if speeds else '',
                            'halting_count': sum(s < parameters['simulation']['stop_speed_mps'] for s in speeds),
                            'closed': edge in closed[physical], 'observation_status': 'observed'})
                counts['snapshots'] += 1
                atomic_json(run_dir / 'progress.json', {'at_jst': stamp(), 'run_id': run_id, 'time_sec': now,
                    'end_sec': end, 'wall_sec': time.monotonic() - wall_start, 'counts': counts.copy(),
                    'people_states': dict(Counter(p['status'] for p in people.values())),
                    'request_states': dict(Counter(q['status'] for q in requests.values()))})
                events.flush()
                for a, b, data in graphs['passenger'].edges(data=True):
                    speeds = grouped.get((b, 'car'), []) + grouped.get((b, 'drt'), [])
                    data['travel_sec'] = graphs['passenger'].nodes[b]['length'] / max(sum(speeds) / len(speeds), .1) if speeds else graphs['passenger'].nodes[b]['free_sec']
            if now >= end:
                break
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
            counts['missing_vehicle_subscriptions'] += len(set(t.vehicle.getIDList()) - set(latest_v))
            counts['missing_person_subscriptions'] += len(set(t.person.getIDList()) - set(latest_p))
            for mode, observed in [('passenger', latest_v), ('pedestrian', latest_p)]:
                for actor, data in observed.items():
                    edge = data.get(tc.VAR_ROAD_ID, '')
                    if mode == 'passenger' and actor in vehicles:
                        v = vehicles[actor]
                        distance = float(data.get(tc.VAR_DISTANCE, 0))
                        increment = max(0, distance - v['distance_m'])
                        if not v['members']:
                            v['empty_distance_m'] += increment
                        v['distance_m'] = max(v['distance_m'], distance)
                        if v['status'] == 'pending':
                            v['status'] = 'travelling'
                        if not edge and v['reentry_expected']:
                            counts['reentry_pending_frames'] += 1
                            event(upper, 'vehicle_reentry_pending', vehicle_id=actor, source_edge=v['route'][0], observed_distance_m=distance)
                        elif edge and v['reentry_expected']:
                            event(upper, 'vehicle_reentry_observed', vehicle_id=actor, edge_id=edge, observed_distance_m=distance)
                            v['reentry_expected'] = False
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
            for vid, v in sorted(vehicles.items())])
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
