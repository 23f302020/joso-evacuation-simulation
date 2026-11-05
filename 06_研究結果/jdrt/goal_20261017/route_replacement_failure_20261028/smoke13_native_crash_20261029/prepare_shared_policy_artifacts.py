"""One-time reviewed shared-repair policy data, never packaging or simulation."""
import copy
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT=Path.cwd().resolve()
sys.path.insert(0,str(ROOT/'.agents/skills/joso-jdrt-runner/scripts'))
from choice_package_toolchain import checked,read_json,sha
from choice_pair_sources import source_tree
from choice_shared_stop_policy import BASE_POLICY,DIAGNOSIS,POLICY,PROPOSAL,TARGET,shared_stop_patch
from choice_native_pair_primary import item,save

D=ROOT/DIAGNOSIS
ST=Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')


def main():
    if (ROOT/POLICY).parent.exists():raise ValueError('Preserve existing policy directory')
    old_path=ROOT/BASE_POLICY;old=read_json(old_path)
    previous=read_json(checked(old['preparation']))
    proposal=read_json(ROOT/PROPOSAL)
    prepared=copy.deepcopy(previous);roles={}
    for role,attempt,loader_folder in (('control','repair02_20261029','repair02_loader2'),
                                       ('patched','repair03_20261029','repair03_loader')):
        path=ST/attempt/'build_state.json';raw=path.read_bytes();s=read_json(path)
        if (s['status']!='COMPILED_VERSION_CHECKED_NOT_SIMULATED' or s['base_role']!=role
                or s['child_pid'] is not None or any(s[k] is not False for k in
                   ('simulation_allowed','research_cli_switch_allowed','technical_ready','research_adoption_permitted'))):
            raise ValueError('Terminal nonadoptable repaired role required')
        for c in s['commands']:
            checked({'path':c['log'],'sha256':c['log_sha256'],'bytes':c['log_bytes']})
            if type(c['exit_code']) is not int or c['exit_code']!=0:raise ValueError('Failed build command')
        if len(s['commands'])!=6:raise ValueError('Six native build/import/version commands required')
        for name,digest in s['snapshot_sha256'].items():checked({'path':path.parent/name,'sha256':digest})
        checked(s['custom_version_header'])
        receipt=read_json(checked(s['source_receipt']))
        source=Path(s['diagnostic_source']);actual=source_tree(source)
        expected={**previous['source_sha256'][role],TARGET:proposal['after_sha256']}
        if (previous['source_sha256'][role][TARGET]!=proposal['before_sha256'] or actual!=expected
                or actual!=receipt['diagnostic_files']):
            raise ValueError('Unexpected repaired source file set/bytes')
        loader_path=D/loader_folder/'diagnosis.json';loader=read_json(loader_path)
        if (loader['status']!='SYSTEM_ONLY_LOADER_VERIFIED_NOT_READY' or loader['state_sha256']!=sha(path)
                or (loader_path.parent/'build_state.snapshot.bin').read_bytes()!=raw):
            raise ValueError('Loader differs from actual terminal role')
        for name,digest in loader['files_sha256'].items():checked({'path':loader_path.parent/name,'sha256':digest})
        for binary in s['binaries']:checked(binary)
        if path.read_bytes()!=raw:raise ValueError('Original role state changed')
        prepared[role+'_source_root']=str(source.resolve())
        prepared['source_sha256'][role]=actual
        roles[role]={'state':item(path),'source_files':len(actual),'source_receipt':s['source_receipt'],
                     'loader':item(loader_path),'binaries':s['binaries'],'commands_verified':6}
    prepared.update(status='TERMINAL_SHARED_REPAIR_SOURCE_SNAPSHOT_NOT_READY',
                    original_preparation=old['preparation'],shared_stop_index_proposal=item(ROOT/PROPOSAL),
                    terminal_builds=roles)
    out=(ROOT/POLICY).parent;out.mkdir(parents=True,exist_ok=False)
    try:
        preparation=out/'preparation.json';save(preparation,prepared)
        policy={**old,'schema':'approved_native_pair_stop_index_policy_v1','previous_policy':item(old_path),
                'preparation':item(preparation),'stop_index_proposal':item(ROOT/PROPOSAL),
                'stop_index_patch':item(ROOT/proposal['patch_path']),
                'scope':'Same scientific conditions and original source commit; unchanged compiler/static settings; original walk-lateral patch selected-only, original Winsock CMake repair both roles, reviewed stop-history index remap both roles. Seven original non-GUI omissions retained. No native behavior, package, selector, research adoption or READY claim.'}
        shared_stop_patch(policy,prepared['source_commit'],ROOT,checked,read_json,sha)
        save(ROOT/POLICY,policy)
        save(out/'terminal_roles_readback.json',{'at_jst':datetime.now().astimezone().isoformat(),
             'status':'BOTH_TERMINAL_ROLE_SOURCES_LOGS_LOADER_BYTES_READ_BACK_PENDING_FULL_PAIR',
             'roles':roles,'parent_original_sessions':{'control':{'session':49235,'exit_code':0},
                                                      'patched':{'session':97479,'exit_code':0}},
             'old_policy_sha256':sha(old_path),'policy':item(ROOT/POLICY),
             'limitations':['Full independent archive/patch/source/metadata/compiler/header/loader pair verifier pending',
                            'No package, simulation, selector switch, READY or research adoption'],
             'technical_ready':False,'research_adoption_permitted':False})
        print(json.dumps({'policy':str(ROOT/POLICY),'source_files_per_role':{r:v['source_files'] for r,v in roles.items()},'technical_ready':False}))
    except BaseException as error:
        save(out/'FAILED_PRESERVED.json',{'error':repr(error),'technical_ready':False})
        raise


if __name__=='__main__':main()
