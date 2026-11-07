"""Mail outbox contract (offline): durable queue, idempotency, no blind resend, bounded work."""
import tempfile
import unittest
from pathlib import Path

import mail_outbox
import watch
from mail_outbox import AcceptanceUnknown, AuthRequired, Outbox, TransportUnavailable

EVENT = {'id': 'e1', 'kind': 'completed', 'target': 'runs/r1/manifest.json',
         'evidence': {'target_id': 'r1', 'status': 'COMPLETED', 'source': 'D:/x/runs/r1/manifest.json',
                      'execution_timing': {'started_at_utc': '2026-11-07T00:00:00+00:00',
                                           'finished_at_utc': '2026-11-07T01:30:05+00:00',
                                           'elapsed_sec': 5405.0, 'status': 'complete'}}}


class FakeTransport:
    def __init__(self, *outcomes):
        self.outcomes, self.sent, self.states = list(outcomes), [], []
        self.directory = None

    def send(self, message):
        if self.directory is not None:
            self.states.append(watch.read_json(self.directory / (message['id'] + '.json'))['state'])
        self.sent.append(message['id'])
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome


class OutboxCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / 'outbox'
        self.box = Outbox(self.dir, max_attachment_bytes=1000, max_attempts=3, backoff_sec=60)

    def transport(self, *outcomes):
        fake = FakeTransport(*outcomes)
        fake.directory = self.dir
        return fake

    def state(self, name='e1'):
        return watch.read_json(self.dir / (name + '.json'))['state']


class Compose(OutboxCase):
    def test_body_has_identity_timing_caution_and_no_direction_claim(self):
        message = watch.read_json(self.box.enqueue(EVENT))
        self.assertIn('r1', message['subject'])
        body = message['body']
        for text in ('r1', 'COMPLETED', '開始（JST）：2026-11-07 09:00:00', '1時間30分5.000秒',
                     'D:/x/runs/r1/manifest.json', '検証PASS', '受信確認'):
            self.assertIn(text, body)
        self.assertNotIn('有利', body)

    def test_small_attachment_is_included_and_large_is_omitted_with_location(self):
        small = Path(self.temp.name) / 'summary.csv'
        big = Path(self.temp.name) / 'trace.bin'
        small.write_bytes(b'a' * 100)
        big.write_bytes(b'b' * 5000)
        message = watch.read_json(self.box.enqueue(EVENT, [small, big]))
        self.assertEqual([a['name'] for a in message['attachments']], ['summary.csv'])
        self.assertEqual([a['name'] for a in message['omitted']], ['trace.bin'])
        self.assertIn(str(big), message['body'])
        self.assertIn('5000', message['body'])

    def test_total_attachment_size_is_capped(self):
        files = []
        for index in range(3):
            path = Path(self.temp.name) / f'f{index}.csv'
            path.write_bytes(b'x' * 400)
            files.append(path)
        message = watch.read_json(self.box.enqueue(EVENT, files))
        self.assertEqual(len(message['attachments']), 2)
        self.assertEqual(len(message['omitted']), 1)

    def test_missing_attachment_is_listed_as_omitted(self):
        message = watch.read_json(self.box.enqueue(EVENT, [Path(self.temp.name) / 'nope.csv']))
        self.assertEqual(message['attachments'], [])
        self.assertEqual(message['omitted'][0]['name'], 'nope.csv')


class Delivery(OutboxCase):
    def test_enqueue_is_idempotent_per_event_and_keeps_existing_state(self):
        first = self.box.enqueue(EVENT)
        self.box.send_next(self.transport(), 1000)
        second = self.box.enqueue(EVENT)
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.dir.glob('*.json'))), 1)
        self.assertEqual(self.state(), 'accepted')

    def test_accepted_message_is_never_sent_again_and_claim_precedes_send(self):
        self.box.enqueue(EVENT)
        fake = self.transport()
        self.assertEqual(self.box.send_next(fake, 1000), 'accepted')
        self.assertIsNone(self.box.send_next(fake, 2000))
        self.assertEqual(fake.sent, ['e1'])
        self.assertEqual(fake.states, ['sending'])

    def test_network_failure_backs_off_then_retries_then_gives_up(self):
        self.box.enqueue(EVENT)
        fake = self.transport(TransportUnavailable(), TransportUnavailable(), TransportUnavailable())
        self.assertEqual(self.box.send_next(fake, 1000), 'queued')
        self.assertIsNone(self.box.send_next(fake, 1030))
        self.assertEqual(self.box.send_next(fake, 1061), 'queued')
        self.assertIsNone(self.box.send_next(fake, 1061 + 119))
        self.assertEqual(self.box.send_next(fake, 1061 + 121), 'failed_preserved')
        self.assertIsNone(self.box.send_next(fake, 10 ** 6))
        self.assertEqual(len(fake.sent), 3)

    def test_auth_expiry_stops_sending_until_resumed_after_signin(self):
        self.box.enqueue(EVENT)
        fake = self.transport(AuthRequired())
        self.assertEqual(self.box.send_next(fake, 1000), 'auth_expired')
        self.assertIsNone(self.box.send_next(fake, 5000))
        self.assertEqual(self.box.resume_after_signin(), 1)
        self.assertEqual(self.box.send_next(fake, 5001), 'accepted')

    def test_unknown_acceptance_is_preserved_and_not_resent(self):
        self.box.enqueue(EVENT)
        fake = self.transport(AcceptanceUnknown())
        self.assertEqual(self.box.send_next(fake, 1000), 'uncertain_preserved')
        self.assertIsNone(self.box.send_next(fake, 10 ** 6))
        self.assertEqual(self.box.resume_after_signin(), 0)
        self.assertEqual(len(fake.sent), 1)

    def test_message_left_sending_by_a_crash_becomes_uncertain_and_is_not_resent(self):
        path = self.box.enqueue(EVENT)
        message = watch.read_json(path)
        message['state'] = 'sending'
        watch.atomic_json(path, message)
        self.assertEqual(self.box.recover_after_restart(), 1)
        self.assertEqual(self.state(), 'uncertain_preserved')
        fake = self.transport()
        self.assertIsNone(self.box.send_next(fake, 10 ** 6))
        self.assertEqual(fake.sent, [])

    def test_unexpected_error_is_preserved_as_uncertain_not_retried(self):
        self.box.enqueue(EVENT)
        fake = self.transport(RuntimeError('boom'))
        self.assertEqual(self.box.send_next(fake, 1000), 'uncertain_preserved')
        self.assertIsNone(self.box.send_next(fake, 10 ** 6))
        self.assertEqual(watch.read_json(self.dir / 'e1.json')['error_type'], 'RuntimeError')

    def test_one_message_per_call_keeps_the_caller_responsive(self):
        for name in ('e1', 'e2', 'e3'):
            self.box.enqueue({**EVENT, 'id': name})
        fake = self.transport()
        self.box.send_next(fake, 1000)
        self.assertEqual(fake.sent, ['e1'])
        self.assertEqual([self.state(n) for n in ('e1', 'e2', 'e3')], ['accepted', 'queued', 'queued'])


if __name__ == '__main__':
    unittest.main()
