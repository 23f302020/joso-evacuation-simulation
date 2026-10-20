"""One-cell transaction for registered realtime-B, isolated from v2 and REAL-R0."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'04_プログラム'))
from scripts.jdrt_realtime_b_junctionfix import PARAM,load_inputs,atomic_json,stamp
from scripts.jdrt_realtime_b_inputs import sha
from scripts.jdrt_realtime_b_validate import validate_run
P=json.loads(PARAM.read_text(encoding='utf-8'));WS=ROOT/P['workspace']
LEDGER=ROOT/'05_タスク管理/jdrt/JDRT-実時間B_セル検証台帳.jsonl'
RECORD=ROOT/'05_タスク管理/jdrt/JDRT-実時間B_full実験記録.md'

def alive(pid):
    if not pid:return False
    if os.name=='nt':
        h=ctypes.windll.kernel32.OpenProcess(0x1000,False,int(pid))
        if h:ctypes.windll.kernel32.CloseHandle(h);return True
        return False
    try:os.kill(int(pid),0);return True
    except OSError:return False

def items():
    result=[]
    for parent in ['runs','smoke']:
        for path in (WS/parent).glob('*/manifest.json'):
            m=json.loads(path.read_text(encoding='utf-8'));m['_directory']=str(path.parent);result.append(m)
    return result

def ledger_ids():
    return {json.loads(line)['run_id'] for line in LEDGER.read_text(encoding='utf-8').splitlines() if line.strip()} if LEDGER.exists() else set()

def status():
    records=items();recorded=ledger_ids();running=[m['run_id'] for m in records if m['status']=='RUNNING']
    known={m['run_id'] for m in records};unresolved=[]
    for path in (WS/'driver_logs').glob('*.state.json'):
        state=json.loads(path.read_text(encoding='utf-8'))
        if state['run_id'] not in known:
            if alive(state.get('pid')):running.append(state['run_id'])
            elif not (WS/'driver_logs'/(state['run_id']+'.diagnosis.json')).exists():unresolved.append(state['run_id'])
    core=[m for m in records if m['purpose']=='core'];unrecorded=[m['run_id'] for m in core if m['status']=='COMPLETED' and m['run_id'] not in recorded]
    unresolved.extend(m['run_id'] for m in core if m['status'] in ['FAILED','INVALID'] and not (WS/'driver_logs'/(m['run_id']+'.diagnosis.json')).exists())
    cells={(m['scenario'],m['seed']) for m in core if m['run_id'] in recorded}
    order=[(scenario,seed) for seed in P['seeds'] for scenario in P['scenarios']]
    return {'protocol':P['protocol'],'running':running,'unrecorded':unrecorded,'recorded_cells':len(cells),'registered_cells':len(order),
            'next_cell':next(({'scenario':a,'seed':b} for a,b in order if (a,b) not in cells),None),
            'failed_runs':[m['run_id'] for m in records if m['status'] in ['FAILED','INVALID']], 'unresolved_failures':unresolved}

def implementation():
    files=[ROOT/'04_プログラム/scripts/jdrt_realtime_b_junctionfix.py',ROOT/'04_プログラム/scripts/jdrt_realtime_b_inputs.py',
           ROOT/'04_プログラム/scripts/jdrt_realtime_b_validate.py',Path(__file__)]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in files}

def preflight():
    parameters,directory,m=load_inputs()
    report=json.loads((WS/'input_validation.json').read_text(encoding='utf-8'))
    if report['status']!='PASS' or report['input_manifest_sha256']!=sha(directory/'manifest.json') or report['validator_sha256']!=sha(ROOT/'04_プログラム/scripts/jdrt_realtime_b_validate.py'):raise RuntimeError('Current independent input PASS required')
    current_runner=sha(ROOT/'04_プログラム/scripts/jdrt_realtime_b_junctionfix.py')
    smoke_pass={}
    for item in items():
        if item['purpose']!='smoke' or item['status']!='COMPLETED':continue
        if item['implementation_sha256'].get('04_プログラム/scripts/jdrt_realtime_b_junctionfix.py')!=current_runner:continue
        validation=Path(item['_directory'])/'validation.json'
        if not validation.exists():continue
        v=json.loads(validation.read_text(encoding='utf-8'))
        if v['status']=='PASS' and v['manifest_sha256']==sha(Path(item['_directory'])/'manifest.json') and v['validator_sha256']==sha(ROOT/'04_プログラム/scripts/jdrt_realtime_b_validate.py'):smoke_pass[item['scenario']]=item['run_id']
    if set(smoke_pass)!=set(P['scenarios']):raise RuntimeError('Current-code validated smoke required for R0/R1/R2: '+str(smoke_pass))
    test=WS/'unit_test_gate.json'
    if not test.exists():raise RuntimeError('Unit-test record missing')
    test_data=json.loads(test.read_text(encoding='utf-8'))
    if test_data.get('status')!='PASS' or test_data['implementation_sha256']!=implementation():raise RuntimeError('Current implementation unit-test PASS required')
    return {'status':'READY','input_validation':report['status'],'smoke_runs':smoke_pass,'implementation_sha256':implementation()}

def launch(scenario,seed,purpose):
    logs=WS/'driver_logs';logs.mkdir(parents=True,exist_ok=True)
    lock=logs/'launch.lock'
    with lock.open('x',encoding='utf-8') as handle:handle.write(json.dumps({'pid':os.getpid(),'at_jst':stamp()}))
    try:return launch_locked(scenario,seed,purpose)
    finally:lock.unlink()

def launch_locked(scenario,seed,purpose):
    state=status()
    if state['running'] or state['unrecorded'] or state['unresolved_failures']:raise RuntimeError('Prior running/unrecorded/undiagnosed cell blocks start: '+str(state))
    load_inputs()
    if purpose=='core':preflight()
    run_id=f"rtb_{purpose}_{scenario.lower()}_seed{seed}_"+datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%dT%H%M%S')
    logs=WS/'driver_logs';logs.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-X','utf8',str(ROOT/'04_プログラム/scripts/jdrt_realtime_b_junctionfix.py'),'--scenario',scenario,'--seed',str(seed),'--run-id',run_id,'--purpose',purpose]
    env=dict(os.environ);env['PYTHONUTF8']='1'
    with (logs/(run_id+'.stdout.log')).open('w',encoding='utf-8') as stdout,(logs/(run_id+'.stderr.log')).open('w',encoding='utf-8') as stderr:
        flags=(subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
        startup=None
        if os.name=='nt':
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=flags,startupinfo=startup,close_fds=True)
    state={'run_id':run_id,'pid':process.pid,'purpose':purpose,'scenario':scenario,'seed':seed,'started_at_jst':stamp(),'command':command}
    atomic_json(logs/(run_id+'.state.json'),state)
    return {'status':'STARTED',**state}

def find(run_id):
    for m in items():
        if m['run_id']==run_id:return m
    raise FileNotFoundError(run_id)

def check(run_id):
    m=find(run_id);directory=Path(m.pop('_directory'));progress=directory/'progress.json'
    return {'run_id':run_id,'status':m['status'],'pid_alive':alive(m.get('pid')),'progress':json.loads(progress.read_text()) if progress.exists() else None,
            'error':m.get('error')}

def record(run_id):
    m=find(run_id)
    if m['purpose']!='core':raise RuntimeError('Smoke never enters research ledger')
    directory=Path(m['_directory']);v=validate_run(directory)
    if v['status']!='PASS':raise RuntimeError('Independent validation FAIL')
    paths=[RECORD,ROOT/'05_タスク管理/jdrt/JDRT-v2_完了後方針・タスク.md',ROOT/'context.md',ROOT/'00_全体整理/決定ログ.md',ROOT/'01_経過報告/経過報告2026年08月/経過報告20260826.md',LEDGER]
    if run_id in ledger_ids() and all(run_id in p.read_text(encoding='utf-8') for p in paths[:-1]):return {'status':'ALREADY_RECORDED','run_id':run_id,'validation':'PASS'}
    original={p:p.read_bytes() if p.exists() else None for p in paths}
    text=f"\n\n### {run_id}（{stamp()}正式記録）\n\nprotocol={P['protocol']}、{m['scenario']}、seed={m['seed']}。独立検証PASS。人物{v['people']}、Type4分母{v['type4_denominator']}、施設受入{v['type4_admitted']}、退出{v['type4_boundary_exit']}。道路観測{v['road_rows']}行、候補{v['candidate_rows']}行、閉鎖進入{v['closed_entries']}、曖昧遷移{v['ambiguous_transitions']}。方式間比較は全5seed完了後。manifest/validation: `{directory.relative_to(ROOT).as_posix()}`。\n"
    try:
        for path in paths[:-1]:
            old=path.read_text(encoding='utf-8') if path.exists() else '# JDRT 実時間B full実験記録\n'
            if run_id in old:continue
            if path.name=='context.md':
                marker='\n<!-- AGENT_CURRENT_END -->';old=old.replace(marker,f'\n\n**実時間B正式記録：** {run_id}、{m["scenario"]} seed{m["seed"]}、validate PASS・record完了。Type4={v["type4_admitted"]}/{v["type4_denominator"]}、退出は別アウトカム。次セルはスキルstatusを参照。\n'+marker,1)
            else:old+=text
            path.write_text(old,encoding='utf-8')
        if run_id not in ledger_ids():
            with LEDGER.open('a',encoding='utf-8') as h:h.write(json.dumps({'run_id':run_id,'scenario':m['scenario'],'seed':m['seed'],'protocol':P['protocol'],'recorded_at_jst':stamp(),'validation':v},ensure_ascii=False)+'\n')
        if not all(run_id in p.read_text(encoding='utf-8') for p in paths):raise RuntimeError('Partial record detected')
    except BaseException:
        for path,contents in original.items():
            if contents is None:
                if path.exists():path.unlink()
            else:path.write_bytes(contents)
        raise
    return {'status':'RECORDED','run_id':run_id,'validation':'PASS','state':status()}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project-root',default=str(ROOT));sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status');sub.add_parser('preflight');sub.add_parser('start-next')
    smoke=sub.add_parser('smoke');smoke.add_argument('--scenario',choices=P['scenarios'],required=True);smoke.add_argument('--seed',type=int,default=P['seeds'][0])
    for name in ['check','validate','record','recover','reject']:
        part=sub.add_parser(name);part.add_argument('--run-id',required=True)
        if name in ['recover','reject']:part.add_argument('--reason',required=True)
    args=parser.parse_args();start=time.monotonic();result=None;failure=None
    try:
        if Path(args.project_root).resolve()!=ROOT:raise ValueError('Unexpected project root')
        if args.command=='status':result=status()
        elif args.command=='preflight':result=preflight()
        elif args.command=='start-next':
            cell=status()['next_cell']
            result=launch(cell['scenario'],cell['seed'],'core') if cell else {'status':'ALL_RECORDED'}
        elif args.command=='smoke':result=launch(args.scenario,args.seed,'smoke')
        elif args.command=='check':result=check(args.run_id)
        elif args.command=='validate':result=validate_run(Path(find(args.run_id)['_directory']))
        elif args.command=='record':result=record(args.run_id)
        elif args.command=='reject':
            m=find(args.run_id)
            if m['status']=='RUNNING' or alive(m.get('pid')) or args.run_id in ledger_ids():raise RuntimeError('Reject requires stopped unrecorded run')
            directory=Path(m.pop('_directory'));logs=WS/'driver_logs'
            original=logs/(args.run_id+'.original_manifest.json')
            if not original.exists():original.write_bytes((directory/'manifest.json').read_bytes())
            m.update(status='INVALID',rejected_at_jst=stamp(),rejection_reason=args.reason);atomic_json(directory/'manifest.json',m)
            atomic_json(logs/(args.run_id+'.diagnosis.json'),{'run_id':args.run_id,'at_jst':stamp(),'reason':args.reason,'disposition':'preserved; not accepted; new ID required','implementation_sha256':implementation()})
            result={'status':'INVALID_PRESERVED','run_id':args.run_id,'reason':args.reason,'state':status()}
        elif args.command=='recover':
            m=find(args.run_id)
            if m['status']!='RUNNING' or alive(m.get('pid')):raise RuntimeError('Recovery requires orphaned RUNNING cell')
            directory=Path(m.pop('_directory'));m.update(status='FAILED',finished_at_jst=stamp(),error_type='RecoveredOrphan',error=args.reason);atomic_json(directory/'manifest.json',m);result={'status':'FAILED_PRESERVED','run_id':args.run_id}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if isinstance(result,dict) and result.get('status')=='FAIL':raise SystemExit(1)
    except BaseException as error:
        failure={'type':type(error).__name__,'message':str(error)};raise
    finally:
        logs=WS/'driver_logs';logs.mkdir(parents=True,exist_ok=True)
        with (logs/'operations.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps({'at_jst':stamp(),'command':args.command,'run_id':getattr(args,'run_id',None),'elapsed_sec':time.monotonic()-start,'result':result,'error':failure},ensure_ascii=False)+'\n')

if __name__=='__main__':main()
