"""Mail worker: drains the outbox through an injected transport, one message per tick.

An exclusive OS lock keeps a single worker alive (two workers could double-send). On start, a message
left 'sending' by a crash is preserved as uncertain and never resent. Sign-in expiry stops sending
until the user signs in and runs `resume`. Nothing here sends unless mail_enabled is true.
A failing tick is contained and logged (error type only) so one bad file cannot silence notifications;
a daily keepalive refreshes the sign-in so the refresh token does not lapse unused.
"""
import argparse
import json
from pathlib import Path
import time

import watch
from mail_outbox import Outbox


def _outbox(runtime):
    return Outbox(Path(runtime) / 'outbox')


def worker_tick(config, runtime, transport, now):
    if config.get('mail_enabled', False) is not True:
        return None
    watch.sync_mail_outbox(config, Path(runtime))
    return _outbox(runtime).send_next(transport, now)


def start(runtime):
    return _outbox(runtime).recover_after_restart()


def resume(runtime):
    return _outbox(runtime).resume_after_signin()


def resume_unsent(runtime):
    return _outbox(runtime).resume_unsent()


def _log_error(runtime, where, error):
    """Error type only: exception text could carry request data."""
    try:
        with (Path(runtime) / 'mail_worker_errors.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'at_utc': watch.stamp(), 'where': where, 'error_type': type(error).__name__}) + '\n')
    except OSError:
        pass


def run(config, runtime, transport, sleep=time.sleep, clock=time.time, stop=lambda: False, interval=5,
        keepalive=None, keepalive_every=86400):
    runtime = Path(runtime)
    lock = watch.Exclusive(runtime / 'mail_worker.lock')
    try:
        try:
            start(runtime)
        except Exception as error:
            _log_error(runtime, 'start', error)
        last_keepalive = None
        while not stop():
            now = clock()
            if keepalive is not None and (last_keepalive is None or now - last_keepalive >= keepalive_every):
                last_keepalive = now
                try:
                    keepalive()
                except Exception as error:
                    _log_error(runtime, 'keepalive', error)
            try:
                worker_tick(config, runtime, transport, now)
            except Exception as error:
                # A message left 'sending' stays so (not re-sent); the next start preserves it as uncertain.
                _log_error(runtime, 'tick', error)
            sleep(interval)
    finally:
        lock.close()


def build_transport(config, runtime):
    recipient = config.get('mail_to')
    if not recipient:
        raise SystemExit('mail_to missing in config')
    provider = config.get('mail_provider', 'graph')
    if provider == 'gmail_smtp':
        import graph_mail
        import smtp_mail
        sender = config.get('mail_sender')
        if not sender:
            raise SystemExit('mail_sender missing in config')
        store = graph_mail.TokenStore(Path(runtime) / 'smtp_secret.bin')
        return smtp_mail.SmtpTransport(sender, recipient, smtp_mail.password_from_store(store))
    if provider != 'graph':
        raise SystemExit(f'unknown mail_provider: {provider}')
    import graph_mail
    auth = graph_mail.build_auth(config, runtime)
    transport = graph_mail.GraphTransport(auth.access_token, recipient, on_unauthorized=auth.invalidate)
    transport.keepalive = auth.access_token
    return transport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'resume', 'resume-unsent'])
    parser.add_argument('--config', type=Path, default=watch.BASE / 'config.json')
    args = parser.parse_args()
    config = watch.read_json(args.config)
    runtime = Path(config['runtime'])
    if args.action == 'resume':
        print(resume(runtime), 'message(s) returned to the queue (after sign-in)')
    elif args.action == 'resume-unsent':
        print(resume_unsent(runtime), 'message(s) returned to the queue (confirmed never sent)')
    else:
        transport = build_transport(config, runtime)
        run(config, runtime, transport, keepalive=getattr(transport, 'keepalive', None))


if __name__ == '__main__':
    main()
