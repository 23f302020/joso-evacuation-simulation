"""Technical monitoring edge cases using synthetic, temporary evidence only."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import choice_technical_monitor as monitor


class TechnicalMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / 'suite'
        self.parent.mkdir()
        (self.parent / 'factory.py').write_text("CASES = ('calibration', 'repeated')\n", encoding='utf-8')

    def child(self, index, purpose='fixture'):
        path = self.root / ('suite_c' + str(index).zfill(2))
        (path / 'execution').mkdir(parents=True)
        value = {'run_id': path.name, 'purpose': purpose, 'protocol': 'realtime_choice_fixture_v1',
                 'research_adoption_permitted': False, 'fixture_case': ('calibration', 'repeated')[index - 1]}
        (path / 'execution/manifest.json').write_text(json.dumps(value), encoding='utf-8')
        return path

    def test_selects_actual_child_after_last_completed_progress(self):
        self.child(1)
        expected = self.child(2)
        (self.parent / 'progress.json').write_text('{"child_run_id":"suite_c01"}', encoding='utf-8')
        self.assertEqual(monitor.select_child(self.parent, 'suite', self.root)[0], expected)

    def test_refuses_non_fixture_and_does_not_fall_back(self):
        self.child(1)
        self.child(2, purpose='core')
        with self.assertRaisesRegex(ValueError, 'non-fixture'):
            monitor.select_child(self.parent, 'suite', self.root)

    def test_missing_actual_manifest_does_not_use_previous_completed_child(self):
        self.child(1)
        (self.root / 'suite_c02').mkdir()
        with self.assertRaises(FileNotFoundError):
            monitor.select_child(self.parent, 'suite', self.root)

    def live_evidence(self):
        first = self.child(1)
        second = self.child(2)
        manifest = monitor.read(first / 'execution/manifest.json')
        manifest.update(status='COMPLETED', pid=12, output_sha256={})
        (first / 'execution/manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        report = {'case': 'calibration', 'status': 'PASS', 'checks': {'outputs': True},
                  'child_run_id': first.name,
                  'execution_manifest_sha256': monitor.file_sha(first / 'execution/manifest.json')}
        (first / 'case_validation.json').write_text(json.dumps(report), encoding='utf-8')
        suite = {'run_id': 'suite', 'status': 'RUNNING', 'pid': 12, 'cases': [],
                 'factory_sha256': monitor.file_sha(self.parent / 'factory.py')}
        progress = {'completed_cases': 1, 'last_case': 'calibration',
                    'last_status': 'PASS', 'child_run_id': first.name}
        return suite, progress, [first, second]

    def test_live_completed_primary_receipt_counts_before_parent_flush(self):
        suite, progress, children = self.live_evidence()
        reported = monitor.reported_children(self.parent, suite, progress, children)
        self.assertEqual(reported, {'suite_c01'})
        self.assertEqual(len([p for p in children if p.name not in reported]), 1)

    def test_multiple_unreported_children_remain_visible(self):
        suite, progress, children = self.live_evidence()
        children.append(self.root / 'suite_c03')
        reported = monitor.reported_children(self.parent, suite, progress, children)
        self.assertEqual(len([p for p in children if p.name not in reported]), 2)

    def test_progress_cannot_supply_missing_primary_receipt(self):
        suite, progress, children = self.live_evidence()
        (children[0] / 'case_validation.json').unlink()
        with self.assertRaises(FileNotFoundError):
            monitor.reported_children(self.parent, suite, progress, children)

    def test_modified_manifest_or_output_fails_closed(self):
        for corrupt in ('manifest', 'output'):
            with self.subTest(corrupt=corrupt):
                suite, progress, children = self.live_evidence()
                path = children[0] / 'execution/manifest.json'
                if corrupt == 'manifest':
                    path.write_bytes(path.read_bytes() + b'\n')
                else:
                    value = monitor.read(path)
                    value['output_sha256'] = {'events.jsonl': 'incorrect'}
                    path.write_text(json.dumps(value), encoding='utf-8')
                    (children[0] / 'execution/events.jsonl').write_text('{}', encoding='utf-8')
                    receipt = monitor.read(children[0] / 'case_validation.json')
                    receipt['execution_manifest_sha256'] = monitor.file_sha(path)
                    (children[0] / 'case_validation.json').write_text(json.dumps(receipt), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'completed child'):
                    monitor.reported_children(self.parent, suite, progress, children)
                for child in children:
                    shutil.rmtree(child)

    def test_selected_case_uses_case_index_not_completion_count(self):
        suite, progress, children = self.live_evidence()
        first = children[0]
        manifest = monitor.read(first / 'execution/manifest.json')
        receipt = monitor.read(first / 'case_validation.json')
        manifest.update(run_id=children[1].name, fixture_case='repeated')
        path = children[1] / 'execution/manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        receipt.update(case='repeated', child_run_id=children[1].name,
                       execution_manifest_sha256=monitor.file_sha(path))
        (children[1] / 'case_validation.json').write_text(json.dumps(receipt), encoding='utf-8')
        progress.update(last_case='repeated', child_run_id=children[1].name)
        self.assertEqual(monitor.reported_children(self.parent, suite, progress, children[1:]), {'suite_c02'})

    def test_changed_factory_and_foreign_parent_case_fail_closed(self):
        suite, progress, children = self.live_evidence()
        with self.assertRaisesRegex(ValueError, 'receipts disagree'):
            monitor.reported_children(self.parent, {**suite, 'cases': [{'child_run_id': 'foreign'}]}, progress, children)
        (self.parent / 'factory.py').write_text("CASES = ('changed',)\n", encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'factory'):
            monitor.reported_children(self.parent, suite, progress, children)

    def test_forged_progress_and_failed_receipt_fail_closed(self):
        suite, progress, children = self.live_evidence()
        for field, value in [('completed_cases', 3), ('completed_cases', True),
                             ('last_case', 'repeated'), ('child_run_id', 'suite_c02'),
                             ('last_status', 'FAILED')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                monitor.reported_children(self.parent, suite, {**progress, field: value}, children)
        path = children[0] / 'case_validation.json'
        receipt = monitor.read(path)
        receipt['checks']['outputs'] = False
        path.write_text(json.dumps(receipt), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'completed child'):
            monitor.reported_children(self.parent, suite, progress, children)

    def test_pid_reuse_is_distinct_from_absence(self):
        created = {'created_at': '2026-10-19T02:00:00+00:00', 'CommandLine': 'python choice_technical.py fixture --run-id suite', 'ProcessId': 12}
        with patch.object(monitor.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(created))):
            self.assertEqual(monitor.process(12, '2026-10-18T20:00:00+09:00', 'suite')['identity'], 'reused')
        with patch.object(monitor.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '')):
            self.assertEqual(monitor.process(12, '2026-10-18T20:00:00+09:00', 'suite')['identity'], 'absent')

    def accounting(self):
        (self.root / 'people.csv').write_text('person_id\np1\np2\n', encoding='utf-8')
        event = {'time_sec': 0, 'event': 'person_state', 'person_id': 'p1', 'before': 'not_ready', 'after': 'travelling_walk'}
        (self.root / 'events.jsonl').write_text(json.dumps(event) + '\n', encoding='utf-8')
        with gzip.open(self.root / 'actor_observations.csv.gz', 'wt', encoding='utf-8') as stream:
            stream.write('time_sec,actor_id\n0.5,p1\n52.5,p1\n')
        return monitor.raw_accounting(self.root, self.root)

    def test_raw_actor_clock_and_person_accounting_are_independent(self):
        result = self.accounting()
        self.assertEqual(result['latest_event_time_sec'], 0)
        self.assertEqual(result['raw_actor_last_time_sec'], 52.5)
        self.assertEqual(result['person_states_from_events'], {'travelling_walk': 1, 'not_ready': 1})
        self.assertEqual(sum(result['person_states_from_events'].values()), result['population_rows'])

    def test_partial_gzip_is_explicitly_incomplete(self):
        self.accounting()
        path = self.root / 'actor_observations.csv.gz'
        path.write_bytes(path.read_bytes()[:-8])
        self.assertFalse(monitor.raw_accounting(self.root, self.root)['raw_actor_complete'])

    def test_person_state_chain_inconsistency_fails_closed(self):
        self.accounting()
        event = {'time_sec': 1, 'event': 'person_state', 'person_id': 'unknown', 'before': 'not_ready', 'after': 'admitted'}
        with (self.root / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event) + '\n')
        with self.assertRaisesRegex(ValueError, 'chain mismatch'):
            monitor.raw_accounting(self.root, self.root)


if __name__ == '__main__':
    unittest.main()
