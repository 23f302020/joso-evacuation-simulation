"""Native build monitoring invariants, using temporary state/log evidence only."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import choice_native_build_monitor as monitor


class NativeBuildMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_path = self.root / 'build_state.json'
        self.log = self.root / 'compile.log'
        self.log.write_text('building\n', encoding='utf-8')
        self.owner = {'ProcessId': 10, 'ParentProcessId': 2, 'CreationDate': '/Date(1792450959791)/',
                      'ExecutablePath': 'python.exe', 'CommandLine': 'python build.py'}
        self.child = {'ProcessId': 11, 'ParentProcessId': 10, 'CreationDate': '/Date(1792450982202)/',
                      'ExecutablePath': 'cmake.exe', 'CommandLine': 'cmake --build isolated'}
        self.state = {'schema': 'isolated_native_build_v1', 'attempt_id': 'a03', 'status': 'RUNNING',
                      'phase': 'compile', 'owner_pid': 10, 'owner_process_identity': self.owner,
                      'child_pid': 11, 'staging': str(self.root), 'started_at_jst': '2026-10-20T08:02:40+09:00',
                      'updated_at_jst': '2026-10-20T08:03:00+09:00',
                      'simulation_allowed': False, 'research_cli_switch_allowed': False,
                      'commands': [{'phase': 'compile', 'pid': 11, 'process_identity': self.child, 'log': str(self.log)}]}
        self.write_state()

    def write_state(self):
        self.state_path.write_text(json.dumps(self.state), encoding='utf-8')

    def query(self, pid):
        return deepcopy({10: self.owner, 11: self.child}[pid])

    def observe(self, query=None):
        return monitor.observe(self.state_path, query or self.query)[0]

    def configure_record(self):
        path = self.root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
        path.parent.mkdir(parents=True)
        path.write_text('{"workspace":"workspace"}', encoding='utf-8')

    def test_matching_creation_command_and_parent(self):
        value = self.observe()
        self.assertEqual(value['owner']['identity'], 'matched')
        self.assertEqual(value['child']['identity'], 'matched')
        self.assertEqual(value['anomaly_flags'], [])
        self.assertFalse(value['downstream_start_permitted'])
        self.assertFalse(value['core_ready'])
        self.assertIsNone(value['logs'][0]['sha256'])

    def test_pid_reuse_distinguished_from_absence(self):
        def reused(pid):
            value = self.query(pid)
            value['CreationDate'] = 1792450982203
            return value
        value = self.observe(reused)
        self.assertEqual(value['child']['identity'], 'reused')
        self.assertIn('child_identity_conflict', value['anomaly_flags'])
        absent = self.observe(lambda pid: None)
        self.assertEqual(absent['owner']['identity'], 'absent')
        self.assertIn('nonterminal_child_absent_or_already_exited', absent['anomaly_flags'])

    def test_missing_creation_and_command_mismatch_fail_closed(self):
        self.child.pop('CreationDate')
        self.write_state()
        self.assertEqual(self.observe()['child']['identity'], 'unknown')
        self.child['CreationDate'] = 1792450982202
        self.write_state()
        def different_command(pid):
            value = self.query(pid)
            value['CommandLine'] += ' other'
            return value
        self.assertEqual(self.observe(different_command)['child']['identity'], 'mismatched')

    def test_terminal_failed_preserved_and_terminal_logs_hashed(self):
        self.state['status'] = 'FAILED'
        self.write_state()
        value = self.observe(lambda pid: None)
        self.assertIn('terminal_build_FAILED', value['anomaly_flags'])
        self.assertEqual(value['logs'][0]['sha256'], sha256(self.log.read_bytes()).hexdigest())
        self.assertFalse(value['downstream_start_permitted'])

    def test_completed_never_implies_regression_or_ready(self):
        self.state['status'] = 'COMPLETED'
        self.write_state()
        value = self.observe(lambda pid: None)
        for key in ('native_regression_verified', 'core_ready', 'downstream_start_permitted', 'formal_validation_or_adoption'):
            self.assertFalse(value[key])

    def test_real_failed_preserved_schema_allows_absent_owner_and_hashes_logs(self):
        self.state.update(status='FAILED_PRESERVED', child_pid=None)
        self.write_state()
        value = self.observe(lambda pid: None)
        self.assertEqual(value['owner']['identity'], 'absent')
        self.assertEqual(value['anomaly_flags'], ['terminal_build_FAILED_PRESERVED'])
        self.assertEqual(value['logs'][0]['sha256'], sha256(self.log.read_bytes()).hexdigest())
        self.assertFalse(value['downstream_start_permitted'])

    def test_unknown_status_remains_fail_closed(self):
        self.state['status'] = 'UNRECOGNIZED'
        self.write_state()
        self.assertIn('missing_partial_or_ambiguous_build_evidence', self.observe()['anomaly_flags'])

    def test_real_compiled_version_status_is_terminal_but_grants_no_regression_or_ready(self):
        self.state.update(status='COMPILED_VERSION_CHECKED_NOT_SIMULATED', phase='completed', child_pid=None)
        self.write_state()
        value = self.observe(lambda pid: None)
        self.assertEqual(value['owner']['identity'], 'absent')
        self.assertEqual(value['anomaly_flags'], [])
        self.assertEqual(value['logs'][0]['sha256'], sha256(self.log.read_bytes()).hexdigest())
        for key in ('native_regression_verified', 'core_ready', 'simulation_allowed',
                    'research_cli_switch_allowed', 'downstream_start_permitted', 'formal_validation_or_adoption'):
            self.assertFalse(value[key])

    def test_partial_json_is_recorded_fail_closed(self):
        self.configure_record()
        self.state_path.write_bytes(b'{"status":')
        value = monitor.record(self.root, self.state_path, self.query)
        self.assertIn('missing_partial_or_ambiguous_build_evidence', value['anomaly_flags'])
        self.assertEqual((self.root / value['state_snapshot_file']).read_bytes(), b'{"status":')
        self.assertFalse(value['downstream_start_permitted'])

    def test_source_bytes_unchanged_and_three_jsonl_entries_identical(self):
        self.configure_record()
        originals = {p: p.read_bytes() for p in (self.state_path, self.log)}
        value = monitor.record(self.root, self.state_path, self.query)
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})
        paths = (self.root / '06_研究結果/jdrt/goal_20261017/operations.jsonl',
                 self.root / 'workspace/driver_logs/operations.jsonl', self.root / 'workspace/driver_logs/monitoring.jsonl')
        self.assertEqual([p.read_text(encoding='utf-8').count('\n') for p in paths], [1, 1, 1])
        self.assertEqual([json.loads(p.read_text(encoding='utf-8')) for p in paths], [value] * 3)
        self.assertEqual(json.loads((self.root / value['report']).read_text(encoding='utf-8')), value)
        second = monitor.record(self.root, self.state_path, self.query)
        self.assertEqual(second['previous_independent_observation_at_utc'], value['at_utc'])
        self.assertGreaterEqual(second['unobserved_interval_sec'], 0)

    def test_prohibition_flags_are_required_false(self):
        self.state.pop('simulation_allowed')
        self.write_state()
        self.assertIn('build_state_simulation_allowed_not_false', self.observe()['anomaly_flags'])

    def test_process_query_error_preserves_observation(self):
        def failed_query(pid):
            raise OSError('CIM unavailable')
        value = self.observe(failed_query)
        self.assertIn('missing_partial_or_ambiguous_build_evidence', value['anomaly_flags'])
        self.assertFalse(value['downstream_start_permitted'])


if __name__ == '__main__':
    unittest.main()
