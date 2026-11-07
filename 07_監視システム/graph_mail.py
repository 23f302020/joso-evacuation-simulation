"""Microsoft Graph sendMail transport and OAuth device-code sign-in, standard library only.

The transport follows the mail_outbox contract: nothing sent -> TransportUnavailable (retry),
sign-in needed -> AuthRequired (stop), definite refusal -> Rejected, possibly accepted ->
AcceptanceUnknown (never resend). Tokens are cached only as Windows DPAPI blobs (current user);
they are never logged or returned in exception text. The client id comes from config/environment,
never from source.
"""
import argparse
import base64
import ctypes
import http.client
import json
import os
from ctypes import wintypes
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from mail_outbox import AcceptanceUnknown, AuthRequired, Rejected, TransportUnavailable

SEND_URL = 'https://graph.microsoft.com/v1.0/me/sendMail'
AUTHORITY = 'https://login.microsoftonline.com/consumers/oauth2/v2.0/'
SCOPE = 'Mail.Send offline_access'
SKEW_SEC = 120
SIGNIN_ERRORS = ('invalid_grant', 'interaction_required', 'consent_required', 'invalid_client',
                 'unauthorized_client')


class HttpConnectError(Exception):
    """The connection was never established; the request cannot have been processed."""


class HttpResponseLost(Exception):
    """The request may have reached the server but no usable response arrived."""


def _marked(base, state):
    class Marked(base):
        def connect(self):
            super().connect()  # includes any proxy tunnel
            state['connected'] = True
    return Marked


class _HttpHandler(urllib.request.HTTPHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def http_open(self, req):
        return self.do_open(_marked(http.client.HTTPConnection, self.state), req)


class _HttpsHandler(urllib.request.HTTPSHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def https_open(self, req):
        return self.do_open(_marked(http.client.HTTPSConnection, self.state), req, context=self._context)


def _post(url, headers, body, timeout):
    """(status, text). Keeps urllib's proxy handling, but records whether the connection was ever
    established: a failure before that is provably unsent; any failure after may have been processed."""
    state = {'connected': False}
    opener = urllib.request.build_opener(_HttpHandler(state), _HttpsHandler(state))
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8', 'replace')
    except urllib.error.URLError:
        raise (HttpResponseLost() if state['connected'] else HttpConnectError()) from None
    except Exception:
        raise HttpResponseLost() from None


def post_json(url, headers, body, timeout):
    return _post(url, headers, body, timeout)


def post_form(url, data):
    status, text = _post(url, {'Content-Type': 'application/x-www-form-urlencoded'},
                         urllib.parse.urlencode(data).encode(), 30)
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = {}
    return status, parsed if isinstance(parsed, dict) else {}


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]


def _dpapi(function, raw):
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    source = _Blob(len(raw), ctypes.cast(ctypes.create_string_buffer(raw, len(raw)), ctypes.POINTER(ctypes.c_char)))
    result = _Blob()
    if function == 'protect':
        ok = crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result))
    else:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result))
    if not ok:
        raise OSError('DPAPI failed')
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def dpapi_protect(raw):
    return _dpapi('protect', raw)


def dpapi_unprotect(blob):
    return _dpapi('unprotect', blob)


class TokenStore:
    def __init__(self, path, protect=dpapi_protect, unprotect=dpapi_unprotect):
        self.path, self.protect, self.unprotect = Path(path), protect, unprotect

    def save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        temp.write_bytes(self.protect(json.dumps(value).encode('utf-8')))
        os.replace(temp, self.path)

    def load(self):
        try:
            return json.loads(self.unprotect(self.path.read_bytes()).decode('utf-8'))
        except Exception:
            return None  # missing, other user, or damaged: sign-in is required


class GraphAuth:
    def __init__(self, client_id, store, http=post_form, clock=time.time):
        self.client_id, self.store, self.http, self.clock = client_id, store, http, clock

    def _tokens(self, body, previous_refresh=None):
        return {'access_token': body['access_token'],
                'refresh_token': body.get('refresh_token') or previous_refresh,
                'expires_at': self.clock() + float(body.get('expires_in', 0))}

    def sign_in(self, prompt=print, sleep=time.sleep):
        status, info = self.http(AUTHORITY + 'devicecode', {'client_id': self.client_id, 'scope': SCOPE})
        if status != 200 or 'device_code' not in info:
            raise RuntimeError('device code request failed')
        prompt(f"{info['verification_uri']} を開き、コード {info['user_code']} を入力してください。")
        interval, deadline = info.get('interval', 5), self.clock() + info.get('expires_in', 900)
        while True:
            sleep(interval)
            if self.clock() > deadline:
                raise AuthRequired('device code expired')
            status, body = self.http(AUTHORITY + 'token', {
                'client_id': self.client_id, 'device_code': info['device_code'],
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'})
            if status == 200 and 'access_token' in body:
                self.store.save(self._tokens(body))
                return
            error = body.get('error')
            if error == 'authorization_pending':
                continue
            if error == 'slow_down':
                interval += 5
                continue
            raise AuthRequired(str(error))

    def invalidate(self):
        """Treat the cached access token as expired (after a 401) so the next call refreshes it."""
        cached = self.store.load()
        if cached:
            cached['expires_at'] = 0
            try:
                self.store.save(cached)
            except OSError:
                pass

    def access_token(self):
        cached = self.store.load()
        if not cached or not cached.get('refresh_token'):
            raise AuthRequired('not signed in')
        if cached.get('expires_at', 0) - SKEW_SEC > self.clock():
            return cached['access_token']
        try:
            status, body = self.http(AUTHORITY + 'token', {
                'client_id': self.client_id, 'grant_type': 'refresh_token',
                'refresh_token': cached['refresh_token'], 'scope': SCOPE})
        except (HttpConnectError, HttpResponseLost):
            raise TransportUnavailable() from None
        if status == 200:
            if 'access_token' not in body:
                raise TransportUnavailable()  # unparsable or proxy page: not a sign-in problem
            try:
                self.store.save(self._tokens(body, cached['refresh_token']))
            except OSError:
                pass  # the token in hand is valid; a lost rotation surfaces later as invalid_grant
            return body['access_token']
        if status == 429 or status >= 500 or not body:
            raise TransportUnavailable()
        raise AuthRequired(str(body.get('error')))


class GraphTransport:
    def __init__(self, token_provider, recipient, http=post_json, timeout=30, on_unauthorized=None):
        self.token_provider, self.recipient, self.http, self.timeout = token_provider, recipient, http, timeout
        self.on_unauthorized = on_unauthorized

    def _attachments(self, message):
        items = []
        for item in message.get('attachments', []):
            try:
                data = Path(item['path']).read_bytes()
            except OSError:
                continue  # vanished since queuing; the body already names it
            items.append({'@odata.type': '#microsoft.graph.fileAttachment', 'name': item['name'],
                          'contentType': 'application/octet-stream',
                          'contentBytes': base64.b64encode(data).decode('ascii')})
        return items

    def _send_once(self, message, token):
        payload = {'message': {'subject': message['subject'],
                               'body': {'contentType': 'Text', 'content': message['body']},
                               'toRecipients': [{'emailAddress': {'address': self.recipient}}],
                               'attachments': self._attachments(message)},
                   'saveToSentItems': True}
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
        try:
            status, _ = self.http(SEND_URL, headers, json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                  self.timeout)
        except HttpConnectError:
            raise TransportUnavailable() from None
        except HttpResponseLost:
            raise AcceptanceUnknown() from None
        return status

    def send(self, message):
        status = self._send_once(message, self.token_provider())
        if status == 401 and self.on_unauthorized is not None:
            # 401 means the request was not processed: refresh once and retry before asking for sign-in.
            self.on_unauthorized()
            status = self._send_once(message, self.token_provider())
        if status == 202:
            return
        if status == 401:
            raise AuthRequired('unauthorized')
        if status in (429, 503):
            raise TransportUnavailable()
        if 400 <= status < 500 and status not in (401, 408, 429):
            raise Rejected(f'graph status {status}')  # body is not echoed: it may contain request data
        raise AcceptanceUnknown()  # other 2xx, 408, other 5xx: the message may have been taken


def build_auth(config, runtime):
    client_id = os.environ.get('JDRT_MAIL_CLIENT_ID') or config.get('mail_client_id')
    if not client_id:
        raise SystemExit('mail client id missing: set JDRT_MAIL_CLIENT_ID or config mail_client_id')
    return GraphAuth(client_id, TokenStore(Path(runtime) / 'mail_token.bin'))


def main():
    from watch import BASE, read_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['signin'])
    parser.add_argument('--config', type=Path, default=BASE / 'config.json')
    args = parser.parse_args()
    config = read_json(args.config)
    build_auth(config, config['runtime']).sign_in()
    print('signed in; token cached (DPAPI, current user)')


if __name__ == '__main__':
    sys.exit(main())
