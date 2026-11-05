"""Read terminal selected-pair primary evidence; never simulate/validate/adopt.

The original parent must separately verify executor termination. This report
binds saved evidence and grants no live start or research READY permission.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from choice_native_regression import failure_receipt, recompute_plans


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main(root, state_path, output):
    root, state_path, output = root.resolve(), state_path.resolve(), output.resolve()
    goal=root/'06_研究結果/jdrt/goal_20261017'
    if not state_path.is_relative_to(goal) or not output.is_relative_to(goal) or output.exists():
        raise ValueError('Existing goal-local state and unused goal-local report required')
    state_hash=sha(state_path)
    s=read(state_path)
    if (s.get('schema')!='selected_native_pair_v1' or s.get('status')!='SELECTED_PAIR_VERIFIED_PENDING_NATIVE_GUARDS'
            or s.get('active') is not None or s.get('research_adoption_permitted') is not False
            or s.get('technical_ready') is not False or [r['role'] for r in s['completed']]!=['control','patched']):
        raise ValueError('Complete nonadoptable selected-pair operation required')
    bound=s['source_and_artifact_sha256']
    mismatches=[name for name,h in bound.items() if sha(Path(name))!=h]
    if mismatches:
        raise ValueError('Changed pair primary files: '+repr(mismatches))
    cfg=read(root/'04_プログラム/config/jdrt_realtime_choice_v1.json')
    workspace=root/cfg['workspace']
    strict={}
    for item in s['completed']:
        role=item['role']
        for case in item['cases']:
            child=case['child'];folder=workspace/'technical'/child
            manifest=folder/'execution/manifest.json'
            m=read(manifest)
            if m['run_id']!=child or m['purpose']!='fixture' or m['research_adoption_permitted'] is not False:
                raise ValueError('Technical child identity mismatch')
            if role=='control' and case['case']=='walk_short_repeated':
                if failure_receipt(m)!=case['raw_failure']:
                    raise ValueError('Control raw failure changed')
                continue
            if m['status']!='COMPLETED' or recompute_plans(folder/'execution/events.jsonl')!=case['primary_plans']:
                raise ValueError('Raw walker position/plan receipts differ')
            printed=read(state_path.parent/(child+'_validate.stdout.log'))
            proof_path=(root/printed['validation_report']).resolve()
            if not proof_path.is_relative_to(workspace) or str(proof_path) not in bound:
                raise ValueError('Unbound validation report')
            proof=read(proof_path)
            components={k:v['status'] for k,v in proof['components'].items()}
            if (printed!=proof or proof['run_id']!=child or proof['status']!='PASS'
                    or proof['core_adoption_permitted'] is not False or len(components)!=7
                    or any(v!='PASS' for v in components.values()) or proof['manifest_sha256']!=sha(manifest)):
                raise ValueError('Independent technical PASS does not bind raw manifest')
            strict[child]={'status':'PASS','components':components,'validation_report':printed['validation_report'],
                           'validation_report_sha256':sha(proof_path)}
    if len(strict)!=3:
        raise ValueError('Expected control calibration and two selected-role independent reports')
    inputs=[]
    for comparison in s['paired_input_comparison']:
        physical=[]
        for key in ('control_input_sha256','patched_input_sha256'):
            table=comparison[key]
            names=set(table)-{'netconvert.log','bounded.net.xml','toolchain_runtime.json'}
            physical.append({n:table[n] for n in names})
        if physical[0]!=physical[1] or comparison['same_semantic_inputs'] is not True:
            raise ValueError('Pair physical inputs differ')
        case=comparison['case'];networks=[]
        for item in s['completed']:
            child=next(c['child'] for c in item['cases'] if c['case']==case)
            path=workspace/'technical'/child/'fixture_inputs/bounded.net.xml'
            networks.append(ET.canonicalize(from_file=path,with_comments=False,strip_text=True))
        if networks[0]!=networks[1]:raise ValueError('Canonical physical networks differ')
        inputs.append({'case':case,'canonical_network_sha256':hashlib.sha256(networks[0].encode()).hexdigest(),
                       'same_nonmetadata_input_sha256':physical[0]})
    if sha(state_path)!=state_hash:raise ValueError('Original operation still changing')
    result={'at_jst':datetime.now().astimezone().isoformat(),'status':'SELECTED_PAIR_CONFIRMED_PENDING_NATIVE_GUARDS',
            'state':state_path.relative_to(root).as_posix(),'state_sha256':state_hash,
            'bound_files_checked':len(bound),'bound_mismatches':0,'strict_reports':strict,
            'paired_inputs_readback':inputs,'research_adoption_permitted':False,'technical_ready':False,
            'live_start_permission':False,'reader_sha256':sha(__file__),
            'limitation':'Saved primary/readback only; caller checks original process exit. No broad native guards/full suite/smokes/READY or study conclusion.'}
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'report':str(output),'bound_files_checked':len(bound),'strict_reports':len(strict),'technical_ready':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,required=True)
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    main(args.project_root,args.state,args.output)
