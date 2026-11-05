"""Exercise main's evidence gate without copying sources, building or starting SUMO."""
from pathlib import Path
from hashlib import sha256
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_trace_build as build

class ReachedBoundSource(Exception):
    pass

class PreparedSourceGate(unittest.TestCase):
    def invoke(self, mutate=None, legacy=False, repair=False):
        with tempfile.TemporaryDirectory() as temp:
            top=Path(temp);basepath=top/'base'/'build_state.json';basepath.parent.mkdir()
            base={'status':'COMPILED_VERSION_CHECKED_NOT_SIMULATED',
                  'simulation_allowed':False,'research_cli_switch_allowed':False}
            basepath.write_text(json.dumps(base),encoding='utf-8')
            prep={'status':'PREPARED_NOT_BUILT' if legacy else 'TERMINAL_SHARED_REPAIR_SOURCE_SNAPSHOT_NOT_READY',
                  'compiler_started':False,'simulation_executed':False,'core_ready':False,
                  'terminal_builds':{'patched':{'state':{'path':str(basepath),'sha256':sha256(basepath.read_bytes()).hexdigest(),
                                                       'bytes':basepath.stat().st_size}}}}
            if mutate:mutate(prep)
            prepared=top/'prepared.json';prepared.write_text(json.dumps(prep),encoding='utf-8')
            bound={str(p):sha256(p.read_bytes()).hexdigest() for p in (basepath,prepared)}
            pair={'status':'SELECTED_PAIR_VERIFIED_PENDING_NATIVE_GUARDS',
                  'research_adoption_permitted':False,'technical_ready':False,'active':None,
                  'source_and_artifact_sha256':bound}
            pairpath=top/'pair.json';pairpath.write_text(json.dumps(pair),encoding='utf-8')
            proof=top/'proof.json';proof.write_text(json.dumps({'bound_mismatches':[],
                'state_sha256':sha256(pairpath.read_bytes()).hexdigest(),'bound_files_checked':len(bound)}),encoding='utf-8')
            args=['choice_native_trace_build.py','--attempt-id','repair99_20000101' if repair else 'diag99_20000101',
                  '--base-state',str(basepath),'--source-preparation',str(prepared),
                  '--pair-state',str(pairpath),'--pair-proof',str(proof)]
            if repair:args.append('--stop-index-repair')
            support=SimpleNamespace()
            with patch.object(sys,'argv',args),patch.dict(sys.modules,{'native_build_support':support}), \
                 patch.object(build,'select_base_source',side_effect=ReachedBoundSource):
                build.main()

    def test_legacy_preparation_reaches_bound_source_before_any_build(self):
        with self.assertRaises(ReachedBoundSource):self.invoke(legacy=True)

    def test_bound_terminal_shared_snapshot_reaches_observation_source(self):
        with self.assertRaises(ReachedBoundSource):self.invoke()

    def test_terminal_snapshot_is_not_permission_to_apply_shared_repair_again(self):
        with self.assertRaises(ValueError):self.invoke(repair=True)

    def test_unrecognized_preparation_status_is_refused(self):
        with self.assertRaises(ValueError):self.invoke(lambda p:p.update(status='READY'))

    def test_terminal_permissions_must_remain_false(self):
        for key in ('compiler_started','simulation_executed','core_ready'):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.invoke(lambda p:p.update({key:True}))

    def test_terminal_base_reference_hash_path_size_are_bound(self):
        for key,value in (('sha256','0'*64),('path','different-build.json'),('bytes',-1)):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.invoke(lambda p:p['terminal_builds']['patched']['state'].update({key:value}))

    def test_missing_terminal_base_reference_is_refused(self):
        with self.assertRaises(ValueError):self.invoke(lambda p:p.pop('terminal_builds'))

if __name__=='__main__':unittest.main()
