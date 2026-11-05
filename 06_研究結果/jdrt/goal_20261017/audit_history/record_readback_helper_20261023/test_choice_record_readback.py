"""Artificial metadata contracts, not SUMO or scientific acceptance tests."""
import copy
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
        self.documents = ['experiment.md', 'task.md', 'context.md', 'decision.md', 'progress.md', 'progress.html']
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

    def test_terminal_record_bytes_changed(self):
        self.put('progress.md', self.marker + '\nchanged\n')
        with self.assertRaises(RuntimeError):
            subject.audit(self.root, self.run)

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
