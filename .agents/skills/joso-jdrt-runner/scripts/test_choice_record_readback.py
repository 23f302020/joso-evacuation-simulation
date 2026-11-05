"""Artificial metadata contracts, not SUMO or scientific acceptance tests."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import choice_record_readback as subject
from choice_finish_cell import CONFIG, HOLDS, digest


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.run = 'artificial01'
        self.workspace = self.root / 'workspace'
        self.operation = self.workspace / 'driver_logs' / (self.run + '.finish')
        self.marker = '<!-- choice_record:' + self.run + ' -->'
        self.documents = ['records/experiment.md', 'task.md', 'context.md', 'decision.md', 'progress.md', 'progress.html']
        for name in self.documents:
            self.put(name, self.marker + '\n' + ('<!-- AGENT_CURRENT_END -->\n' if name == 'context.md' else ''))
        self.implementation = {}
        for name in ['implementation.py', 'inputs.py', 'validator.py', 'policy.py', 'cli.py']:
            self.put(name, 'artificial source ' + name + '\n')
            self.implementation[name] = digest(self.root / name)
        self.put('input/manifest.json', '{}')
        self.cfg = {'protocol': 'realtime_choice_v1', 'registration_id': 'artificial-registration',
                    'workspace': 'workspace', 'record_files': self.documents + ['ledger.jsonl'],
                    'execution': {'implementation_files': list(self.implementation)},
                    'cells': [{'cell_id': 'cell01'}, {'cell_id': 'cell02'}]}
        self.dump(CONFIG, self.cfg)
        self.manifest = {'run_id': self.run, 'protocol': self.cfg['protocol'],
                         'registration_id': self.cfg['registration_id'], 'purpose': 'core',
                         'status': 'COMPLETED', 'cell_id': 'cell01', 'input_directory': 'input',
                         'input_manifest_sha256': digest(self.root / 'input/manifest.json'),
                         'parameter_sha256': digest(self.root / CONFIG),
                         'implementation_sha256': self.implementation}
        self.dump('workspace/runs/' + self.run + '/manifest.json', self.manifest)
        self.report = {'run_id': self.run, 'purpose': 'core', 'status': 'PASS', 'core_adoption_permitted': True,
                       'manifest_sha256': digest(self.workspace / 'runs' / self.run / 'manifest.json'),
                       'parameter_sha256': self.manifest['parameter_sha256'],
                       'input_manifest_sha256': self.manifest['input_manifest_sha256'],
                       'implementation_sha256': self.manifest['implementation_sha256'],
                       'components': {key: {'status': 'PASS', 'artificial': True} for key in
                                      ['person_tables', 'candidate_tables', 'road_snapshots', 'actor_stream',
                                       'movement_events', 'native_logs', 'native_fixture_boundaries']}}
        self.dump('workspace/independent.json', self.report)
        self.dump('workspace/formal.json', self.report)
        self.row = {**{k: self.manifest[k] for k in ['run_id', 'protocol', 'registration_id', 'purpose',
                       'cell_id', 'input_manifest_sha256', 'implementation_sha256']},
                    'validation_status': 'PASS', 'validation_report': 'workspace/formal.json',
                    'validation_report_sha256': digest(self.workspace / 'formal.json'),
                    'manifest_sha256': self.report['manifest_sha256']}
        self.dump('ledger.jsonl', self.row, compact=True)
        self.state = {'run_id': self.run, 'status': 'RECORDED_VERIFIED',
                      'formal_record_result': 'RECORDED', 'record_attempted': True,
                      'next_start_performed': False, 'config_sha256': digest(self.root / CONFIG),
                      'validation_report_sha256': digest(self.workspace / 'independent.json'),
                      'record_files_sha256': {name: digest(self.root / name) for name in self.cfg['record_files']}}
        self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', self.state)
        self.dump('workspace/driver_logs/' + self.run + '.finish/validate.stdout.log',
                  {'validation_report': 'workspace/independent.json'})
        self.dump('workspace/driver_logs/' + self.run + '.finish/record.stdout.log',
                  {'run_id': self.run, 'status': 'RECORDED', 'validation_report': 'workspace/formal.json'})
        self.status = {**{k: [] for k in HOLDS}, 'recorded_cells': 1, 'next_cell': self.cfg['cells'][1]}
        self.dump('workspace/driver_logs/' + self.run + '.finish/status.stdout.log', self.status)
        self.journal_path = 'workspace/record_transactions/' + self.run + '_artificial/journal.json'
        self.journal = {'status': 'COMMITTED', 'run_id': self.run,
                        'sha256_after': self.state['record_files_sha256']}
        self.dump(self.journal_path, self.journal)

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def dump(self, name, data, compact=False):
        self.put(name, json.dumps(data, ensure_ascii=False, indent=None if compact else 2) + '\n')

    def rebind_records(self):
        self.state['record_files_sha256'] = {p: digest(self.root / p) for p in self.cfg['record_files']}
        self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', self.state)
        self.journal['sha256_after'] = self.state['record_files_sha256']
        self.dump(self.journal_path, self.journal)

    def test_complete_metadata_readback_is_read_only(self):
        before = {p.relative_to(self.root).as_posix(): digest(p) for p in self.root.rglob('*') if p.is_file()}
        result = subject.audit(self.root, self.run)
        self.assertEqual(result.get('status'), 'RECORD7_PRIMARY_READBACK_PASS')
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): digest(p) for p in self.root.rglob('*') if p.is_file()})

    def recovered_precommit(self):
        self.recovery = self.root / '06_研究結果/jdrt/goal_20261017/recovery/recovery_operation.json'
        self.recovery.parent.mkdir(parents=True)
        for name in ('record.stdout.log', 'status.stdout.log'):
            (self.recovery.parent / name).write_bytes((self.operation / name).read_bytes())
        original = copy.deepcopy(self.state)
        original.update(status='RUNNING', phase='record', formal_record_result=None, commands=[
            {'command': 'check', 'status': 'COMPLETED', 'run_id': self.run},
            {'command': 'validate', 'status': 'PASS', 'run_id': self.run,
             'validation_report': 'workspace/independent.json'}])
        self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', original)
        self.put('workspace/driver_logs/' + self.run + '.finish/record.stdout.log', '')
        preserved = {}
        archive = self.recovery.parent / 'before02'
        archive.mkdir()
        for name in self.cfg['record_files']:
            raw = b'' if name == 'ledger.jsonl' else b'previous document\n'
            sha = hashlib.sha256(raw).hexdigest()
            (archive / (sha + Path(name).suffix)).write_bytes(raw)
            preserved[name] = sha
        self.diagnosis = {'status': 'ORPHAN_PRECOMMIT_RECORD_CONFIRMED', 'run_id': self.run,
                          'formal_rows_before': 0, 'preserved_sha256': preserved}
        self.dump(self.recovery.parent.relative_to(self.root).as_posix() + '/diagnosis.json', self.diagnosis)
        self.recovered = {**self.state, 'kind': 'explicit_orphan_precommit_record_recovery_v1',
                          'phase': 'status', 'record_exit_code': 0, 'status_exit_code': 0,
                          'original_operation': (self.operation / 'operation.json').relative_to(self.root).as_posix(),
                          'original_operation_sha256': digest(self.operation / 'operation.json'),
                          'diagnosis': (self.recovery.parent / 'diagnosis.json').relative_to(self.root).as_posix(),
                          'diagnosis_sha256': digest(self.recovery.parent / 'diagnosis.json')}
        self.dump(self.recovery.relative_to(self.root).as_posix(), self.recovered)

    def test_explicit_recovered_record_preserves_original_interruption(self):
        self.recovered_precommit()
        before = {p.relative_to(self.root).as_posix(): digest(p) for p in self.root.rglob('*') if p.is_file()}
        result = subject.audit(self.root, self.run, recovery_operation=self.recovery)
        self.assertEqual(result['status'], 'RECORD7_PRIMARY_READBACK_PASS')
        self.assertTrue(result['precommit_interruption_preserved'])
        self.assertEqual(result['finish_operation_status'], 'RUNNING')
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): digest(p) for p in self.root.rglob('*') if p.is_file()})

    def test_recovered_record_rejects_original_operation_changes(self):
        self.recovered_precommit()
        self.put('workspace/driver_logs/' + self.run + '.finish/operation.json', '{}')
        with self.assertRaisesRegex(RuntimeError, 'Original interrupted operation changed'):
            subject.audit(self.root, self.run, recovery_operation=self.recovery)

    def test_recovered_record_rejects_incomplete_or_foreign_recovery(self):
        self.recovered_precommit()
        for field, value in [('status', 'RUNNING'), ('record_exit_code', 1), ('run_id', 'foreign'),
                             ('formal_record_result', None), ('kind', 'ordinary_record')]:
            with self.subTest(field=field):
                changed = {**self.recovered, field: value}
                self.dump(self.recovery.relative_to(self.root).as_posix(), changed)
                with self.assertRaises(RuntimeError):
                    subject.audit(self.root, self.run, recovery_operation=self.recovery)

    def test_recovered_record_requires_preserved_precommit_bytes(self):
        self.recovered_precommit()
        ledger_sha = self.diagnosis['preserved_sha256']['ledger.jsonl']
        (self.recovery.parent / 'before02' / (ledger_sha + '.jsonl')).write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run, recovery_operation=self.recovery)

    def test_recovered_record_still_rejects_changed_terminal_record(self):
        self.recovered_precommit()
        self.put('task.md', self.marker + '\nchanged\n')
        with self.assertRaisesRegex(RuntimeError, 'Record bytes changed'):
            subject.audit(self.root, self.run, recovery_operation=self.recovery)

    def test_unfinished_original_never_passes_without_explicit_recovery(self):
        self.recovered_precommit()
        with self.assertRaisesRegex(RuntimeError, 'Finish not terminal/recorded'):
            subject.audit(self.root, self.run)

    def test_recovered_record_rejects_changed_diagnosis(self):
        self.recovered_precommit()
        self.put(self.recovered['diagnosis'], '{}')
        with self.assertRaisesRegex(RuntimeError, 'Recovery diagnosis changed'):
            subject.audit(self.root, self.run, recovery_operation=self.recovery)

    def test_recovered_record_rejects_previous_marker(self):
        self.recovered_precommit()
        raw = self.marker.encode('utf-8')
        sha = hashlib.sha256(raw).hexdigest()
        (self.recovery.parent / 'before02' / (sha + '.md')).write_bytes(raw)
        self.diagnosis['preserved_sha256']['task.md'] = sha
        self.dump(self.recovered['diagnosis'], self.diagnosis)
        self.recovered['diagnosis_sha256'] = digest(self.root / self.recovered['diagnosis'])
        self.dump(self.recovery.relative_to(self.root).as_posix(), self.recovered)
        with self.assertRaisesRegex(RuntimeError, 'Record marker already existed'):
            subject.audit(self.root, self.run, recovery_operation=self.recovery)

    def failed_postcommit(self):
        self.state.update(status='FAILED_PRESERVED', error_type='PermissionError', phase='status',
                          formal_record_result='RECORDED', record_attempted=True,
                          error='Artificial terminal metadata replace failure', commands=[
                              {'command': 'check', 'status': 'COMPLETED', 'run_id': self.run},
                              {'command': 'validate', 'status': 'PASS', 'run_id': self.run},
                              {'command': 'record', 'status': 'RECORDED', 'run_id': self.run},
                              {'command': 'status', 'status': None, 'run_id': None}])
        self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', self.state)

    def test_postcommit_auxiliary_failure_readback_preserves_original_failure(self):
        self.failed_postcommit()
        before = {p.relative_to(self.root).as_posix(): digest(p) for p in self.root.rglob('*') if p.is_file()}
        result = subject.audit(self.root, self.run)
        self.assertEqual(result['status'], 'RECORD7_PRIMARY_READBACK_PASS')
        self.assertEqual(result['finish_operation_status'], 'FAILED_PRESERVED')
        self.assertTrue(result['finish_auxiliary_failure_preserved'])
        self.assertFalse(result['next_start_performed'])
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): digest(p) for p in self.root.rglob('*') if p.is_file()})

    def test_failed_postcommit_requires_exact_terminal_history(self):
        for field, value in [('phase', 'record'), ('error_type', 'OSError'), ('commands', []),
                             ('formal_record_result', None), ('record_attempted', False)]:
            with self.subTest(field=field):
                self.failed_postcommit()
                self.state[field] = value
                self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', self.state)
                with self.assertRaises(RuntimeError):
                    subject.audit(self.root, self.run)

    def test_failed_postcommit_still_rejects_changed_record_bytes(self):
        self.failed_postcommit()
        self.put('progress.md', self.marker + '\nchanged\n')
        with self.assertRaisesRegex(RuntimeError, 'Record bytes changed'):
            subject.audit(self.root, self.run)

    def test_failed_postcommit_still_rejects_pending_journal(self):
        self.failed_postcommit()
        self.status['pending_record_journals'] = ['unfinished']
        self.dump('workspace/driver_logs/' + self.run + '.finish/status.stdout.log', self.status)
        with self.assertRaisesRegex(RuntimeError, 'Finish status retains a hold'):
            subject.audit(self.root, self.run)

    def test_terminal_record_bytes_changed(self):
        self.put('progress.md', self.marker + '\nchanged\n')
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_native_windows_finish_paths_match_posix_journal_paths(self):
        self.state['record_files_sha256'] = {name.replace('/', '\\'): value
                                           for name, value in self.state['record_files_sha256'].items()}
        self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', self.state)
        self.assertEqual(subject.audit(self.root, self.run)['status'], 'RECORD7_PRIMARY_READBACK_PASS')

    def test_context_marker_only_in_history_is_not_current(self):
        self.put('context.md', '<!-- AGENT_CURRENT_END -->\n' + self.marker + '\n')
        self.rebind_records()
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_duplicate_record_marker(self):
        self.put('task.md', self.marker + '\n' + self.marker + '\n')
        self.rebind_records()
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_duplicate_ledger_identity(self):
        self.put('ledger.jsonl', json.dumps(self.row) + '\n' + json.dumps(self.row) + '\n')
        self.rebind_records()
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_foreign_registration(self):
        self.row['registration_id'] = 'old-registration'
        self.dump('ledger.jsonl', self.row, compact=True)
        self.rebind_records()
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_current_implementation_changed(self):
        self.put('implementation.py', 'changed source\n')
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_five_matching_but_unregistered_sources(self):
        self.put('other.py', 'artificial unregistered source\n')
        replacement = dict(self.implementation)
        replacement.pop('implementation.py')
        replacement['other.py'] = digest(self.root / 'other.py')
        self.manifest['implementation_sha256'] = replacement
        self.dump('workspace/runs/' + self.run + '/manifest.json', self.manifest)
        self.report['implementation_sha256'] = replacement
        self.report['manifest_sha256'] = digest(self.workspace / 'runs' / self.run / 'manifest.json')
        self.dump('workspace/independent.json', self.report)
        self.dump('workspace/formal.json', self.report)
        self.row.update(implementation_sha256=replacement, manifest_sha256=self.report['manifest_sha256'],
                        validation_report_sha256=digest(self.workspace / 'formal.json'))
        self.dump('ledger.jsonl', self.row, compact=True)
        self.state['validation_report_sha256'] = digest(self.workspace / 'independent.json')
        self.rebind_records()
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_not_committed_or_not_terminal(self):
        for label in ['PREPARED', 'RUNNING']:
            with self.subTest(label=label):
                if label == 'PREPARED':
                    self.journal['status'] = label
                    self.dump(self.journal_path, self.journal)
                else:
                    self.journal['status'] = 'COMMITTED'
                    self.dump(self.journal_path, self.journal)
                    self.state['status'] = label
                    self.dump('workspace/driver_logs/' + self.run + '.finish/operation.json', self.state)
                with self.assertRaises(RuntimeError):
                    subject.audit(self.root, self.run)

    def test_dedicated_status_retains_hold(self):
        self.status['pending_record_journals'] = ['unfinished']
        self.dump('workspace/driver_logs/' + self.run + '.finish/status.stdout.log', self.status)
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_independent_and_record_components_differ(self):
        changed = copy.deepcopy(self.report)
        changed['components']['movement_events']['artificial'] = False
        self.dump('workspace/formal.json', changed)
        self.row['validation_report_sha256'] = digest(self.workspace / 'formal.json')
        self.dump('ledger.jsonl', self.row, compact=True)
        self.rebind_records()
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

    def test_nonadoptable_or_invalid_formal_report(self):
        for field, value in [('core_adoption_permitted', False), ('status', 'INVALID')]:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.report)
                changed[field] = value
                self.dump('workspace/formal.json', changed)
                self.row['validation_report_sha256'] = digest(self.workspace / 'formal.json')
                self.dump('ledger.jsonl', self.row, compact=True)
                self.rebind_records()
                with self.assertRaises(RuntimeError):
                    subject.audit(self.root, self.run)

    def test_cli_never_adds_a_file_to_research_workspace(self):
        output = self.workspace / 'runs' / self.run / 'new-report.json'
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(Path(subject.__file__).resolve()),
                                 '--project-root', str(self.root), '--run-id', self.run, '--output', str(output)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Write metadata only inside the goal evidence folder', result.stderr)
        self.assertFalse(output.exists())

    def test_cli_writes_fresh_goal_report_and_never_overwrites(self):
        output = self.root / '06_研究結果/jdrt/goal_20261017/readback.json'
        output.parent.mkdir(parents=True)
        args = [sys.executable, '-B', '-X', 'utf8', str(Path(subject.__file__).resolve()), '--project-root', str(self.root),
                '--run-id', self.run, '--output', str(output)]
        first = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['recorded_cells'], 1)
        before = digest(output)
        second = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('FileExistsError', second.stderr)
        self.assertEqual(digest(output), before)


if __name__ == '__main__':
    unittest.main()
