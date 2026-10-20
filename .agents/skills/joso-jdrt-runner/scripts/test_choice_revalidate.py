"""Artificial contract checks only: never import or launch SUMO."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import choice_revalidate as target


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sources = [target.SCRIPTS / name for name in ('choice_revalidate.py', 'choice_technical.py',
                   'choice_smoke_sequence.py', 'realtime_choice_cell.py')]
        sources += [target.AUDITOR, Path('04_プログラム/scripts/jdrt_choice_fixtures.py')]
        for name in sources + [Path('common' + str(i) + '.py') for i in range(5)]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('artificial source', encoding='utf-8')
        write(self.root / target.PARAM, {'workspace': 'workspace', 'protocol': 'artificial',
              'execution': {'implementation_files': ['common' + str(i) + '.py' for i in range(5)]},
              'seeds': [1], 'cells': [{'seed': 1, 'cell_id': 'a'}, {'seed': 1, 'cell_id': 'b'}]})
        self.runner = target.Revalidation(self.root, 'suite', 'smoke')
        self.calls = []

    def child(self, stage, args):
        r = self.runner
        r.frozen()
        self.calls.append(stage)
        r.state['active'] = {'stage': stage, 'command': args, 'exit_code': 0, 'pid': 123,
                             'started_at_jst': target.stamp(), 'finished_at_jst': target.stamp()}
        stdout = r.out / (stage + '.json')
        if stage == 'fixture':
            child = write(r.workspace / 'technical/c1/execution/manifest.json',
                          {'status': 'COMPLETED', 'implementation_sha256': r.current})
            suite = {'run_id': r.suite, 'status': 'COMPLETED', 'research_adoption_permitted': False,
                     'cases': [{'status': 'PASS', 'child_run_id': 'c1', 'execution_manifest_sha256': target.sha(child)}]}
            write(r.workspace / 'technical' / r.suite / 'manifest.json', suite)
            write(stdout, suite)
        elif stage == 'independent':
            report = {'status': 'PASS', 'suite': r.suite, 'historical_diagnostic': False,
                      'primary_outputs_unchanged': True, 'core_adoption_permitted': False, 'technical_ready': False,
                      'counterexamples': [{'pass': True}], 'fixture_components': [{'implementation_sha256': r.current}],
                      'test_sha256': r.sources[target.AUDITOR.as_posix()]}
            write(r.out / '正式検証器_表会計候補_new.json', report)
            write(stdout, {k: v for k, v in report.items() if k != 'fixture_components'})
        elif stage == 'smoke':
            completed = []
            for i, cell in enumerate(r.params['cells'], 1):
                run_id = 'smoke_' + str(i).zfill(2)
                manifest = write(r.workspace / 'smoke' / run_id / 'manifest.json',
                                 {'status': 'COMPLETED', 'implementation_sha256': r.current})
                proof = write(r.out / (run_id + '_proof.json'),
                              {'status': 'PASS', 'core_adoption_permitted': False, 'manifest_sha256': target.sha(manifest)})
                completed.append({'run_id': run_id, 'cell': cell, 'manifest_sha256': target.sha(manifest),
                                  'validation_report': proof.relative_to(self.root).as_posix()})
            write(r.out / 'smoke_smoke_sequence.json', {'status': 'COMPLETED', 'active': None,
                  'implementation_sha256': r.current, 'research_adoption_permitted': False, 'completed': completed,
                  'audit_path': r.audit_path.relative_to(self.root).as_posix(), 'audit_sha256': target.sha(r.audit_path)})
        else:
            receipt = write(r.out / 'receipt.json', {'status': 'READY', 'implementation_sha256': r.current,
                  'independent_receipt_checks': {'all': True}, 'evidence_sha256': dict(r.state['artifacts']),
                  'evidence': {'counterexamples': r.audit_path.relative_to(self.root).as_posix(),
                  'fixture_manifest': (r.workspace / 'technical' / r.suite / 'manifest.json').relative_to(self.root).as_posix()}})
            write(stdout, {'status': 'READY', 'checks': {'all': True}, 'report': receipt.relative_to(self.root).as_posix()})
        return stdout

    def run_fake(self, mutate=None):
        def fake(stage, args):
            path = self.child(stage, args)
            if mutate:
                mutate(stage, path)
            return path
        with patch.object(self.runner, 'command', side_effect=fake):
            return self.runner.run()

    def test_complete_serial_technical_contract(self):
        state = target.read_json(self.run_fake())
        self.assertEqual(self.calls, ['fixture', 'independent', 'smoke', 'preflight'])
        self.assertEqual(state['status'], 'COMPLETED')
        self.assertEqual(len(state['completed']), 4)
        self.assertFalse(state['research_adoption_permitted'])
        self.assertTrue(all(s['result_path'] in state['artifacts'] for s in state['completed']))
        self.assertFalse((self.runner.out / 'choice_revalidate.lock').exists())

    def test_result_list_stops_before_audit(self):
        with self.assertRaisesRegex(ValueError, 'expected dict, got list'):
            self.run_fake(lambda stage, path: write(path, []) if stage == 'fixture' else None)
        self.assertEqual(self.calls, ['fixture'])
        self.assertEqual(target.read_json(self.runner.state_path)['status'], 'FAILED')

    def test_ambiguous_new_audit_stops(self):
        def alter(stage, path):
            if stage == 'independent':
                write(self.runner.out / '正式検証器_表会計候補_extra.json', {})
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.run_fake(alter)
        self.assertEqual(self.calls, ['fixture', 'independent'])

    def test_counterexample_wrong_shape_stops(self):
        def alter(stage, path):
            if stage == 'independent':
                report = target.read_json(self.runner.out / '正式検証器_表会計候補_new.json')
                report['counterexamples'] = {'pass': True}
                write(self.runner.out / '正式検証器_表会計候補_new.json', report)
                write(path, {k: v for k, v in report.items() if k != 'fixture_components'})
        with self.assertRaisesRegex(ValueError, 'counterexample list'):
            self.run_fake(alter)
        self.assertEqual(self.calls, ['fixture', 'independent'])

    def test_frozen_source_change_stops_next_command(self):
        def alter(stage, path):
            if stage == 'fixture':
                (self.root / 'common0.py').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_fake(alter)
        self.assertEqual(self.calls, ['fixture'])

    def test_duplicate_suite_never_overwrites_state(self):
        self.run_fake()
        before = self.runner.state_path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.runner.run()
        self.assertEqual(before, self.runner.state_path.read_bytes())

    def test_prefix_reserved_even_failure_before_smoke(self):
        with self.assertRaises(ValueError):
            self.run_fake(lambda stage, path: write(path, []) if stage == 'fixture' else None)
        other = target.Revalidation(self.root, 'new_suite', 'smoke')
        with self.assertRaises(FileExistsError), patch.object(other, 'command') as command:
            other.run()
        command.assert_not_called()

    def test_incomplete_smoke_blocks_preflight(self):
        def alter(stage, path):
            if stage == 'smoke':
                state_path = self.runner.out / 'smoke_smoke_sequence.json'
                state = target.read_json(state_path)
                state['completed'].pop()
                write(state_path, state)
        with self.assertRaisesRegex(ValueError, 'Incomplete registered'):
            self.run_fake(alter)
        self.assertEqual(self.calls, ['fixture', 'independent', 'smoke'])

    def test_child_timeout_keeps_same_pid_then_nonzero_stops(self):
        r = self.runner
        r.out.mkdir(parents=True, exist_ok=True)
        r.save()
        child = Mock(pid=123)
        child.wait.side_effect = [subprocess.TimeoutExpired('artificial', 15), 4]
        with patch.object(target.subprocess, 'Popen', return_value=child) as start:
            with self.assertRaisesRegex(ValueError, 'exit code 4'):
                r.command('fixture', ['artificial'])
        start.assert_called_once()
        self.assertEqual(child.wait.call_count, 2)
        state = target.read_json(r.state_path)
        self.assertEqual(state['active']['pid'], 123)
        self.assertEqual(state['active']['exit_code'], 4)
        self.assertIn('observed_at_jst', state['active'])
        child.kill.assert_not_called()
        child.terminate.assert_not_called()

    def test_nonzero_child_full_workflow_preserves_failure(self):
        child = Mock(pid=123)
        child.wait.return_value = 5
        with patch.object(target.subprocess, 'Popen', return_value=child) as start:
            with self.assertRaisesRegex(ValueError, 'exit code 5'):
                self.runner.run()
        start.assert_called_once()
        state = target.read_json(self.runner.state_path)
        self.assertEqual(state['status'], 'FAILED')
        self.assertEqual(state['active']['exit_code'], 5)
        self.assertEqual(state['completed'], [])

    def test_preflight_receipt_sha_mismatch_blocks_completion(self):
        def alter(stage, path):
            if stage == 'preflight':
                receipt_path = self.runner.out / 'receipt.json'
                receipt = target.read_json(receipt_path)
                receipt['evidence_sha256'][next(iter(receipt['evidence_sha256']))] = '0' * 64
                write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'Preflight evidence SHA mismatch'):
            self.run_fake(alter)
        self.assertEqual(target.read_json(self.runner.state_path)['status'], 'FAILED')

    def test_interrupted_child_retains_lock_and_pid(self):
        r = self.runner
        child = Mock(pid=123)
        child.wait.side_effect = KeyboardInterrupt
        with patch.object(target.subprocess, 'Popen', return_value=child):
            with self.assertRaises(KeyboardInterrupt):
                r.run()
        state = target.read_json(r.state_path)
        self.assertEqual(state['status'], 'FAILED')
        self.assertEqual(state['active']['pid'], 123)
        self.assertIsNone(state['active']['exit_code'])
        self.assertTrue((r.out / 'choice_revalidate.lock').exists())

    def test_local_evidence_boundary(self):
        with self.assertRaisesRegex(ValueError, 'inside project'):
            self.runner.local('../outside.json')


if __name__ == '__main__':
    unittest.main()
