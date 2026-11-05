"""New-policy integration contracts using artificial full-pair primary files."""
import copy
import difflib
import json
from pathlib import Path
import shutil
import unittest
import zipfile
from unittest.mock import patch
import test_choice_pair_proof as pair_contracts
import choice_shared_stop_policy as shared
import choice_native_pair_primary as primary


class SharedNativePairContracts(unittest.TestCase):
    def setUp(self):
        self.case=pair_contracts.PairContracts(methodName='runTest');self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        c=self.case;self.packaging_args=c.packaging_inputs() if self._testMethodName.startswith('test_package') else None
        before=b'past stop old\n';after=b'past stop remapped\n'
        with zipfile.ZipFile(c.archive,'a') as archive:
            archive.writestr('sumo-'+c.commit+'/'+shared.TARGET,before)
        for role in c.states:
            old_source=Path(c.prepared[role+'_source_root'])
            c.prepared['source_sha256'][role][shared.TARGET]=c.put(old_source/shared.TARGET,before)['sha256']
        c.save(c.snapshot_path,c.prepared)
        c.policy.update(archive=c.item(c.archive),preparation=c.item(c.snapshot_path))
        c.save(c.policy_path,c.policy);previous=c.item(c.policy_path)
        prepared=copy.deepcopy(c.prepared)
        for role in c.states:
            old_source=Path(prepared[role+'_source_root']);new_source=c.root/(role+'_repaired/source')
            shutil.copytree(old_source,new_source)
            prepared[role+'_source_root']=str(new_source)
            prepared['source_sha256'][role][shared.TARGET]=c.put(new_source/shared.TARGET,after)['sha256']
            command=c.states[role]['commands'][0]['command'];command[command.index('-S')+1]=str(new_source)
            item=c.pair['builds'][role]['metadata']['CMakeCache.txt'];p=Path(item['path'])
            text=p.read_text().replace(old_source.as_posix(),new_source.as_posix())
            c.pair['builds'][role]['metadata']['CMakeCache.txt']=c.put(p,text.encode())
            state=c.states[role]
            configure,build,*versions=state['commands']
            state['commands']=[{**configure,'phase':'diagnostic_configure'},
                               {**build,'phase':'diagnostic_sumo_build'}]
            for name,binary,version in zip(('sumo','netconvert'),state['binaries'],versions):
                raw=c.put(Path(binary['path']).parent.parent/(name+'_imports.log'),b'DLL Name: kernel32.dll\n 123 1 ArtificialSymbol\n')
                state['commands'].extend([{'phase':name+'_diagnostic_imports',
                    'command':['artificial-objdump','-p',binary['path']],'exit_code':0,
                    'log':raw['path'],'log_sha256':raw['sha256'],'log_bytes':raw['bytes']},
                    {**version,'phase':name+'_diagnostic_version'}])
                for key in ('clean_path_version_exit_code','version_log','version_log_sha256'):binary.pop(key)
            state.update(child_pid=None,simulation_allowed=False,research_cli_switch_allowed=False,
                         technical_ready=False,research_adoption_permitted=False,base_role=role,
                         role='ISOLATED_STOP_INDEX_REPAIR_CANDIDATE_NOT_ADOPTED')
            state.pop('zlib_dependency',None)
            c.update_state(role)
        preparation=c.root/shared.POLICY.parent/'preparation.json';c.save(preparation,prepared)
        diff=''.join(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),
                                        fromfile='a/'+shared.TARGET,tofile='b/'+shared.TARGET)).encode()
        patch_ref=c.put(c.root/shared.DIAGNOSIS/'rebase_retained_past_stop_indices.patch',diff)
        proposal={'schema':'isolated_native_shared_patch_proposal_v1','source_commit':c.commit,
                  'target':shared.TARGET,'roles':['control','patched'],'before_sha256':c.digest(before),
                  'after_sha256':c.digest(after),'patch_path':patch_ref['path'],'patch_sha256':patch_ref['sha256'],
                  'methodological_change':False,'core_adoption_permitted':False,'technical_ready':False}
        proposal_path=c.root/shared.PROPOSAL;c.save(proposal_path,proposal)
        self.policy={**copy.deepcopy(c.policy),'schema':'approved_native_pair_stop_index_policy_v1',
                     'previous_policy':previous,'preparation':c.item(preparation),
                     'stop_index_proposal':c.item(proposal_path),'stop_index_patch':patch_ref,
                     'scope':'Artificial shared repair provenance contract, never native behavior or adoption.'}
        self.policy_path=c.root/shared.POLICY;c.save(self.policy_path,self.policy)
        c.pair['policy']=c.item(self.policy_path)
        self.prepared=prepared;self.preparation=preparation

    def test_complete_new_pair_keeps_existing_metadata_source_loader_gates(self):
        for role in ('control','patched'):
            self.case.selected=role
            result=self.case.verify()
            self.assertFalse(result['native_behavior_verified'])
            self.assertFalse(result['core_ready'])
            self.assertEqual(result['metadata_pairs'],10)

    def test_control_missing_shared_fix_rejected_even_after_inventory_refresh(self):
        c=self.case;p=Path(self.prepared['control_source_root'])/shared.TARGET
        self.prepared['source_sha256']['control'][shared.TARGET]=c.put(p,b'past stop old\n')['sha256']
        c.save(self.preparation,self.prepared);self.policy['preparation']=c.item(self.preparation)
        c.save(self.policy_path,self.policy);c.pair['policy']=c.item(self.policy_path)
        with self.assertRaises(ValueError):c.verify()

    def test_new_policy_does_not_bypass_metadata_difference(self):
        c=self.case;item=c.pair['builds']['control']['metadata']['src/CMakeFiles/sumo.dir/flags.make']
        p=Path(item['path']);c.pair['builds']['control']['metadata']['src/CMakeFiles/sumo.dir/flags.make']=c.put(p,b'changed flags\n')
        with self.assertRaises(ValueError):c.verify()

    def test_version_requires_exact_primary_command_and_phase(self):
        c=self.case;original=copy.deepcopy(c.states['control'])
        for kind in ('other_executable','wrong_phase','missing_command'):
            c.states['control']=copy.deepcopy(original)
            if kind=='other_executable':c.states['control']['commands'][-1]['command'][0]='foreign.exe'
            elif kind=='wrong_phase':c.states['control']['commands'][-1]['phase']='unrelated_version'
            else:c.states['control']['commands'].pop()
            c.update_state('control')
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.verify()

    def capture(self):
        c=self.case;inventory=c.root/'inventory.json'
        if self.packaging_args is None:c.save(inventory,{})
        output=c.root/'06_研究結果/jdrt/goal_20261017/new_pair_capture'
        with patch.object(primary,'pe_imports',return_value=['kernel32.dll']):
            primary.capture(c.root,self.policy_path,
                            {r:Path(c.pair['builds'][r]['state']['path']) for r in c.states},
                            {r:Path(c.pair['builds'][r]['loader']['path']) for r in c.states},inventory,output)
        return output

    def test_capture_generates_primary_files_and_uses_full_verifier(self):
        output=self.capture();result=json.loads((output/'verification.json').read_bytes())
        self.assertEqual(result['status'],'PRIMARY_PAIR_VERIFIED_NOT_READY')
        self.assertFalse(result['bundle_created'])
        self.assertFalse(result['core_ready'])
        self.assertTrue((output/'control_provenance.json').is_file())
        self.assertTrue((output/'patched_provenance.json').is_file())

    def test_capture_preserves_failed_command_evidence_without_verification(self):
        c=self.case;c.states['control']['commands'][-1]['exit_code']=1;c.update_state('control')
        with self.assertRaises(ValueError):self.capture()
        output=c.root/'06_研究結果/jdrt/goal_20261017/new_pair_capture'
        self.assertTrue((output/'FAILED_PRESERVED.json').is_file())
        self.assertFalse((output/'verification.json').exists())

    def test_package_uses_verified_raw_versions_and_paired_dependencies(self):
        output=self.capture();args=list(self.packaging_args);args[3]=output/'patched_provenance.json'
        manifest=pair_contracts.io.package(*args)
        self.assertTrue(manifest.is_file())
        self.assertFalse(json.loads((output/'patched_provenance.json').read_bytes())['simulation_executed'])

    def test_package_still_requires_official_zip_reference(self):
        output=self.capture();args=list(self.packaging_args);proof=output/'patched_provenance.json'
        value=json.loads(proof.read_bytes());value['files']=[ref for ref in value['files'] if not ref['path'].endswith('.zip')]
        self.case.save(proof,value);args[3]=proof
        with self.assertRaises(ValueError):pair_contracts.io.package(*args)
        self.assertFalse(args[5].exists())


if __name__=='__main__':unittest.main()
