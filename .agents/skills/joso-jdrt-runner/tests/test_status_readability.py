"""Reader-facing summaries use synthetic states, without adopting any result."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import choice_sync_status as sync
from status_readability import normalize_progress


class ReaderSummaryTests(unittest.TestCase):
    def state(self):
        return {'recorded_cells': 2, 'registered_cells': 9, 'running': ['example'],
                'unrecorded': [], 'unresolved_failures': [], 'unresolved_launches': []}

    def test_running_is_a_dated_observation_and_not_adoption(self):
        observed = {'status': 'RUNNING', 'pid_alive': True,
                    'progress': {'at_jst': '2001-02-03T04:05:06+09:00', 'time_sec': 30}}
        result = sync.reader_summary(self.state(), observed, False, '2001-02-03T04:00:00+09:00')
        self.assertIn('9回のうち2回', result)
        self.assertIn('実行中', result)
        self.assertIn('04:05', result)
        self.assertNotIn('PASS', result)
        self.assertNotIn('優れています', result)

    def test_finished_unrecorded_is_not_reported_as_accepted(self):
        state = self.state()
        state.update(running=[], unrecorded=['example'])
        result = sync.reader_summary(state, {'status': 'COMPLETED', 'pid_alive': False, 'progress': None}, False, '2001-02-03T04:00:00+09:00')
        self.assertIn('計算が終わり', result)
        self.assertIn('確認・記録', result)
        self.assertIn('9回のうち2回', result)

    def test_hold_and_dead_process_never_claim_running_or_permission(self):
        for hold in (False, True):
            with self.subTest(hold=hold):
                result = sync.reader_summary(self.state(), {'status': 'RUNNING', 'pid_alive': False, 'progress': None}, hold, '2001-02-03T04:00:00+09:00')
                self.assertIn('状態の確認が必要', result)
                self.assertIn('開始できません', result)

    def test_missing_progress_is_not_a_recent_observation(self):
        result = sync.reader_summary(self.state(), {'status': 'RUNNING', 'pid_alive': True, 'progress': None}, False, '2001-02-03T04:00:00+09:00')
        self.assertIn('進み具合は未確認', result)

    def test_recorder_line_is_normalized_without_altering_marker_or_history(self):
        before = ('\ufeffHISTORY R0 / seed=1\r\n<!-- PROGRESS_LOG_BEGIN -->\r\n'
                  '### 2001-02-03\r\n<!-- choice_record:example -->\r\n'
                  '- R0 / seed=1：独立検証PASS・正式記録（example）。\r\n'
                  '<!-- PROGRESS_LOG_END -->\r\nTAIL')
        after = normalize_progress(before)
        self.assertIn('確認と正式な記録が終わりました', after)
        self.assertIn('設定番号=1、実行番号=example', after)
        self.assertIn('<!-- choice_record:example -->', after)
        self.assertEqual(after.count('\r\n'), before.count('\r\n'))
        self.assertTrue(after.startswith('\ufeffHISTORY R0 / seed=1'))
        self.assertEqual(normalize_progress(after), after)

    def test_unresolved_failure_blocks_next_experiment_without_claiming_adoption(self):
        state = self.state()
        state.update(running=[], unresolved_failures=['example'])
        result = sync.reader_summary(state, None, False, '2001-02-03T04:00:00+09:00')
        self.assertIn('開始できません', result)
        self.assertIn('9回のうち2回', result)


if __name__ == '__main__':
    unittest.main()
