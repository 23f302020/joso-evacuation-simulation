"""Real SUMO cancellation/stop probes. Synthetic fixtures, never research cells."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET

from scripts.jdrt_choice_toolchain import resolve_choice_toolchain, load_choice_traci, choice_runtime_fingerprint
from scripts.jdrt.full_run import summarize_sumo_error_log
from scripts.jdrt_choice_policy import request_transition, unboarded_expired
from scripts.jdrt_realtime_choice import cancel_vehicle_to_wait, set_vehicle_route, traffic_observation_state

ROOT = Path(__file__).resolve().parents[2]


def stamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def atomic(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_probe(run_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id):
        raise ValueError('Use a simple unique probe ID')
    params = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    workspace = ROOT / params['workspace']
    directory = workspace / 'technical' / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {'run_id': run_id, 'protocol': params['protocol'], 'purpose': 'technical_probe',
                'status': 'RUNNING', 'pid': os.getpid(), 'started_at_jst': stamp(),
                'implementation_sha256': {str(path.relative_to(ROOT)): sha(path) for path in
                    (Path(__file__), ROOT / '04_プログラム/scripts/jdrt_realtime_choice.py',
                     ROOT / '04_プログラム/scripts/jdrt_choice_policy.py')},
                'research_adoption_permitted': False}
    atomic(directory / 'manifest.json', manifest)
    try:
        for name, expected in manifest['implementation_sha256'].items():
            archived = directory / 'implementation' / name
            archived.parent.mkdir(parents=True, exist_ok=True)
            archived.write_bytes((ROOT / name).read_bytes())
            if sha(archived) != expected:
                raise ValueError('Probe source changed during archival')
        toolchain = resolve_choice_toolchain()
        binary = toolchain['sumo']
        traci = load_choice_traci(toolchain)
        manifest['runtime_sha256'] = choice_runtime_fingerprint(toolchain, traci)
        manifest['sumo_version'] = subprocess.run([str(binary), '--version'], capture_output=True,
                                                  text=True, check=True).stdout.splitlines()[0]
        nodes = ET.Element('nodes')
        for name, x, y in [('A', 0, 0), ('B', 100, 0), ('C', 100, 100), ('D', 200, 100)]:
            ET.SubElement(nodes, 'node', id=name, x=str(x), y=str(y), type='priority')
        edges = ET.Element('edges')
        for index, (start, end) in enumerate([('A', 'B'), ('B', 'C'), ('C', 'D')]):
            ET.SubElement(edges, 'edge', id='e' + str(index), **{'from': start, 'to': end},
                          speed='5', numLanes='1', allow='passenger', sidewalkWidth='2')
        ET.ElementTree(nodes).write(directory / 'nodes.xml', encoding='utf-8', xml_declaration=True)
        ET.ElementTree(edges).write(directory / 'edges.xml', encoding='utf-8', xml_declaration=True)
        command = [str(toolchain['netconvert']), '--node-files', 'nodes.xml',
                   '--edge-files', 'edges.xml', '--output-file', 'fixture.net.xml', '--no-turnarounds', 'true']
        network = subprocess.run(command, cwd=directory, capture_output=True, text=True)
        (directory / 'netconvert.log').write_text(network.stdout + network.stderr, encoding='utf-8')
        network.check_returncode()
        net = ET.parse(directory / 'fixture.net.xml').getroot()
        lanes = {}
        for edge in net.findall('edge'):
            if edge.attrib['id'].startswith(':'):
                continue
            for lane in edge.findall('lane'):
                if 'passenger' in lane.attrib.get('allow', '').split():
                    lanes[edge.attrib['id']] = (int(lane.attrib['index']), float(lane.attrib['length']))
        if set(lanes) != {'e0', 'e1', 'e2'}:
            raise ValueError('Fixture passenger lane definitions incomplete')
        reports = []
        for case in ('stop_release_delivery', 'external_cancel', 'internal_cancel', 'deadline_equal'):
            reports.append(run_case(directory, case, binary, traci, lanes))
            atomic(directory / 'progress.json', {'at_jst': stamp(), 'completed_cases': len(reports),
                                                'last_case': case, 'last_status': reports[-1]['status']})
        for reverse in (False, True):
            reports.append(run_placement_case(directory, binary, traci, lanes, reverse))
        reports.append(run_placement_case(directory, binary, traci, lanes, False, reroute=True))
        manifest.update(status='COMPLETED' if all(r['status'] == 'PASS' for r in reports) else 'FAILED',
                        finished_at_jst=stamp(), cases=reports)
        atomic(directory / 'manifest.json', manifest)
        if manifest['status'] != 'COMPLETED':
            raise RuntimeError('Technical probe checks failed; preserve this directory')
        return manifest
    except BaseException as error:
        (directory / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        manifest.update(status='FAILED', finished_at_jst=stamp(), error_type=type(error).__name__, error=str(error))
        atomic(directory / 'manifest.json', manifest)
        raise


def run_case(parent, name, binary, traci, lanes):
    directory = parent / name
    directory.mkdir(exist_ok=False)
    types = ET.Element('routes')
    ET.SubElement(types, 'vType', id='drt', vClass='passenger', length='4.5', minGap='2.5',
                  maxSpeed='5', sigma='0')
    ET.SubElement(types, 'vType', id='walk', vClass='pedestrian', maxSpeed='0.58')
    ET.ElementTree(types).write(directory / 'types.xml', encoding='utf-8', xml_declaration=True)
    command = [str(binary), '--net-file', '../fixture.net.xml', '--route-files', 'types.xml',
               '--step-length', '0.5', '--seed', '23423', '--time-to-teleport', '-1',
               '--collision.action', 'teleport', '--no-step-log', 'true', '--duration-log.disable', 'true',
               '--log', 'sumo.log', '--error-log', 'sumo_errors.log', '--tripinfo-output', 'tripinfo.xml',
               '--tripinfo-output.write-unfinished', 'true']
    label = parent.name + '_' + name
    old = Path.cwd()
    connection = None
    try:
        os.chdir(directory)
        traci.start(command, label=label, doSwitch=False, verbose=False)
        connection = traci.getConnection(label)
    finally:
        os.chdir(old)
    t = connection
    start = time.monotonic()
    checks, actions = {}, []
    teleports = collisions = 0
    phase = 'approach'
    cancel_pending = False
    until = None
    walker_added = False
    walker_arrived = False
    request = 'accepted'
    completed = False
    reentry = None
    end = 1600
    try:
        t.route.add('initial', ['e0'] if name in ('stop_release_delivery', 'deadline_equal') else ['e0', 'e1', 'e2'])
        t.vehicle.add('v', 'initial', typeID='drt', depart='now', departLane=str(lanes['e0'][0]))
        target = 'e0' if name in ('stop_release_delivery', 'deadline_equal') else 'e2'
        t.vehicle.setStop('v', target, pos=lanes[target][1] - 1, laneIndex=lanes[target][0],
                          duration=end + 1, flags=traci.constants.STOP_PARKING)
        t.vehicle.subscribe('v', [traci.constants.VAR_ROAD_ID, traci.constants.VAR_ROUTE_INDEX])
        with (directory / 'steps.jsonl').open('w', encoding='utf-8') as stream:
            while float(t.simulation.getTime()) <= end:
                now = float(t.simulation.getTime())
                ids = set(t.vehicle.getIDList())
                if 'p' in t.simulation.getArrivedPersonIDList():
                    walker_arrived = True
                if 'v' in ids:
                    edge = t.vehicle.getRoadID('v')
                    stopped = t.vehicle.isStopped('v')
                    before_position = t.vehicle.getPosition('v')
                    before_lane_position = t.vehicle.getLanePosition('v')
                    before_distance = t.vehicle.getDistance('v')
                    valid_position = before_position[0] != traci.constants.INVALID_DOUBLE_VALUE
                    if reentry is not None and valid_position:
                        elapsed = now - reentry['time_sec']
                        increment = before_distance - reentry['distance_m']
                        checks['release_reentry_continuous_distance'] = (increment >= 0
                            and increment <= 5 * elapsed + 1e-6)
                        if edge == reentry['edge']:
                            checks['release_reentry_retains_progress'] = (before_lane_position >= reentry['lane_position']
                                and before_lane_position - reentry['lane_position'] <= 5 * elapsed + 1e-6)
                        else:
                            checks['release_reentry_retains_progress'] = increment >= lanes[reentry['edge']][1] - reentry['lane_position']
                        actions.append({'time_sec': now, 'event': 'first_valid_reentry', 'edge': edge,
                                        'position': before_position, 'lane_position': before_lane_position,
                                        'distance_m': before_distance, 'elapsed_sec': elapsed})
                        reentry = None
                    if name == 'stop_release_delivery':
                        if phase == 'approach' and stopped:
                            actual_route = set_vehicle_route(t, 'v', ['e0', 'e1'], lanes, end + 1)
                            checks['returned_route_matches_backend'] = actual_route == list(t.vehicle.getRoute('v'))
                            checks['release_preserves_odometer_during_control'] = t.vehicle.getDistance('v') == before_distance
                            reentry = {'time_sec': now, 'edge': edge, 'lane_position': before_lane_position,
                                       'distance_m': before_distance}
                            actions.append({'time_sec': now, 'event': 'assign_from_stopped',
                                'world_position_before': before_position, 'world_position_after': t.vehicle.getPosition('v'),
                                'lane_position_before': before_lane_position, 'lane_position_after': t.vehicle.getLanePosition('v'),
                                'distance_before': before_distance, 'distance_after': t.vehicle.getDistance('v')})
                            phase = 'pickup'
                        elif phase == 'pickup' and edge == 'e1' and stopped:
                            request = request_transition(request, 'boarding_started')
                            until = now + 300
                            actions.append({'time_sec': now, 'event': 'boarding_started'})
                            phase = 'boarding'
                        elif phase == 'boarding' and now >= until:
                            request = request_transition(request, 'boarded')
                            actual_route = set_vehicle_route(t, 'v', ['e1', 'e2'], lanes, end + 1)
                            checks['returned_route_matches_backend'] &= actual_route == list(t.vehicle.getRoute('v'))
                            actions.append({'time_sec': now, 'event': 'boarded'})
                            phase = 'delivery'
                        elif phase == 'delivery' and edge == 'e2' and stopped:
                            request = request_transition(request, 'alighting_started')
                            until = now + 300
                            actions.append({'time_sec': now, 'event': 'alighting_started'})
                            phase = 'alighting'
                        elif phase == 'alighting' and now >= until:
                            request = request_transition(request, 'alighted')
                            actions.append({'time_sec': now, 'event': 'alighted'})
                            completed = request == 'served'
                    else:
                        trigger = (phase == 'approach' and (
                            (name == 'external_cancel' and now >= 10 and not edge.startswith(':'))
                            or (name == 'internal_cancel' and edge.startswith(':'))
                            or (name == 'deadline_equal' and now >= 30 and stopped)))
                        if trigger:
                            if name == 'deadline_equal':
                                checks['expiry_before_equal_boarding'] = unboarded_expired('assigned_origin', now, now)
                            request = request_transition(request, 'timeout')
                            phase = 'cancel_pending'
                            cancel_pending = True
                            actions.append({'time_sec': now, 'event': 'cancelled', 'edge': edge,
                                            'position': before_position})
                            if name == 'internal_cancel':
                                checks['internal_control_deferred'] = cancel_vehicle_to_wait(t, 'v', lanes, end + 1, .5) is None
                            t.person.add('p', 'e0', pos=0, typeID='walk')
                            t.person.appendWalkingStage('p', ['e0', 'e1', 'e2'], arrivalPos=-1, speed=.58)
                            walker_added = True
                            actions.append({'time_sec': now, 'event': 'fallback_walk_requested', 'origin': 'e0'})
                        if cancel_pending:
                            path = cancel_vehicle_to_wait(t, 'v', lanes, end + 1, .5)
                            if path:
                                checks['cancel_returned_route_matches_backend'] = path == list(t.vehicle.getRoute('v'))
                                checks['cancel_control_does_not_move_position'] = t.vehicle.getPosition('v') == before_position
                                checks['only_cancel_wait_stop_remains'] = (len(t.vehicle.getStops('v')) == 1
                                    and t.vehicle.getStops('v')[0].lane.rsplit('_', 1)[0] == edge)
                                actions.append({'time_sec': now, 'event': 'cancel_wait_route', 'edge': edge,
                                    'world_position_before': before_position, 'world_position_after': t.vehicle.getPosition('v'),
                                    'lane_position_before': before_lane_position, 'lane_position_after': t.vehicle.getLanePosition('v'),
                                    'distance_before': before_distance, 'distance_after': t.vehicle.getDistance('v')})
                                cancel_pending = False
                                phase = 'waiting'
                        if phase == 'waiting' and t.vehicle.isStopped('v') and walker_arrived:
                            completed = True
                    stream.write(json.dumps({'time_sec': now, 'edge': edge, 'position': before_position,
                        'lane_position': t.vehicle.getLanePosition('v'), 'distance_m': t.vehicle.getDistance('v'),
                        'speed': t.vehicle.getSpeed('v'), 'phase': phase, 'request': request,
                        'actual_route': t.vehicle.getRoute('v'), 'actual_route_index': t.vehicle.getRouteIndex('v'),
                        'subscription': t.vehicle.getSubscriptionResults('v'),
                        'stops': [dict(stop.__dict__) for stop in t.vehicle.getStops('v')],
                        'walking_actor_count': len(t.person.getIDList())}, ensure_ascii=False) + '\n')
                elif now > 1:
                    raise RuntimeError('Controlled vehicle left the fixture unexpectedly')
                if completed:
                    break
                t.simulationStep()
                teleports += len(t.simulation.getStartingTeleportIDList())
                collisions += len(t.simulation.getCollidingVehiclesIDList())
                if now % 60 == 0:
                    stream.flush()
                    atomic(parent / 'progress.json', {'at_jst': stamp(), 'case': name,
                                                      'sim_sec': t.simulation.getTime(), 'phase': phase})
        checks['completed'] = completed
        checks['zero_teleports'] = teleports == 0
        checks['zero_collisions'] = collisions == 0
        if name != 'stop_release_delivery':
            checks['single_fallback_completed'] = walker_added and walker_arrived and request == 'cancelled_timeout'
            checks['vehicle_retained_after_cancel'] = 'v' in set(t.vehicle.getIDList())
        t.close()
        connection = None
        errors = summarize_sumo_error_log(directory / 'sumo_errors.log')
        checks['sumo_error_zero'] = errors['error_count'] == 0
        report = {'case': name, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
                  'actions': actions, 'wall_sec': time.monotonic() - start, 'sumo_log_summary': errors}
        atomic(directory / 'report.json', report)
        return report
    except BaseException:
        (directory / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        if connection is not None:
            connection.close()


def run_placement_case(parent, binary, traci, lanes, reverse, reroute=False):
    name = 'placement_reroute' if reroute else 'placement_reverse' if reverse else 'placement_forward_parking'
    directory = parent / name
    directory.mkdir(exist_ok=False)
    types = ET.Element('routes')
    ET.SubElement(types, 'vType', id='drt', vClass='passenger', length='4.5', minGap='2.5', maxSpeed='5', sigma='0')
    ET.SubElement(types, 'vType', id='walk', vClass='pedestrian', maxSpeed='0.58')
    ET.ElementTree(types).write(directory / 'types.xml', encoding='utf-8', xml_declaration=True)
    command = [str(binary), '--net-file', '../fixture.net.xml', '--route-files', 'types.xml',
               '--step-length', '0.5', '--seed', '23423', '--time-to-teleport', '-1',
               '--no-step-log', 'true', '--duration-log.disable', 'true', '--error-log', 'sumo_errors.log',
               '--tripinfo-output', 'tripinfo.xml', '--tripinfo-output.write-unfinished', 'true']
    label = parent.name + '_' + name
    previous = Path.cwd()
    try:
        os.chdir(directory)
        traci.start(command, label=label, doSwitch=False, verbose=False)
        t = traci.getConnection(label)
    finally:
        os.chdir(previous)
    checks, measurements = {}, {}
    parked_frames = reentry_frames = 0
    walking_speed_integral = 0.
    max_walking_speed = 0.
    first_park = None
    released = False
    first_person = first_vehicle = None
    arrived = False
    rerouted = False
    try:
        t.route.add('initial', ['e0', 'e1'])
        t.vehicle.add('v', 'initial', typeID='drt', depart='now', departLane=str(lanes['e0'][0]), departPos='40')
        t.vehicle.setStop('v', 'e1', pos=40, laneIndex=lanes['e1'][0], duration=1200, flags=traci.constants.STOP_PARKING)
        origin_pos, arrival_pos = (80, 20) if reverse else (40, 20)
        path = ['e0'] if reverse else ['e0', 'e1', 'e2']
        t.person.add('p', 'e0', pos=origin_pos, typeID='walk')
        t.person.appendWalkingStage('p', path, arrivalPos=arrival_pos, speed=.58)
        measurements['initial_stages'] = [vars(t.person.getStage('p', i)) for i in range(t.person.getRemainingStages('p'))]
        with (directory / 'observations.jsonl').open('w', encoding='utf-8') as stream:
            while t.simulation.getTime() < 1200:
                t.simulationStep()
                now = float(t.simulation.getTime())
                record = {'time_sec': now}
                if 'v' in t.vehicle.getIDList():
                    position = t.vehicle.getPosition('v')
                    parking = t.vehicle.isStoppedParking('v')
                    stop_state = t.vehicle.getStopState('v')
                    state = traffic_observation_state(stop_state, position[0] != traci.constants.INVALID_DOUBLE_VALUE, released)
                    record.update(vehicle_lane_pos=t.vehicle.getLanePosition('v'), vehicle_position=position,
                                  vehicle_road=t.vehicle.getRoadID('v'), stop_state=stop_state,
                                  is_stopped_parking=parking, traffic_state=state,
                                  vehicle_speed=t.vehicle.getSpeed('v'))
                    if first_vehicle is None:
                        first_vehicle = record['vehicle_lane_pos']
                    if parking:
                        parked_frames += 1
                        checks['parked_state_matches_api'] = checks.get('parked_state_matches_api', True) and state == 'parked'
                        measurements['parked_vehicle_in_edge_ids'] = 'v' in t.edge.getLastStepVehicleIDs(record['vehicle_road'])
                        if first_park is None:
                            first_park = now
                            before = t.vehicle.getPosition('v')
                            before_lane = t.vehicle.getLanePosition('v')
                            cancel_vehicle_to_wait(t, 'v', lanes, 1200, .5)
                            checks['mid_edge_cancel_keeps_position'] = before == t.vehicle.getPosition('v') and t.vehicle.getLanePosition('v') == before_lane
                        elif now >= first_park + 10 and not released:
                            set_vehicle_route(t, 'v', ['e1', 'e2'], lanes, 1200, stop_pos=60)
                            released = True
                            reentry = traffic_observation_state(t.vehicle.getStopState('v'),
                                t.vehicle.getPosition('v')[0] != traci.constants.INVALID_DOUBLE_VALUE, True)
                            measurements['immediate_release_observation'] = reentry
                            checks['release_is_not_counted_onroad_during_invalid_position'] = reentry != 'onroad'
                    if state == 'reentry_pending':
                        reentry_frames += 1
                if 'p' in t.person.getIDList():
                    speed = t.person.getSpeed('p')
                    walking_speed_integral += speed * .5
                    max_walking_speed = max(max_walking_speed, speed)
                    record.update(person_lane_pos=t.person.getLanePosition('p'), person_road=t.person.getRoadID('p'),
                                  person_position=t.person.getPosition('p'), person_speed=speed,
                                  walking_stage=vars(t.person.getStage('p')))
                    if first_person is None:
                        first_person = record['person_lane_pos']
                        measurements['first_active_stage'] = record['walking_stage']
                    if reroute and not rerouted and now >= 50:
                        before = t.person.getPosition('p')
                        before_lane = t.person.getLanePosition('p')
                        stage = t.person.getStage('p')
                        old_length = stage.length
                        stage.departPos = before_lane
                        t.person.replaceStage('p', 0, stage)
                        replacement = t.person.getStage('p')
                        checks['replacement_keeps_lane_progress'] = before_lane == t.person.getLanePosition('p')
                        measurements['reroute_details'] = {'time_sec': now, 'position_before': before,
                            'position_after': t.person.getPosition('p'), 'lane_position': before_lane,
                            'old_stage_length_m': old_length, 'new_stage': vars(replacement),
                            'speed_integral_so_far_m': walking_speed_integral}
                        rerouted = True
                if 'p' in t.simulation.getArrivedPersonIDList():
                    arrived = True
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
                if arrived and released and t.vehicle.isStopped('v') and t.vehicle.getRoadID('v') == 'e2':
                    break
        checks['person_starts_at_requested_position'] = first_person == origin_pos
        checks['vehicle_starts_at_requested_position'] = first_vehicle == 40
        checks['person_arrived'] = arrived
        checks['parked_frames_observed'] = parked_frames > 0
        checks['target_mid_edge_stop'] = t.vehicle.getRoadID('v') == 'e2' and t.vehicle.getLanePosition('v') == 60
        t.close()
        t = None
        personinfo = ET.parse(directory / 'tripinfo.xml').getroot().find('personinfo')
        walking_length = sum(float(stage.attrib['routeLength']) for stage in personinfo.findall('walk'))
        measurements.update(walking_speed_integral_m=walking_speed_integral, personinfo_walk_length_m=walking_length,
                            integral_minus_personinfo_m=walking_speed_integral - walking_length,
                            max_observed_walk_speed_mps=max_walking_speed, parked_frames=parked_frames,
                            reentry_pending_frames=reentry_frames)
        errors = summarize_sumo_error_log(directory / 'sumo_errors.log')
        checks['sumo_error_zero'] = errors['error_count'] == 0
        report = {'case': name, 'status': 'PASS' if all(checks.values()) else 'FAIL',
                  'checks': checks, 'measurements': measurements, 'sumo_log_summary': errors}
        atomic(directory / 'report.json', report)
        return report
    except BaseException:
        (directory / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        if t is not None:
            t.close()
