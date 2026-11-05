"""Artificial lineage/refusal contracts; no native package, compiler or core."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import choice_shared_stop_policy as target


class SharedPolicyContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.commit='a'*40
        self.old={'schema':'approved_native_pair_policy_v1','source_commit':self.commit,
                  'archive':{'path':'archive.zip'},'proposal':{'path':'walk.json'},
                  'native_patch':{'path':'walk.patch'},'shared_patch':{'path':'cmake.patch'},
                  'allowed_missing':['src/utils/tests/fixture.cpp']}
        old_ref=self.save(target.BASE_POLICY,self.old)
        patch_ref=self.put(target.DIAGNOSIS/'rebase_retained_past_stop_indices.patch',b'artificial patch\n')
        self.proposal={'schema':'isolated_native_shared_patch_proposal_v1','source_commit':self.commit,
                       'target':target.TARGET,'roles':['control','patched'],'before_sha256':'b'*64,
                       'after_sha256':'c'*64,'patch_path':str(target.DIAGNOSIS/'rebase_retained_past_stop_indices.patch'),
                       'patch_sha256':patch_ref['sha256'],'methodological_change':False,
                       'core_adoption_permitted':False,'technical_ready':False}
        self.policy={**copy.deepcopy(self.old),'schema':'approved_native_pair_stop_index_policy_v1',
                     'previous_policy':old_ref,'stop_index_proposal':self.save(target.PROPOSAL,self.proposal),
                     'stop_index_patch':patch_ref}

    def put(self,name,raw):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        return {'path':str(p),'sha256':self.sha(p),'bytes':len(raw)}

    def save(self,name,value):return self.put(name,json.dumps(value).encode())
    @staticmethod
    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    def observed(self,ref):
        p=Path(ref['path']).resolve()
        if not p.is_relative_to(self.root.resolve()) or self.sha(p)!=ref['sha256'] or p.stat().st_size!=ref['bytes']:
            raise ValueError('Artificial tracked reference changed')
        return p

    def check(self):
        return target.shared_stop_patch(self.policy,self.commit,self.root,self.observed,
                                        lambda p:json.loads(Path(p).read_bytes()),self.sha)

    def test_retains_base_policy_and_returns_only_reviewed_both_role_patch(self):
        self.assertEqual(self.check(),{target.TARGET:{**self.policy['stop_index_patch'],
                         'before_sha256':'b'*64,'after_sha256':'c'*64,'roles':['control','patched']}})

    def test_inherited_scope_cannot_be_widened(self):
        for field in ('archive','proposal','native_patch','shared_patch','allowed_missing'):
            with self.subTest(field=field):
                before=self.policy[field];self.policy[field]=[]
                with self.assertRaises(ValueError):self.check()
                self.policy[field]=before

    def test_unreviewed_previous_policy_path_rejected(self):
        self.policy['previous_policy']=self.save('different/policy.json',self.old)
        with self.assertRaises(ValueError):self.check()

    def test_proposal_target_roles_commit_and_adoption_boundaries(self):
        for field,value in (('target','src/other.cpp'),('roles',['patched']),('source_commit','d'*40),
                            ('methodological_change',True),('core_adoption_permitted',True),
                            ('technical_ready',True),('before_sha256','invalid')):
            with self.subTest(field=field):
                proposal={**self.proposal,field:value}
                self.policy['stop_index_proposal']=self.save(target.PROPOSAL,proposal)
                with self.assertRaises(ValueError):self.check()

    def test_proposal_and_patch_paths_are_bound(self):
        self.policy['stop_index_proposal']=self.save('other/proposal.json',self.proposal)
        with self.assertRaises(ValueError):self.check()
        self.policy['stop_index_proposal']=self.save(target.PROPOSAL,self.proposal)
        self.policy['stop_index_patch']=self.put('other/patch.diff',b'artificial patch\n')
        with self.assertRaises(ValueError):self.check()

    def test_patch_hash_mismatch_rejected_even_when_tracking_ref_updated(self):
        self.policy['stop_index_patch']=self.put(target.DIAGNOSIS/'rebase_retained_past_stop_indices.patch',b'other patch\n')
        with self.assertRaises(ValueError):self.check()


if __name__=='__main__':unittest.main()
