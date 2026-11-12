"""Independent-review (Fable) fixes for the Gmail SMTP path: deterministic errors are not 'uncertain',
AUTH 4xx is transient, resume resets the retry window, check/send-test commands, worker halt on
auth failure, loopback-only plaintext, stable Message-ID, visible retries."""
import email
import smtplib
import tempfile
import unittest
from email import policy
from pathlib import Path
from unittest import mock

import mail_outbox
import mail_worker
import smtp_mail
import watch
from graph_mail import TokenStore
from mail_outbox import AcceptanceUnknown, AuthRequired, Outbox, Rejected, TransportUnavailable
from smtp_mail import SmtpTransport
from test_smtp_mail import FakeSMTP, MESSAGE, SENDER, TO, transport

GOOD = 'abcdefghijklmnop'
EVENT = {'id': 'e1', 'kind': 'failed', 'target': 't', 'evidence': {'target_id': 'r1', 'status': 'FAILED', 'source': 's'}}


def xor(data):
    return bytes(b ^ 0x5A for b in data)


class Password(unittest.TestCase):
    def test_save_removes_all_whitespace_and_rejects_anything_that_is_not_16_ascii_letters_or_digits(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(Path(temp) / 's.bin', xor, xor)
            smtp_mail.save_password(store, 'abcd efgh ijkl　mnop')
            self.assertEqual(store.load()[smtp_mail.SECRET_KEY], GOOD)
            for bad in ('short', 'abcdefghijklmnop1', 'abcdefghijklmnoé', 'abcdefghijklmn!p'):
                with self.assertRaises(ValueError) as caught:
                    smtp_mail.save_password(store, bad)
                self.assertNotIn(bad, str(caught.exception))
            with self.assertRaises(ValueError):
                smtp_mail.save_password(store, '   ')

    def test_a_non_ascii_password_that_slipped_through_is_a_sign_in_problem_not_uncertain(self):
        fake = FakeSMTP(login=UnicodeEncodeError('ascii', 'x', 0, 1, 'bad'))
        with self.assertRaises(AuthRequired):
            transport(fake).send(MESSAGE)


class Auth(unittest.TestCase):
    def check(self, code, expected):
        with self.assertRaises(expected, msg=code):
            transport(FakeSMTP(login=smtplib.SMTPAuthenticationError(code, b'x'))).send(MESSAGE)

    def test_temporary_auth_replies_are_retried_permanent_ones_need_sign_in(self):
        for code in (421, 450, 451, 454):
            self.check(code, TransportUnavailable)
        for code in (534, 535, 538):
            self.check(code, AuthRequired)


class Build(unittest.TestCase):
    def built(self, message):
        return email.message_from_bytes(smtp_mail.build_email(message, SENDER, TO), policy=policy.default)

    def test_control_characters_in_the_subject_do_not_break_the_message(self):
        built = self.built({**MESSAGE, 'subject': 'a\nb c\rd'})
        self.assertEqual(built['Subject'], 'a b c d')

    def test_message_id_is_stable_per_event_and_marks_auto_submitted(self):
        first, second = self.built(MESSAGE), self.built(MESSAGE)
        self.assertEqual(first['Message-ID'], second['Message-ID'])
        self.assertIn('e1', first['Message-ID'])
        self.assertEqual(first['Auto-Submitted'], 'auto-generated')

    def test_a_message_that_cannot_be_built_is_a_definite_refusal(self):
        with mock.patch.object(smtp_mail, 'build_email', side_effect=ValueError('x')):
            with self.assertRaises(Rejected):
                transport(FakeSMTP()).send(MESSAGE)


class Connection(unittest.TestCase):
    def test_default_connection_pins_the_ehlo_name_and_verifies_tls(self):
        with mock.patch.object(smtp_mail.smtplib, 'SMTP_SSL') as ssl_cls:
            SmtpTransport(SENDER, TO, lambda: GOOD)._connect('smtp.gmail.com', 465, 30)
        kwargs = ssl_cls.call_args.kwargs
        self.assertEqual(kwargs['local_hostname'], 'localhost')
        self.assertIsNotNone(kwargs['context'])

    def test_plaintext_is_refused_except_on_loopback(self):
        with self.assertRaises(ValueError):
            SmtpTransport(SENDER, TO, lambda: GOOD, host='smtp.example.invalid', use_ssl=False)
        SmtpTransport(SENDER, TO, lambda: GOOD, host='127.0.0.1', use_ssl=False)

    def test_the_end_of_data_reply_gets_a_long_timeout(self):
        class Sock:
            timeouts = []

            def settimeout(self, value):
                self.timeouts.append(value)
        fake = FakeSMTP()
        fake.sock = Sock()
        transport(fake).send(MESSAGE)
        self.assertEqual(Sock.timeouts, [300])


class CheckAndSendTest(unittest.TestCase):
    def test_check_connects_and_logs_in_but_sends_nothing(self):
        fake = FakeSMTP()
        transport(fake).check()
        self.assertEqual(fake.calls[0], 'login')
        self.assertNotIn('mail', fake.calls)
        self.assertNotIn('data', fake.calls)

    def test_check_reports_the_same_classification(self):
        with self.assertRaises(AuthRequired):
            transport(FakeSMTP(login=smtplib.SMTPAuthenticationError(535, b'x'))).check()

    def test_send_test_shows_the_content_and_sends_only_after_yes(self):
        shown = []
        fake = FakeSMTP()
        self.assertEqual(smtp_mail.send_test(transport(fake), TO, input_fn=lambda _: 'no', output_fn=shown.append),
                         'cancelled')
        self.assertEqual(fake.calls, [])
        self.assertTrue(any(TO in line for line in shown))
        self.assertTrue(any('試験メール' in line for line in shown))
        self.assertEqual(smtp_mail.send_test(transport(fake), TO, input_fn=lambda _: ' yes ', output_fn=shown.append),
                         'sent')
        self.assertIn('data', fake.calls)


class Queue(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / 'outbox'

    def test_resume_after_signin_starts_a_fresh_retry_window(self):
        box = Outbox(self.dir)
        box.enqueue(EVENT)
        path = self.dir / 'e1.json'
        message = watch.read_json(path)
        message.update(state='auth_expired', first_attempt_epoch=1000, attempts=2)
        watch.atomic_json(path, message)
        self.assertEqual(box.resume_after_signin(), 1)
        far_later = 1000 + 5 * 86400

        class Down:
            def send(self, message):
                raise TransportUnavailable('connect:TimeoutError')
        self.assertEqual(box.send_next(Down(), far_later), 'queued')

    def test_the_reason_of_a_retry_is_recorded_without_server_text(self):
        box = Outbox(self.dir)
        box.enqueue(EVENT)

        class Down:
            def send(self, message):
                raise TransportUnavailable('rcpt:450 secret=hunter2')
        box.send_next(Down(), 1000)
        recorded = watch.read_json(self.dir / 'e1.json')['last_error']
        self.assertTrue(recorded.startswith('rcpt:450'))
        self.assertNotIn('=', recorded)

    def test_smtp_failures_carry_a_safe_stage_code(self):
        with self.assertRaises(TransportUnavailable) as caught:
            transport(FakeSMTP(rcpt=(450, b'busy'))).send(MESSAGE)
        self.assertEqual(str(caught.exception), 'rcpt:450')
        with self.assertRaises(TransportUnavailable) as caught:
            transport(factory_error=TimeoutError()).send(MESSAGE)
        self.assertEqual(str(caught.exception), 'connect:TimeoutError')

    def test_retries_become_visible_after_three_attempts(self):
        runtime = Path(self.temp.name)
        outbox = runtime / 'outbox'
        outbox.mkdir()
        for name, attempts in (('a', 2), ('b', 3)):
            watch.atomic_json(outbox / (name + '.json'),
                              {'schema': 'simulation_watch_mail_v1', 'id': name, 'state': 'queued',
                               'attempts': attempts, 'last_error': 'connect:TimeoutError'})
        watch.surface_mail_trouble({'diagnostics_enabled': False}, runtime)
        events = [watch.read_json(p) for p in (runtime / 'events').glob('*.json')]
        self.assertEqual([e['kind'] for e in events], ['mail_retrying'])
        self.assertIn('connect:TimeoutError', events[0]['evidence']['status'])
        self.assertFalse(watch.mail_worthy('mail_retrying'))


class WorkerHalt(unittest.TestCase):
    def test_no_new_login_attempts_while_a_message_waits_for_sign_in(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            box = Outbox(runtime / 'outbox')
            box.enqueue(EVENT)
            box.enqueue({**EVENT, 'id': 'e2'})
            path = runtime / 'outbox' / 'e1.json'
            message = watch.read_json(path)
            message['state'] = 'auth_expired'
            watch.atomic_json(path, message)
            fake = FakeSMTP()
            self.assertIsNone(mail_worker.worker_tick({'mail_enabled': True}, runtime, transport(fake), 1000))
            self.assertEqual(fake.calls, [])


if __name__ == '__main__':
    unittest.main()
