"""Record the current technical batch without modifying research code or inputs."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WS = ROOT / '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1'
now = datetime.now(timezone(timedelta(hours=9))).isoformat()
state_path = OUT / 'G4実装・実SUMO_継続チェックポイント.json'
old_bytes = state_path.read_bytes()
old = json.loads(old_bytes)
batch = json.loads((OUT / 'cs261018a_smoke_sequence.json').read_text(encoding='utf-8'))
audit_path = OUT / '正式検証器_表会計候補_20261018T095748.json'
audit = json.loads(audit_path.read_text(encoding='utf-8'))
assert audit['status'] == 'PASS' and audit['suite'] == 'cf26101801'
assert not audit['historical_diagnostic']
for relative, expected in batch['implementation_sha256'].items():
    assert sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
for item in batch['completed']:
    proof = json.loads((ROOT / item['validation_report']).read_text(encoding='utf-8'))
    assert proof['status'] == 'PASS' and not proof['core_adoption_permitted']
count = len(batch['completed'])
summary = (
    f'最終goal ACTIVE。受付・代替行動70セルの研究core 0・正式記録0。'
    f'Windows venv起動不成立ch261018_001はSUMO/研究run作成前のFAILEDとして原本保全し、'
    f'親子PID確認を修正後52unit PASS。固定した現行共通5実装でcf26101801全21ケース・'
    f'独立再計算/35改変拒否・一次357ファイル不変がPASS。cs261018aは{count}/14設定を独立PASS、'
    f'進行状態{batch["status"]}、同一session46869を継続監視中。'
    f'上位pipelineの報告JSON型判定エラーは試験完了後・smoke起動前に停止した履歴として保全し、'
    f'共通実装を変えず専用smoke列を継続。全14完了後preflightを新規実行する。'
    f'旧READY/旧技術証跡/図v6は履歴、監視jdrt-b-15は再検証中PAUSED。'
    f'新READY後に監視を再有効化して新IDの最初の1セルを開始する。Drive読取のみ・外部送信なし。'
)
history = OUT / 'checkpoint_history'
history.mkdir(exist_ok=True)
backup = history / (sha256(old_bytes).hexdigest() + '.json')
if not backup.exists():
    backup.write_bytes(old_bytes)
new = dict(old)
new.update(at_jst=now, summary=summary, integrated_suite='cf26101801',
           integrated_cases_pass=len(audit['fixture_components']),
           canonical_partial_report=audit_path.relative_to(ROOT).as_posix(),
           canonical_partial_report_sha256=sha256(audit_path.read_bytes()).hexdigest(),
           smoke_sequence_session=46869, smoke_sequence_state='06_研究結果/jdrt/goal_20261017/cs261018a_smoke_sequence.json',
           smoke_sequence_status=batch['status'], smoke_setting_count=count,
           current_implementation_sha256=batch['implementation_sha256'],
           historical_smokes_current_implementation=False, technical_ready=False,
           running=[batch['active']] if batch['active'] else [],
           next='finish same cs261018a session46869; then new preflight cf26101801/current audit; READY review; activate monitor; new core ID',
           remaining_formal_gates=['current all14 independently PASS', 'new preflight receipt and capacity'])
state_path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
changed = []
for relative in ['context.md', '00_全体整理/現状把握_静的・動的シミュレーション整理.md',
                 '00_全体整理/現状把握_静的・動的シミュレーション整理.html']:
    path = ROOT / relative
    content = path.read_text(encoding='utf-8')
    assert old['summary'] in content, relative
    content = content.replace(old['summary'], summary)
    if relative == 'context.md':
        content = content.replace('**最終更新：** 2026-10-18（共通21/35改変・全14設定PASS、preflight照合中・研究未開始）',
                                  f'**最終更新：** 2026-10-18（現行21/35改変PASS・smoke {count}/14・研究未開始）')
    path.write_text(content, encoding='utf-8')
    changed.append(relative)
entry = {'at_jst': now, 'action': 'current_fixed_implementation_verification_checkpoint',
         'summary': summary, 'smoke_state': batch, 'checkpoint_backup': backup.relative_to(ROOT).as_posix(),
         'updated_documents': changed, 'core_runs': 0, 'input_changed': False,
         'pipeline_failure': "after successful fixture and audit, report-list scan AttributeError; preserved, format guard fixed outside common5", 
         'progress_classification': 'progress_and_verified_wait_session46869'}
for path in [OUT / 'operations.jsonl', WS / 'driver_logs/operations.jsonl', WS / 'driver_logs/monitoring.jsonl']:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
for relative in ['05_タスク管理/jdrt/JDRT-受付代替行動_専用CLI・開始ゲート実装手順.md',
                 '05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md',
                 '05_タスク管理/jdrt/JDRT_最終ゴール自律進行計画.md',
                 '01_経過報告/経過報告2026年08月/経過報告20260826.md',
                 '00_全体整理/決定ログ.md']:
    path = ROOT / relative
    with path.open('a', encoding='utf-8') as stream:
        stream.write('\n\n### 現行共通版の再検証・継続記録 ' + now + '\n\n' + summary + '\n\n'
                     '上位pipelineはFAILEDの原状態を残す。成功した21ケース/独立監査を再起動せず、'
                     'current suiteと現行SHAを参照してsmoke列を継続した。研究入力・比較条件・主要指標・除外規則の変更なし。\n')
print(json.dumps({'at_jst': now, 'verified_smokes': count, 'status': batch['status'], 'updated': changed}, ensure_ascii=False))
