"""Capture explicit terminal native roles and strictly verify their primary pair.

Extracted from the preserved native_pair_primary_20261020.py recipe. Never
creates a policy, builds, simulates, packages or switches the research selector.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from choice_package_toolchain import checked, read_json, sha, pe_imports
from choice_pair_metadata import FILES, cache_entries
from choice_pair_sources import source_tree
from choice_pair_proof import TOOLS, verify_pair


def item(path):
    path=Path(path).resolve(strict=True)
    return {'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size}


def save(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def capture(root,policy_path,states_by_role,loaders,inventory,output):
    root,output=root.resolve(),output.resolve()
    if output.exists() or not output.is_relative_to(root/'06_研究結果/jdrt/goal_20261017'):
        raise ValueError('Unused goal-local output required')
    if set(states_by_role)!={'control','patched'} or set(loaders)!=set(states_by_role):
        raise ValueError('Two explicit native roles and loaders required')
    policy=read_json(policy_path);states={role:read_json(path) for role,path in states_by_role.items()}
    if any(state.get('status')!='COMPILED_VERSION_CHECKED_NOT_SIMULATED'
           or state.get('child_pid') is not None
           or state.get('simulation_allowed') is not False
           or state.get('research_cli_switch_allowed') is not False for state in states.values()):
        raise ValueError('Both roles must be terminal/nonadoptable; caller confirms original exit')
    helper_names=('choice_native_pair_primary','choice_package_toolchain','choice_pair_proof',
                  'choice_pair_sources','choice_pair_metadata','choice_shared_stop_policy')
    helpers={str(Path(sys.modules[name].__file__).resolve()):sha(Path(sys.modules[name].__file__))
             for name in helper_names if name in sys.modules}
    helpers[str(Path(__file__).resolve())]=sha(Path(__file__))
    output.mkdir(parents=True,exist_ok=False)
    try:
        pair={'schema':'isolated_native_pair_v1','source_commit':policy['source_commit'],
              'policy':item(policy_path),'builds':{}}
        for role,state in states.items():
            commands=[c['command'] for c in state['commands'] if '-S' in c['command'] and '-B' in c['command']]
            if len(commands)!=1:raise ValueError('Unique configured build required')
            build=Path(commands[0][commands[0].index('-B')+1]);cache=cache_entries((build/'CMakeCache.txt').read_text())
            headers={}
            for label,key in (('xerces','XercesC_INCLUDE_DIR'),('zlib','ZLIB_INCLUDE_DIR')):
                include=Path(cache[key][1])
                for name in source_tree(include):headers[label+'/'+name]=item(include/name)
            pair['builds'][role]={'state':item(states_by_role[role]),'metadata':{name:item(build/name) for name in FILES},
                'tools':{name:item(cache[key][1]) for name,key in TOOLS.items()},'headers':headers,
                'version_header':item(build/'src/version.h'),'target_directories':item(build/'CMakeFiles/TargetDirectories.txt'),
                'loader':item(loaders[role])}
        pair_path=output/'pair.json';save(pair_path,pair);proofs={}
        for role,state in states.items():
            entry=pair['builds'][role]
            evidence=[item(policy_path),item(pair_path),item(inventory),policy['archive'],
                      policy['preparation'],policy['proposal'],policy['native_patch'],policy['shared_patch'],
                      *entry['metadata'].values(),
                      *entry['tools'].values(),entry['state'],entry['version_header'],entry['target_directories']]
            proofs[role]={'schema':'isolated_native_provenance_v1','role':role,'source_commit':policy['source_commit'],
                'custom_version':state['custom_version'],'state':state,'files':evidence,
                'binaries':[{**b,'pe_imports':pe_imports(Path(b['path']))} for b in state['binaries']],
                'pair_evidence':item(pair_path),'simulation_executed':False,'research_cli_switched':False,
                'source_scope':policy['scope']}
            save(output/(role+'_provenance.json'),proofs[role])
        validated={}
        def track(ref):
            path=checked(ref)
            if path in validated and validated[path]!=ref['sha256']:raise ValueError('Conflicting primary SHA')
            validated[path]=ref['sha256'];return path
        result=verify_pair(proofs['patched'],root,track,read_json,sha,pe_imports)
        if any(sha(path)!=value for path,value in validated.items()) or any(sha(Path(path))!=value for path,value in helpers.items()):
            raise ValueError('Primary files or verifier changed during capture')
        result={k:([str(p) for p in v] if k=='evidence_files' else str(v) if isinstance(v,Path) else v)
                for k,v in result.items()}
        result.update(at_jst=datetime.now().astimezone().isoformat(),status='PRIMARY_PAIR_VERIFIED_NOT_READY',
                      verified_primary_files=len(validated),helper_sources_sha256=helpers,
                      simulation_executed=False,bundle_created=False,research_adoption_permitted=False)
        save(output/'verification.json',result)
        print(json.dumps({k:result[k] for k in ('status','verified_primary_files','source_files_per_role','metadata_pairs','core_ready')}))
    except BaseException as error:
        save(output/'FAILED_PRESERVED.json',{'error':repr(error),'bundle_created':False,'core_ready':False})
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('project-root','policy','control-state','patched-state','control-loader','patched-loader','tools-inventory','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    capture(a.project_root,a.policy,{'control':a.control_state,'patched':a.patched_state},
            {'control':a.control_loader,'patched':a.patched_loader},a.tools_inventory,a.output)
