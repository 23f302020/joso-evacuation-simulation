"""Durable mail outbox for result notifications (no network code; the transport is injected).

States: queued -> sending -> accepted | queued (retry with capped backoff) | auth_expired |
uncertain_preserved | failed_preserved.  A claim ('sending') is written BEFORE the transport is
called, so a crash can never lead to a silent second send: such a message becomes
'uncertain_preserved' and is not retried.  Graph's 202 only means "accepted for sending".

failed_preserved with unsent_confirmed=True means the server never took the message (retries
exhausted, or a definite rejection); only those can be re-queued with resume_unsent().
Anything that may have been sent (unknown acceptance, unexpected errors) is uncertain_preserved.
"""
import json
import os
import re
from pathlib import Path
import uuid

from watch import atomic_json, read_json, stamp, timing_text

CAUTION = ('このメールは監視の検出通知です。完了は検証PASS・研究採用を意味しません。'
           '送信の受付は受信確認ではありません。')


class TransportUnavailable(Exception):
    """Nothing was sent (e.g. no connection). Safe to retry later."""


class AuthRequired(Exception):
    """Sign-in expired or missing. Needs the user; nothing is retried automatically."""


class AcceptanceUnknown(Exception):
    """The request may have been accepted (e.g. the response was lost). Never resend."""


class Rejected(RuntimeError):
    """The server definitively refused the request; nothing was sent. Retrying will not help."""


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
    lines = [f'識別：{target}', f"種類：{event.get('kind')}", f"状態：{evidence.get('status', '不明')}"]
    if event.get('kind') != 'parent_progress':  # a progress notice has no run to time: "不明" looks like a fault
        lines.append(timing_text(evidence.get('execution_timing')))
    lines += [f"保存先（学校PC上）：{evidence.get('source', event.get('target', '不明'))}",
              '添付：' + (', '.join(a['name'] for a in included) or 'なし')]
    for item in omitted:
        size = '不明' if item['bytes'] is None else f"{item['bytes']}バイト"
        lines.append(f"省略した添付：{item['name']}（{size}、{item['reason']}）保存先：{item['path']}")
    lines.append(CAUTION)
    return f"[JDRT監視] {event.get('kind')} {target}", '\n'.join(lines), included, omitted


def _create_new(path, value):
    """Create `path` only if it does not exist; never overwrite a message another process made meanwhile.

    Windows os.rename refuses an existing destination (unlike os.replace), which is the point.
    """
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.rename(temp, path)
    except FileExistsError:
        temp.unlink(missing_ok=True)
        return False
    return True


class Outbox:
    def __init__(self, directory, max_attachment_bytes=3_000_000, max_attempts=None, backoff_sec=60,
                 max_backoff_sec=3600, give_up_after_sec=2 * 86400):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_attachment_bytes, self.max_attempts, self.backoff_sec = max_attachment_bytes, max_attempts, backoff_sec
        self.max_backoff_sec, self.give_up_after_sec = max_backoff_sec, give_up_after_sec

    def _files(self):
        return sorted(self.directory.glob('*.json'))

    def _read(self, path):
        """A message, or None when it cannot be used now. A transient OS error (file busy) is skipped;
        content that is not valid JSON is quarantined so one bad file never stops the queue."""
        try:
            return read_json(path)
        except OSError:
            return None
        except ValueError:
            try:
                os.replace(path, path.with_name(path.name + '.corrupt'))
            except OSError:
                pass
            return None

    def enqueue(self, event, attachments=()):
        """Idempotent per event id: an existing message (whatever its state) is left untouched."""
        if not re.fullmatch(r'[0-9A-Za-z_-]+', str(event.get('id', ''))):
            raise ValueError('event id is not a safe file name')
        path = self.directory / (event['id'] + '.json')
        if not path.exists():
            subject, body, included, omitted = compose(event, attachments, self.max_attachment_bytes)
            _create_new(path, {'schema': 'simulation_watch_mail_v1', 'id': event['id'], 'event_id': event['id'],
                               'subject': subject, 'body': body, 'attachments': included, 'omitted': omitted,
                               'state': 'queued', 'attempts': 0, 'next_attempt_epoch': 0,
                               'created_at_utc': stamp()})
        return path

    def _retag(self, source, target, only=None, reset_attempts=False):
        count = 0
        for path in self._files():
            message = self._read(path)
            if message is None or message['state'] != source or (only and not only(message)):
                continue
            message['state'] = target
            if target == 'queued':
                message['next_attempt_epoch'] = 0
            if reset_attempts:
                message.update(attempts=0, first_attempt_epoch=None)
                message.pop('unsent_confirmed', None)
            atomic_json(path, message)
            count += 1
        return count

    def recover_after_restart(self):
        """A message still 'sending' after a restart may or may not have gone out: preserve it."""
        return self._retag('sending', 'uncertain_preserved')

    def resume_after_signin(self):
        """Only auth_expired messages return to the queue; uncertain/failed ones never do."""
        return self._retag('auth_expired', 'queued', reset_attempts=True)  # a fresh retry window

    def waiting_for_signin(self):
        """True while any message waits for a sign-in: nothing should try to log in again meanwhile."""
        for path in self._files():
            message = self._read(path)
            if message is not None and message.get('state') == 'auth_expired':
                return True
        return False

    def resume_unsent(self):
        """Re-queue only failures where the server never took the message (unsent_confirmed)."""
        return self._retag('failed_preserved', 'queued', only=lambda m: m.get('unsent_confirmed') is True,
                           reset_attempts=True)

    def send_next(self, transport, now):
        """Process at most one due message so the caller's loop is never blocked by a backlog."""
        for path in self._files():
            message = self._read(path)
            if message is None or message['state'] != 'queued' or message['next_attempt_epoch'] > now:
                continue
            first = message.get('first_attempt_epoch') or now
            message.update(state='sending', attempts=message['attempts'] + 1, last_attempt_epoch=now,
                           first_attempt_epoch=first)
            atomic_json(path, message)
            try:
                transport.send(message)
                message.update(state='accepted', accepted_at_utc=stamp())
            except TransportUnavailable as error:
                # Only a stage code such as 'rcpt:450' is kept: never server text, which could echo secrets.
                message['last_error'] = re.sub(r'[^A-Za-z0-9:_.-]', '', (str(error).split() or [''])[0])[:60]
                exhausted = ((self.max_attempts is not None and message['attempts'] >= self.max_attempts)
                             or now - first >= self.give_up_after_sec)
                if exhausted:
                    message.update(state='failed_preserved', unsent_confirmed=True, error_type='retries_exhausted')
                else:
                    delay = min(self.backoff_sec * 2 ** min(message['attempts'] - 1, 20), self.max_backoff_sec)
                    message.update(state='queued', next_attempt_epoch=now + delay)
            except AuthRequired:
                message.update(state='auth_expired', attempts=message['attempts'] - 1)
            except AcceptanceUnknown:
                message['state'] = 'uncertain_preserved'
            except Rejected as error:
                message.update(state='failed_preserved', unsent_confirmed=True, error_type=type(error).__name__)
            except Exception as error:
                # Unexpected errors can happen after the request left: never claim it was unsent.
                message.update(state='uncertain_preserved', error_type=type(error).__name__)
            atomic_json(path, message)
            return message['state']
        return None
