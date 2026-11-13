"""End-to-end mail check through the real queue: one test notice -> outbox -> running worker -> inbox.

`smtp_mail.py send-test` proves the account and the network. This proves the rest of the path the
real notices take: the message is placed in the outbox like any notice, and the running worker
(JDRT-MailWorker) has to pick it up and send it. Nothing research-related is read or written:
no event is created (the monitor's events folder is untouched), only one outbox message
'selftest-<UTC time>' that the operator confirms by typing yes.

Usage: mail_selftest.py [--config PATH] [--wait SEC]
Exit: 0 accepted by the server / 1 refused, cancelled or preserved / 2 not sent within --wait.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import uuid

import watch
from mail_outbox import Outbox

DONE = ('accepted', 'auth_expired', 'uncertain_preserved', 'failed_preserved')


def mask(address):
    """'a***@example.com': enough to recognise the recipient, without copying it into logs."""
    local, _, domain = str(address or '').partition('@')
    return (local[:1] + '***@' + domain) if domain else '(not set)'


def selftest_event(now, token=None):
    # A fresh suffix per run: a rerun within the same second must never reuse an earlier message.
    stamp = now.strftime('%Y%m%dT%H%M%SZ') + '-' + (token or uuid.uuid4().hex[:8])
    return {'id': 'selftest-' + stamp, 'kind': 'selftest', 'target': 'mail-selftest',
            'evidence': {'target_id': 'mail-selftest',
                         'status': '試験（研究とは無関係。キューとワーカーを通る経路の確認）',
                         'source': 'mail_selftest.py'}}


def worker_running(runtime):
    """True while some process holds the worker's OS lock (the lock file alone proves nothing)."""
    path = Path(runtime) / 'mail_worker.lock'
    if not path.exists():
        return False
    try:
        watch.Exclusive(path).close()
    except RuntimeError:
        return True
    return False


def queue_test(config, input_fn=input, output_fn=print, clock=time.time, sleep=time.sleep, wait_sec=180,
               now=None, token=None):
    if config.get('mail_enabled') is not True:
        output_fn('mail_enabled is not true: finish the mail setup first (nothing queued)')
        return 1
    runtime = Path(config['runtime'])
    if not worker_running(runtime):
        output_fn('the mail worker is not running (JDRT-MailWorker): start it first (nothing queued)')
        return 1
    event = selftest_event(now or datetime.now(timezone.utc), token)
    outbox = Outbox(runtime / 'outbox')
    output_fn(f"宛先: {mask(config.get('mail_to'))}（config.json の mail_to）")
    output_fn(f"件名: [JDRT監視] selftest mail-selftest（識別 {event['id']}）")
    output_fn('本文: 試験であること・研究とは無関係であることを書いた通知（監視の通知と同じ形式）')
    if input_fn('この試験通知を1通、送信キューに入れます。入れる場合は yes と入力: ').strip() != 'yes':
        output_fn('cancelled: nothing was queued')
        return 1
    path = outbox.enqueue(event)
    output_fn(f'queued: {path.name}（ワーカーが拾うのを待ちます。最大 {wait_sec} 秒）')
    deadline = clock() + wait_sec
    state = None
    while clock() < deadline:
        try:
            state = watch.read_json(path).get('state')
        except (OSError, ValueError):
            state = None
        if state in DONE:
            break
        sleep(5)
    aside = (f' This test message ({path.name}) now blocks the parent-loop mail check: after reviewing, move it '
             'out of the outbox folder (e.g. to outbox_reviewed) and note why.')
    advice = {'accepted': 'accepted by the server: check the inbox (and the spam folder) of the recipient',
              'auth_expired': 'sign-in failed: run smtp_mail.py setup again, then mail_worker.py resume '
                              '(real notices also wait until then)',
              'uncertain_preserved': 'may have been sent: check the inbox; it is never resent automatically',
              'failed_preserved': 'refused or never reached the server: see last_error in the outbox file.' + aside}
    if state in advice:
        output_fn(f'{state}: {advice[state]}')
        return 0 if state == 'accepted' else 1
    output_fn(f'still {state or "unreadable"} after {wait_sec} s: is the worker running? The message stays queued '
              'and will be sent whenever the worker picks it up; if it keeps retrying (3+ attempts) it blocks '
              'the parent-loop mail check.' + aside.replace('now blocks', 'can block'))
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', type=Path, default=watch.BASE / 'config.json')
    parser.add_argument('--wait', type=int, default=180, help='seconds to wait for the worker (default 180)')
    args = parser.parse_args()
    return queue_test(watch.read_json(args.config), wait_sec=args.wait)


if __name__ == '__main__':
    sys.exit(main())
