"""Isolated native route-history counterexample; never a research cell."""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET


def stamp():
    return datetime.now().astimezone().isoformat()


def snapshot(t):
    return {'time_sec': t.simulation.getTime(), 'road': t.vehicle.getRoadID('v'),
            'lane': t.vehicle.getLaneID('v'), 'position': t.vehicle.getLanePosition('v'),
            'world_position': list(t.vehicle.getPosition('v')),
            'distance': t.vehicle.getDistance('v'), 'speed': t.vehicle.getSpeed('v'),
            'route': list(t.vehicle.getRoute('v')), 'route_index': t.vehicle.getRouteIndex('v'),
            'stopped': t.vehicle.isStopped('v')}


def route_id_candidate(t, vehicle, path, lanes, duration, route_id):
    """Isolated candidate; no transient-permission or route-error bypass."""
    from scripts.jdrt_realtime_choice import clear_vehicle_stops
    from traci.constants import STOP_PARKING
    current = t.vehicle.getRoadID(vehicle)
    if not path or current.startswith(':') or path[0] != current:
        raise ValueError('Candidate needs current external source')
    lane, length = lanes[path[-1]]
    if not 0 <= length-1 <= length:
        raise ValueError('Candidate stop position outside target lane')
    clear_vehicle_stops(t, vehicle)
    t.route.add(route_id, path)
    t.vehicle.setRouteID(vehicle, route_id)
    t.vehicle.setStop(vehicle, path[-1], pos=length-1, laneIndex=lane, duration=duration,
                      flags=STOP_PARKING)
    return list(t.vehicle.getRoute(vehicle))


def run(root, run_id, variant='control'):
    root = Path(root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', run_id):
        raise ValueError('New short technical ID required')
    sys.path.insert(0, str(root / '04_プログラム'))
    from scripts.jdrt_choice_toolchain import resolve_choice_toolchain, load_choice_traci, choice_runtime_fingerprint
    from scripts.jdrt_realtime_choice import set_vehicle_route
    cfg_path = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    if cfg['municipality_code'] != '08211' or cfg['protocol'] != 'realtime_choice_v1':
        raise ValueError('Current Joso choice registration required')
    workspace = root / cfg['workspace']
    for kind in ('runs', 'smoke', 'technical'):
        for path in (workspace / kind).glob('*/manifest.json'):
            if json.loads(path.read_text(encoding='utf-8')).get('status') == 'RUNNING':
                raise RuntimeError('An existing simulation owner must finish first')
    folder = workspace / 'technical' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {'run_id': run_id, 'protocol': cfg['protocol'], 'purpose': 'technical_probe',
                'pid': os.getpid(), 'status': 'RUNNING', 'started_at_jst': stamp(),
                'research_adoption_permitted': False, 'core_adoption_permitted': False,
                'scope': 'ISOLATED_ROUTE_HISTORY_DIAGNOSIS_NOT_REPAIR_OR_READY', 'variant': variant,
                'source_sha256': {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
                                  for p in [Path(__file__).resolve(), root / '04_プログラム/scripts/jdrt_realtime_choice.py']}}
    def save():
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    save()
    connection = None
    try:
        tool = resolve_choice_toolchain(require_manifest=True)
        traci = load_choice_traci(tool)
        manifest['runtime_sha256'] = choice_runtime_fingerprint(tool, traci)
        nodes = ET.Element('nodes')
        for i in range(5):
            ET.SubElement(nodes, 'node', id='n'+str(i), x=str(100*i), y='0', type='priority')
        edges = ET.Element('edges')
        for i, name in enumerate(('a', 'b', 'c', 'd')):
            ET.SubElement(edges, 'edge', {'id': name, 'from': 'n'+str(i), 'to': 'n'+str(i+1),
                                        'speed': '10', 'numLanes': '1', 'sidewalkWidth': '2'})
        for name, element in [('nodes.xml', nodes), ('edges.xml', edges)]:
            ET.ElementTree(element).write(folder/name, encoding='utf-8', xml_declaration=True)
        command = [str(tool['netconvert']), '--node-files', str(folder/'nodes.xml'),
                   '--edge-files', str(folder/'edges.xml'), '--output-file', str(folder/'fixture.net.xml'),
                   '--no-turnarounds', 'true']
        converted = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (folder/'netconvert.log').write_text(converted.stdout+converted.stderr, encoding='utf-8')
        if converted.returncode:
            raise RuntimeError('Artificial netconvert failed')
        net = ET.parse(folder/'fixture.net.xml').getroot()
        lanes = {}
        for edge in net.findall('edge'):
            if edge.get('id') not in ('a', 'b', 'c', 'd'):
                continue
            lane = next(l for l in edge.findall('lane') if l.get('allow') != 'pedestrian')
            lanes[edge.get('id')] = (int(lane.get('index')), float(lane.get('length')))
        types = ET.Element('routes')
        ET.SubElement(types, 'vType', id='drt', vClass='passenger', maxSpeed='10', sigma='0', length='4.5', minGap='2.5')
        ET.ElementTree(types).write(folder/'types.xml', encoding='utf-8', xml_declaration=True)
        command = [str(tool['sumo']), '--net-file', str(folder/'fixture.net.xml'),
                   '--route-files', str(folder/'types.xml'), '--step-length', '0.5', '--seed', '23423',
                   '--time-to-teleport', '-1', '--collision.action', 'teleport', '--no-step-log', 'true',
                   '--duration-log.disable', 'true', '--log', str(folder/'sumo.log'),
                   '--error-log', str(folder/'sumo_errors.log'), '--tripinfo-output', str(folder/'tripinfo.xml'),
                   '--tripinfo-output.write-unfinished', 'true']
        manifest['command'] = command
        save()
        traci.start(command, label=run_id, doSwitch=False, verbose=False)
        connection = traci.getConnection(run_id)
        t = connection
        manifest['sumo_version'] = t.getVersion()
        t.route.add('old', ['a', 'b', 'c'])
        t.vehicle.add('v', 'old', typeID='drt', depart='now', departPos='0')
        t.vehicle.setStop('v', 'c', pos=lanes['c'][1]-1, laneIndex=lanes['c'][0], duration=1000.0,
                          flags=traci.constants.STOP_PARKING)
        frames = []
        for _ in range(240):
            t.simulationStep()
            if t.simulation.getStartingTeleportNumber() or t.simulation.getCollidingVehiclesNumber():
                raise RuntimeError('Unexpected teleport/collision')
            if 'v' in t.vehicle.getIDList():
                frames.append(snapshot(t))
                if frames[-1]['road'] == 'c' and frames[-1]['stopped']:
                    break
        else:
            raise RuntimeError('Synthetic vehicle never parked on c')
        before = snapshot(t)
        t.edge.setDisallowed('b', ['passenger'])
        if variant == 'route_id_future_closed':
            t.edge.setDisallowed('d', ['passenger'])
        native_error = None
        try:
            if variant == 'control':
                set_vehicle_route(t, 'v', ['c', 'd'], lanes, 1000.0)
            else:
                route_id_candidate(t, 'v', ['c', 'd'], lanes, 1000.0, run_id+'_remaining')
        except traci.exceptions.TraCIException as error:
            native_error = str(error)
        checks = {'past_b_was_traversed': any(x['road'] == 'b' for x in frames),
                  'current_edge_is_c': before['road'] == 'c' and before['route_index'] == 2,
                  'requested_remaining_excludes_b': 'b' not in ['c', 'd']}
        if variant == 'control':
            checks['reproduced_past_prefix_error'] = native_error is not None and "No connection between edge 'a' and edge 'b'" in native_error
        elif variant == 'route_id_future_closed':
            checks['future_closed_route_rejected'] = native_error is not None
        else:
            after = snapshot(t)
            pending = (before['stopped'] and after['road'] == ''
                       and after['position'] == traci.constants.INVALID_DOUBLE_VALUE
                       and after['world_position'][0] == traci.constants.INVALID_DOUBLE_VALUE)
            unchanged = after['road'] == before['road'] and abs(after['position']-before['position']) < 1e-9
            checks.update(candidate_assignment_succeeded=native_error is None,
                          requested_route_exact=after['route'] == ['c', 'd'],
                          immediate_source_valid_or_explicit_native_reentry_pending=unchanged or pending,
                          cumulative_distance_unchanged=abs(after['distance']-before['distance']) < 1e-9,
                          new_route_index_zero=after['route_index'] == 0)
            manifest['immediate_after'] = after
            manifest['explicit_native_reentry_pending'] = pending
            previous = after
            distance_continuous = True
            first_reentry = None
            for _ in range(240):
                t.simulationStep()
                if t.simulation.getStartingTeleportNumber() or t.simulation.getCollidingVehiclesNumber():
                    raise RuntimeError('Unexpected candidate teleport/collision')
                now = snapshot(t)
                elapsed = now['time_sec'] - previous['time_sec']
                delta = now['distance'] - previous['distance']
                distance_continuous &= -1e-6 <= delta <= 10*elapsed+1e-6
                if first_reentry is None and now['road'] and now['position'] >= 0:
                    first_reentry = now
                frames.append(now)
                previous = now
                if now['road'] == 'd' and now['stopped']:
                    break
            else:
                raise RuntimeError('Candidate did not reach its new parking stop')
            checks.update(reentry_and_motion_distance_continuous=distance_continuous,
                          reached_new_stop=previous['road'] == 'd' and previous['stopped'])
            checks['first_reentry_source_edge_retained'] = first_reentry is not None and first_reentry['road'] == before['road']
            checks['first_reentry_position_and_distance_bounded'] = (first_reentry is not None
                and 0 < first_reentry['time_sec']-before['time_sec'] <= 0.5+1e-9
                and -1e-6 <= first_reentry['position']-before['position'] <= 10*(first_reentry['time_sec']-before['time_sec'])+1e-6
                and -1e-6 <= first_reentry['distance']-before['distance'] <= 10*(first_reentry['time_sec']-before['time_sec'])+1e-6)
            manifest['first_valid_reentry'] = first_reentry
            manifest['final_native'] = previous
        (folder/'frames.json').write_text(json.dumps(frames, indent=2)+'\n', encoding='utf-8')
        manifest.update(before=before, requested_remaining=['c', 'd'], native_error=native_error, checks=checks)
        if not all(checks.values()):
            raise RuntimeError('Route-history diagnostic contract failed')
        connection.close()
        connection = None
        if variant == 'route_id_future_closed':
            errors = (folder/'sumo_errors.log').read_text(encoding='utf-8')
            checks['native_error_identifies_future_pair'] = "No connection between edge 'c' and edge 'd'" in errors
            if not checks['native_error_identifies_future_pair']:
                raise RuntimeError('Future rejection lacks exact native connection evidence')
        result = ('REPRODUCED_CONTROL_FAILURE_NOT_REPAIR' if variant == 'control' else
                  'CANDIDATE_ISOLATED_CHECKS_ONLY_NOT_ADOPTION')
        manifest.update(status='COMPLETED', result=result, finished_at_jst=stamp())
        save()
        return manifest
    except BaseException as error:
        (folder/'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
        manifest.update(status='FAILED', error_type=type(error).__name__, error=str(error), finished_at_jst=stamp())
        save()
        raise
    finally:
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--variant', choices=['control', 'route_id', 'route_id_future_closed'], default='control')
    args = parser.parse_args()
    result = run(args.project_root, args.run_id, args.variant)
    print(json.dumps({k: result[k] for k in ('run_id', 'status', 'result', 'checks')}, ensure_ascii=False))
