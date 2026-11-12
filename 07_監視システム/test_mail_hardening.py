"""Review-driven hardening (independent T3 review A1-A9): races, retry window, rejection vs unknown,
corrupt-file containment, 401 refresh, token-endpoint classification, connect-vs-response phases."""
import json
import os
import socket
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import graph_mail
import mail_outbox
import mail_worker
import watch
from graph_mail import GraphAuth, GraphTransport, HttpConnectError, HttpResponseLost, TokenStore
from mail_outbox import AcceptanceUnknown, AuthRequired, Outbox, Rejected, TransportUnavailable

EVENT = {'id': 'e1', 'kind': 'failed', 'target': 't', 'evidence': {'target_id': 'r1', 'status': 'FAILED', 'source': 's'}}


class FakeTransport:
    def __init__(self, *outcomes, repeat=None):
        self.outcomes, self.repeat, self.sent = list(outcomes), repeat, []

    def send(self, message):
        self.sent.append(message['id'])
        outcome = self.outcomes.pop(0) if self.outcomes else self.repeat
        if isinstance(outcome, BaseException):
            raise outcome


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / 'outbox'

    def state(self, name='e1'):
        return watch.read_json(self.dir / (name + '.json'))['state']


class Race(Base):
    def test_enqueue_never_overwrites_a_message_created_and_sent_meanwhile(self):
        box, other = Outbox(self.dir), Outbox(self.dir)
        real = mail_outbox.compose

        busy = []

        def racing(event, attachments, max_bytes):
            if not busy:
                busy.append(1)  # the other process runs with the real compose
                with mock.patch.object(mail_outbox, 'compose', real):
                    other.enqueue(event)
                    other.send_next(FakeTransport(), 1000)
            return real(event, attachments, max_bytes)

        with mock.patch.object(mail_outbox, 'compose', racing):
            box.enqueue(EVENT)
        self.assertEqual(self.state(), 'accepted')
        fake = FakeTransport()
        self.assertIsNone(box.send_next(fake, 10 ** 6))
        self.assertEqual(fake.sent, [])


class RetryWindow(Base):
    def test_default_policy_retries_with_capped_backoff_for_two_days_then_preserves(self):
        box = Outbox(self.dir)
        box.enqueue(EVENT)
        fake = FakeTransport(repeat=TransportUnavailable())
        now, start, gaps, result = 1000.0, 1000.0, [], None
        for _ in range(400):
            result = box.send_next(fake, now)
            message = watch.read_json(self.dir / 'e1.json')
            if result == 'failed_preserved':
                break
            gaps.append(message['next_attempt_epoch'] - now)
            now = message['next_attempt_epoch']
        self.assertEqual(result, 'failed_preserved')
        self.assertGreater(now - start, 2 * 86400 - 3600)
        self.assertLessEqual(max(gaps), 3600)
        self.assertTrue(watch.read_json(self.dir / 'e1.json')['unsent_confirmed'])

    def test_resume_unsent_returns_only_failures_confirmed_unsent(self):
        box = Outbox(self.dir, max_attempts=1)
        box.enqueue(EVENT)
        box.send_next(FakeTransport(TransportUnavailable()), 1000)
        box.enqueue({**EVENT, 'id': 'e2'})
        box.send_next(FakeTransport(RuntimeError('x')), 1000)
        self.assertEqual((self.state('e1'), self.state('e2')), ('failed_preserved', 'uncertain_preserved'))
        self.assertEqual(box.resume_unsent(), 1)
        self.assertEqual((self.state('e1'), self.state('e2')), ('queued', 'uncertain_preserved'))


class Classification(Base):
    def test_definite_rejection_is_failed_and_confirmed_unsent_without_retry(self):
        box = Outbox(self.dir)
        box.enqueue(EVENT)
        fake = FakeTransport(Rejected('graph status 403'))
        self.assertEqual(box.send_next(fake, 1000), 'failed_preserved')
        self.assertTrue(watch.read_json(self.dir / 'e1.json')['unsent_confirmed'])
        self.assertIsNone(box.send_next(fake, 10 ** 6))

    def test_unexpected_error_may_have_been_sent_so_it_is_uncertain(self):
        box = Outbox(self.dir)
        box.enqueue(EVENT)
        self.assertEqual(box.send_next(FakeTransport(RuntimeError('boom')), 1000), 'uncertain_preserved')
        self.assertEqual(watch.read_json(self.dir / 'e1.json')['error_type'], 'RuntimeError')
        self.assertEqual(box.resume_unsent(), 0)


class Containment(Base):
    def test_corrupt_file_is_quarantined_and_does_not_stop_the_queue(self):
        box = Outbox(self.dir)
        (self.dir / 'bad.json').write_text('{not json', encoding='utf-8')
        box.enqueue(EVENT)
        self.assertEqual(box.recover_after_restart(), 0)
        self.assertEqual(box.send_next(FakeTransport(), 1000), 'accepted')
        self.assertFalse((self.dir / 'bad.json').exists())
        self.assertTrue((self.dir / 'bad.json.corrupt').exists())

    def test_worker_loop_survives_a_failing_tick_and_logs_only_the_error_type(self):
        runtime = Path(self.temp.name)
        calls = []

        def flaky(config, rt, transport, now):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError('secret-looking detail')
            return None

        stops = iter([False, False, False, True])
        with mock.patch.object(mail_worker, 'worker_tick', flaky):
            mail_worker.run({'mail_enabled': True}, runtime, FakeTransport(), sleep=lambda _: None,
                            clock=lambda: 1.0, stop=lambda: next(stops))
        self.assertEqual(len(calls), 3)
        log = (runtime / 'mail_worker_errors.jsonl').read_text(encoding='utf-8')
        self.assertIn('PermissionError', log)
        self.assertNotIn('secret-looking', log)

    def test_keepalive_runs_and_its_failure_is_contained(self):
        runtime = Path(self.temp.name)
        seen = []

        def keepalive():
            seen.append(1)
            raise OSError('no network')

        stops = iter([False, False, True])
        mail_worker.run({'mail_enabled': True}, runtime, FakeTransport(), sleep=lambda _: None,
                        clock=lambda: 1.0, stop=lambda: next(stops), keepalive=keepalive, keepalive_every=0)
        self.assertEqual(len(seen), 2)


class Http(unittest.TestCase):
    def test_status_mapping_distinguishes_rejection_from_unknown(self):
        def run(status):
            transport = GraphTransport(lambda: 't', 'to@example.invalid', http=lambda *a: (status, ''))
            transport.send({'subject': 's', 'body': 'b', 'attachments': []})
        for status in (400, 403, 404, 413):
            with self.assertRaises(Rejected, msg=status):
                run(status)
        for status in (200, 201, 204, 408, 501, 500, 502, 504):
            with self.assertRaises(AcceptanceUnknown, msg=status):
                run(status)
        for status in (429, 503):
            with self.assertRaises(TransportUnavailable, msg=status):
                run(status)

    def test_401_refreshes_once_then_requires_signin(self):
        tokens, hits = iter(['old', 'new']), []
        outcomes = iter([(401, ''), (202, '')])

        def http(url, headers, body, timeout):
            hits.append(headers['Authorization'])
            return next(outcomes)

        invalidated = []
        transport = GraphTransport(lambda: next(tokens), 'to@example.invalid', http=http,
                                   on_unauthorized=lambda: invalidated.append(1))
        transport.send({'subject': 's', 'body': 'b', 'attachments': []})
        self.assertEqual(hits, ['Bearer old', 'Bearer new'])
        self.assertEqual(invalidated, [1])
        always = GraphTransport(lambda: 'x', 'to@example.invalid', http=lambda *a: (401, ''),
                                on_unauthorized=lambda: None)
        with self.assertRaises(AuthRequired):
            always.send({'subject': 's', 'body': 'b', 'attachments': []})


class TokenEndpoint(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TokenStore(Path(self.temp.name) / 't.bin', lambda b: b'P' + b, lambda b: b[1:])
        self.store.save({'access_token': 'old', 'refresh_token': 'r', 'expires_at': 0})

    def auth(self, outcome):
        return GraphAuth('client-synthetic', self.store, lambda url, data: outcome, clock=lambda: 1000.0)

    def test_transient_and_unparsable_responses_are_retryable(self):
        for outcome in ((500, {}), (429, {}), (502, {}), (200, {})):
            with self.assertRaises(TransportUnavailable, msg=outcome):
                self.auth(outcome).access_token()

    def test_client_configuration_errors_require_signin_or_setup(self):
        for error in ('invalid_client', 'unauthorized_client', 'invalid_grant'):
            with self.assertRaises(AuthRequired, msg=error):
                self.auth((400, {'error': error})).access_token()

    def test_failure_to_save_the_refreshed_token_still_returns_it(self):
        auth = self.auth((200, {'access_token': 'new', 'refresh_token': 'r2', 'expires_in': 3600}))
        with mock.patch.object(self.store, 'save', side_effect=PermissionError('locked')):
            self.assertEqual(auth.access_token(), 'new')

    def test_invalidate_forces_the_next_call_to_refresh(self):
        self.store.save({'access_token': 'cached', 'refresh_token': 'r', 'expires_at': 10 ** 9})
        auth = self.auth((200, {'access_token': 'fresh', 'expires_in': 3600}))
        self.assertEqual(auth.access_token(), 'cached')
        auth.invalidate()
        self.assertEqual(auth.access_token(), 'fresh')


class Phases(unittest.TestCase):
    """Loopback only: a closed port never reached a server; a dropped connection may have been processed."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def free_port(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def serve(self, handler):
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True
        server = Server(('127.0.0.1', 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]

    def test_closed_port_is_a_connect_error(self):
        with self.assertRaises(HttpConnectError):
            graph_mail._post('http://127.0.0.1:%d/' % self.free_port(), {}, b'{}', 3)

    def test_connection_dropped_without_a_response_is_lost_not_unsent(self):
        class Drop(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(65536)
        port = self.serve(Drop)
        with self.assertRaises(HttpResponseLost):
            graph_mail._post('http://127.0.0.1:%d/' % port, {}, b'{}', 3)

    def test_normal_response_is_returned(self):
        class Ok(socketserver.BaseRequestHandler):
            def handle(self):
                data = b''
                while b'\r\n\r\n' not in data:
                    chunk = self.request.recv(65536)
                    if not chunk:
                        return
                    data += chunk
                head, _, body = data.partition(b'\r\n\r\n')
                length = next((int(l.split(b':')[1]) for l in head.split(b'\r\n')
                               if l.lower().startswith(b'content-length')), 0)
                while len(body) < length:  # read the whole request: closing early resets the connection
                    chunk = self.request.recv(65536)
                    if not chunk:
                        break
                    body += chunk
                self.request.sendall(b'HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        port = self.serve(Ok)
        self.assertEqual(graph_mail._post('http://127.0.0.1:%d/' % port, {}, b'{}', 3), (202, ''))


if __name__ == '__main__':
    unittest.main()
