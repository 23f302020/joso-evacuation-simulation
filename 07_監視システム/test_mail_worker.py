"""Mail worker (offline, fake transport): event -> queue -> one send per tick, exclusive, restart-safe."""
import tempfile
import unittest
from pathlib import Path

import mail_worker
import watch
from mail_outbox import AuthRequired, Outbox

CONFIG = {'mail_enabled': True}


class FakeTransport:
    def __init__(self, *outcomes):
        self.outcomes, self.sent = list(outcomes), []

    def send(self, message):
        self.sent.append(message['id'])
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome


class WorkerCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)

    def event(self, target, kind):
        watch.save_event(self.runtime / 'events', target, kind,
                         {'target_id': target, 'status': 'X', 'source': target}, ai_diagnostics=False)

    def states(self):
        return sorted(watch.read_json(p)['state'] for p in (self.runtime / 'outbox').glob('*.json'))


class Tick(WorkerCase):
    def test_disabled_sends_nothing_and_creates_nothing(self):
        self.event('t1', 'failed')
        fake = FakeTransport()
        self.assertIsNone(mail_worker.worker_tick({}, self.runtime, fake, 1000))
        self.assertEqual(fake.sent, [])
        self.assertFalse((self.runtime / 'outbox').exists())

    def test_event_reaches_transport_exactly_once(self):
        self.event('t1', 'failed')
        self.event('t2', 'completed')
        fake = FakeTransport()
        self.assertEqual(mail_worker.worker_tick(CONFIG, self.runtime, fake, 1000), 'accepted')
        self.assertIsNone(mail_worker.worker_tick(CONFIG, self.runtime, fake, 2000))
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(self.states(), ['accepted'])

    def test_one_message_per_tick(self):
        self.event('t1', 'failed')
        self.event('t2', 'stalled')
        fake = FakeTransport()
        mail_worker.worker_tick(CONFIG, self.runtime, fake, 1000)
        self.assertEqual(self.states(), ['accepted', 'queued'])

    def test_auth_expiry_halts_until_resume_after_signin(self):
        self.event('t1', 'failed')
        fake = FakeTransport(AuthRequired())
        self.assertEqual(mail_worker.worker_tick(CONFIG, self.runtime, fake, 1000), 'auth_expired')
        self.assertIsNone(mail_worker.worker_tick(CONFIG, self.runtime, fake, 5000))
        self.assertEqual(mail_worker.resume(self.runtime), 1)
        self.assertEqual(mail_worker.worker_tick(CONFIG, self.runtime, fake, 5001), 'accepted')


class Restart(WorkerCase):
    def test_start_preserves_a_message_left_sending_and_never_resends_it(self):
        self.event('t1', 'failed')
        mail_worker.worker_tick(CONFIG, self.runtime, FakeTransport(), 1000)
        path = next((self.runtime / 'outbox').glob('*.json'))
        message = watch.read_json(path)
        message['state'] = 'sending'
        watch.atomic_json(path, message)
        self.assertEqual(mail_worker.start(self.runtime), 1)
        fake = FakeTransport()
        self.assertIsNone(mail_worker.worker_tick(CONFIG, self.runtime, fake, 10 ** 6))
        self.assertEqual(fake.sent, [])
        self.assertEqual(self.states(), ['uncertain_preserved'])


class Loop(WorkerCase):
    def test_run_processes_then_stops_and_releases_its_lock(self):
        self.event('t1', 'failed')
        fake = FakeTransport()
        calls = []

        def stop():
            calls.append(1)
            return len(calls) > 2

        mail_worker.run(CONFIG, self.runtime, fake, sleep=lambda _: None, clock=lambda: 1000.0, stop=stop)
        self.assertEqual(len(fake.sent), 1)
        lock = watch.Exclusive(self.runtime / 'mail_worker.lock')  # free again after run()
        lock.close()

    def test_second_worker_is_refused_while_one_runs(self):
        held = watch.Exclusive(self.runtime / 'mail_worker.lock')
        self.addCleanup(held.close)
        with self.assertRaises(RuntimeError):
            mail_worker.run(CONFIG, self.runtime, FakeTransport(), sleep=lambda _: None,
                            clock=lambda: 1.0, stop=lambda: True)


class Build(unittest.TestCase):
    def test_recipient_must_be_configured(self):
        with self.assertRaises(SystemExit):
            mail_worker.build_transport({'runtime': tempfile.gettempdir()}, Path(tempfile.gettempdir()))


if __name__ == '__main__':
    unittest.main()
