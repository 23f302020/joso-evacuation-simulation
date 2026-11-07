"""SP-04 (offline): Graph sendMail transport and OAuth token handling with fake HTTP only."""
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

import graph_mail
from graph_mail import GraphAuth, GraphTransport, HttpConnectError, HttpResponseLost, TokenStore
from mail_outbox import AcceptanceUnknown, AuthRequired, TransportUnavailable

TO = 'recipient@example.invalid'
SECRET = 'SECRET-ACCESS-TOKEN-VALUE'
REFRESH = 'SECRET-REFRESH-TOKEN-VALUE'
MESSAGE = {'id': 'e1', 'subject': '[JDRT監視] failed r1', 'body': '本文', 'attachments': []}


class FakeHttp:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({'url': url, 'headers': headers, 'body': body})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def transport(*outcomes, token=SECRET):
    http = FakeHttp(*outcomes)
    return GraphTransport(lambda: token, TO, http=http), http


class Mapping(unittest.TestCase):
    def test_202_is_accepted_and_request_is_well_formed(self):
        graph, http = transport((202, ''))
        graph.send(MESSAGE)
        call = http.calls[0]
        self.assertTrue(call['url'].endswith('/me/sendMail'))
        self.assertEqual(call['headers']['Authorization'], 'Bearer ' + SECRET)
        payload = json.loads(call['body'])
        self.assertEqual(payload['message']['toRecipients'][0]['emailAddress']['address'], TO)
        self.assertEqual(payload['message']['subject'], MESSAGE['subject'])
        self.assertEqual(payload['message']['body']['content'], '本文')

    def test_unreachable_server_is_retryable_nothing_sent(self):
        graph, _ = transport(HttpConnectError())
        with self.assertRaises(TransportUnavailable):
            graph.send(MESSAGE)

    def test_lost_response_is_unknown_and_never_resent(self):
        graph, _ = transport(HttpResponseLost())
        with self.assertRaises(AcceptanceUnknown):
            graph.send(MESSAGE)

    def test_401_requires_signin(self):
        graph, _ = transport((401, 'x'))
        with self.assertRaises(AuthRequired):
            graph.send(MESSAGE)

    def test_throttling_is_retryable_and_server_errors_are_unknown(self):
        for status in (429, 503):
            with self.assertRaises(TransportUnavailable, msg=status):
                transport((status, ''))[0].send(MESSAGE)
        for status in (500, 502, 504):
            with self.assertRaises(AcceptanceUnknown, msg=status):
                transport((status, ''))[0].send(MESSAGE)

    def test_client_errors_are_preserved_without_leaking_body_or_token(self):
        for status in (400, 403):
            with self.assertRaises(RuntimeError) as caught:
                transport((status, 'detail ' + SECRET))[0].send(MESSAGE)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_attachments_are_base64_and_missing_ones_are_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'summary.csv'
            path.write_bytes(b'a,b\n1,2\n')
            message = {**MESSAGE, 'attachments': [{'name': 'summary.csv', 'path': str(path), 'bytes': 8},
                                                  {'name': 'gone.csv', 'path': str(Path(temp) / 'gone.csv'), 'bytes': 1}]}
            graph, http = transport((202, ''))
            graph.send(message)
        attached = json.loads(http.calls[0]['body'])['message']['attachments']
        self.assertEqual([a['name'] for a in attached], ['summary.csv'])
        self.assertEqual(base64.b64decode(attached[0]['contentBytes']), b'a,b\n1,2\n')


def form_http(*outcomes):
    calls = []

    def call(url, data):
        calls.append((url, dict(data)))
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
    call.calls = calls
    return call


def fake_protect(raw):
    return b'P1' + bytes(b ^ 0x5A for b in raw)


def fake_unprotect(blob):
    assert blob[:2] == b'P1'
    return bytes(b ^ 0x5A for b in blob[2:])


class Auth(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'token.bin'
        self.store = TokenStore(self.path, fake_protect, fake_unprotect)
        self.now = [1000.0]

    def auth(self, *outcomes):
        http = form_http(*outcomes)
        return GraphAuth('client-id-synthetic', self.store, http, clock=lambda: self.now[0]), http

    def test_cache_file_holds_no_plaintext_tokens(self):
        self.store.save({'access_token': SECRET, 'refresh_token': REFRESH, 'expires_at': 5000})
        raw = self.path.read_bytes()
        self.assertNotIn(SECRET.encode(), raw)
        self.assertNotIn(REFRESH.encode(), raw)
        self.assertEqual(self.store.load()['refresh_token'], REFRESH)

    @unittest.skipUnless(sys.platform == 'win32', 'DPAPI is Windows only')
    def test_real_dpapi_round_trip_and_no_plaintext(self):
        store = TokenStore(self.path)
        store.save({'access_token': SECRET, 'refresh_token': REFRESH, 'expires_at': 5000})
        self.assertNotIn(SECRET.encode(), self.path.read_bytes())
        self.assertEqual(store.load()['access_token'], SECRET)

    def test_no_cache_requires_signin(self):
        auth, http = self.auth()
        with self.assertRaises(AuthRequired):
            auth.access_token()
        self.assertEqual(http.calls, [])

    def test_valid_cached_token_needs_no_network(self):
        self.store.save({'access_token': SECRET, 'refresh_token': REFRESH, 'expires_at': 5000})
        auth, http = self.auth()
        self.assertEqual(auth.access_token(), SECRET)
        self.assertEqual(http.calls, [])

    def test_expired_token_is_refreshed_and_cache_updated(self):
        self.store.save({'access_token': 'old', 'refresh_token': REFRESH, 'expires_at': 1050})
        auth, http = self.auth((200, {'access_token': 'new', 'refresh_token': 'rotated', 'expires_in': 3600}))
        self.assertEqual(auth.access_token(), 'new')
        self.assertEqual(http.calls[0][1]['grant_type'], 'refresh_token')
        self.assertEqual(self.store.load()['refresh_token'], 'rotated')
        self.assertEqual(self.store.load()['expires_at'], 1000 + 3600)

    def test_refresh_keeps_old_refresh_token_when_none_returned(self):
        self.store.save({'access_token': 'old', 'refresh_token': REFRESH, 'expires_at': 0})
        auth, _ = self.auth((200, {'access_token': 'new', 'expires_in': 60}))
        auth.access_token()
        self.assertEqual(self.store.load()['refresh_token'], REFRESH)

    def test_rejected_refresh_requires_signin_and_network_failure_is_retryable(self):
        self.store.save({'access_token': 'old', 'refresh_token': REFRESH, 'expires_at': 0})
        auth, _ = self.auth((400, {'error': 'invalid_grant'}))
        with self.assertRaises(AuthRequired):
            auth.access_token()
        auth, _ = self.auth(HttpConnectError())
        with self.assertRaises(TransportUnavailable):
            auth.access_token()

    def test_device_code_signin_polls_until_approved_and_stores_tokens(self):
        auth, http = self.auth(
            (200, {'device_code': 'dc', 'user_code': 'ABCD-1234', 'verification_uri': 'https://example.invalid/device',
                   'expires_in': 900, 'interval': 5}),
            (400, {'error': 'authorization_pending'}),
            (400, {'error': 'slow_down'}),
            (200, {'access_token': SECRET, 'refresh_token': REFRESH, 'expires_in': 3600}))
        shown, waits = [], []
        auth.sign_in(prompt=shown.append, sleep=waits.append)
        self.assertIn('ABCD-1234', shown[0])
        self.assertEqual(waits, [5, 5, 10])
        self.assertEqual(http.calls[0][1]['scope'], 'Mail.Send offline_access')
        self.assertEqual(self.store.load()['access_token'], SECRET)
        self.assertNotIn(SECRET, ''.join(shown))

    def test_declined_or_expired_device_code_stops_with_authrequired(self):
        for error in ('expired_token', 'authorization_declined', 'bad_verification_code'):
            auth, _ = self.auth(
                (200, {'device_code': 'dc', 'user_code': 'X', 'verification_uri': 'u', 'expires_in': 900, 'interval': 1}),
                (400, {'error': error}))
            with self.assertRaises(AuthRequired, msg=error):
                auth.sign_in(prompt=lambda _: None, sleep=lambda _: None)
            self.assertIsNone(self.store.load())


class Secrets(unittest.TestCase):
    def test_module_has_no_embedded_client_id_or_token(self):
        text = Path(graph_mail.__file__).read_text(encoding='utf-8')
        self.assertNotRegex(text, r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


if __name__ == '__main__':
    unittest.main()
