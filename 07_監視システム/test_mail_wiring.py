"""SP-05: only 'all targets complete' and 'abnormal stop' reach the mail outbox (offline, fail closed)."""
import tempfile
import unittest
from pathlib import Path

import watch

ACTIVE_T = {'status': 'RUNNING', 'historical': False, 'purpose': None}


def done(name='a', **extra):
    return {'status': 'COMPLETED', 'historical': False, 'purpose': 'core', 'target_id': name,
            'source': 'D:/ws/runs/' + name + '/manifest.json', **extra}


class MailWorthy(unittest.TestCase):
    def test_abnormal_stops_and_all_complete_only(self):
        for kind in ('failed', 'process_absent', 'process_unknown', 'stalled', 'process_identity_changed',
                     'process_command_mismatch', 'state_missing', 'unreadable_state', 'all_complete',
                     'parent_stopped', 'parent_progress'):
            self.assertTrue(watch.mail_worthy(kind), kind)
        for kind in ('completed', 'nonzero_teleports', 'nonzero_collisions', 'log_error', 'log_truncated',
                     'unknown_status', 'monitoring_gap', 'target_identity_changed', 'oversize_log_line', ''):
            self.assertFalse(watch.mail_worthy(kind), kind)


class AllComplete(unittest.TestCase):
    def targets(self, *items):
        return {'targets': {str(i): item for i, item in enumerate(items)}}

    def test_never_fires_without_an_expected_count(self):
        state = self.targets(done('a'), done('b'))
        self.assertIsNone(watch.all_complete_evidence({}, state))
        self.assertIsNone(watch.all_complete_evidence({'expected_completed_targets': 0}, state))
        self.assertIsNone(watch.all_complete_evidence({'expected_completed_targets': True}, state))
        self.assertIsNone(watch.all_complete_evidence({'expected_completed_targets': '2'}, state))

    def test_fires_only_when_expected_count_reached_and_nothing_active(self):
        config = {'expected_completed_targets': 2}
        self.assertIsNone(watch.all_complete_evidence(config, self.targets(done('a'))))
        self.assertIsNone(watch.all_complete_evidence(config, self.targets(done('a'), ACTIVE_T)))
        evidence = watch.all_complete_evidence(config, self.targets(done('a'), done('b')))
        self.assertEqual(evidence['completed_targets'], 2)
        self.assertIn('ALL_COMPLETE', evidence['status'])

    def test_gap_between_sequential_cells_is_not_all_complete(self):
        # 70 cells run one after another: after cell 1 nothing is active, but 1 < 70.
        self.assertIsNone(watch.all_complete_evidence({'expected_completed_targets': 70},
                                                      self.targets(done('a'))))

    def test_historical_and_fixture_targets_are_not_counted(self):
        config = {'expected_completed_targets': 2}
        state = self.targets(done('a'), done('b', historical=True), {**done('c'), 'purpose': 'fixture'})
        self.assertIsNone(watch.all_complete_evidence(config, state))

    def test_failed_targets_are_reported_not_hidden(self):
        config = {'expected_completed_targets': 1}
        failed = {'status': 'FAILED', 'historical': False, 'purpose': 'core', 'source': 'D:/ws/runs/f/manifest.json'}
        evidence = watch.all_complete_evidence(config, self.targets(done('a'), failed))
        self.assertIn('失敗保全1', evidence['status'])


class Wiring(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.events = self.runtime / 'events'
        self.outbox = self.runtime / 'outbox'

    def event(self, target, kind):
        watch.save_event(self.events, target, kind, {'target_id': target, 'status': 'X', 'source': target},
                         ai_diagnostics=False)

    def test_disabled_by_default_writes_nothing(self):
        self.event('t1', 'failed')
        self.assertEqual(watch.sync_mail_outbox({}, self.runtime), 0)
        self.assertFalse(self.outbox.exists() and any(self.outbox.glob('*.json')))

    def test_only_mail_worthy_events_are_enqueued_once(self):
        for target, kind in (('t1', 'failed'), ('t2', 'completed'), ('t3', 'nonzero_collisions'),
                             ('t4', 'stalled'), ('t5', 'all_complete')):
            self.event(target, kind)
        config = {'mail_enabled': True}
        self.assertEqual(watch.sync_mail_outbox(config, self.runtime), 3)
        self.assertEqual(watch.sync_mail_outbox(config, self.runtime), 0)
        kinds = sorted(watch.read_json(p)['subject'].split()[1] for p in self.outbox.glob('*.json'))
        self.assertEqual(kinds, ['all_complete', 'failed', 'stalled'])

    def test_parent_loop_stop_is_enqueued_once_per_stop(self):
        # SP-14: the runner-side parent loop places one event per stop (unique target per stop id).
        self.event('choice-parent-stop:a', 'parent_stopped')
        self.event('choice-parent-stop:a', 'parent_stopped')
        self.event('choice-parent-stop:b', 'parent_stopped')
        self.assertEqual(watch.sync_mail_outbox({'mail_enabled': True}, self.runtime), 2)
        subjects = [watch.read_json(p)['subject'] for p in self.outbox.glob('*.json')]
        self.assertTrue(all('parent_stopped' in s for s in subjects))

    def test_enqueue_is_queued_only_and_has_no_network(self):
        self.event('t1', 'failed')
        watch.sync_mail_outbox({'mail_enabled': True}, self.runtime)
        message = next(self.outbox.glob('*.json'))
        self.assertEqual(watch.read_json(message)['state'], 'queued')

    def test_detect_all_complete_saves_one_event(self):
        config = {'expected_completed_targets': 1}
        state = {'targets': {'a': done('a')}}
        watch.detect_all_complete(config, self.runtime, state)
        watch.detect_all_complete(config, self.runtime, state)
        files = list(self.events.glob('*.json'))
        self.assertEqual(len(files), 1)
        self.assertEqual(watch.read_json(files[0])['kind'], 'all_complete')

    def test_detect_all_complete_silent_when_not_complete(self):
        watch.detect_all_complete({'expected_completed_targets': 2}, self.runtime,
                                  {'targets': {'a': done('a')}})
        self.assertFalse(self.events.exists() and any(self.events.glob('*.json')))


if __name__ == '__main__':
    unittest.main()
