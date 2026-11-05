"""Artificial orchestration/file contracts, never native or research adoption."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import choice_finish_cell as helper


class FinishContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_id = 'artificial01'
        self.workspace = self.root / 'workspace'
        self.folder = self.workspace / 'runs' / self.run_id
        self.folder.mkdir(parents=True)
        self.records = ['runs.md', 'tasks.md', 'context.md', 'decisions.md',
                        'progress.md', 'progress.html', 'ledger.jsonl']
        self.config = {'protocol': 'realtime_choice_v1', 'registration_id': 'artificial_registration',
                       'workspace': 'workspace', 'record_files': self.records,
                       'cells': [{'cell_id': 'artificial_cell'}]}
        self.config_path = self.root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
        self.config_path.parent.mkdir(parents=True)
        self.save(self.config_path, self.config)
        self.manifest = {'protocol': self.config['protocol'], 'registration_id': self.config['registration_id'],
                         'run_id': self.run_id, 'purpose': 'core', 'status': 'COMPLETED',
                         'cell_id': 'artificial_cell'}
        self.save(self.folder / 'manifest.json', self.manifest)
        self.validation = {'run_id': self.run_id, 'purpose': 'core', 'status': 'PASS',
                           'core_adoption_permitted': True, 'validation_report': 'validation.json'}
        self.save(self.root / 'validation.json', self.validation)
        self.row = {'run_id': self.run_id, 'cell_id': 'artificial_cell',
                    'protocol': self.config['protocol'], 'registration_id': self.config['registration_id']}
        self.calls = []
        self.skip_marker = None
        self.duplicate = False
        self.context_after_end = False
        self.bad_status = False
        self.change_config = False
        self.record_response_lost = False

    @staticmethod
    def save(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def fake_cli(self, root, operation, run_id, command):
        self.calls.append(command)
        if command == 'check':
            return {'run_id': run_id, 'status': 'COMPLETED', 'pid_alive': False}
        if command == 'validate':
            if self.change_config:
                self.config_path.write_text('{}', encoding='utf-8')
            return dict(self.validation)
        if command == 'record':
            marker = '<!-- choice_record:' + run_id + ' -->'
            for name in self.records[:-1]:
                text = '' if name == self.skip_marker else marker
                if name == 'context.md' and self.context_after_end:
                    text = '<!-- AGENT_CURRENT_END -->\n' + marker
                (root / name).write_text(text, encoding='utf-8')
            rows = [self.row, self.row] if self.duplicate else [self.row]
            (root / self.records[-1]).write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            if self.record_response_lost:
                raise RuntimeError('Artificial interruption after record mutation')
            return {'status': 'RECORDED', 'run_id': run_id}
        if command == 'status':
            result = {name: [] for name in ('running', 'unrecorded', 'partial_records',
                'record_identity_mismatch', 'unresolved_failures', 'unresolved_launches',
                'pending_record_journals', 'foreign_running_manifests', 'active_native_processes')}
            result['recorded_cells'] = 1
            if self.bad_status:
                result['pending_record_journals'] = ['artificial_pending']
            return result
        self.fail('Unexpected command: ' + command)

    def invoke(self, busy=False):
        with patch.object(helper, 'call_cli', side_effect=self.fake_cli), \
                patch.object(helper, 'other_validation_owner', return_value=busy):
            return helper.finish(self.root, self.run_id)

    def test_order_and_all_seven_recorded(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'RECORDED_VERIFIED')
        self.assertEqual(self.calls, ['check', 'validate', 'record', 'status'])

    def test_transient_terminal_replace_never_replays_cli(self):
        original = Path.replace
        attempts = []

        def replace(path, target):
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['status'] == 'RECORDED_VERIFIED':
                attempts.append(state['status'])
                if len(attempts) == 1:
                    raise PermissionError('Artificial transient sharing conflict')
            return original(path, target)

        with patch.object(Path, 'replace', replace):
            result = self.invoke()
        self.assertEqual(result['status'], 'RECORDED_VERIFIED')
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.calls, ['check', 'validate', 'record', 'status'])

    def test_persistent_terminal_replace_is_bounded_and_preserved(self):
        original = Path.replace
        attempts = []

        def replace(path, target):
            if json.loads(path.read_text(encoding='utf-8'))['status'] == 'RECORDED_VERIFIED':
                attempts.append(True)
                raise PermissionError('Artificial persistent sharing conflict')
            return original(path, target)

        with patch.object(Path, 'replace', replace), self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(len(attempts), 5)
        state = json.loads((self.workspace / 'driver_logs' / (self.run_id + '.finish') /
                            'operation.json').read_text(encoding='utf-8'))
        self.assertEqual(state['status'], 'FAILED_PRESERVED')
        self.assertEqual(state['formal_record_result'], 'RECORDED')
        self.assertTrue(state['record_attempted'])
        self.assertEqual(len(state['record_files_sha256']), 7)
        self.assertEqual(self.calls, ['check', 'validate', 'record', 'status'])
        self.assertTrue(all((self.root / name).is_file() for name in self.records))

    def test_other_terminal_replace_error_is_not_retried(self):
        original = Path.replace
        attempts = []

        def replace(path, target):
            if json.loads(path.read_text(encoding='utf-8'))['status'] == 'RECORDED_VERIFIED':
                attempts.append(True)
                raise OSError('Artificial non-sharing I/O failure')
            return original(path, target)

        with patch.object(Path, 'replace', replace), self.assertRaises(OSError):
            self.invoke()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.calls, ['check', 'validate', 'record', 'status'])

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows sharing semantics')
    def test_owned_windows_sharing_lock_is_released_before_retry(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        original = Path.replace
        sharing_errors = []

        def replace(path, target):
            if (json.loads(path.read_text(encoding='utf-8'))['status'] == 'RECORDED_VERIFIED'
                    and not sharing_errors):
                # This test owns both files. Excluding FILE_SHARE_DELETE blocks replacement.
                handle = kernel.CreateFileW(str(target), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
                self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
                try:
                    return original(path, target)
                except PermissionError as error:
                    sharing_errors.append(error.winerror)
                    raise
                finally:
                    self.assertTrue(kernel.CloseHandle(handle))
            return original(path, target)

        with patch.object(Path, 'replace', replace):
            result = self.invoke()
        self.assertEqual(result['status'], 'RECORDED_VERIFIED')
        self.assertEqual(len(sharing_errors), 1)
        self.assertIn(sharing_errors[0], (5, 32))
        self.assertEqual(self.calls, ['check', 'validate', 'record', 'status'])

    def test_invalid_does_not_record(self):
        self.validation.update(status='INVALID', core_adoption_permitted=False)
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertNotIn('record', self.calls)

        operation = self.workspace / 'driver_logs' / (self.run_id + '.finish') / 'operation.json'
        self.assertFalse(json.loads(operation.read_text(encoding='utf-8'))['record_attempted'])

    def test_running_manifest_blocks_commands(self):
        self.manifest['status'] = 'RUNNING'
        self.save(self.folder / 'manifest.json', self.manifest)
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_foreign_registration_blocks_commands(self):
        self.manifest['registration_id'] = 'other_registration'
        self.save(self.folder / 'manifest.json', self.manifest)
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_existing_operation_is_not_overwritten(self):
        operation = self.workspace / 'driver_logs' / (self.run_id + '.finish')
        operation.mkdir(parents=True)
        proof = operation / 'preserved.txt'
        proof.write_bytes(b'preserve')
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(proof.read_bytes(), b'preserve')
        self.assertEqual(self.calls, [])

    def test_other_validation_owner_blocks_commands(self):
        with self.assertRaises(RuntimeError):
            self.invoke(busy=True)
        self.assertEqual(self.calls, [])

    def test_missing_marker_is_not_success(self):
        self.skip_marker = 'progress.html'
        with self.assertRaises(RuntimeError):
            self.invoke()

    def test_context_marker_after_boundary_is_not_success(self):
        self.context_after_end = True
        with self.assertRaises(RuntimeError):
            self.invoke()

    def test_duplicate_ledger_is_not_success(self):
        self.duplicate = True
        with self.assertRaises(RuntimeError):
            self.invoke()

    def test_pending_journal_is_not_success(self):
        self.bad_status = True
        with self.assertRaises(RuntimeError):
            self.invoke()

    def test_config_change_blocks_record(self):
        self.change_config = True
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertNotIn('record', self.calls)
        operation = self.workspace / 'driver_logs' / (self.run_id + '.finish') / 'operation.json'
        self.assertFalse(json.loads(operation.read_text(encoding='utf-8'))['record_attempted'])

    def test_existing_ledger_row_blocks_revalidation(self):
        (self.root / 'ledger.jsonl').write_text(json.dumps(self.row) + '\n', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_path_traversal_id_blocks_commands(self):
        self.run_id = '../outside'
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_original_report_purpose_must_be_core(self):
        self.save(self.root / 'validation.json', {**self.validation, 'purpose': 'fixture'})
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertNotIn('record', self.calls)

    def test_lost_record_response_preserves_possible_commit(self):
        self.record_response_lost = True
        with self.assertRaises(RuntimeError):
            self.invoke()
        path = self.workspace / 'driver_logs' / (self.run_id + '.finish') / 'operation.json'
        state = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(state.get('record_attempted', False))
        self.assertIsNone(state['formal_record_result'])
        self.assertEqual(state['status'], 'FAILED_PRESERVED')
        self.assertTrue((self.root / 'ledger.jsonl').exists())

    def test_transport_cannot_start_or_recover(self):
        operation = self.root / 'transport'
        operation.mkdir()
        for command in ('start-next', 'recover'):
            with self.subTest(command=command), \
                    patch.object(helper.subprocess, 'Popen', side_effect=AssertionError('Forbidden child spawn')):
                with self.assertRaisesRegex(RuntimeError, 'Unsupported'):
                    helper.call_cli(self.root, operation, self.run_id, command)


if __name__ == '__main__':
    unittest.main()
