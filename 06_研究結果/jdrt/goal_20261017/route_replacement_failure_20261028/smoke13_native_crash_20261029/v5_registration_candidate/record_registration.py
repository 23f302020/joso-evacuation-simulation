"""Read back this metadata transaction and prepared inputs; record current gates."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
import json

root=Path.cwd().resolve()
goal=root/'06_研究結果/jdrt/goal_20261017'
d=goal/'route_replacement_failure_20261028/smoke13_native_crash_20261029'
out=d/'v5_registration_candidate/application01'
def ext(p):return Path('\\\\?\\'+str(Path(p).resolve()))
def data(p):return ext(p).read_bytes()
def sha(p):return sha256(data(p)).hexdigest()
def read(p):return json.loads(data(p).decode('utf-8-sig'))
def rel(p):return Path(p).resolve().relative_to(root).as_posix()
def save(p,v):ext(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def archive(p):
    folder=goal/'document_history'
    target=folder/(sha(p)+'_'+p.name)
    if ext(target).exists():assert data(target)==data(p)
    else:ext(target).write_bytes(data(p))
def text(p,t):ext(p).write_text(t,encoding='utf-8')
now=datetime.now().astimezone().isoformat()
tx=read(out/'transaction.json')
assert tx['state']=='APPLIED_METADATA_ONLY_NOT_READY'
param=root/'04_プログラム/config/jdrt_realtime_choice_v1.json'
cfg=read(param)
assert sha(param)==tx['config_sha256']
assert all(sha(root/p)==h for p,h in tx['common5'].items())
previous=read(root/cfg['amendments'][-1]['previous_v4_input_manifest']['path'])
folder=root/cfg['workspace']/cfg['input_directory']
current=read(folder/'manifest.json')
assert current['registration_id']==cfg['registration_id']
assert current['registered_cells']==70 and current['people']==11965
assert set(current['artifacts'])==set(previous['artifacts'])
assert current['artifacts']==previous['artifacts']
assert all(sha(folder/p)==h for p,h in current['artifacts'].items())
assert all(sha(root/p)==h for p,h in current['source_sha256'].items())
validation=read(root/cfg['workspace']/'input_validation.json')
assert validation['status']=='PASS' and all(v is True for v in validation['checks'].values())
assert validation['input_manifest_sha256']==sha(folder/'manifest.json')
assert data(root/cfg['record_files'][-1])==b''
assert not list((root/cfg['workspace']/'runs').glob('*'))
report={'at_jst':now,'status':'REGISTERED_V5_INPUTS_INDEPENDENTLY_VALIDATED_NOT_READY',
 'transaction':rel(out/'transaction.json'),'transaction_sha256':sha(out/'transaction.json'),
 'registration_id':cfg['registration_id'],'config_sha256':sha(param),
 'common5':tx['common5'],'all70_cells_and_scientific_values_unchanged':True,
 'input_manifest':rel(folder/'manifest.json'),'input_manifest_sha256':sha(folder/'manifest.json'),
 'all_input_artifacts_byte_identical_to_v4':True,'input_artifacts':len(current['artifacts']),
 'source_sha256_current':True,'independent_input_checks':len(validation['checks']),
 'bundles':tx['bundles'],'formal_cells':0,'core_running':0,'technical_ready':False,
 'original_package_session':25180,'original_package_exit_code':0,
 'original_import_verify_session':69728,'original_import_verify_exit_code':0,
 'observation_limit':'Completion handle and manifest observed at20:19; no continuous observation or invented finish time for16:39-20:19',
 'input_validation_stdout_relocation':'Initial stdout was redirected to one named parent-directory file; moved into application01 after original1050 exit0. No input or validation result changed.',
 'next':'New same-source native pair/stop-index guards, full controller suite/audit/all14/new preflight/G6/capacity/07 before core'}
assert not (out/'readback.json').exists()
save(out/'readback.json',report)
cp=goal/'G4実装・実SUMO_継続チェックポイント.json'
archive(cp);c=read(cp)
c['actual_native_packaging'].update(status='TERMINAL_PACKAGE_AND_IMPORT_READBACK_VERIFIED_NOT_READY',
 original_package_exit_code=0,verify_session=69728,verify_exit_code=0,
 manifest=tx['bundles']['patched']['manifest'],manifest_sha256=tx['bundles']['patched']['manifest_sha256'],
 readback=rel(out/'readback.json'))
c['v5_registration_candidate'].update(status='APPLIED_SEPARATE_TECHNICAL_V5_NOT_READY',
 applied_config_sha256=sha(param),readback=rel(out/'readback.json'),next=report['next'])
c.update(at_jst=now,registration_id=cfg['registration_id'],workspace=cfg['workspace'],
 current_toolchain_manifest=tx['bundles']['patched']['manifest'],current_toolchain_manifest_sha256=tx['bundles']['patched']['manifest_sha256'],
 observed_formally_recorded=0,technical_ready=False,current_hold='NO_CURRENT_READY',
 next=report['next'],progress_classification='PROGRESS_v5_registered_and_new_input28_PASS')
save(cp,c)
summary='両版の新しい実行ファイル一式を作成し、各237ファイルのSHAと原本・別プロセスの読み込みを確認しました。研究設定と70条件を変えず、別の技術登録v5と新入力を作成し、全入力artifactの旧v4とのバイト一致と独立28検査を確認しました。正式0/70・READY=falseで、本実験は未開始です。次は新両版の実動作回帰、全controller試験・独立監査・全14設定smoke・開始前検査です。'
task=root/'05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md'
archive(task);t=task.read_text(encoding='utf-8');pos=t.index('\n')
text(task,t[:pos+1]+'\n**2026-10-29 20時台の続報：** '+summary+'\n\n[技術v5の原本照合](../../'+rel(out/'readback.json')+')。\n'+t[pos+1:])
md=root/'00_全体整理/現状把握_静的・動的シミュレーション整理.md'
archive(md);t=md.read_text(encoding='utf-8');anchor='### 2026-10-29\n';assert t.count(anchor)==1
text(md,t.replace(anchor,anchor+'\n- '+summary+'\n',1))
context=root/'context.md';archive(context);t=context.read_text(encoding='utf-8')
a=t.index('<!-- CHOICE_CURRENT_CONTEXT_BEGIN -->');b=t.index('<!-- CHOICE_CURRENT_CONTEXT_END -->',a)
text(context,t[:a]+'<!-- CHOICE_CURRENT_CONTEXT_BEGIN -->\n'+f'最新HOLD（{now}点観測）：'+summary+' 研究用の以後のprocess-local選択先は `'+tx['bundles']['patched']['manifest']+'`、manifest SHA `'+tx['bundles']['patched']['manifest_sha256']+'`。OS/global SUMOは変更なし。元パッケージ25180/別読込69728はいずれもexit0、独立原本照合は `'+rel(out/'readback.json')+'`。旧v4/旧採用/FAILEDは保全し新比較へ混ぜない。具体操作はG4 checkpointと元handleを参照。Drive読取のみ、外部送信/公開更新なし。\n'+t[b:])
ref=root/'.agents/skills/joso-jdrt-runner/references/routine_operations.md'
archive(ref);t=ref.read_text(encoding='utf-8')
section='\n\n## Technical registration after a shared native repair\n\nIf the current technical registration promises unchanged native binaries, preserve it and use a separate technical registration/workspace for an authorized native correctness repair. Before changing metadata, finish both role packages and fresh-process imports, bind the actual manifest/file/provenance hashes, archive the selected config/document/input manifest and all record targets, then prove that scientific values and all cell IDs/order are identical. Preserve old amendments and the original preregistration/previous-input archive contract; do not repoint that contract merely to the most recent workspace. Record both bundle pins and the prior current technical document/input in the new amendment.\n\nUse the existing input preparation and independent input verifier in the new workspace; compare every regenerated artifact with the previous current artifacts. Start with an empty new formal ledger. Packaging, metadata registration and input PASS are not native behavior PASS or READY. Select the new bundle only in each calling process and require fresh affected native/controller/audit/all-setting/preflight/G6/capacity/monitor evidence before core. A failed metadata transaction is preserved and blocks starts; never replay an archived one-shot application recipe.\n\n2026-10-29 scope: registration v5 applied metadata only, all70/scientific values unchanged, both237-file bundles and all input artifacts read back, independent input28 PASS. Prior reference bytes are in goal document_history; application evidence and one-shot source are in route_replacement_failure_20261028/smoke13_native_crash_20261029/v5_registration_candidate/application01. This instruction addition changes no helper behavior, frozen common5 or acceptance gates.\n'
assert '## Technical registration after a shared native repair' not in t;text(ref,t+section)
record='\n\n### JD-20261029-root-v5-registration\n\n判断時点：'+now+'。担当：本chat、選択モデルを維持し実backendは独立未確認。ユーザーの最終goal自律実行とAGENTS技術修正権限に従う。旧v4のnative不変条項へ例外を上書きする代替案は採らず、科学的値/70条件を維持した別v5へ固定した。旧原本・全履歴・失敗を保全。根拠は `'+rel(out/'readback.json')+'` とtransactionのSHA付き原本。両237ファイル・全入力artifact一致/28独立検査は事実。native安全性・現実精度・全体READYは未実証であり、後続全検査と本実験/分析/大型バス/最終報告が残る。技術分離・値同一性の確信度は高、研究結果への効果は未評価。状態：進行、core不可。\n'
for p in (root/'00_全体整理/決定ログ.md',root/'00_全体整理/判断と結果の台帳.md'):
    archive(p);t=p.read_text(encoding='utf-8');assert '### JD-20261029-root-v5-registration' not in t;text(p,t+record)
row={'at_jst':now,'action':'technical_v5_registration_and_input_readback','classification':'PROGRESS','report':rel(out/'readback.json'),
 'registration_id':cfg['registration_id'],'formal_cells':0,'technical_ready':False,'next':report['next']}
for p in (goal/'operations.jsonl',root/cfg['workspace']/'driver_logs/monitoring.jsonl'):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
print(json.dumps({'status':report['status'],'input_artifacts':report['input_artifacts'],'independent_checks':28,
 'core_ready':False,'readback':rel(out/'readback.json')},ensure_ascii=False))
