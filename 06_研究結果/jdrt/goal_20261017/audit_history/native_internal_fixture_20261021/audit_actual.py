"""Independent raw native guard readback, not a READY/adoption writer."""
from pathlib import Path
from datetime import datetime
import collections,hashlib,json,re,sys
root=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(root/'.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_trace_check as trace
import choice_native_guard_audit as audit
base=root/'04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1/technical/ng261021g'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_bytes())
m=read(base/'manifest.json');plan=read(base/'plan.json')
assert m['status']=='COMPLETED' and len(m['completed'])==3*len(plan['cases'])==45
assert sha(base/'plan.json')==m['plan_sha256'] and sha(base/'trace_build.json')==m['trace_build_sha256']
assert sha(base/'collection_source.py')==m['collection_source_sha256']
for path,expected in plan['sources'].items():assert sha(path)==expected,path
for path,expected in m['current_implementation_sha256'].items():assert sha(root/path)==expected,path
cfg=read(root/'04_プログラム/config/jdrt_realtime_choice_v1.json')
speeds={'p3':cfg['population']['walk_mps']['type3'],'p4':cfg['population']['walk_mps']['type4']}
native_root=Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
source=native_root/'sources/control126_20261020/src/utils/common/SUMOTime.h'
unit=re.search(rb'#define STEPS2TIME\(x\) \(static_cast<double>\(x\)/(\d+\.)\)',source.read_bytes())
assert unit,'Pinned native clock conversion not found'
units=float(unit[1])
roles={'control':root/'04_プログラム/output/sumo/toolchains/native_ctl_20261020a/toolchain.json','patched':root/'04_プログラム/output/sumo/toolchains/native_lat_20261020a/toolchain.json'}
expected_binaries={r:p.parent/'bin/sumo.exe' for r,p in roles.items()}
expected_binaries['trace']=Path(read(base/'trace_build.json')['binaries'][0]['path'])
binary_hashes={r:sha(p) for r,p in expected_binaries.items()}
for role,manifest in roles.items():assert binary_hashes[role]==read(manifest)['files']['bin/sumo.exe']
net_names=[Path(p) for p in plan['sources'] if Path(p).name=='bounded.net.xml'];assert len(net_names)==1
assert sha(base/'bounded.net.xml')==sha(net_names[0])
report={'at_jst':datetime.now().astimezone().isoformat(),'run_id':m['run_id'],'manifest_sha256':sha(base/'manifest.json'),'native_units_per_second':units,'native_time_source':{'path':str(source),'sha256':sha(source)},'cases':[],'primary_artifacts_rehashed':0,'research_adoption_permitted':False,'technical_ready':False,'native_regression_complete':False,'audit_source_sha256':sha(__file__),'audit_helpers_sha256':{p:sha(root/p) for p in ['.agents/skills/joso-jdrt-runner/scripts/choice_native_guard_audit.py','.agents/skills/joso-jdrt-runner/scripts/choice_native_trace_check.py']},'limitations':['Native pointer equality/null booleans are observations, not independent debugger memory-address reads','Observation window is finite; no complete evacuation or method-effect claim','Speed is native longitudinal getter, not Euclidean XY speed']}
for spec in plan['cases']:
 case=spec['id'];data={};derived=None;rawtrace=None
 assert (base/case/'routes.xml').read_bytes()==spec['routes_xml'].encode('utf-8')
 for role in ('control','patched','trace'):
  entries=[e for e in m['completed'] if e['case']==case and e['role']==role];assert len(entries)==1
  e=entries[0];folder=Path(e['output']);assert folder==base/case/role
  assert e['exit_code']==0 and Path(e['binary'])==expected_binaries[role] and e['binary_sha256']==binary_hashes[role]
  assert set(e['server_endpoint_owners'])=={e['pid']} and e['process_identity']['ProcessId']==e['pid'] and e['process_identity']['ParentProcessId']==m['pid']
  assert e['api_version'][0]==22
  command=e['command']
  for option,expected in [('--net-file',str(base/'bounded.net.xml')),('--route-files',str(base/case/'routes.xml')),('--step-length',str(spec['step_sec'])),('--seed',str(cfg['seeds'][0])),('--pedestrian.model','striping')]:
   assert command.count(option)==1 and command[command.index(option)+1]==expected,(case,role,option)
  for option,expected in zip(spec['sumo_options'][::2],spec['sumo_options'][1::2]):assert command[command.index(option)+1]==expected
  for name,expected in e['artifacts'].items():assert sha(folder/name)==expected,(case,role,name)
  assert set(e['artifacts'])=={p.name for p in folder.iterdir() if p.is_file()}
  report['primary_artifacts_rehashed']+=len(e['artifacts'])
  rows=[json.loads(s) for s in (folder/'actors.jsonl').read_text().splitlines()]
  ops=[json.loads(s) for s in (folder/'operations.jsonl').read_text().splitlines()]
  account=audit.actor_accounting(rows,speeds,spec['step_sec'])
  audit.position_receipts(ops,exact_target=role!='control' and spec['operation']!='internal_replace')
  frames={row['time_sec']:row['actors'] for row in rows};current={}
  for op in ops:
   assert op['time_sec'] in frames
   expected=current.get(op['time_sec'],frames[op['time_sec']]);assert op['before']==expected,(case,role,'operation/frame linkage')
   current[op['time_sec']]=op['after']
  stderr=(folder/'native.stderr.log').read_text();warnings=stderr.splitlines()
  if case=='internal_walk':
   assert len(warnings)==len(ops)>0
   for line in warnings:
    assert re.fullmatch(r"Warning: Invalid departPos [-0-9.]+ given for person '[^']+' walking from edge ':[^']+'. Using edge end instead\.",line),line
  else:assert not stderr,(case,role,stderr)
  if role=='trace':
   rawtrace=trace.parse((folder/'native.stdout.log').read_bytes())
   derived=[trace.derive(row,**plan['constants']) for row in rawtrace]
   linked=audit.link_operations(ops,rawtrace,units)
  normalized=[{k:v for k,v in op.items() if k not in ('trace_count_before','trace_count_after')} for op in ops]
  data[role]={'rows':rows,'ops':ops,'normalized_ops':normalized,'accounting':account,'warnings':warnings}
 assert data['patched']['rows']==data['trace']['rows'],(case,'trace changed physical trajectory')
 assert data['patched']['normalized_ops']==data['trace']['normalized_ops'],(case,'trace changed replacement receipts')
 result={'id':case,'group':spec['group'],'branches':dict(collections.Counter(x['branch'] for x in derived)),'raw_trace_rows':rawtrace,'derived_trace':derived,'patched_trace_all_actor_rows_equal':True,'patched_trace_all_receipts_equal':True,'accounting':{r:d['accounting'] for r,d in data.items()},'warnings':{r:d['warnings'] for r,d in data.items()}}
 if spec['operation']=='observe' or case=='internal_walk':
  assert data['control']['rows']==data['patched']['rows'],(case,'negative case physical baseline differs')
  assert data['control']['normalized_ops']==data['patched']['normalized_ops']
  assert not any(x['inherited'] for x in derived)
  expected='explicit' if case=='explicit_lateral' else 'random' if case=='random_lateral' else 'legacy' if case=='legacy' else 'default'
  assert {x['branch'] for x in derived}=={expected}
  result['control_patched_all_actor_rows_equal']=True
  result['observed_group_contract']=True
 elif case=='position_mismatch':
  actual_false=[row for row in rawtrace if row.get('position_same')=='0' or row.get('time_same')=='0']
  assert not actual_false,'A new mismatch path needs separate inspection'
  result['observed_group_contract']=False
  result['classification']='UNEXERCISED_FALSE_POSITION_OR_TIME_GUARD; API-requested departPos does not become constructor position'
 else:
  indices=audit.link_operations(data['trace']['ops'],rawtrace,units)
  assert indices and all(derived[i]['inherited'] for i in indices)
  directions=audit.next_directions(data['patched']['ops'],data['patched']['rows'])
  for op,i in zip(data['trace']['ops'],indices):
   if op['purpose']=='new_route':assert derived[i]['new_route_direction']==directions[op['person']]
  result['next_nonzero_directions']=directions
  result['observed_group_contract']=True
 report['cases'].append(result)
groups={c['group'] for c in report['cases']};observed={c['group'] for c in report['cases'] if c['observed_group_contract']}
assert len(groups)==13 and len(observed)==12
report.update(status='OBSERVED_CONTRACTS_PASS_WITH_ONE_UNEXERCISED_GROUP',native_runs=45,groups_requested=sorted(groups),groups_observed=sorted(observed),groups_unexercised=sorted(groups-observed))
report['warning_classification']='Internal technical replacement: convertTraCIStage constructs with p->getArrivalPos (old final position), then MSStageWalking constructor warns before proceed restores actual previous current-edge position. Same in all3 binaries; finite window/accounting/trace checked. No core warning whitelist changed.'
for name in ['libsumo/Person.cpp','microsim/transportables/MSStageWalking.cpp']:
 p=native_root/'sources/control126_20261020/src'/name
 report.setdefault('native_api_source_sha256',{})[str(p)]=sha(p)
out=Path(__file__).with_name('actual_native_audit_v2.json')
with out.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps({'status':report['status'],'artifact_hashes':report['primary_artifacts_rehashed'],'groups_observed':len(observed),'groups_unexercised':report['groups_unexercised'],'report':str(out)},ensure_ascii=False))
