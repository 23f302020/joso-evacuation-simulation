"""Synchronize the actual first core start; never create formal acceptance records."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WS = ROOT / '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1'
run_id = 'ch261018_002'
mp = WS / 'runs' / run_id / 'manifest.json'
m = json.loads(mp.read_text(encoding='utf-8'))
check_path = OUT / ('check_' + run_id + '_initial.json')
check = json.loads(check_path.read_text(encoding='utf-8-sig'))
ready = json.loads((WS / 'preflight_ready.json').read_text(encoding='utf-8'))
assert m['purpose'] == 'core' and m['protocol'] == 'realtime_choice_v1'
assert check['run_id'] == run_id and check['status'] == m['status']
assert ready['status'] == 'READY' and all(ready['independent_receipt_checks'].values())
assert m['implementation_sha256'] == ready['implementation_sha256']
unit = json.loads((ROOT / ready['evidence']['unit']).read_text(encoding='utf-8'))
storage = json.loads((ROOT / ready['evidence']['storage']).read_text(encoding='utf-8'))
inputs = json.loads((ROOT / ready['evidence']['input']).read_text(encoding='utf-8'))
counter = json.loads((ROOT / ready['evidence']['counterexamples']).read_text(encoding='utf-8'))
input_count = len(inputs['checks'])
fixture_count = len(ready['evidence']['fixture_validations'])
smoke_count = len(ready['evidence']['smoke_validations'])
counter_count = len(counter['counterexamples'])
now = datetime.now(timezone(timedelta(hours=9))).isoformat()
point = check.get('progress') or {}
summary = (
    f'最終goal ACTIVE。受付・代替行動70セルの最初の研究core {run_id}'
    f'（{m["cell_id"]}）を{m["started_at_jst"]}開始、観測時点{check["status"]}・'
    f'PID生存{check["pid_alive"]}・sim {point.get("time_sec", "未観測")}/{m["end_sec"]}秒。正式記録0/70。'
    f'現行共通5実装の入力{input_count}検査/{unit["tests_run"]}unit/人工{fixture_count}ケース・独立{counter_count}改変拒否/全{smoke_count}smokeがPASS、'
    f'{len(ready["evidence_sha256"])}一次証跡と独立{len(ready["independent_receipt_checks"])}検査で新READYを確認。'
    f'15分監視jdrt-b-15を新系列でACTIVEへ戻し、単一セルを監視する。'
    f'終了後validate→PASSだけ6ファイルrecord→statusを完了してから次の1件。'
    f'容量は毎回1セル予約を再確認し、全70保存可能という保証はしない。'
    f'旧launch失敗/旧READY/旧技術試験/旧系列を保全、独立図v7と分析対応表を新規保存。'
    f'新河川縦断図・点群仕様は参考資料で橋面高未取得のまま、現行入力へ追加なし。'
    f'全70採用前の方向解釈なし。Drive読取のみ・外部送信なし。'
)
history = OUT / 'document_history'
history.mkdir(exist_ok=True)
def preserve(path):
    raw = path.read_bytes()
    copy = history / (sha256(raw).hexdigest() + path.suffix)
    if not copy.exists():
        copy.write_bytes(raw)
    return raw
cp = OUT / 'G4実装・実SUMO_継続チェックポイント.json'
old = json.loads(preserve(cp))
changed = []
for name in ['context.md', '00_全体整理/現状把握_静的・動的シミュレーション整理.md',
             '00_全体整理/現状把握_静的・動的シミュレーション整理.html']:
    p = ROOT / name
    text = preserve(p).decode('utf-8').replace('\r\n', '\n')
    assert old['summary'] in text, name
    text = text.replace(old['summary'], summary)
    if name == 'context.md':
        import re
        text = re.sub(r'\*\*最終更新：\*\* 2026-10-18[^\n]*', '**最終更新：** 2026-10-18（新READY確認・受付代替行動の最初のcore開始）', text, count=1)
    p.write_text(text, encoding='utf-8')
    changed.append(name)
old.update(at_jst=now, summary=summary, core_runs=1, technical_ready=True,
           running=[{'run_id': run_id, 'pid': m['pid'], 'status': check['status'], 'progress': point}],
           preflight_session=94282, preflight_state='READY current cf26101801/cs261018a',
           monitor_status='ACTIVE realtime_choice_v1', remaining_formal_gates=[],
           new_diagram='03_研究設計文書/図表・UML/JDRT_受付代替行動_READY・資料位置づけ_v7.html',
           next='monitor same core; complete independent validate and record6 before next registered cell')
cp.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
task = ROOT / '05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md'
text = preserve(task).decode('utf-8')
updates = {'CH-T2': f'現行cs261018a全{smoke_count}設定が独立PASS、技術のみ。新preflightでも全件再検証。旧版は履歴',
           'CH-G1': f'現行入力{input_count}/{unit["tests_run"]}unit/人工{fixture_count}/{counter_count}改変/全{smoke_count}/容量・排他・来歴の新READY確認。独立{len(ready["independent_receipt_checks"])}検査と{len(ready["evidence_sha256"])}一次証跡を照合。新図v7作成',
           'CH-M1': '最初のcore ' + run_id + ' を開始。15分監視ACTIVE、正式記録0/70。現runのvalidate/record6が完了するまで後続開始なし'}
lines = []
for line in text.splitlines():
    key = next((k for k in updates if line.startswith('| ' + k + ' |')), None)
    if key:
        parts = line.split('|'); parts[-2] = ' ' + updates[key] + ' '; line = '|'.join(parts)
    lines.append(line)
text = '\n'.join(lines) + '\n'
import re
text = re.sub(r'最新状態 [^\n]+', '最新状態 ' + now + '：新READY確認・最初のcore ' + run_id
              + ' 開始。正式記録0/70。実行中/次セルは専用CLI status、正式採用はrecordを正本とする。', text, count=1)
text = re.sub(r'現在の次の1件：[^\n]+', '現在の次の1件：' + run_id
              + ' を15分監視→終了後validate→PASSだけrecord6/一意確認→status。下記の初期実装順は経緯として保持する。', text, count=1)
task.write_text(text, encoding='utf-8')
event = {'at_jst': now, 'action': 'first_current_core_started_and_documents_synchronized',
         'summary': summary, 'run_id': run_id, 'check': check, 'manifest_path': mp.relative_to(ROOT).as_posix(),
         'manifest_sha256_at_observation': sha256(mp.read_bytes()).hexdigest(),
         'ready_sha256': sha256((WS / 'preflight_ready.json').read_bytes()).hexdigest(),
         'storage_before_start': storage, 'monitor_id': 'jdrt-b-15', 'formal_adoption_claim': False,
         'changed_documents': changed + [task.relative_to(ROOT).as_posix()]}
for path in [OUT / 'operations.jsonl', WS / 'driver_logs/operations.jsonl', WS / 'driver_logs/monitoring.jsonl']:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')
for name in ['05_タスク管理/jdrt/JDRT_最終ゴール自律進行計画.md',
             '05_タスク管理/jdrt/JDRT-受付代替行動_専用CLI・開始ゲート実装手順.md',
             '00_全体整理/決定ログ.md', '01_経過報告/経過報告2026年08月/経過報告20260826.md']:
    with (ROOT / name).open('a', encoding='utf-8') as stream:
        stream.write('\n\n### 現行受付・代替行動の初回core開始 ' + now + '\n\n' + summary + '\n\n'
                     '新READY: preflight/20261018T101404862963/receipt.json。旧初回起動失敗を再利用せず別ID。'
                     'モデル条件・入力・共通実装を変更せず、一次成果物の検証・正式記録は専用スキルだけで行う。\n')
print(json.dumps({'status': 'SYNCHRONIZED', 'run_id': run_id, 'check_status': check['status'],
                  'pid_alive': check['pid_alive'], 'sim_sec': point.get('time_sec')}, ensure_ascii=False))
