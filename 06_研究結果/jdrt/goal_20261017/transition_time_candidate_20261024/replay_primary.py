"""Read-only targeted replay of one preserved interval, not formal validation."""
from datetime import datetime
from hashlib import sha256
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from observer_candidate import Anchor, advance, passenger_links

root = Path.cwd()
goal = root / '06_研究結果/jdrt/goal_20261017'
folder = root / '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/runs/nc26102402'
extract_path = goal / 'nc26102402_閉鎖進入_個体時刻抽出_20261024.json'
diagnosis_path = goal / 'nc26102402_短道路・交差点_閉鎖進入診断_20261024.json'
extract = json.loads(extract_path.read_text(encoding='utf-8'))
diagnosis = json.loads(diagnosis_path.read_text(encoding='utf-8'))
manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
inputs = root / manifest['input_directory']
net_path = inputs / 'bounded.net.xml'
links = passenger_links(ET.parse(net_path).getroot())
route = next(e['native_source']['route'] for e in extract['matching_events']
             if e['event'] == 'vehicle_route_feasibility')
with (inputs / 'hazard.csv').open(encoding='utf-8', newline='') as stream:
    closures = {r['edge_id']: float(r['closure_sec']) for r in csv.DictReader(stream)
                if r['mode'] == 'passenger' and r['closure_sec'] != ''}
lower = diagnosis['entry_interval_discrete']['lower_exclusive_sec']
frames = [r for r in extract['actor_rows'] if float(r['time_sec']) >= lower]
anchor = Anchor(lower, int(frames[0]['route_index']), int(frames[0]['route_version']))
entries = []
for frame in frames:
    anchor, new = advance(anchor, frame, route, links, closures)
    entries.extend(new)
target_edge = diagnosis['raw_transition']['to']
target = [r for r in entries if r['to_edge'] == target_edge]
assert len(target) == 1
assert target[0]['time_upper_sec'] == diagnosis['entry_interval_discrete']['upper_inclusive_sec']
assert not target[0]['closed_entry']
common = {name: sha256((root / name).read_bytes()).hexdigest() == h
          for name, h in manifest['implementation_sha256'].items()}
assert all(common.values())
report = {'at_jst': datetime.now().astimezone().isoformat(),
          'status': 'CANDIDATE_TARGETED_REPLAY_PASS_NOT_ADOPTABLE',
          'run_id': manifest['run_id'], 'actor_id': extract['actor_id'],
          'entry_rows': entries, 'outgoing_internal_lane_pairs': sorted(links[frames[1]['lane_id']]),
          'source_common5_unchanged': common,
          'bindings': {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in (extract_path, diagnosis_path, net_path, Path(__file__),
                                 Path(__file__).with_name('observer_candidate.py'))},
          'formal_adoption_permitted': False, 'research_artifact_edits': False,
          'limits': ['one preserved actor/time window only; not the full core audit',
                     'native integration/factory counterexamples and full version-consistent revalidation remain',
                     'original frozen validator result must be retained and cannot be replaced by this replay']}
with Path(__file__).with_name('primary_replay.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'status': report['status'], 'entry_rows': entries,
                  'common5_unchanged': all(common.values())}, ensure_ascii=False))
