"""mail_selftest: one confirmed test notice through the real outbox; never touches events or research files."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import mail_selftest
import watch

NOW = datetime(2026, 11, 13, 3, 15, 0, tzinfo=timezone.utc)


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name).resolve() / 'runtime'
        (self.runtime / 'events').mkdir(parents=True)
        self.config = {'runtime': str(self.runtime), 'mail_enabled': True, 'mail_to': 'to.synthetic@example.invalid'}
        self.lock = watch.Exclusive(self.runtime / 'mail_worker.lock')  # stands in for the live worker
        self.addCleanup(lambda: self.lock.close())
        self.out = []
        self.time = 0.0

    def run_test(self, answer='yes', worker_state=None, wait_sec=30, config=None, token='t1'):
        message = self.runtime / 'outbox' / f'selftest-20261113T031500Z-{token}.json'

        def sleep(seconds):
            self.time += seconds
            if worker_state and message.exists():  # the worker picks it up during the wait
                watch.atomic_json(message, dict(watch.read_json(message), state=worker_state))

        return mail_selftest.queue_test(config or self.config, input_fn=lambda _: answer, output_fn=self.out.append,
                                        clock=lambda: self.time, sleep=sleep, wait_sec=wait_sec, now=NOW,
                                        token=token)

    def outbox(self):
        folder = self.runtime / 'outbox'
        return sorted(p.name for p in folder.glob('*.json')) if folder.exists() else []

    def test_accepted_by_the_worker_is_success_and_nothing_else_is_written(self):
        self.assertEqual(self.run_test(worker_state='accepted'), 0)
        self.assertEqual(self.outbox(), ['selftest-20261113T031500Z-t1.json'])
        message = watch.read_json(self.runtime / 'outbox' / 'selftest-20261113T031500Z-t1.json')
        self.assertEqual((message['state'], message['schema']), ('accepted', 'simulation_watch_mail_v1'))
        self.assertIn('研究とは無関係', message['body'])
        self.assertEqual(list((self.runtime / 'events').iterdir()), [])  # the monitor's events are untouched

    def test_not_picked_up_in_time_stays_queued_and_is_reported(self):
        self.assertEqual(self.run_test(wait_sec=15), 2)
        self.assertEqual(watch.read_json(self.runtime / 'outbox' / 'selftest-20261113T031500Z-t1.json')['state'], 'queued')
        self.assertTrue(self.out[-1].startswith('still queued'))

    def test_trouble_states_are_failures(self):
        for state in ('auth_expired', 'uncertain_preserved', 'failed_preserved'):
            with self.subTest(state=state):
                for path in (self.runtime / 'outbox').glob('*.json'):
                    path.unlink()
                self.assertEqual(self.run_test(worker_state=state), 1)
                self.assertTrue(self.out[-1].startswith(state))

    def test_nothing_is_queued_without_yes_mail_enabled_or_a_live_worker(self):
        self.assertEqual(self.run_test(answer='no'), 1)
        self.assertEqual(self.outbox(), [])
        self.assertEqual(self.run_test(config=dict(self.config, mail_enabled=False)), 1)
        self.assertEqual(self.outbox(), [])
        self.lock.close()
        self.assertEqual(self.run_test(), 1)  # lock file present but nobody holds it
        self.assertEqual(self.outbox(), [])
        self.lock = watch.Exclusive(self.runtime / 'mail_worker.lock')

    def test_rerun_in_the_same_second_is_a_new_message_and_the_address_is_masked(self):
        self.assertEqual(self.run_test(worker_state='accepted'), 0)
        self.assertEqual(self.run_test(worker_state='accepted', token='t2'), 0)
        self.assertEqual(self.outbox(), ['selftest-20261113T031500Z-t1.json', 'selftest-20261113T031500Z-t2.json'])
        self.assertNotIn('to.synthetic@example.invalid', '\n'.join(self.out))
        self.assertIn('t***@example.invalid', '\n'.join(self.out))
        self.assertNotEqual(mail_selftest.selftest_event(NOW)['id'], mail_selftest.selftest_event(NOW)['id'])


if __name__ == '__main__':
    unittest.main()
