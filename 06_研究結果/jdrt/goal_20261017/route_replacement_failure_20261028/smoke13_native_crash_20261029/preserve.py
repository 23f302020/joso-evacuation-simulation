"""Read original failed technical evidence; no run, adoption or recovery."""
import json
from pathlib import Path
from hashlib import sha256
from datetime import datetime

root = Path(__file__).resolve().parents[5]
out = Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):
    return sha256(p.read_bytes()).hexdigest()
cfg = read(root / '04_プログラム/config/jdrt_realtime_choice_v1.json')
workspace = root / cfg['workspace']
folder = workspace / 'smoke/rs261029b_13'
m = read(folder / 'manifest.json')
s = root / '06_研究結果/jdrt/goal_20261017/rs261029b_smoke_sequence.json'
seq = read(s)
assert m['status'] == seq['status'] == 'FAILED' and len(seq['completed']) == 12
assert m['error_type'] == 'FatalTraCIError'
sources = {p: digest(root / p) for p in cfg['execution']['implementation_files']}
assert sources == seq['implementation_sha256'] == m['implementation_sha256']
events = [json.loads(x) for x in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
last = events[-1]['time_sec']
recent = [x for x in events if x['time_sec'] == last]
before = [x for x in events if x.get('event') == 'vehicle_path_decision']
rows = []
for item in seq['completed']:
    p = root / item['validation_report']
    proof = read(p)
    mp = workspace / 'smoke' / item['run_id'] / 'manifest.json'
    assert proof['status'] == 'PASS' and proof['core_adoption_permitted'] is False
    assert digest(mp) == item['manifest_sha256'] == proof['manifest_sha256']
    rows.append({'run_id': item['run_id'], 'report': item['validation_report'], 'sha256': digest(p)})
files = {p.relative_to(root).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size}
         for p in folder.rglob('*') if p.is_file()}
for p in [s, root / '06_研究結果/jdrt/goal_20261017/rs261029b_13_smoke.stderr.log']:
    files[p.relative_to(root).as_posix()] = {'sha256': digest(p), 'bytes': p.stat().st_size}
native = root / '04_プログラム/output/sumo/toolchains/native_lat_20261020a/bin/sumo.exe'
old = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019/b05/src/sumo.exe')
assert digest(native) == digest(old)
report = {'at_jst': datetime.now().astimezone().isoformat(), 'previous_goal_turn': 'verified wait of original36247, now terminal exit1',
          'run_id': m['run_id'], 'sequence': s.relative_to(root).as_posix(), 'sequence_status': seq['status'],
          'original_session': 36247, 'original_exit_code': 1, 'independent_smokes_completed': rows,
          'common5_unchanged': sources, 'native_sha256': digest(native),
          'last_periodic_progress': read(folder/'progress.json'), 'last_controller_time_sec': last,
          'last_events': recent, 'original_file_inventory': files,
          'confirmed': ['OS Application Error1000/Windows Error Reporting1001 identify same SUMO, c0000005 and RVA0x3f03b0',
                        'same-byte native disassembly places fault in MSBaseVehicle::setSkips, dereferencing route iterator',
                        'source replaceRoute retains past stops whose edge remains, without rewriting their routeIndex',
                        'setSkips uses myRoute->begin()+myPastStops.back().routeIndex before dereference'],
          'hypothesis_not_yet_reproduced': 'Named remaining route shrinks old indices; retained past stop index can exceed new route. Reproduce with synthetic long prefix and same source stop.',
          'technical_ready': False, 'core_started': False, 'formal_cells': 0,
          'next': 'Preserve originals, diagnose with new isolated IDs. No remaining smoke, preflight or core before resolution. No acceptance relaxation.'}
with (out/'preservation.json').open('x',encoding='utf-8') as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
row={'at_jst':report['at_jst'],'action':'smoke13_native_access_violation_preserved','report':(out/'preservation.json').relative_to(root).as_posix(),
     'run_id':m['run_id'],'original_session':36247,'exit_code':1,'smokes_complete':12,'formal_core_count':0,'technical_ready':False}
for p in [root/'06_研究結果/jdrt/goal_20261017/operations.jsonl',workspace/'driver_logs/monitoring.jsonl']:
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
print(json.dumps({'report':row['report'],'last_controller_time_sec':last,'files':len(files),'smokes_complete':12}))
