"""SMTP transport (Gmail by default) that honours the mail_outbox contract.

Classification follows the SMTP phase (RFC 5321). Before the end-of-data reply nothing has been
accepted, so a failure there is unsent (retry) or a definite refusal. A connection lost during or
after DATA may have been accepted: never resend. Error text from the server is never copied into
exceptions (it could echo credentials); only reply codes are kept.

The app password lives only as a Windows DPAPI blob (current user), set with `smtp_mail.py setup`.
Neither the password nor any address is embedded in the source.
"""
import argparse
import email.policy
import email.utils
import getpass
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
import sys

from graph_mail import TokenStore
from mail_outbox import AcceptanceUnknown, AuthRequired, Rejected, TransportUnavailable

SECRET_KEY = 'smtp_app_password'


def build_email(message, sender, recipient):
    msg = EmailMessage(policy=email.policy.SMTP)
    msg['From'], msg['To'], msg['Subject'] = sender, recipient, message['subject']
    msg['Date'] = email.utils.formatdate(usegmt=True)
    msg['Message-ID'] = email.utils.make_msgid(domain=sender.rsplit('@', 1)[-1])
    msg['X-JDRT-Event-Id'] = str(message.get('id', ''))
    msg.set_content(message['body'], charset='utf-8', cte='base64')
    for item in message.get('attachments', []):
        try:
            data = Path(item['path']).read_bytes()
        except OSError:
            continue  # vanished since queuing; the body already names it
        msg.add_attachment(data, maintype='application', subtype='octet-stream', filename=item['name'])
    return msg.as_bytes(policy=email.policy.SMTP)


def save_password(store, password):
    store.save({SECRET_KEY: password.replace(' ', '')})  # Google shows app passwords in groups of four


def password_from_store(store):
    def provider():
        data = store.load()
        password = data.get(SECRET_KEY) if data else None
        if not password:
            raise AuthRequired('smtp app password not set')
        return password
    return provider


class SmtpTransport:
    def __init__(self, sender, recipient, password_provider, host='smtp.gmail.com', port=None, use_ssl=True,
                 timeout=30, factory=None):
        self.sender, self.recipient, self.password_provider = sender, recipient, password_provider
        self.host, self.use_ssl, self.timeout = host, use_ssl, timeout
        self.port = port if port is not None else (465 if use_ssl else 25)
        self.factory = factory or self._connect

    def _connect(self, host, port, timeout):
        if self.use_ssl:
            return smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
        return smtplib.SMTP(host, port, timeout=timeout)

    def send(self, message):
        password = self.password_provider()  # AuthRequired propagates: nothing was attempted
        payload = build_email(message, self.sender, self.recipient)
        try:
            server = self.factory(self.host, self.port, self.timeout)
        except (OSError, smtplib.SMTPException):
            raise TransportUnavailable() from None  # no greeting reached us: nothing sent
        try:
            self._login(server, password)
            self._envelope(server)
            self._data(server, payload)
        finally:
            self._close(server)

    def _login(self, server, password):
        try:
            server.login(self.sender, password)
        except smtplib.SMTPAuthenticationError:
            raise AuthRequired('smtp authentication failed') from None
        except smtplib.SMTPNotSupportedError:
            raise Rejected('smtp authentication unsupported') from None
        except (smtplib.SMTPException, OSError):
            raise TransportUnavailable() from None

    def _envelope(self, server):
        steps = (('mail', lambda: server.mail(self.sender), (250,)),
                 ('rcpt', lambda: server.rcpt(self.recipient), (250, 251)))
        for phase, call, accepted in steps:
            try:
                code, _ = call()
            except (smtplib.SMTPException, OSError):
                raise TransportUnavailable() from None  # nothing is accepted before DATA completes
            if code in accepted:
                continue
            if 400 <= code < 500:
                raise TransportUnavailable()
            raise Rejected(f'smtp {phase} refused ({code})')

    def _data(self, server, payload):
        try:
            code, _ = server.data(payload)
        except smtplib.SMTPDataError as error:  # refusal of the DATA command itself: no body was taken
            if 400 <= error.smtp_code < 500:
                raise TransportUnavailable() from None
            raise Rejected(f'smtp data refused ({error.smtp_code})') from None
        except (smtplib.SMTPException, OSError):
            raise AcceptanceUnknown() from None  # may have been accepted before the connection broke
        if code == 250:
            return
        if 400 <= code < 500:
            raise TransportUnavailable()  # RFC: a 4xx end-of-data reply means not accepted
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


def main():
    from watch import BASE, read_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup'])
    parser.add_argument('--config', type=Path, default=BASE / 'config.json')
    args = parser.parse_args()
    config = read_json(args.config)
    password = getpass.getpass('Gmail app password (input is hidden): ').strip()
    if not password:
        raise SystemExit('empty password; nothing saved')
    save_password(TokenStore(Path(config['runtime']) / 'smtp_secret.bin'), password)
    print('saved (Windows DPAPI, current user)')


if __name__ == '__main__':
    sys.exit(main())
