"""SMTP transport (Gmail by default) that honours the mail_outbox contract.

Classification follows the SMTP phase (RFC 5321). Before the end-of-data reply nothing has been
accepted, so a failure there is unsent (retry) or a definite refusal. A connection lost during or
after DATA may have been accepted: never resend. Error text from the server is never copied into
exceptions or the queue (it could echo credentials); only a stage code such as 'rcpt:450' or
'connect:TimeoutError' is kept.

The app password lives only as a Windows DPAPI blob (current user), set with `smtp_mail.py setup`.
Neither the password nor any address is embedded in the source.

Commands: `setup` (store the app password), `check` (connect and sign in; sends nothing),
`send-test` (shows the message and sends one test mail only after you type yes).
"""
import argparse
import email.policy
import email.utils
import getpass
import re
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
import sys

from graph_mail import TokenStore
from mail_outbox import AcceptanceUnknown, AuthRequired, Rejected, TransportUnavailable

SECRET_KEY = 'smtp_app_password'
LOOPBACK = ('127.0.0.1', 'localhost', '::1')
DATA_REPLY_TIMEOUT_SEC = 300  # RFC 5321 4.5.3.2.6 recommends minutes for the end-of-data reply
LINE_BREAKS = re.compile(r'[\r\n\x0b\x0c\x1c-\x1e\x85  ]')
TEST_SUBJECT = '[JDRT監視] 試験メール'
TEST_BODY = ('これは JDRT 監視システムの試験メールです。\n'
             'このメールが届けば、メール送信の設定は正しく動いています。\n'
             '研究の結果ではなく、完了や異常を意味しません。')


def build_email(message, sender, recipient):
    msg = EmailMessage(policy=email.policy.SMTP)
    msg['From'], msg['To'] = sender, recipient
    msg['Subject'] = LINE_BREAKS.sub(' ', str(message['subject']))
    msg['Date'] = email.utils.formatdate(usegmt=True)
    # Stable per event: a manual re-send after an uncertain outcome carries the same id.
    event_id = re.sub(r'[^A-Za-z0-9_-]', '', str(message.get('id', ''))) or 'noid'
    msg['Message-ID'] = f"<jdrt-{event_id}@{sender.rsplit('@', 1)[-1]}>"
    msg['X-JDRT-Event-Id'] = event_id
    msg['Auto-Submitted'] = 'auto-generated'
    msg.set_content(message['body'], charset='utf-8', cte='base64')
    for item in message.get('attachments', []):
        try:
            data = Path(item['path']).read_bytes()
        except OSError:
            continue  # vanished since queuing; the body already names it
        msg.add_attachment(data, maintype='application', subtype='octet-stream', filename=item['name'])
    return msg.as_bytes(policy=email.policy.SMTP)


ANSI_SEQUENCE = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')


def clean_password(raw):
    """Google shows the 16 characters in groups, and a terminal paste can bring invisible markers
    (bracketed-paste escapes, a BOM, a trailing newline): drop all of that before validating."""
    return re.sub(r'[\s\x00-\x1f\x7f﻿]+', '', ANSI_SEQUENCE.sub('', raw))


def _password_problem(cleaned):
    """Explain a rejected input by counts only: the characters themselves are never echoed."""
    if not cleaned:
        return 'nothing was entered (empty input)'
    non_ascii = sum(ord(c) > 127 for c in cleaned)
    symbols = sum(c.isascii() and not c.isalnum() for c in cleaned)
    letters = len(cleaned) - non_ascii - symbols
    return (f'an app password is 16 ASCII letters or digits; the input has {len(cleaned)} characters '
            f'({letters} letters/digits, {symbols} symbols, {non_ascii} non-ASCII)')


def save_password(store, password):
    cleaned = clean_password(password)
    if not re.fullmatch(r'[A-Za-z0-9]{16}', cleaned):
        raise ValueError(_password_problem(cleaned))
    store.save({SECRET_KEY: cleaned})


def password_from_store(store):
    def provider():
        data = store.load()
        password = data.get(SECRET_KEY) if data else None
        if not password:
            raise AuthRequired('smtp app password not set')
        return password
    return provider


def _stage(stage, detail):
    return f'{stage}:{detail}'


class SmtpTransport:
    def __init__(self, sender, recipient, password_provider, host='smtp.gmail.com', port=None, use_ssl=True,
                 timeout=30, factory=None):
        if not use_ssl and host not in LOOPBACK:
            raise ValueError('plaintext SMTP is allowed only on loopback')
        self.sender, self.recipient, self.password_provider = sender, recipient, password_provider
        self.host, self.use_ssl, self.timeout = host, use_ssl, timeout
        self.port = port if port is not None else (465 if use_ssl else 25)
        self.factory = factory or self._connect

    def _connect(self, host, port, timeout):
        # A fixed EHLO name: the PC name may be non-ASCII and would otherwise travel in the headers.
        if self.use_ssl:
            return smtplib.SMTP_SSL(host, port, timeout=timeout, local_hostname='localhost',
                                    context=ssl.create_default_context())
        return smtplib.SMTP(host, port, timeout=timeout, local_hostname='localhost')

    def _open(self):
        try:
            return self.factory(self.host, self.port, self.timeout)
        except (OSError, smtplib.SMTPException) as error:
            raise TransportUnavailable(_stage('connect', type(error).__name__)) from None  # no greeting: unsent

    def send(self, message):
        password = self.password_provider()  # AuthRequired propagates: nothing was attempted
        try:
            payload = build_email(message, self.sender, self.recipient)
        except (ValueError, UnicodeError):
            raise Rejected('message could not be built') from None  # deterministic: retrying cannot help
        server = self._open()
        try:
            self._login(server, password)
            self._envelope(server)
            self._data(server, payload)
        finally:
            self._close(server)

    def check(self):
        """Connect and sign in, nothing else. Same classification as send()."""
        password = self.password_provider()
        server = self._open()
        try:
            self._login(server, password)
        finally:
            self._close(server)

    def _login(self, server, password):
        try:
            server.login(self.sender, password)
        except smtplib.SMTPAuthenticationError as error:
            if 400 <= error.smtp_code < 500:  # 454 "too many login attempts" and the like: temporary
                raise TransportUnavailable(_stage('login', error.smtp_code)) from None
            raise AuthRequired('smtp authentication failed') from None
        except UnicodeError:
            raise AuthRequired('smtp credentials are not ASCII') from None
        except smtplib.SMTPNotSupportedError:
            raise Rejected('smtp authentication unsupported') from None
        except (smtplib.SMTPException, OSError) as error:
            raise TransportUnavailable(_stage('login', type(error).__name__)) from None

    def _envelope(self, server):
        steps = (('mail', lambda: server.mail(self.sender), (250,)),
                 ('rcpt', lambda: server.rcpt(self.recipient), (250, 251)))
        for phase, call, accepted in steps:
            try:
                code, _ = call()
            except (smtplib.SMTPException, OSError) as error:
                raise TransportUnavailable(_stage(phase, type(error).__name__)) from None  # nothing accepted yet
            if code in accepted:
                continue
            if 400 <= code < 500:
                raise TransportUnavailable(_stage(phase, code))
            raise Rejected(f'smtp {phase} refused ({code})')

    def _data(self, server, payload):
        sock = getattr(server, 'sock', None)
        if sock is not None:
            try:
                sock.settimeout(DATA_REPLY_TIMEOUT_SEC)
            except OSError:
                pass
        try:
            code, _ = server.data(payload)
        except smtplib.SMTPDataError as error:  # refusal of the DATA command itself: no body was taken
            if 400 <= error.smtp_code < 500:
                raise TransportUnavailable(_stage('data', error.smtp_code)) from None
            raise Rejected(f'smtp data refused ({error.smtp_code})') from None
        except (smtplib.SMTPException, OSError):
            raise AcceptanceUnknown() from None  # may have been accepted before the connection broke
        if code == 250:
            return
        if 400 <= code < 500:
            raise TransportUnavailable(_stage('data', code))  # RFC: a 4xx end-of-data reply means not accepted
        if 500 <= code < 600:
            raise Rejected(f'smtp end of data refused ({code})')
        raise AcceptanceUnknown()

    @staticmethod
    def _close(server):
        for name in ('quit', 'close'):
            try:
                getattr(server, name)()
            except Exception:
                pass  # the outcome of the message is already decided


def send_test(transport, recipient, input_fn=input, output_fn=print):
    """Show exactly what would be sent and send it only after the operator types yes."""
    output_fn(f'宛先: {recipient}')
    output_fn(f'件名: {TEST_SUBJECT}')
    output_fn('本文:')
    output_fn(TEST_BODY)
    if input_fn('この内容で試験メールを1通送ります。送る場合は yes と入力: ').strip() != 'yes':
        return 'cancelled'
    transport.send({'id': 'jdrt-test', 'subject': TEST_SUBJECT, 'body': TEST_BODY, 'attachments': []})
    return 'sent'


def _report(error):
    if isinstance(error, AuthRequired):
        return 'sign-in failed (app password wrong or revoked): run setup again'
    if isinstance(error, TransportUnavailable):
        return f"could not reach or sign in (retryable): {error or 'no detail'}"
    if isinstance(error, Rejected):
        return f'refused (retrying will not help): {error}'
    if isinstance(error, AcceptanceUnknown):
        return 'the connection broke after the message was sent: check the inbox before sending again'
    return f'unexpected error: {type(error).__name__}'


def main():
    from watch import BASE, read_json
    import mail_worker
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'check', 'send-test'])
    parser.add_argument('--config', type=Path, default=BASE / 'config.json')
    args = parser.parse_args()
    config = read_json(args.config)
    if args.action == 'setup':
        password = getpass.getpass('Gmail app password (input is hidden): ')
        try:
            save_password(TokenStore(Path(config['runtime']) / 'smtp_secret.bin'), password)
        except ValueError as error:
            raise SystemExit(f'not saved: {error}')
        print('saved (Windows DPAPI, current user)')
        return 0
    smtp = mail_worker.build_transport({**config, 'mail_provider': 'gmail_smtp'}, Path(config['runtime']))
    try:
        if args.action == 'check':
            smtp.check()
            print('OK: connected and signed in (nothing was sent)')
        else:
            print({'sent': 'sent: check the inbox and the spam folder of the recipient',
                   'cancelled': 'cancelled: nothing was sent'}[send_test(smtp, config['mail_to'])])
    except (AuthRequired, TransportUnavailable, Rejected, AcceptanceUnknown) as error:
        print(_report(error))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
