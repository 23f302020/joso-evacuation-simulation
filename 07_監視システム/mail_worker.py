"""Mail worker: drains the outbox through an injected transport, one message per tick.

An exclusive OS lock keeps a single worker alive (two workers could double-send). On start, a message
left 'sending' by a crash is preserved as uncertain and never resent. Sign-in expiry stops sending
until the user signs in and runs `resume`. Nothing here sends unless mail_enabled is true.
"""
import argparse
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


def run(config, runtime, transport, sleep=time.sleep, clock=time.time, stop=lambda: False, interval=5):
    runtime = Path(runtime)
    lock = watch.Exclusive(runtime / 'mail_worker.lock')
    try:
        start(runtime)
        while not stop():
            worker_tick(config, runtime, transport, clock())
            sleep(interval)
    finally:
        lock.close()


def build_transport(config, runtime):
    import graph_mail
    recipient = config.get('mail_to')
    if not recipient:
        raise SystemExit('mail_to missing in config')
    return graph_mail.GraphTransport(graph_mail.build_auth(config, runtime).access_token, recipient)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'resume'])
    parser.add_argument('--config', type=Path, default=watch.BASE / 'config.json')
    args = parser.parse_args()
    config = watch.read_json(args.config)
    runtime = Path(config['runtime'])
    if args.action == 'resume':
        print(resume(runtime), 'message(s) returned to the queue')
    else:
        run(config, runtime, build_transport(config, runtime))


if __name__ == '__main__':
    main()
