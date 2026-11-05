"""Validate the explicit shared stop-history policy extension, never adopt it."""
from pathlib import Path
import re

BASE_POLICY = Path('06_研究結果/jdrt/goal_20261017/audit_history/native_pair_policy_20261020/policy.json')
DIAGNOSIS = Path('06_研究結果/jdrt/goal_20261017/route_replacement_failure_20261028/smoke13_native_crash_20261029')
POLICY = DIAGNOSIS / 'native_stop_index_pair_policy/policy.json'
PROPOSAL = DIAGNOSIS / 'native_stop_index_shared_proposal.json'
TARGET = 'src/microsim/MSBaseVehicle.cpp'


def shared_stop_patch(policy, source_commit, project_root, observed, read_json, sha):
    root=Path(project_root).resolve()
    if (policy.get('schema')!='approved_native_pair_stop_index_policy_v1'
            or policy.get('source_commit')!=source_commit):
        raise ValueError('Explicit shared stop-history policy schema/commit required')
    previous=observed(policy['previous_policy'])
    if previous!=(root/BASE_POLICY).resolve():
        raise ValueError('Previous policy must be the preserved reviewed policy')
    base=read_json(previous)
    if base.get('schema')!='approved_native_pair_policy_v1' or base.get('source_commit')!=source_commit:
        raise ValueError('Previous policy commit/schema differs')
    for key in ('archive','proposal','native_patch','shared_patch','allowed_missing'):
        if key not in base or policy.get(key)!=base[key]:
            raise ValueError('Inherited native scope changed: '+key)
    proposal_path=observed(policy['stop_index_proposal'])
    if proposal_path!=(root/PROPOSAL).resolve():
        raise ValueError('Explicit reviewed shared stop-history proposal required')
    proposal=read_json(proposal_path)
    if (proposal.get('schema')!='isolated_native_shared_patch_proposal_v1'
            or proposal.get('source_commit')!=source_commit or proposal.get('target')!=TARGET
            or proposal.get('roles')!=['control','patched']
            or any(proposal.get(key) is not False for key in
                   ('methodological_change','core_adoption_permitted','technical_ready'))
            or any(not isinstance(proposal.get(key),str) or not re.fullmatch('[0-9a-f]{64}',proposal[key])
                   for key in ('before_sha256','after_sha256','patch_sha256'))
            or proposal['before_sha256']==proposal['after_sha256']):
        raise ValueError('Shared stop-history target/roles/hash/adoption scope differs')
    patch=observed(policy['stop_index_patch'])
    expected_patch=(root/DIAGNOSIS/'rebase_retained_past_stop_indices.patch').resolve()
    if (patch!=expected_patch or (root/proposal['patch_path']).resolve()!=patch
            or sha(patch)!=proposal['patch_sha256']):
        raise ValueError('Shared stop-history patch path/hash differs')
    return {TARGET:{**policy['stop_index_patch'],'path':str(patch),
                    'before_sha256':proposal['before_sha256'],'after_sha256':proposal['after_sha256'],
                    'roles':['control','patched']}}
