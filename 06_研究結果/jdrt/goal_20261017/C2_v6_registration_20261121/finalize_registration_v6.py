"""One-shot v6 technical re-registration transaction (C2). Pattern: v5 finalize_registration.py.

Usage (from the project root or anywhere):
  python -B -X utf8 finalize_registration_v6.py --dry-run   # all pre-checks, writes nothing
  python -B -X utf8 finalize_registration_v6.py --apply     # one transaction; never reuse application01

Scientific values stay identical: only 7 metadata keys of the config change.
On failure after the first write, the state is preserved and reported (no automatic rollback/deletion);
originals are restorable from application01/before/.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
import argparse
import copy
import json
import sys

here = Path(__file__).resolve().parent
root = here.parents[3]
assert (root / '04_プログラム').is_dir() and (root / '.agents').is_dir(), root
out = here / 'application01'


def ext(p): return Path('\\\\?\\' + str(Path(p).resolve()))
def raw(p): return ext(p).read_bytes()
def digest(p): return sha256(raw(p)).hexdigest()
def read(p): return json.loads(raw(p).decode('utf-8-sig'))
def rel(p): return Path(p).resolve().relative_to(root).as_posix()
def dumps(value): return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
def save_x(p, value):
    with ext(p).open('xb') as f:
        f.write(dumps(value))


ap = argparse.ArgumentParser()
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument('--dry-run', action='store_true')
g.add_argument('--apply', action='store_true')
args = ap.parse_args()

now = datetime.now().astimezone().isoformat()
REG_DATE = '20261121'
NEW_REG = 'choice_parked_abort_v6_' + REG_DATE
NEW_WS = '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_parkedabort_v6'
NEW_RECORD = '05_タスク管理/jdrt/JDRT-受付代替行動_停車中除去v6_full実験記録.md'
NEW_LEDGER = '05_タスク管理/jdrt/JDRT-受付代替行動_停車中除去v6_セル検証台帳.jsonl'
NEW_DOC = '03_研究設計文書/jdrt/常総市JDRT_受付代替行動_停車中除去分類_技術再登録_v6.md'
OLD_CFG_SHA = '226ee318cfe114dd4ba4361bd4e63e51633b25496d8502c150b288532347bb49'
OLD_REG = 'choice_shared_stopindex_v5_20261029'
CONTRACT_KEY = 'parked_drt_abort_stop_on_current_closure'
CONTRACT_VALUE = 'abort_only_with_parked_stop_bit_same_time_closure_applied_initial_or_current_closed'
CHANGED = {'workspace', 'registration_id', 'record_files', 'native_observation_addendum',
           'amendments', 'status', 'native_diagnostic_observation_contract'}
V5_TXN = root / ('06_研究結果/jdrt/goal_20261017/route_replacement_failure_20261028/'
                 'smoke13_native_crash_20261029/v5_registration_candidate/application01/transaction.json')
VALIDATE = '04_プログラム/scripts/jdrt_realtime_choice_validate.py'
OPERATIONS = '06_研究結果/jdrt/goal_20261017/operations.jsonl'
APPROVAL = '承認済み（ユーザー 2026-11-21「承認する」）・登録済み。技術READY=false。'

param = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
checks = []


def check(name, fn):
    try:
        ok = bool(fn())
        checks.append({'check': name, 'pass': ok})
    except Exception as exc:  # report every failing check, never write
        checks.append({'check': name, 'pass': False, 'error': repr(exc)})


old_bytes = raw(param)
old = json.loads(old_bytes.decode('utf-8-sig'))
check('current_config_sha256', lambda: digest(param) == OLD_CFG_SHA)
check('config_lf_roundtrip_format', lambda: dumps(old) == old_bytes)
check('old_registration_id_v5', lambda: old['registration_id'] == OLD_REG)
check('old_amendments_4', lambda: len(old['amendments']) == 4)

old_ws_manifest = root / old['workspace'] / old['input_directory'] / 'manifest.json'
v5_manifest = read(old_ws_manifest) if ext(old_ws_manifest).exists() else None
old_doc = root / old['native_observation_addendum']

# ---- build the new config in memory ----
cfg = copy.deepcopy(old)
cfg['workspace'] = NEW_WS
cfg['registration_id'] = NEW_REG
cfg['record_files'] = [NEW_RECORD] + list(old['record_files'][1:-1]) + [NEW_LEDGER]
cfg['native_observation_addendum'] = NEW_DOC
cfg['status'] = 'DESIGN_REGISTERED_TECHNICAL_NOT_READY'
cfg['native_diagnostic_observation_contract'] = dict(old['native_diagnostic_observation_contract'])
cfg['native_diagnostic_observation_contract'][CONTRACT_KEY] = CONTRACT_VALUE
amendment = {
    'at_jst': now,
    'kind': 'parked_abort_stop_classifier_technical_reregistration_v6',
    'authority': ('User decision C2 and choice C (status not a condition); classifier rule text approved by user '
                  'before registration; no scientific method/metric/comparison/exclusion change'),
    'previous_registered_config_sha256': OLD_CFG_SHA,
    'previous_registration': OLD_REG,
    'previous_current_accepted_cells': 24,
    'v5_recorded24_and_invalid25_preserved': True,
    'cell_set_changed': False,
    'scientific_conditions_changed': False,
    'changed_common_implementation': [VALIDATE],
    'classifier_rule': ('aborts stop accepted only with (a)-(f) of the v6 document; existing boarding/alighting '
                        'and skips-stop branches unchanged'),
    'new_fixture_case': 'drt_parked_current_closure (appended last to CASES)',
    'status': 'REGISTERED_TECHNICAL_PREPARATION_NOT_READY',
    'previous_technical_document': {'path': old['native_observation_addendum'], 'sha256': digest(old_doc)},
    'previous_v5_input_manifest': {'path': rel(old_ws_manifest),
                                   'sha256': digest(old_ws_manifest) if v5_manifest is not None else None},
}
cfg['amendments'] = list(old['amendments']) + [amendment]

# ---- pre-checks (v5 lines 28-38 pattern, plus v6 items) ----
check('key_set_equal', lambda: set(cfg) == set(old))
check('unchanged_keys_equal', lambda: all(cfg[k] == old[k] for k in old if k not in CHANGED))
# status is in the permitted 7 but keeps the same value (diff proposal item 6; v5 wrote this value too),
# so the keys whose value actually changes are exactly the other 6.
check('value_changed_keys_exactly_6_and_status_same_value',
      lambda: {k for k in old if cfg[k] != old[k]} == CHANGED - {'status'}
      and old['status'] == cfg['status'] == 'DESIGN_REGISTERED_TECHNICAL_NOT_READY')
check('cells_70_same_order', lambda: len(cfg['cells']) == 70 and cfg['cells'] == old['cells'])
check('amendments_prefix_equal', lambda: cfg['amendments'][:-1] == old['amendments'])
check('record_files_middle_equal', lambda: cfg['record_files'][1:-1] == old['record_files'][1:-1]
      and len(cfg['record_files']) == 7)
check('previous_choice_input_manifest_equal',
      lambda: cfg['previous_choice_input_manifest'] == old['previous_choice_input_manifest'])
check('contract_existing_7_keys_equal', lambda: len(old['native_diagnostic_observation_contract']) == 7 and all(
    cfg['native_diagnostic_observation_contract'][k] == v for k, v in old['native_diagnostic_observation_contract'].items())
    and len(cfg['native_diagnostic_observation_contract']) == 8)
check('new_workspace_absent', lambda: not ext(root / NEW_WS).exists())
check('new_record_files_absent', lambda: not ext(root / NEW_RECORD).exists() and not ext(root / NEW_LEDGER).exists())
check('application_dir_absent', lambda: not ext(out).exists())
check('v5_input_manifest_present', lambda: v5_manifest is not None)

v5_common5 = read(V5_TXN)['common5']
check('v5_common5_has_5', lambda: len(v5_common5) == 5 and set(v5_common5) == set(old['execution']['implementation_files']))
check('common4_sha_same_as_v5', lambda: all(digest(root / n) == v for n, v in v5_common5.items() if n != VALIDATE))
check('validate_sha_changed_from_v5', lambda: digest(root / VALIDATE) != v5_common5[VALIDATE])

# PAP / Registry / state spec / alignment addendum vs the SHA recorded in the v5 input manifest
doc_keys = ('pap', 'registry_document', 'state_contract', 'alignment_addendum')
doc_sha = {old[k]: digest(root / old[k]) for k in doc_keys}
check('pap_registry_state_sha_unchanged_vs_v5_manifest',
      lambda: all(v5_manifest['source_sha256'][n] == v for n, v in doc_sha.items()))

# v6 document: exists, is still the draft, anchors present exactly once
new_doc_path = root / NEW_DOC
doc_old_bytes = raw(new_doc_path) if ext(new_doc_path).exists() else b''
doc_text = doc_old_bytes.decode('utf-8')
anchors = {
    'title': '技術再登録v6（下書き）',
    'status': ('状態：**ドラフト。ユーザー承認前。** 未登録、技術READY=false、本実験開始不可。config は未適用'
               '（差分案：`05_タスク管理/jdrt/C2_v6_config差分案_20261121.md`）。'),
    'plan': '登録案：registration_id `choice_parked_abort_v6_<YYYYMMDD>`、',
    's5_item3': '3. 「この1件を見てから基準を変える」危険の受容（設計書 §3.5）。',
    's6': '\n## 6. 設計書との差分（実装で決めた点）',
}
anchors_ok = all(doc_text.count(a) == 1 for a in anchors.values())
check('v6_doc_draft_anchors_once', lambda: anchors_ok)


def build_doc(text):
    receipt_path = rel(out / 'registration_receipt.json')
    text = text.replace(anchors['title'], '技術再登録v6')
    text = text.replace(anchors['status'],
                        '状態：**' + APPROVAL + '** 本実験開始不可。登録時点：' + now
                        + '。config の7項目を書き換え、新しい記録2ファイルを作成した（取引の受領：`' + receipt_path
                        + '`）。新系列の全開始前検証（入力・READY・U4・監視・1セル目）は未完。')
    text = text.replace(anchors['plan'], '登録：registration_id `' + NEW_REG + '`、')
    s6 = text.index(anchors['s6'])
    record = ('\n**承認の記録（2026-11-21）：** 開発PCのチャットで、ユーザーが上の1〜3を「承認する」と直接回答した'
              '（台帳 `00_全体整理/判断と結果の台帳.md` の JD-20261121-v6-rule-approved）。status の範囲は、それ以前の'
              '「1案c」（JD-20261121-c2-user-decisions）による。25番目 ss261119a25 の棄却は「aで行う」'
              '（JD-20261121-reject-approved）で、学校PCが実行した。この承認に基づいて、' + now[:19]
              + '（JST）に登録の取引を行った（registration_id `' + NEW_REG + '`、受領 `' + receipt_path + '`）。\n')
    return text[:s6] + '\n' + record + text[s6:]


new_doc_text = build_doc(doc_text) if anchors_ok else ''
check('v6_doc_new_text_ok', lambda: APPROVAL in new_doc_text and '（下書き）' not in new_doc_text
      and '<YYYYMMDD>' not in new_doc_text and 'ユーザー承認前' not in new_doc_text)
check('amendment_no_placeholder', lambda: '<' not in json.dumps(amendment, ensure_ascii=False)
      and amendment['previous_v5_input_manifest']['sha256'] is not None)

# record 8 files: read only
record8 = list(old['record_files']) + [OPERATIONS]
check('record8_count_8_present', lambda: len(set(record8)) == 8 and all(ext(root / n).is_file() for n in record8))
record8_sha = {n: digest(root / n) for n in record8 if ext(root / n).is_file()}

new_record_text = ('# 受付・代替行動 停車中除去v6：正式実験記録\n\n登録：' + NEW_REG
                   + '\n\n正式0/70。技術準備中・READY=false。v5の記録済み24セルとINVALIDの25番目（ss261119a25）を含む旧系列・'
                   'smoke・fixtureを採用しない。正式採用は専用CLI recordのみ。\n')

new_cfg_bytes = dumps(cfg)
failed = [c for c in checks if not c['pass']]
summary = {'mode': 'dry-run' if args.dry_run else 'apply', 'at_jst': now, 'checks': checks,
           'all_pass': not failed, 'old_config_sha256': digest(param),
           'new_config_sha256_preview': sha256(new_cfg_bytes).hexdigest(),
           'changed_keys': sorted(CHANGED)}
if failed or args.dry_run:
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(1 if failed else 0)

# ---- apply: preserve (copies only; originals untouched) ----
out.mkdir()
archive = out / 'before'
archive.mkdir()
to_preserve = [param, old_doc, old_ws_manifest, new_doc_path] + [root / n for n in record8]
archive_map = {}
for i, p in enumerate(to_preserve):
    dest = archive / ('%02d_%s' % (i, p.name))
    ext(dest).write_bytes(raw(p))
    assert raw(dest) == raw(p)
    archive_map[rel(p)] = {'sha256': digest(p), 'archive': rel(dest)}
with ext(out / 'prepared_config.json').open('xb') as f:
    f.write(new_cfg_bytes)
with ext(out / 'prepared_document.md').open('xb') as f:
    f.write(new_doc_text.encode('utf-8'))
receipt = {'at_jst': now, 'state': 'PREPARED', 'registration_id': NEW_REG, 'previous_registration': OLD_REG,
           'old_config_sha256': OLD_CFG_SHA, 'changed_keys': sorted(CHANGED),
           'changes': {k: {'old': old[k], 'new': cfg[k]} for k in sorted(CHANGED) if k != 'amendments'},
           'amendment_appended': amendment, 'checks': checks, 'before': archive_map,
           'common5_v5': v5_common5, 'common5_now': {n: digest(root / n) for n in v5_common5},
           'pap_registry_state_alignment_sha256': doc_sha, 'record8_sha256_before': record8_sha,
           'v6_document_sha256_before': sha256(doc_old_bytes).hexdigest(),
           'core_ready': False, 'core_started': False}
save_x(out / 'registration_receipt.prepared.json', receipt)
written = []
try:
    with ext(root / NEW_RECORD).open('xb') as f:
        f.write(new_record_text.encode('utf-8'))
    written.append(NEW_RECORD)
    with ext(root / NEW_LEDGER).open('xb'):
        pass
    written.append(NEW_LEDGER)
    assert digest(param) == OLD_CFG_SHA
    ext(param).write_bytes(new_cfg_bytes)
    written.append(rel(param))
    assert raw(new_doc_path) == doc_old_bytes
    ext(new_doc_path).write_bytes(new_doc_text.encode('utf-8'))
    written.append(NEW_DOC)
    # read back
    assert read(param) == cfg and raw(param) == new_cfg_bytes
    assert all(read(param)[k] == old[k] for k in old if k not in CHANGED)
    assert raw(new_doc_path) == raw(out / 'prepared_document.md')
    assert raw(root / NEW_LEDGER) == b''
    assert all(digest(root / n) == v for n, v in v5_common5.items() if n != VALIDATE)
    assert all(digest(root / n) == v for n, v in record8_sha.items()), 'record8 changed'
    assert all(digest(root / n) == v for n, v in doc_sha.items())
    assert digest(old_ws_manifest) == amendment['previous_v5_input_manifest']['sha256']
    assert not ext(root / NEW_WS).exists()
    receipt.update(state='APPLIED_METADATA_ONLY_NOT_READY', new_config_sha256=digest(param),
                   created={NEW_RECORD: digest(root / NEW_RECORD), NEW_LEDGER: digest(root / NEW_LEDGER)},
                   v6_document_sha256_after=digest(new_doc_path), written=written,
                   record8_sha256_after={n: digest(root / n) for n in record8},
                   next=('commit/push on dev PC; school PC pulls after reject/ack, builds new inputs, '
                         'verifies physical SHA equal to v5, READY, U4, monitor patterns, first cell by CLI'))
except BaseException as exc:
    receipt.update(state='FAILED_PRESERVED_STOP', error=repr(exc), written=written,
                   restore_from='application01/before (manual; no automatic rollback)')
    save_x(out / 'registration_receipt.json', receipt)
    raise
save_x(out / 'registration_receipt.json', receipt)
print(json.dumps({'state': receipt['state'], 'old_config_sha256': OLD_CFG_SHA,
                  'new_config_sha256': receipt['new_config_sha256'], 'written': written,
                  'checks_passed': sum(c['pass'] for c in checks), 'checks_total': len(checks)},
                 ensure_ascii=False, indent=2))
