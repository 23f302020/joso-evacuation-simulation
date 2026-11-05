"""Current HOLD is not evidence of stale versions; uses isolated writer files."""
from pathlib import Path
from hashlib import sha256
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/joso-jdrt-runner/scripts'))
import choice_sync_status as sync

class FakeController:
    def __init__(self,root):
        self.workspace=root/'work';self.logs=self.workspace/'driver_logs';self.logs.mkdir(parents=True)
    def records(self):return []
    def status(self,**kwargs):
        return dict(partial_records=[],record_identity_mismatch=[],pending_record_journals=[],running=[],unrecorded=[],unresolved_failures=[],unresolved_launches=[],recorded_cells=0,registered_cells=70,next_cell={'cell_id':'next'})

class DisplayCurrentness(unittest.TestCase):
    def prepare(self,root,changed=False,ready=False):
        out=root/'06_研究結果/jdrt/goal_20261017';out.mkdir(parents=True)
        (root/'04_プログラム/config').mkdir(parents=True)
        (root/'source.py').write_bytes(b'current implementation')
        current={'source.py':sha256((root/'source.py').read_bytes()).hexdigest()}
        (root/'04_プログラム/config/jdrt_realtime_choice_v1.json').write_text(json.dumps({'execution':{'implementation_files':['source.py']}}))
        path=out/'G4実装・実SUMO_継続チェックポイント.json'
        path.write_text(json.dumps(dict(goal_status='ACTIVE',at_jst='2026-01-01T00:00:00+09:00',summary='HOLD READY=false',technical_ready=ready,current_hold=True,current_implementation_sha256={'source.py':'0'*64} if changed else current,independent_audit_status='PASS_CURRENT',smoke_sequence_status='COMPLETED_CURRENT',preflight_state='STALE historical: old READY')))
        return path
    def apply(self,root,path):
        controller=FakeController(root)
        with patch.object(sync,'display_plans',return_value={}):
            result=sync.synchronize(root=root,apply=True,controller=controller)
        self.assertFalse(result['formal_adoption_created'])
        return json.loads(path.read_bytes())
    def test_current_version_pass_is_retained_while_other_prerequisites_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=self.prepare(root);updated=self.apply(root,p)
            self.assertEqual(updated['independent_audit_status'],'PASS_CURRENT')
            self.assertEqual(updated['smoke_sequence_status'],'COMPLETED_CURRENT')
            self.assertFalse(updated['technical_ready'])
    def test_source_drift_still_marks_previous_pass_historical(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=self.prepare(root,changed=True);updated=self.apply(root,p)
            self.assertEqual(updated['independent_audit_status'],'STALE historical: PASS_CURRENT')
            self.assertEqual(updated['preflight_state'],'STALE historical: old READY')
            self.assertFalse(updated['technical_ready'])
    def test_hold_can_never_promote_or_retain_ready_even_without_source_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=self.prepare(root,ready=True);updated=self.apply(root,p)
            self.assertFalse(updated['technical_ready'])
            self.assertIn('HOLD',updated['summary'])

if __name__=='__main__':unittest.main()
