"""Save point-dated technical HOLD; formal research records are not edited."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
import json

root = Path(__file__).resolve().parents[5]
out = Path(__file__).resolve().parent
goal = root / '06_研究結果/jdrt/goal_20261017'
stamp = datetime.now().astimezone().isoformat()
def sha(p): return sha256(p.read_bytes()).hexdigest()
def archive(p):
    dest = goal / 'document_history' / (sha(p) + '_' + p.name)
    if dest.exists(): assert dest.read_bytes() == p.read_bytes()
    else: dest.write_bytes(p.read_bytes())
p = goal / 'G4実装・実SUMO_継続チェックポイント.json'
archive(p)
c = json.loads(p.read_text(encoding='utf-8'))
summary = (f'最新HOLD（観測時点 {stamp}）：新v4正式0/70、研究core稼働0。'
 '全14smokeは12件の独立PASS後、13件目rs261029b_13が1172秒の配送設定でnativeアクセス違反によりFAILED。'
 '元36247はexit1、14件目/preflight/coreは未開始。全30/65反例PASSは保全するが技術READY=false。'
 '人工診断ps261029bで新経路2区間に過去停車番号66が残る条件を直接観測。人工試験自体は完走しクラッシュ再現なし。'
 '別保存先の観測専用nativeのみ構築し、研究common5/input/bundleは不変。'
 '原因仮説・旧失敗・12PASSと診断原本を保全し、正しい履歴対応の修正と必要な再検証が終わるまで後続禁止。')
c.update(at_jst=stamp, summary=summary, technical_ready=False,
 progress_classification='PROGRESS_native_access_violation_preserved_and_out_of_range_index_observed',
 smoke_sequence_status='FAILED_PRESERVED rs261029b; 12 independent PASS, smoke13 FAILED, smoke14 NOT_STARTED',
 smoke_independently_completed=12, current_smoke_observation={'at_jst':stamp,'status':'FAILED_PRESERVED',
 'original_session':36247,'exit_code':1,'active':None,'failed_run':'rs261029b_13','completed':12},
 current_native_stop_index_diagnosis=(out/'diagnosis.md').relative_to(root).as_posix(),
 native_trace_build={'receipt':'C:/Users/Ko_rr/AppData/Local/JDRT-native-diagnostics/stopindex261029b/receipt.json',
 'original_session':64765,'exit_code':0,'research_selector_unchanged':True},
 next='HOLD. Correctly map retained past stop to replaced route in isolated candidate; verify loop/source/closed-future/moving/parking contracts and real native regression before common/native adoption and full current prerequisites. No smoke14/preflight/core now.')
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
task=root/'05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md'
archive(task)
t=task.read_text(encoding='utf-8')
note=('\n**2026-10-29の技術停止：** 現登録v4は正式0/70です。14条件の短時間試験は12件の独立確認後、13件目でSUMO本体が停止しました。'
 '人工診断で新経路と過去停車番号の不整合を観測しましたが、修正は未採用です。'
 '[診断と次の作業](../../06_研究結果/jdrt/goal_20261017/route_replacement_failure_20261028/smoke13_native_crash_20261029/diagnosis.md)を参照し、'
 '本実験・開始前検査・後続条件は停止します。旧v3と旧証跡を保全します。\n')
assert '現登録v4は正式0/70です。14条件の短時間試験は12件' not in t
first=t.index('\n')
task.write_text(t[:first+1]+note+t[first+1:],encoding='utf-8')
md=root/'00_全体整理/現状把握_静的・動的シミュレーション整理.md'
archive(md)
t=md.read_text(encoding='utf-8')
anchor='### 2026-10-29\n'
assert t.count(anchor)==1
bullet=('\n- 14条件の短時間試験は12条件を独立確認した後、13条件目で計算ソフト本体が停止しました。'
 '人工診断で、新経路に過去の停車番号が対応しない条件を確認しました。修正・再検証まで本実験は停止し、正式採用は0/70です。'
 '失敗と診断の原本を保全しています。\n')
md.write_text(t.replace(anchor,anchor+bullet,1),encoding='utf-8')
cfg=json.loads((root/'04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
row={'at_jst':stamp,'action':'native_stop_index_diagnosis_current_HOLD_recorded','report':(out/'diagnosis.md').relative_to(root).as_posix(),
 'classification':'progress','technical_ready':False,'formal_cells':0,'preflight_started':False,
 'trace_native_scope':'OBSERVATION_ONLY_NOT_ADOPTION','native_index_observed':{'route_size':2,'past_index':66},
 'native_crash_reproduced_in_synthetic':False,'next':c['next']}
for p in (goal/'operations.jsonl',root/cfg['workspace']/'driver_logs/monitoring.jsonl'):
    with p.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
print(json.dumps(row,ensure_ascii=False))
