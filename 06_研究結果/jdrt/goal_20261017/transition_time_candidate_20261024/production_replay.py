"""Compare repaired producer and independent verifier on preserved primary rows.

No run, CSV, report, configuration or adoption is modified. The old frozen
producer remains a negative control and the original INVALID remains intact.
"""
import ast
from collections import Counter
from datetime import datetime
from hashlib import sha256
import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

root = Path.cwd()
goal = root / '06_研究結果/jdrt/goal_20261017'
folder = Path(__file__).resolve().parent
sys.path.insert(0, str(root / '04_プログラム'))
from scripts import jdrt_realtime_choice as runtime
from scripts import jdrt_realtime_choice_validate as validator

read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
digest = lambda path: sha256(path.read_bytes()).hexdigest()
extract_path = goal / 'nc26102402_閉鎖進入_個体時刻抽出_20261024.json'
diagnosis_path = goal / 'nc26102402_短道路・交差点_閉鎖進入診断_20261024.json'
extract, diagnosis = read(extract_path), read(diagnosis_path)
baseline = read(folder / 'repair_baseline.json')
original_manifest = root / baseline['preserved'][
    '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/runs/nc26102402/manifest.json']['archive']
manifest = read(original_manifest)
inputs = root / manifest['input_directory']
net_path = inputs / 'bounded.net.xml'
net = ET.parse(net_path).getroot()
forward, backward = runtime.passenger_transition_links(net), validator.native_transition_backlinks(net)

# Compare the complete static native-topology relations by two constructions.
reverse_pairs = {}
for lane, target in backward:
    pending, visited, sources = [lane], set(), set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for parent in backward.get((current, target), set()):
            edge = parent.rsplit('_', 1)[0]
            if edge.startswith(':'):
                pending.append(parent)
            else:
                sources.add(edge)
    if sources:
        reverse_pairs.setdefault(lane, set()).update((source, target) for source in sources)
assert forward == reverse_pairs, 'Forward/reverse topology relation differs'

route = next(e['native_source']['route'] for e in extract['matching_events']
             if e['event'] == 'vehicle_route_feasibility')
actor = extract['actor_id']
lower = diagnosis['entry_interval_discrete']['lower_exclusive_sec']
frames = [r for r in extract['actor_rows'] if float(r['time_sec']) >= lower]
index = int(frames[0]['route_index'])
with (inputs / 'hazard.csv').open(encoding='utf-8', newline='') as stream:
    hazards = {(r['edge_id'], r['mode']): float(r['closure_sec'])
               for r in csv.DictReader(stream) if r['closure_sec'] != ''}


def definition(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def produce(path, repaired):
    rows = []
    context = {'last': {actor: (route[index], lower, index)}, 'latest_v': {},
               'tc': SimpleNamespace(VAR_ROUTE_INDEX='index'),
               'vehicles': {actor: {'status': 'travelling'}}, 'true_times': hazards,
               'transitions': SimpleNamespace(writerow=rows.append), 'counts': Counter()}
    module = ast.Module(body=[definition(path, 'observe_transition')], type_ignores=[])
    exec(compile(module, str(path), 'exec'), context)
    for row in frames:
        edge, at, occurrence = row['road_id'], float(row['time_sec']), int(row['route_index'])
        context['latest_v'][actor] = {'index': occurrence}
        if repaired:
            edge = runtime.passenger_transition_source(route, edge, row['lane_id'], occurrence, forward)
        elif edge.startswith(':'):
            continue
        context['observe_transition'](actor, 'passenger', edge, at, route)
    return rows


producer = Path(runtime.__file__)
old_producer = root / baseline['preserved']['04_プログラム/scripts/jdrt_realtime_choice.py']['archive']
generated, old_generated = produce(producer, True), produce(old_producer, False)
keys = ('time_lower_sec', 'time_upper_sec', 'actor_id', 'mode', 'from_edge', 'to_edge',
        'kind', 'closure_sec', 'ambiguous')
errors, expected = [], []
context = {'keys': keys, 'routes': {actor: route}, 'anchors': {actor: (route[index], lower, index)},
           'hazards': hazards, 'fail': lambda *detail: errors.append(detail)}
verifier = Path(validator.__file__)
module = ast.Module(body=[definition(verifier, 'transition_key'), definition(verifier, 'visit')], type_ignores=[])
exec(compile(module, str(verifier), 'exec'), context)
for row in frames:
    edge = (validator.verified_internal_source(route, row, backward)
            if row['road_id'].startswith(':') else row['road_id'])
    context['visit'](actor, 'passenger', edge, int(row['route_index']), float(row['time_sec']), expected)
actual = Counter(context['transition_key'](r) for r in generated)
old_actual = Counter(context['transition_key'](r) for r in old_generated)
assert not errors and Counter(expected) == actual
assert Counter(expected) != old_actual, 'Old external-only producer must be rejected'
target_edge = diagnosis['raw_transition']['to']
target = next(r for r in generated if r['to_edge'] == target_edge)
assert target['time_upper_sec'] <= diagnosis['entry_interval_discrete']['upper_inclusive_sec']
assert target['kind'] == 'transition'
mutated = [dict(row) for row in generated]
next(row for row in mutated if row['to_edge'] == target_edge)['time_upper_sec'] = diagnosis['raw_transition']['upper']
assert Counter(context['transition_key'](r) for r in mutated) != Counter(expected)

result = {'at_jst': datetime.now().astimezone().isoformat(),
          'status': 'PRODUCTION_PRIMARY_WINDOW_REPLAY_PASS_NOT_ADOPTABLE',
          'run_id': manifest['run_id'], 'actor_id': actor,
          'generated_rows': generated, 'old_generated_rows': old_generated,
          'independent_multiset_matches': True, 'old_external_only_control_rejected': True,
          'late_timestamp_mutation_rejected': True,
          'actual_native_internal_lanes': len(forward),
          'actual_native_internal_route_pairs': sum(map(len, forward.values())),
          'forward_reverse_topology_relations_equal': True,
          'bindings': {p.relative_to(root).as_posix(): digest(p) for p in
                       (extract_path, diagnosis_path, original_manifest, net_path, producer, verifier, old_producer)},
          'original_formal_validation_status': 'INVALID_PRESERVED',
          'formal_adoption_permitted': False, 'research_artifacts_modified': False,
          'limits': ['one preserved actor window, not full-run revalidation',
                     'real-SUMO integration/factory mutants/new registration/full READY remain required',
                     'pure AST replay does not prove native physical safety']}
with (folder / 'production_primary_replay.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({k: result[k] for k in ('status', 'actual_native_internal_lanes',
                 'actual_native_internal_route_pairs', 'old_external_only_control_rejected')}, ensure_ascii=False))
