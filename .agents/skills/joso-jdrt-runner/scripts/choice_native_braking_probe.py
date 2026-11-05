"""Collect a nonadoptable, fixed crossing/no-crossing native diagnostic pair."""
import hashlib
import argparse
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_sources(root, sources):
    root = Path(root).resolve()
    if not sources:
        raise ValueError('Explicit primary sources required')
    observed = {}
    for name, expected in sources.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Missing/outside-project primary source')
        observed[name] = sha(path)
        if observed[name] != expected:
            raise ValueError('Primary source changed: ' + name)
    return observed


def make_routes(plan, car_type, pedestrian):
    for key in ('car_depart_pos_m', 'walk_depart_pos_m', 'walk_speed_mps', 'walk_speed_factor'):
        value = plan[key]
        if not math.isfinite(value) or value < 0 or (key.startswith('walk_speed') and value == 0):
            raise ValueError('Finite nonnegative position and positive walking speed required')
    if not plan['car_route'] or not plan['walk_route'] or car_type.get('id') != 'car':
        raise ValueError('Explicit nonempty native routes and original car type required')
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', **car_type)
    ET.SubElement(routes, 'vType', id='walk_probe', vClass='pedestrian',
                  maxSpeed=str(plan['walk_speed_mps']), speedFactor=str(plan['walk_speed_factor']), speedDev='0')
    ET.SubElement(routes, 'route', id='local_car', edges=' '.join(plan['car_route']))
    ET.SubElement(routes, 'vehicle', id='probe_car', type='car', route='local_car', depart='0',
                  departPos=str(plan['car_depart_pos_m']), departLane=plan['car_depart_lane'],
                  departSpeed=plan['car_depart_speed'])
    if pedestrian:
        person = ET.SubElement(routes, 'person', id='probe_p3', type='walk_probe', depart='0',
                               departPos=str(plan['walk_depart_pos_m']))
        ET.SubElement(person, 'walk', edges=' '.join(plan['walk_route']), speed=str(plan['walk_speed_mps']))
    return ET.tostring(routes, encoding='utf-8', xml_declaration=True)


def collect_case(traci, binary, net, output, plan, state, save):
    from choice_native_guard import cim_utf8, endpoint_owners, now, write_json
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    command = list(map(str, [binary, '--net-file', net, '--route-files', output / 'routes.rou.xml',
        '--step-length', plan['step_sec'], '--seed', plan['seed'], '--begin', 0,
        '--end', plan['horizon_sec'] + plan['step_sec'], '--time-to-teleport', -1,
        '--collision.action', 'teleport', '--no-step-log', 'true', '--duration-log.disable', 'true',
        '--error-log', output / 'sumo_errors.log', '--log', output / 'sumo.log',
        '--tripinfo-output', output / 'tripinfo.xml', '--tripinfo-output.write-unfinished', 'true',
        '--remote-port', port]))
    entry = dict(case=output.name, command=command, binary_sha256=sha(binary), started_at_jst=now())
    connection = process = None
    with (output / 'native.stdout.log').open('xb') as stdout, (output / 'native.stderr.log').open('xb') as stderr, \
            (output / 'actors.jsonl').open('x', encoding='utf-8') as actors:
        try:
            env = {**os.environ, 'PATH': r'C:\Windows\System32;C:\Windows'}
            env.pop('SUMO_HOME', None)
            process = subprocess.Popen(command, cwd=output, env=env, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            entry['pid'] = process.pid
            state['active'] = entry
            save()
            entry['process_identity'] = cim_utf8(process.pid)
            connection = traci.connect(port, numRetries=30, proc=process, waitBetweenRetries=.1)
            connection.startTracing(str(output / 'traci_calls.py'), True,
                [connection.simulation, connection.vehicle, connection.vehicletype, connection.person])
            entry['server_endpoint_owners'] = endpoint_owners(port)
            if set(entry['server_endpoint_owners']) != {process.pid}:
                raise ValueError('Native endpoint owner mismatch')
            entry['api_version'] = connection.getVersion()
            if entry['api_version'][0] != traci.constants.TRACI_VERSION:
                raise ValueError('Native API/transport version mismatch')
            entry['car_type_properties'] = dict(
                decel=connection.vehicletype.getDecel('car'),
                emergencyDecel=connection.vehicletype.getEmergencyDecel('car'),
                accel=connection.vehicletype.getAccel('car'),
                minGap=connection.vehicletype.getMinGap('car'))
            while connection.simulation.getTime() < plan['horizon_sec']:
                connection.simulationStep()
                at = connection.simulation.getTime()
                cars = {}
                for vehicle in connection.vehicle.getIDList():
                    v = connection.vehicle
                    cars[vehicle] = dict(road=v.getRoadID(vehicle), lane=v.getLaneID(vehicle),
                        position=v.getLanePosition(vehicle), xy=v.getPosition(vehicle), speed=v.getSpeed(vehicle),
                        acceleration=v.getAcceleration(vehicle), decel=v.getDecel(vehicle),
                        emergencyDecel=v.getEmergencyDecel(vehicle), route_index=v.getRouteIndex(vehicle))
                people = {}
                for person in connection.person.getIDList():
                    d = connection.person
                    people[person] = dict(road=d.getRoadID(person), lane=d.getLaneID(person),
                        position=d.getLanePosition(person), xy=d.getPosition(person), speed=d.getSpeed(person),
                        max_speed=d.getMaxSpeed(person), speed_factor=d.getSpeedFactor(person))
                row = dict(time_sec=at, phase='after_step_before_control', vehicles=cars, persons=people,
                    collisions=list(connection.simulation.getCollidingVehiclesIDList()),
                    teleports=list(connection.simulation.getStartingTeleportIDList()))
                actors.write(json.dumps(row, allow_nan=False) + '\n')
                actors.flush()
                state['progress'] = dict(time_sec=at, end_sec=plan['horizon_sec'], case=output.name, at_jst=now())
                save()
                if row['collisions'] or row['teleports']:
                    raise ValueError('Native collision/teleport: preserve and stop pair')
        finally:
            if connection is not None:
                try:
                    connection.close(wait=False)
                except Exception as error:
                    entry['close_error'] = dict(type=type(error).__name__, message=str(error))
            if process is not None and (connection is not None or process.poll() is not None):
                while True:
                    try:
                        entry['exit_code'] = process.wait(timeout=15)
                        break
                    except subprocess.TimeoutExpired:
                        entry['waiting_on_same_child'] = now()
                        save()
            entry['ended_at_jst'] = now()
            write_json(output / 'child.json', entry)
    if entry.get('exit_code') != 0:
        raise ValueError('Native child nonzero/unobserved terminal exit')
    if entry.get('close_error'):
        raise ValueError('Native close failed; preserve terminal evidence')
    entry['artifacts'] = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--plan', required=True, type=Path)
    options = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}', options.run_id):
        raise ValueError('Fresh short technical ID required')
    root = options.project_root.resolve()
    sys.path.insert(0, str(root / '04_プログラム'))
    from realtime_choice_cell import ChoiceController, single_writer
    from choice_native_guard import cim_utf8, now, write_json
    from scripts.jdrt_choice_toolchain import resolve_choice_toolchain, load_choice_traci
    plan_raw = options.plan.read_bytes()
    plan = json.loads(plan_raw)
    if plan['schema'] != 'native_braking_probe_plan_v1' or not 0 < plan['step_sec'] <= plan['horizon_sec'] <= 60:
        raise ValueError('Explicit bounded nonadoptable diagnostic plan required')
    controller = ChoiceController(root)
    with single_writer(controller.workspace):
        controller.assert_idle()
        source_path, source_run = controller.find(plan['source_run_id'])
        if source_run['purpose'] != 'core' or source_run['status'] != 'INVALID':
            raise ValueError('Preserved rejected core required; no live/core replay')
        before = verify_sources(root, plan['sources'])
        if source_path.relative_to(root).as_posix() not in before:
            raise ValueError('Rejected core manifest binding missing')
        if plan['step_sec'] != source_run['step_sec'] or plan['seed'] != source_run['seed']:
            raise ValueError('Diagnostic step/seed must match the explicitly selected source')
        tools = resolve_choice_toolchain(require_manifest=True)
        manifest_path = Path(os.environ['JDRT_CHOICE_TOOLCHAIN_MANIFEST']).resolve()
        if sha(manifest_path) != plan['toolchain_manifest_sha256']:
            raise ValueError('Native toolchain differs from fixed plan')
        if sha(tools['sumo']) not in source_run['runtime_sha256'].values():
            raise ValueError('Native binary was not the rejected core runtime')
        traci = load_choice_traci(tools)
        net_path, types_path = root / plan['net_path'], root / plan['types_path']
        if plan['net_path'] not in before or plan['types_path'] not in before:
            raise ValueError('Net/type primary source binding missing')
        net = ET.parse(net_path).getroot()
        edges = {e.get('id'): e for e in net.findall('edge')}
        for route, position in ((plan['car_route'], plan['car_depart_pos_m']), (plan['walk_route'], plan['walk_depart_pos_m'])):
            if any(e not in edges for e in route) or not 0 <= position <= float(edges[route[0]].find('lane').get('length')):
                raise ValueError('Invalid native route/initial geometry; no clamping')
        car_type = next(t.attrib.copy() for t in ET.parse(types_path).getroot() if t.get('id') == 'car')
        output = controller.workspace / 'technical' / options.run_id
        output.mkdir(exist_ok=False)
        state = dict(protocol='realtime_choice_v1', purpose='technical_native_braking',
            run_id=options.run_id, pid=os.getpid(), process_identity=cim_utf8(os.getpid()),
            status='RUNNING', started_at_jst=now(), core_adoption_permitted=False, technical_ready=False,
            plan_sha256=hashlib.sha256(plan_raw).hexdigest(), sources=before,
            collector_sha256=sha(__file__), common_five=controller.implementation(), completed=[], active=None)
        state['helper_sha256'] = {name: sha(Path(__file__).parent / name)
                                  for name in ('choice_native_guard.py', 'choice_native_trace_build.py', 'realtime_choice_cell.py')}
        def save():
            state['updated_at_jst'] = now()
            write_json(output / 'manifest.json', state)
            if state.get('progress'):
                write_json(output / 'progress.json', state['progress'])
        try:
            (output / 'plan.json').write_bytes(plan_raw)
            (output / 'collector.py').write_bytes(Path(__file__).read_bytes())
            (output / 'bounded.net.xml').write_bytes(net_path.read_bytes())
            save()
            for present in (False, True):
                case = output / ('with_crossing_person' if present else 'without_person')
                case.mkdir()
                (case / 'routes.rou.xml').write_bytes(make_routes(plan, car_type, present))
                state['completed'].append(collect_case(traci, tools['sumo'], output / 'bounded.net.xml', case, plan, state, save))
                state['active'] = None
                save()
            verify_sources(root, before)
            if controller.implementation() != state['common_five'] or sha(__file__) != state['collector_sha256']:
                raise ValueError('Collector/common implementation changed during collection')
            resolve_choice_toolchain(require_manifest=True)
            state['status'] = 'COMPLETED'
        except BaseException as error:
            state.update(status='FAILED', error_type=type(error).__name__, error=str(error))
            raise
        finally:
            state['finished_at_jst'] = now()
            save()
    print(json.dumps(dict(status=state['status'], run_id=options.run_id, core_adoption_permitted=False)))


if __name__ == '__main__':
    main()
