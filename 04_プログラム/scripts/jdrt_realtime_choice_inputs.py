"""Exclusive input preparation for the preregistered choice series; never starts SUMO."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import json
import math
import shutil

import networkx as nx

from scripts.jdrt_choice_policy import facility_first_destinations, hash_number, select_intents

ROOT = Path(__file__).resolve().parents[2]
PARAM = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def place_positions(directory, sources, contract):
    """Project source references; preserve the registered edge and every place ID."""
    from scripts.jdrt_choice_toolchain import resolve_choice_toolchain, load_choice_traci
    load_choice_traci(resolve_choice_toolchain())
    import sumolib
    net = sumolib.net.readNet(str(directory / 'bounded.net.xml'), withInternal=True)
    references = {}
    for kind, suffix, identifier in [('origin', 'scenario_c_agent_types.csv', 'origin_id'),
                                     ('terminal', 'shelters_sumo.csv', 'shelter_id')]:
        paths = [ROOT / name for name in sources if name.endswith(suffix)]
        if len(paths) != 1:
            raise ValueError('Ambiguous reference: ' + suffix)
        references[kind] = {r[identifier]: r for r in read_csv(paths[0])}
    fields = ('place_id kind edge_id status source_kind reference_lon reference_lat reference_x reference_y '
              'car_lane_id car_lane_length_m car_unclamped_pos_m car_pos_m clamp_shift_m car_x car_y '
              'pedestrian_lane_id pedestrian_lane_length_m pedestrian_pos_m pedestrian_x pedestrian_y '
              'lane_point_gap_m reference_to_car_point_m').split()
    output = []
    for kind, filename, identifier in [('origin', 'origins.csv', 'origin_id'),
                                       ('terminal', 'terminals.csv', 'terminal_id')]:
        for place in read_csv(directory / filename):
            row = dict.fromkeys(fields, '')
            row.update(place_id=place[identifier], kind=kind, edge_id=place['edge_id'])
            if not place['edge_id']:
                row['status'] = 'no_origin_connection'
                output.append(row)
                continue
            lanes = net.getEdge(place['edge_id']).getLanes()
            car_lanes = [lane for lane in lanes if lane.allows('passenger')]
            foot_lanes = [lane for lane in lanes if lane.allows('pedestrian')]
            if not car_lanes or len(foot_lanes) != 1:
                raise ValueError('Unresolved mode lane: ' + place[identifier])
            car, foot = car_lanes[0], foot_lanes[0]
            if any(lane.getLength() != car.getLength() for lane in car_lanes):
                raise ValueError('Best departure lane lengths differ')
            lower = contract['minimum_front_pos_m']
            upper = car.getLength() - contract['end_buffer_m']
            if lower > upper:
                raise ValueError('Vehicle cannot fit registered placement interval')
            car_shape, foot_shape = car.getShape(), foot.getShape()
            car_geom = sumolib.geomhelper.polyLength(car_shape)
            foot_geom = sumolib.geomhelper.polyLength(foot_shape)
            if min(car_geom, foot_geom) <= 0:
                raise ValueError('Degenerate lane geometry')
            if kind == 'terminal' and place['kind'] == 'boundary_exit':
                raw = upper
                point = sumolib.geomhelper.positionAtShapeOffset(car_shape, raw / car.getLength() * car_geom)
                reference = point
                row['source_kind'] = 'registered_exit_downstream_section'
            else:
                ref = references[kind][place[identifier]]
                lon, lat = float(ref['lon']), float(ref['lat'])
                reference = net.convertLonLat2XY(lon, lat)
                offset = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint(reference, car_shape)
                raw = offset / car_geom * car.getLength()
                row.update(reference_lon=lon, reference_lat=lat,
                           source_kind='reference_origin_centroid' if kind == 'origin'
                           else 'reference_facility_point_not_verified_entrance')
            position = min(upper, max(lower, raw))
            point = sumolib.geomhelper.positionAtShapeOffset(car_shape, position / car.getLength() * car_geom)
            foot_offset = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint(point, foot_shape)
            foot_pos = foot_offset / foot_geom * foot.getLength()
            foot_point = sumolib.geomhelper.positionAtShapeOffset(foot_shape, foot_offset)
            row.update(status='mapped', reference_x=reference[0], reference_y=reference[1],
                       car_lane_id=car.getID(), car_lane_length_m=car.getLength(),
                       car_unclamped_pos_m=raw, car_pos_m=position, clamp_shift_m=position - raw,
                       car_x=point[0], car_y=point[1], pedestrian_lane_id=foot.getID(),
                       pedestrian_lane_length_m=foot.getLength(), pedestrian_pos_m=foot_pos,
                       pedestrian_x=foot_point[0], pedestrian_y=foot_point[1],
                       lane_point_gap_m=math.dist(point, foot_point),
                       reference_to_car_point_m=math.dist(reference, point))
            output.append(row)
    write_csv(directory / 'place_positions.csv', output)
    return {'places': len(output), 'statuses': dict(Counter(r['status'] for r in output)),
            'net_offset': net.getLocationOffset(), 'net_projection': str(net.getGeoProj())}


def prepare():
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    parent = ROOT / params['parent_input_manifest']
    prior = json.loads(parent.read_text(encoding='utf-8'))
    for name, expected in prior['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Parent source SHA mismatch: ' + name)
    for name, expected in prior['artifacts'].items():
        if sha(parent.parent / name) != expected:
            raise ValueError('Parent artifact SHA mismatch: ' + name)
    directory = ROOT / params['workspace'] / params['input_directory']
    directory.mkdir(parents=True, exist_ok=False)
    for name in prior['artifacts']:
        shutil.copy2(parent.parent / name, directory / name)
    positions = place_positions(directory, prior['source_sha256'], params['position_contract'])
    raw_graphs = json.loads((directory / 'graphs.json').read_text(encoding='utf-8'))
    graphs = {}
    for mode, data in raw_graphs.items():
        g = nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from(data['nodes'].items())
        g.add_edges_from(data['edges'])
        g.remove_nodes_from(row['edge_id'] for row in read_csv(directory / 'hazard.csv')
                            if row['mode'] == mode and row['closure_sec'] == '0')
        graphs[mode] = g
    origins = read_csv(directory / 'origins.csv')
    terminals = read_csv(directory / 'terminals.csv')
    # D0 is copied exactly, not regenerated with changed tie semantics.
    shutil.copy2(directory / 'origins.csv', directory / 'destinations_fixed_reference.csv')
    improved = facility_first_destinations(origins, graphs, terminals)
    for row in improved:
        row['car_route'] = json.dumps(row['car_route'])
        row['walk_route'] = json.dumps(row['walk_route'])
    write_csv(directory / 'destinations_facility_first.csv', improved)
    people = read_csv(directory / 'people.csv')
    for seed in params['seeds']:
        masks = {key: select_intents(people, seed, value['fraction'])
                 for key, value in params['demand_levels'].items()}
        low, high = params['population']['ready_interval_sec']
        rows = []
        for person in sorted(people, key=lambda row: row['person_id']):
            pid = person['person_id']
            key = person['vehicle_id'] or pid
            rows.append({**person, 'ready_sec': low + hash_number(seed, key, 'ready') % (high - low + 1),
                         **{'intent_' + level: pid in mask for level, mask in masks.items()}})
        write_csv(directory / f'common_realization_seed{seed}.csv', rows)
    (directory / 'cells.json').write_text(json.dumps(params['cells'], ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8')
    sources = dict(prior['source_sha256'])
    for path in (PARAM, parent, Path(__file__), ROOT / params['pap'],
                 ROOT / params['registry_document'], ROOT / params['state_contract'],
                 ROOT / params['alignment_addendum'], ROOT / params['preregistration_archive'],
                 ROOT / params['previous_choice_input_manifest'],
                 ROOT / '04_プログラム/scripts/jdrt_choice_policy.py'):
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
    artifacts = {path.name: sha(path) for path in directory.iterdir() if path.is_file()}
    if any(artifacts[name] != expected for name, expected in prior['artifacts'].items()):
        raise ValueError('Physical copy differs from parent')
    manifest = {
        'protocol': params['protocol'], 'created_at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'status': 'PREPARED_PENDING_INDEPENDENT_VALIDATION',
        'source_sha256': sources, 'artifacts': artifacts,
        'physical_artifacts_sha256': prior['artifacts'],
        'lineage': {'parent_manifest': params['parent_input_manifest'], 'parent_manifest_sha256': sha(parent)},
        'execution_contract': params['execution'],
        'input_revision': params['input_revision'], 'position_contract': params['position_contract'],
        'traffic_observation_contract': params['traffic_observation_contract'],
        'walking_distance_contract': params['walking_distance_contract'],
        'position_summary': positions,
        'people': len(people), 'population_counts': dict(Counter(row['person_type'] for row in people)),
        'origins': len(origins), 'depot_edge': prior['depot_edge'],
        'facilities': prior['facilities'], 'boundary_exits': prior['boundary_exits'],
        'registered_cells': len(params['cells']), 'technical_ready': False,
    }
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8')
    return manifest


if __name__ == '__main__':
    report = prepare()
    print(json.dumps({key: report[key] for key in ('protocol', 'status', 'people', 'registered_cells',
                                                  'technical_ready')}, ensure_ascii=False, indent=2))
