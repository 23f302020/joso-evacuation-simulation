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
            'distance': t.vehicle.getDistance('v'), 'speed': t.vehicle.getSpeed('v'),
            'route': list(t.vehicle.getRoute('v')), 'route_index': t.vehicle.getRouteIndex('v'),
            'stopped': t.vehicle.isStopped('v')}


def run(root, run_id):
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
                'scope': 'CONTROL_REPRODUCTION_ONLY_NOT_REPAIR_OR_READY',
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
        t.vehicle.setStop('v', 'c', pos=lanes['c'][1]-1, laneIndex=lanes['c'][0], duration=1000,
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
        native_error = None
        try:
            set_vehicle_route(t, 'v', ['c', 'd'], lanes, 1000)
        except traci.exceptions.TraCIException as error:
            native_error = str(error)
        checks = {'past_b_was_traversed': any(x['road'] == 'b' for x in frames),
                  'current_edge_is_c': before['road'] == 'c' and before['route_index'] == 2,
                  'requested_remaining_excludes_b': 'b' not in ['c', 'd'],
                  'reproduced_past_prefix_error': native_error is not None
                      and "No connection between edge 'a' and edge 'b'" in native_error}
        (folder/'frames.json').write_text(json.dumps(frames, indent=2)+'\n', encoding='utf-8')
        manifest.update(before=before, requested_remaining=['c', 'd'], native_error=native_error, checks=checks)
        if not all(checks.values()):
            raise RuntimeError('Control did not reproduce the hypothesized route-history error')
        connection.close()
        connection = None
        manifest.update(status='COMPLETED', result='REPRODUCED_CONTROL_FAILURE_NOT_REPAIR', finished_at_jst=stamp())
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
    args = parser.parse_args()
    result = run(args.project_root, args.run_id)
    print(json.dumps({k: result[k] for k in ('run_id', 'status', 'result', 'checks')}, ensure_ascii=False))
