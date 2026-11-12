"""Gmail SMTP transport (offline): classification by SMTP phase, no secret leakage, provider switch.

Rule (RFC 5321): before the end-of-data reply nothing is accepted -> unsent (retry or reject);
a lost connection during/after DATA may have been accepted -> never resend.
"""
import email
import smtplib
import socket
import socketserver
import ssl
import tempfile
import threading
import unittest
from email import policy
from pathlib import Path
from unittest import mock

import mail_worker
import smtp_mail
import watch
from graph_mail import TokenStore
from mail_outbox import AcceptanceUnknown, AuthRequired, Outbox, Rejected, TransportUnavailable
from smtp_mail import SmtpTransport

SENDER, TO, SECRET = 'sender.synthetic@example.invalid', 'to.synthetic@example.invalid', 'SYNTHETIC-APP-PASSWORD'
MESSAGE = {'id': 'e1', 'subject': '[JDRT監視] failed r1', 'body': '本文です', 'attachments': []}


class FakeSMTP:
    """Records calls; each phase can be told to raise or to return a reply code."""

    def __init__(self, login=None, mail=(250, b'ok'), rcpt=(250, b'ok'), data=(250, b'queued'), quit_error=None):
        self.plan = dict(login=login, mail=mail, rcpt=rcpt, data=data)
        self.quit_error, self.calls, self.payload = quit_error, [], None

    def _do(self, phase, *args):
        self.calls.append(phase)
        outcome = self.plan[phase]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def login(self, user, password):
        self.calls.append('login')
        self.logged_in = (user, password)
        if isinstance(self.plan['login'], BaseException):
            raise self.plan['login']

    def mail(self, sender):
        return self._do('mail', sender)

    def rcpt(self, to):
        return self._do('rcpt', to)

    def data(self, payload):
        self.payload = payload
        return self._do('data', payload)

    def quit(self):
        self.calls.append('quit')
        if self.quit_error:
            raise self.quit_error

    def close(self):
        self.calls.append('close')


def transport(fake=None, factory_error=None, password=SECRET):
    def factory(host, port, timeout):
        if factory_error:
            raise factory_error
        return fake
    return SmtpTransport(SENDER, TO, lambda: password, factory=factory)


class Build(unittest.TestCase):
    def test_message_has_headers_utf8_body_attachment_and_event_id(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'summary.csv'
            path.write_bytes(b'a,b\n1,2\n')
            message = {**MESSAGE, 'attachments': [{'name': 'summary.csv', 'path': str(path)},
                                                  {'name': 'gone.csv', 'path': str(Path(temp) / 'gone.csv')}]}
            built = email.message_from_bytes(smtp_mail.build_email(message, SENDER, TO), policy=policy.default)
        self.assertEqual((built['From'], built['To']), (SENDER, TO))
        self.assertEqual(built['Subject'], MESSAGE['subject'])
        self.assertEqual(built['X-JDRT-Event-Id'], 'e1')
        self.assertIn('本文です', built.get_body(preferencelist=('plain',)).get_content())
        self.assertEqual([p.get_filename() for p in built.iter_attachments()], ['summary.csv'])


class Happy(unittest.TestCase):
    def test_accepted_path_calls_each_phase_in_order_and_closes(self):
        fake = FakeSMTP()
        transport(fake).send(MESSAGE)
        self.assertEqual(fake.calls[:4], ['login', 'mail', 'rcpt', 'data'])
        self.assertEqual(fake.logged_in, (SENDER, SECRET))
        self.assertIn('quit', fake.calls)

    def test_a_failing_quit_after_acceptance_is_not_an_error(self):
        transport(FakeSMTP(quit_error=smtplib.SMTPServerDisconnected('bye'))).send(MESSAGE)


class Classification(unittest.TestCase):
    def check(self, expected, fake=None, factory_error=None):
        with self.assertRaises(expected):
            transport(fake, factory_error).send(MESSAGE)

    def test_connection_phase_failures_are_unsent(self):
        for error in (ConnectionRefusedError(), socket.timeout(), socket.gaierror(), ssl.SSLError(),
                      smtplib.SMTPConnectError(421, b'busy'), smtplib.SMTPServerDisconnected('greeting')):
            self.check(TransportUnavailable, factory_error=error)

    def test_authentication(self):
        self.check(AuthRequired, FakeSMTP(login=smtplib.SMTPAuthenticationError(535, b'bad')))
        self.check(TransportUnavailable, FakeSMTP(login=smtplib.SMTPServerDisconnected('x')))
        self.check(Rejected, FakeSMTP(login=smtplib.SMTPNotSupportedError('no auth')))

    def test_envelope_phase_is_never_unknown(self):
        self.check(Rejected, FakeSMTP(mail=(550, b'no')))
        self.check(TransportUnavailable, FakeSMTP(mail=(451, b'later')))
        self.check(TransportUnavailable, FakeSMTP(mail=smtplib.SMTPServerDisconnected('x')))
        self.check(Rejected, FakeSMTP(rcpt=(550, b'no such user')))
        self.check(TransportUnavailable, FakeSMTP(rcpt=(450, b'mailbox busy')))
        self.check(TransportUnavailable, FakeSMTP(rcpt=OSError('reset')))

    def test_data_command_refusal_is_a_clean_refusal(self):
        self.check(Rejected, FakeSMTP(data=smtplib.SMTPDataError(554, b'no')))
        self.check(TransportUnavailable, FakeSMTP(data=smtplib.SMTPDataError(451, b'later')))

    def test_lost_connection_during_data_may_have_been_accepted(self):
        for error in (smtplib.SMTPServerDisconnected('lost'), socket.timeout(), OSError('reset'), ssl.SSLError()):
            self.check(AcceptanceUnknown, FakeSMTP(data=error))

    def test_end_of_data_reply_decides(self):
        self.check(TransportUnavailable, FakeSMTP(data=(452, b'insufficient storage')))
        self.check(Rejected, FakeSMTP(data=(554, b'spam')))
        self.check(AcceptanceUnknown, FakeSMTP(data=(200, b'odd')))


class Secrets(unittest.TestCase):
    def test_password_never_appears_in_errors(self):
        for fake, expected in ((FakeSMTP(login=smtplib.SMTPAuthenticationError(535, SECRET.encode())), AuthRequired),
                               (FakeSMTP(data=smtplib.SMTPDataError(554, SECRET.encode())), Rejected),
                               (FakeSMTP(data=OSError(SECRET)), AcceptanceUnknown)):
            with self.assertRaises(expected) as caught:
                transport(fake).send(MESSAGE)
            self.assertNotIn(SECRET, str(caught.exception))
            self.assertNotIn(SECRET, repr(caught.exception))

    def test_missing_password_requires_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(Path(temp) / 's.bin', lambda b: bytes(x ^ 0x5A for x in b), lambda b: bytes(x ^ 0x5A for x in b))
            provider = smtp_mail.password_from_store(store)
            with self.assertRaises(AuthRequired):
                provider()
            smtp_mail.save_password(store, SECRET)
            self.assertEqual(provider(), SECRET)
            self.assertNotIn(SECRET.encode(), (Path(temp) / 's.bin').read_bytes())

    def test_module_has_no_embedded_password_or_address(self):
        text = Path(smtp_mail.__file__).read_text(encoding='utf-8')
        self.assertNotRegex(text, r'[A-Za-z0-9._%+-]+@gmail\.com')
        self.assertNotRegex(text, r'\b[a-z]{16}\b\s*[\'"]')


class Loopback(unittest.TestCase):
    """Real smtplib against 127.0.0.1 (no TLS): what the default connection classification really sees."""

    def free_port(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def test_closed_port_is_unsent(self):
        plain = SmtpTransport(SENDER, TO, lambda: SECRET, host='127.0.0.1', port=self.free_port(), use_ssl=False,
                              timeout=3)
        with self.assertRaises(TransportUnavailable):
            plain.send(MESSAGE)

    def test_server_that_hangs_up_at_the_greeting_is_unsent(self):
        class Hangup(socketserver.BaseRequestHandler):
            def handle(self):
                pass
        server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Hangup)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        plain = SmtpTransport(SENDER, TO, lambda: SECRET, host='127.0.0.1', port=server.server_address[1],
                              use_ssl=False, timeout=3)
        with self.assertRaises(TransportUnavailable):
            plain.send(MESSAGE)


class Provider(unittest.TestCase):
    def test_worker_builds_the_smtp_transport_from_config(self):
        with tempfile.TemporaryDirectory() as temp:
            config = {'mail_provider': 'gmail_smtp', 'mail_sender': SENDER, 'mail_to': TO}
            built = mail_worker.build_transport(config, Path(temp))
            self.assertIsInstance(built, SmtpTransport)
            for missing in ('mail_sender', 'mail_to'):
                with self.assertRaises(SystemExit):
                    mail_worker.build_transport({k: v for k, v in config.items() if k != missing}, Path(temp))
            with self.assertRaises(SystemExit):
                mail_worker.build_transport({**config, 'mail_provider': 'nope'}, Path(temp))

    def test_outbox_to_smtp_end_to_end_with_a_fake_server(self):
        with tempfile.TemporaryDirectory() as temp:
            box = Outbox(Path(temp) / 'outbox')
            box.enqueue({'id': 'e1', 'kind': 'failed', 'target': 't',
                         'evidence': {'target_id': 'r1', 'status': 'FAILED', 'source': 's'}})
            fake = FakeSMTP()
            self.assertEqual(box.send_next(transport(fake), 1000), 'accepted')
            self.assertEqual(watch.read_json(Path(temp) / 'outbox' / 'e1.json')['state'], 'accepted')


if __name__ == '__main__':
    unittest.main()
