"""Copy immutable physical B artifacts and bind the approved boundary contract."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import shutil
from scripts.jdrt_realtime_b_inputs import ROOT,EVIDENCE,SOURCE,REF,read_csv,write_csv,sha

PARAM=ROOT/'04_プログラム/config/jdrt_realtime_b_boundary_v2.json'


def prepare():
    p=json.loads(PARAM.read_text(encoding='utf-8'))
    prior=json.loads((ROOT/p['parent_parameter_registry']).read_text(encoding='utf-8'))
    for key in ['municipality_code','scenarios','seeds','simulation','hazard','population','operation','evaluation','dispatch_weights']:
        if p[key]!=prior[key]:raise ValueError('Physical/reference parameter changed: '+key)
    parent=ROOT/p['parent_input_manifest']
    old=json.loads(parent.read_text(encoding='utf-8'))
    for name,expected in old['source_sha256'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Parent source SHA mismatch: '+name)
    out=ROOT/p['workspace']/p['input_directory']
    out.mkdir(parents=True,exist_ok=False)
    copied={}
    for name,expected in old['artifacts'].items():
        source=parent.parent/name
        if sha(source)!=expected:raise ValueError('Parent artifact SHA mismatch: '+name)
        shutil.copy2(source,out/name)
        copied[name]=sha(out/name)
        if copied[name]!=expected:raise ValueError('Copy SHA mismatch: '+name)
    sources=dict(old['source_sha256'])
    for path in [PARAM,Path(__file__),ROOT/p['pap'],parent]:
        sources[path.relative_to(ROOT).as_posix()]=sha(path)
    manifest={**old,'protocol':p['protocol'],
              'created_at_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'status':'COPIED_PENDING_INDEPENDENT_VALIDATION','source_sha256':sources,'artifacts':copied,
              'execution_contract':p['execution'],
              'lineage':{'parent_manifest':p['parent_input_manifest'],'parent_manifest_sha256':sha(parent),
                         'parent_protocol':old['protocol'],'physical_artifacts_byte_identical':copied==old['artifacts']}}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
