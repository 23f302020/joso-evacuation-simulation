"""One-shot metadata/data transaction; all scientific values remain identical."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
import json

root = Path.cwd().resolve()
d = root / '06_研究結果/jdrt/goal_20261017/route_replacement_failure_20261028/smoke13_native_crash_20261029'
candidate = d / 'v5_registration_candidate'
out = candidate / 'application01'
assert not out.exists(), 'Never reuse an application directory'

def ext(p): return Path('\\\\?\\' + str(Path(p).resolve()))
def raw(p): return ext(p).read_bytes()
def digest(p): return sha256(raw(p)).hexdigest()
def read(p): return json.loads(raw(p).decode('utf-8-sig'))
def rel(p): return Path(p).resolve().relative_to(root).as_posix()
def save(p, value):
    with ext(p).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

now = datetime.now().astimezone().isoformat()
param = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
old = read(param)
assert digest(param) == '782252f9f3ffaf044a1598d79ef89a38f63a90ba17ffdd45273f3817f49882b8'
cfg = read(candidate / 'parameters.draft.json')
changed = {'workspace', 'registration_id', 'record_files', 'native_observation_addendum', 'amendments', 'status'}
assert set(cfg) == set(old)
assert all(cfg[k] == old[k] for k in old if k not in changed)
assert len(cfg['cells']) == 70 and cfg['cells'] == old['cells']
assert cfg['amendments'][:-1] == old['amendments']
assert cfg['record_files'][1:-1] == old['record_files'][1:-1]
assert cfg['previous_choice_input_manifest'] == old['previous_choice_input_manifest']
assert cfg['registration_id'] == 'choice_shared_stopindex_v5_20261029'
assert not (root / cfg['workspace']).exists()
targets = [root / cfg['native_observation_addendum'], root / cfg['record_files'][0], root / cfg['record_files'][-1]]
assert not any(p.exists() for p in targets)

baseline = {name: digest(root / name) for name in (
    '04_プログラム/scripts/jdrt_realtime_choice.py',
    '04_プログラム/scripts/jdrt_realtime_choice_inputs.py',
    '04_プログラム/scripts/jdrt_realtime_choice_validate.py',
    '04_プログラム/scripts/jdrt_choice_policy.py',
    '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py')}
bundles = {}
for role, dirname, reportname in (
        ('control', 'native_ctl_si29a', 'control_si29a_manifest_verification.json'),
        ('patched', 'native_lat_si29a', 'selected_si29a_manifest_verification.json')):
    directory = root / '04_プログラム/output/sumo/toolchains' / dirname
    path = directory / 'toolchain.json'
    m = read(path)
    vpath = d / reportname
    v = read(vpath)
    assert v['status'] == 'IMPORTS_VERIFIED_NOT_SIMULATED' and v['simulation_executed'] is False
    assert v['fingerprint']['toolchain_manifest_sha256'] == digest(path)
    assert m['provenance']['role'] == role
    assert len(m['files']) == 237
    assert all(digest(directory / name) == value for name, value in m['files'].items())
    assert {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()} == set(m['files']) | {'toolchain.json'}
    provenance = directory / m['provenance']['native_provenance']
    original = d / 'full_pair_primary02' / (role + '_provenance.json')
    assert raw(provenance) == raw(original)
    binaries = {key: digest(directory / m['roles'][key]) for key in ('sumo', 'netconvert')}
    bundles[role] = {'manifest': rel(path), 'manifest_sha256': digest(path),
                     'files': len(m['files']), 'all_file_sha256_verified': True,
                     'provenance_exact_copy': True, 'binary_sha256': binaries,
                     'fresh_import_report': rel(vpath), 'fresh_import_report_sha256': digest(vpath)}

assert bundles['control']['manifest_sha256'] == '8fc615c82ca284c4f5ff94e808e39f2fa974cb0ef0d76933a2b79373f33cdf98'
assert bundles['patched']['manifest_sha256'] == '9441822d02fe1a068ade0d24aade92ba4228e13d53a3c12edb229cdc80607669'
assert all(digest(root / name) == value for name, value in baseline.items())
out.mkdir()
archive = out / 'before'
archive.mkdir()
archive_map = {}
to_preserve = [param, root / old['native_observation_addendum'],
               root / old['workspace'] / old['input_directory'] / 'manifest.json']
to_preserve += [root / name for name in old['record_files']]
for i, p in enumerate(to_preserve):
    dest = archive / (str(i) + '.bin')
    ext(dest).write_bytes(raw(p))
    assert raw(dest) == raw(p)
    archive_map[rel(p)] = {'sha256': digest(p), 'archive': rel(dest)}

cfg['status'] = 'DESIGN_REGISTERED_TECHNICAL_NOT_READY'
am = cfg['amendments'][-1]
am.update(at_jst=now, status='REGISTERED_TECHNICAL_PREPARATION_NOT_READY',
          bundle_manifest_binding=bundles,
          previous_technical_document={'path': old['native_observation_addendum'], 'sha256': digest(root / old['native_observation_addendum'])},
          previous_v4_input_manifest={'path': rel(to_preserve[2]), 'sha256': digest(to_preserve[2])})
assert all(cfg[k] == old[k] for k in old if k not in changed)
doc = (candidate / 'registration.draft.md').read_text(encoding='utf-8')
doc = doc.replace('技術再登録v5（隔離下書き）', '技術再登録v5')
start = doc.index('状態：DRAFT_NOT_APPLIED')
end = doc.index('\n\n', start)
doc = doc[:start] + f'登録時点：{now}。状態：REGISTERED_TECHNICAL_PREPARATION_NOT_READY、技術READY=false、本実験開始不可。原本を保全して管理情報だけの技術再登録を行った。両版bundleの元パッケージ処理と別プロセスの読み込み検証はexit0。新系列の全開始前検証は未完。' + doc[end:]
doc = doc.replace('新登録候補は', '新登録は').replace('新workspace候補は', '新workspaceは')
doc = doc.replace('現在は対照版を作成中、選択版は未開始。', '両版の元処理・読み込み検証が正常終了し、全237ファイルずつを独立照合した。')
doc = doc.replace('候補のstatusはDRAFTで、未適用のままREADYへ読み替えない。', '登録済みでもREADYへ読み替えない。')
for role, label in (('control', '対照'), ('patched', '選択')):
    b = bundles[role]
    doc = doc.replace(f'- {label}bundle manifest/SHA：PENDING', f"- {label}bundle manifest/SHA：`{b['manifest']}` / `{b['manifest_sha256']}`")
doc = doc.replace('## 正本化時に固定する証拠（未固定欄を残さない）', '## 登録時の固定証拠')
doc += '\n\n登録の旧config・v4文書・入力manifest・全7記録先の原本、科学的設定/70セルの一致とbundle読戻しは `v5_registration_candidate/application01/transaction.json` に保存する。過去の下書きと比較報告は書き換えない。\n'
assert 'PENDING' not in doc and '隔離下書き）' not in doc
save(out / 'prepared_config.json', cfg)
with ext(out / 'prepared_document.md').open('x', encoding='utf-8', newline='\n') as f: f.write(doc)
txn = {'at_jst': now, 'state': 'PREPARED', 'previous': archive_map, 'common5': baseline,
       'bundles': bundles, 'scientific_projection_equal': True, 'all70_cells_and_order_equal': True,
       'prior_input_archive_contract_unchanged': True, 'core_ready': False, 'core_started': False}
save(out / 'transaction.prepared.json', txn)
try:
    with ext(targets[0]).open('x', encoding='utf-8', newline='\n') as f: f.write(doc)
    with ext(targets[1]).open('x', encoding='utf-8', newline='\n') as f:
        f.write('# 受付・代替行動 停車履歴v5：正式実験記録\n\n登録：' + cfg['registration_id'] + '\n\n正式0/70。技術準備中・READY=false。旧系列・smoke・fixtureを採用しない。正式採用は専用CLI recordのみ。\n')
    with ext(targets[2]).open('x', encoding='utf-8') as f: pass
    assert digest(param) == am['previous_registered_config_sha256']
    ext(param).write_bytes(raw(out / 'prepared_config.json'))
    assert read(param) == cfg and raw(targets[0]) == raw(out / 'prepared_document.md')
    assert raw(targets[2]) == b''
    assert all(digest(root / name) == value for name, value in baseline.items())
    assert all(digest(root / name) == value['sha256'] for name, value in archive_map.items() if name != rel(param))
    txn.update(state='APPLIED_METADATA_ONLY_NOT_READY', config_sha256=digest(param),
               created={rel(p): digest(p) for p in targets}, next='Prepare new inputs with existing input builder, verify unchanged artifacts; new native/full controller/audit/all14/preflight/G6/capacity/07 before core')
except BaseException as exc:
    txn.update(state='FAILED_PRESERVED_STOP', error=repr(exc))
    save(out / 'transaction.json', txn)
    raise
save(out / 'transaction.json', txn)
print(json.dumps({'state': txn['state'], 'config_sha256': txn['config_sha256'], 'bundle_files_per_role': 237,
                  'scientific_projection_equal': True, 'core_ready': False}, ensure_ascii=False))
