"""Durable mail outbox for result notifications (no network code; the transport is injected).

States: queued -> sending -> accepted | queued (retry with backoff) | auth_expired |
uncertain_preserved | failed_preserved.  A claim ('sending') is written BEFORE the transport is
called, so a crash can never lead to a silent second send: such a message becomes
'uncertain_preserved' and is not retried.  Graph's 202 only means "accepted for sending".
"""
import re
from pathlib import Path

from watch import atomic_json, read_json, stamp, timing_text

CAUTION = ('このメールは監視の検出通知です。完了は検証PASS・研究採用を意味しません。'
           '送信の受付は受信確認ではありません。')


class TransportUnavailable(Exception):
    """Nothing was sent (e.g. no connection). Safe to retry later."""


class AuthRequired(Exception):
    """Sign-in expired or missing. Needs the user; nothing is retried automatically."""


class AcceptanceUnknown(Exception):
    """The request may have been accepted (e.g. the response was lost). Never resend."""


def compose(event, attachments, max_bytes):
    evidence = event.get('evidence') or {}
    included, omitted, total = [], [], 0
    for path in map(Path, attachments):
        try:
            size = path.stat().st_size
        except OSError:
            omitted.append({'name': path.name, 'path': str(path), 'bytes': None, 'reason': 'missing'})
            continue
        item = {'name': path.name, 'path': str(path), 'bytes': size}
        if total + size <= max_bytes:
            included.append(item)
            total += size
        else:
            omitted.append({**item, 'reason': 'size_limit'})
    target = evidence.get('target_id') or event.get('target', 'monitor')
    lines = [f'識別：{target}', f"種類：{event.get('kind')}", f"状態：{evidence.get('status', '不明')}",
             timing_text(evidence.get('execution_timing')),
             f"保存先（学校PC上）：{evidence.get('source', event.get('target', '不明'))}",
             '添付：' + (', '.join(a['name'] for a in included) or 'なし')]
    for item in omitted:
        size = '不明' if item['bytes'] is None else f"{item['bytes']}バイト"
        lines.append(f"省略した添付：{item['name']}（{size}、{item['reason']}）保存先：{item['path']}")
    lines.append(CAUTION)
    return f"[JDRT監視] {event.get('kind')} {target}", '\n'.join(lines), included, omitted


class Outbox:
    def __init__(self, directory, max_attachment_bytes=3_000_000, max_attempts=5, backoff_sec=60):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_attachment_bytes, self.max_attempts, self.backoff_sec = max_attachment_bytes, max_attempts, backoff_sec

    def _files(self):
        return sorted(self.directory.glob('*.json'))

    def enqueue(self, event, attachments=()):
        """Idempotent per event id: an existing message (whatever its state) is left untouched."""
        if not re.fullmatch(r'[0-9A-Za-z_-]+', str(event.get('id', ''))):
            raise ValueError('event id is not a safe file name')
        path = self.directory / (event['id'] + '.json')
        if not path.exists():
            subject, body, included, omitted = compose(event, attachments, self.max_attachment_bytes)
            atomic_json(path, {'schema': 'simulation_watch_mail_v1', 'id': event['id'], 'event_id': event['id'],
                              'subject': subject, 'body': body, 'attachments': included, 'omitted': omitted,
                              'state': 'queued', 'attempts': 0, 'next_attempt_epoch': 0,
                              'created_at_utc': stamp()})
        return path

    def _retag(self, source, target):
        count = 0
        for path in self._files():
            message = read_json(path)
            if message['state'] == source:
                message['state'] = target
                if target == 'queued':
                    message['next_attempt_epoch'] = 0
                atomic_json(path, message)
                count += 1
        return count

    def recover_after_restart(self):
        """A message still 'sending' after a restart may or may not have gone out: preserve it."""
        return self._retag('sending', 'uncertain_preserved')

    def resume_after_signin(self):
        """Only auth_expired messages return to the queue; uncertain/failed ones never do."""
        return self._retag('auth_expired', 'queued')

    def send_next(self, transport, now):
        """Process at most one due message so the caller's loop is never blocked by a backlog."""
        for path in self._files():
            message = read_json(path)
            if message['state'] != 'queued' or message['next_attempt_epoch'] > now:
                continue
            message.update(state='sending', attempts=message['attempts'] + 1, last_attempt_epoch=now)
            atomic_json(path, message)
            try:
                transport.send(message)
                message.update(state='accepted', accepted_at_utc=stamp())
            except TransportUnavailable:
                if message['attempts'] >= self.max_attempts:
                    message['state'] = 'failed_preserved'
                else:
                    message.update(state='queued', next_attempt_epoch=now + self.backoff_sec * 2 ** (message['attempts'] - 1))
            except AuthRequired:
                message.update(state='auth_expired', attempts=message['attempts'] - 1)
            except AcceptanceUnknown:
                message['state'] = 'uncertain_preserved'
            except Exception as error:
                message.update(state='failed_preserved', error_type=type(error).__name__)
            atomic_json(path, message)
            return message['state']
        return None
