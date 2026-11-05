"""RED control from the unchanged archived producer, not a core execution."""
import ast
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import json

root = Path.cwd()
source = root / '04_プログラム/scripts/jdrt_realtime_choice.py'
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'observe_transition')
module = ast.Module(body=[function], type_ignores=[])
extract = json.loads((root / '06_研究結果/jdrt/goal_20261017/nc26102402_閉鎖進入_個体時刻抽出_20261024.json').read_text(encoding='utf-8'))
route = next(e['native_source']['route'] for e in extract['matching_events'] if e['event'] == 'vehicle_route_feasibility')


class Rows:
    def __init__(self):
        self.rows = []

    def writerow(self, row):
        self.rows.append(row)


writer = Rows()
context = {'last': {}, 'latest_v': {}, 'tc': SimpleNamespace(VAR_ROUTE_INDEX='index'),
           'vehicles': {}, 'true_times': {('2013#1', 'passenger'): 3300},
           'transitions': writer, 'counts': Counter()}
exec(compile(module, str(source), 'exec'), context)
for frame in extract['actor_rows']:
    if float(frame['time_sec']) < 3298.5:
        continue
    context['latest_v'][extract['actor_id']] = {'index': int(frame['route_index'])}
    # This is the frozen caller's exact external-only observation condition.
    if not frame['road_id'].startswith(':'):
        context['observe_transition'](extract['actor_id'], 'passenger', frame['road_id'],
                                      float(frame['time_sec']), route)
print(json.dumps({'frozen_generated_rows': writer.rows, 'closed': context['counts']['closed_entry_rows']}))
# The independently certified outgoing-internal frame bounds this entry before closure.
assert context['counts']['closed_entry_rows'] == 0, 'Frozen producer falsely dates the passed short edge at the next external observation'
