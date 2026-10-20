"""Candidate-only geometric audit; does not mutate registered inputs or run SUMO."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '04_プログラム'))
from scripts.jdrt.smoke import load_traci, resolve_sumo_binary
load_traci(resolve_sumo_binary())
import sumolib
from pyproj import Transformer
from shapely.geometry import LineString, Point


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = Path(__file__).parent
    parameters = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    directory = ROOT / parameters['workspace'] / parameters['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    origin_source = next(ROOT / p for p in manifest['source_sha256'] if p.endswith('scenario_c_agent_types.csv'))
    facility_source = next(ROOT / p for p in manifest['source_sha256'] if p.endswith('shelters_sumo.csv'))
    origin_reference = {r['origin_id']: r for r in rows(origin_source)}
    facility_reference = {r['shelter_id']: r for r in rows(facility_source)}
    net = sumolib.net.readNet(str(directory / 'bounded.net.xml'), withInternal=True)
    offset = net.getLocationOffset()
    transform = Transformer.from_crs(4326, 32654, always_xy=True)
    candidates = []
    independent_errors = []
    for kind, places in [('origin', rows(directory / 'origins.csv')), ('terminal', rows(directory / 'terminals.csv'))]:
        for place in places:
            identifier = place['origin_id'] if kind == 'origin' else place['terminal_id']
            edge_id = place['edge_id']
            row = {'place_id': identifier, 'kind': kind, 'edge_id': edge_id, 'candidate_only': True}
            if not edge_id:
                candidates.append({**row, 'status': 'no_origin_connection'})
                continue
            edge = net.getEdge(edge_id)
            car_lane = next(lane for lane in edge.getLanes() if lane.allows('passenger'))
            pedestrian_lane = next(lane for lane in edge.getLanes() if lane.allows('pedestrian'))
            car_shape, foot_shape = car_lane.getShape(), pedestrian_lane.getShape()
            car_line, foot_line = LineString(car_shape), LineString(foot_shape)
            if kind == 'terminal' and place['kind'] == 'boundary_exit':
                car_pos = car_lane.getLength() - 1
                xy = sumolib.geomhelper.positionAtShapeOffset(car_shape, car_pos / car_lane.getLength() * car_line.length)
                raw_pos = car_pos
                reference = xy
                source_kind = 'registered_exit_downstream_section'
            else:
                ref = origin_reference[identifier] if kind == 'origin' else facility_reference[identifier]
                lon, lat = float(ref['lon']), float(ref['lat'])
                reference = net.convertLonLat2XY(lon, lat)
                independent_xy = transform.transform(lon, lat)
                independent_xy = (independent_xy[0] + offset[0], independent_xy[1] + offset[1])
                independent_errors.append(math.dist(reference, independent_xy))
                geom_pos = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint(reference, car_shape)
                raw_pos = geom_pos / car_line.length * car_lane.getLength()
                car_pos = min(max(raw_pos, 7.), car_lane.getLength() - 1.)
                xy = sumolib.geomhelper.positionAtShapeOffset(car_shape, car_pos / car_lane.getLength() * car_line.length)
                source_kind = 'reference_origin_centroid' if kind == 'origin' else 'reference_facility_point_not_verified_entrance'
            foot_offset = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint(xy, foot_shape)
            foot_pos = foot_offset / foot_line.length * pedestrian_lane.getLength()
            foot_xy = sumolib.geomhelper.positionAtShapeOffset(foot_shape, foot_offset)
            independent_car_pos = car_line.project(Point(reference)) / car_line.length * car_lane.getLength()
            if source_kind == 'registered_exit_downstream_section':
                independent_car_pos = raw_pos
            independent_errors.append(abs(independent_car_pos - raw_pos))
            independent_foot = foot_line.project(Point(xy)) / foot_line.length * pedestrian_lane.getLength()
            independent_errors.append(abs(independent_foot - foot_pos))
            row.update(status='candidate', source_kind=source_kind, reference_x=reference[0], reference_y=reference[1],
                car_lane_id=car_lane.getID(), car_lane_length_m=car_lane.getLength(),
                car_unclamped_pos_m=raw_pos, car_pos_m=car_pos, clamp_shift_m=car_pos - raw_pos,
                car_x=xy[0], car_y=xy[1], pedestrian_lane_id=pedestrian_lane.getID(),
                pedestrian_lane_length_m=pedestrian_lane.getLength(), pedestrian_pos_m=foot_pos,
                pedestrian_x=foot_xy[0], pedestrian_y=foot_xy[1],
                lane_point_gap_m=math.dist(xy, foot_xy), reference_to_car_point_m=math.dist(reference, xy))
            candidates.append(row)
    keys = list(dict.fromkeys(key for row in candidates for key in row))
    with (out / 'G4_位置投影候補.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(candidates)
    connected = [r for r in candidates if r['status'] == 'candidate']
    summary = {'status': 'CANDIDATE_ONLY', 'adopted': False, 'places': len(candidates),
        'statuses': dict(Counter(r['status'] for r in candidates)), 'net_offset': offset,
        'net_projection': str(net.getGeoProj()), 'independent_max_error_m': max(independent_errors),
        'candidate_min_front_position_m': 7, 'candidate_end_buffer_m': 1,
        'clamped_places': sum(abs(r['clamp_shift_m']) > 1e-8 for r in connected),
        'max_clamp_shift_m': max(abs(r['clamp_shift_m']) for r in connected),
        'max_lane_point_gap_m': max(r['lane_point_gap_m'] for r in connected),
        'max_reference_access_m': max(r['reference_to_car_point_m'] for r in connected),
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in
            (directory / 'manifest.json', directory / 'bounded.net.xml', origin_source, facility_source, Path(__file__))}}
    (out / 'G4_位置投影候補_監査.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in summary.items() if key != 'source_sha256'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
