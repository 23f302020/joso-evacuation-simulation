"""Technical monitoring edge cases using synthetic, temporary evidence only."""
import gzip
import json
from pathlib import Path
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
