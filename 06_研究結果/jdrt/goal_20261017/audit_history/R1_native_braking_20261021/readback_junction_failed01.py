"""Recompute diagnostic topology/time evidence. No run or validator modifications."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from extract_window import digest


def main(root):
    root = Path(root).resolve()
    packet = Path(__file__).resolve().parent
    output = packet / 'junction_context_readback.json'
    if output.exists():
        raise ValueError('Never overwrite an existing diagnostic report')
    window_path = packet / 'window03/window.json'
    window = json.loads(window_path.read_text(encoding='utf-8'))
    source_proof = json.loads((packet / 'source_clock_and_deceleration.json').read_text(encoding='utf-8'))
    archive = Path(source_proof['official_source_zip'])
    if digest(archive) != source_proof['archive_sha256']:
        raise ValueError('Official source ZIP changed')
    source_root = Path(source_proof['files'][0]['path']).parents[2]
    selections = {
        'src/microsim/MSNet.cpp': [(825, 860)],
        'src/microsim/MSLink.cpp': [(1864, 1902)],
        'src/microsim/MSVehicle.cpp': [(3362, 3376), (3534, 3555), (4908, 4933)],
        'src/microsim/transportables/MSPModel_Striping.cpp': [(162, 171), (2624, 2630)],
        'src/microsim/transportables/MSPModel_Interacting.cpp': [(71, 108)],
    }
    sources = []
    with zipfile.ZipFile(archive) as zipped:
        prefix = source_proof['files'][0]['zip_member'].split('/src/')[0]
        for relative, ranges in selections.items():
            path = source_root / relative
            raw = path.read_bytes()
            member = prefix + '/' + relative
            if raw != zipped.read(member):
                raise ValueError('Selected diagnostic source differs from pinned official ZIP')
            lines = raw.decode('utf-8').splitlines()
            sources.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                                zip_member=member, matches_official_zip=True,
                                excerpts=[dict(start=a, end=b, lines=lines[a-1:b]) for a, b in ranges]))
    primary = {p: digest(root / p) for p in window['primary_sha256']}
    if primary != window['primary_sha256']:
        raise ValueError('Primary bytes differ from extracted window')
    target = window['target']
    cars = sorted({r['actor_id'] for r in window['actor_rows'] if r['kind'] == 'car'})
    rows = [r for r in window['actor_rows'] if r['actor_id'] == target]
    before = next(r for r in rows if float(r['time_sec']) == window['warning_sec'])
    after = rows[rows.index(before)+1]
    duration = float(after['time_sec']) - float(before['time_sec'])
    crossings = {ET.fromstring(e).get('id') for e in window['edge_xml']
                 if ET.fromstring(e).get('function') == 'crossing'}
    pedestrian_entries = []
    for row in window['actor_rows']:
        if row['kind'] == 'walk' and row['road_id'] in crossings and row['time_sec'] == after['time_sec']:
            previous = next((r for r in window['actor_rows']
                             if r['actor_id'] == row['actor_id'] and r['time_sec'] == before['time_sec']), None)
            if previous and previous['road_id'] != row['road_id']:
                pedestrian_entries.append(dict(before=previous, after=row))
    junction_xml = next(ET.fromstring(j) for j in window['junction_xml']
                        if after['lane_id'] in ET.fromstring(j).get('intLanes').split())
    lanes = junction_xml.get('intLanes').split()
    car_link_index = lanes.index(after['lane_id'])
    request = next(r for r in junction_xml.findall('request') if int(r.get('index')) == car_link_index)
    responses = []
    for entry in pedestrian_entries:
        lane = entry['after']['road_id'] + '_0'
        if lane in lanes:
            index = lanes.index(lane)
            responses.append(dict(crossing_lane=lane, crossing_link_index=index,
                                  vehicle_link_index=car_link_index,
                                  response_bits=request.get('response'), foes_bits=request.get('foes'),
                                  response_to_crossing=request.get('response')[::-1][index] == '1',
                                  crossing_is_foe=request.get('foes')[::-1][index] == '1'))
    result = dict(at_jst=datetime.now().astimezone().isoformat(), status='DIAGNOSTIC_NOT_ADOPTABLE',
                  run_id=window['run_id'], window_sha256=digest(window_path),
                  primary_bytes_unchanged=True, primary_sha256=primary,
                  source_archive_sha256=source_proof['archive_sha256'], sources=sources,
                  time_window_sec=window['window_sec'], local_edge_count=len(window['local_edges']),
                  spatial_supplement_radius_m=window['spatial_supplement_radius_m'],
                  local_actor_ids=sorted({r['actor_id'] for r in window['actor_rows']}),
                  local_car_ids=cars, local_actor_rows=len(window['actor_rows']),
                  braking=dict(before=before, after=after, step_sec=duration,
                               observed_acceleration_mps2=(float(after['speed_mps'])-float(before['speed_mps']))/duration),
                  same_step_crossing_entries=pedestrian_entries, junction_responses=responses,
                  source_order='Pedestrian movement is scheduled at begin-of-timestep; MSNet executes begin events before vehicle planMovements/executeMovements.',
                  inference='Observed crossing entry, yielding topology and source pedestrian stopSpeed path support a pedestrian-response hypothesis.',
                  not_proved=['Original per-link native leader/stopSpeed decision was not logged.',
                              'Finite spatial/time context does not establish every upstream approach was irrelevant.',
                              'No physical-safety, harmless-warning, unique-cause or research-adoption conclusion.',
                              'Source-derived emergencyDecel is not a native API property observation.'],
                  next='Isolated nonadoptable reduced crossing/no-crossing native probe with identical frozen binary/options and full raw receipts; separately assess version-consistent new registration if a generic validator correction is justified.',
                  core_adoption_permitted=False, formal_recorded_cells=1, downstream_start_permitted=False)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(status=result['status'], rows=result['local_actor_rows'],
                          crossing_entries=len(pedestrian_entries), junction_responses=responses,
                          primary_bytes_unchanged=True), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    main(parser.parse_args().project_root)
