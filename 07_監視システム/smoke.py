"""Artificial process/event end-to-end probe. Never launches SUMO or research CLI."""
import argparse
from pathlib import Path
import subprocess
import sys
import time

import watch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    source = args.output / 'artificial' / 'manifest.json'
    marker = 'simulation_watch_artificial_child'
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)', marker])
    try:
        watch.atomic_json(source, {'run_id': marker, 'status': 'RUNNING', 'pid': child.pid})
        initial = watch.snapshot(source, {}, time.time())
        watch.atomic_json(args.output / 'initial.json', initial)
        assert initial['process']['state'] == 'alive' and not initial['flags'], initial
        child.wait(timeout=10)
        # A manifest terminal status is separate evidence from the process exit.
        watch.atomic_json(source, {'run_id': marker, 'status': 'COMPLETED', 'pid': child.pid})
        final = watch.snapshot(source, initial, time.time())
        assert watch.classify(final, initial, time.time(), 60) == ['completed']
        event_path = watch.save_event(args.output / 'events', str(source), 'completed', final)
        config = watch.read_json(watch.BASE / 'config.json')
        config['diagnostics_enabled'] = args.codex
        dispatcher = watch.Dispatcher(config, args.output)
        began = time.time()
        while True:
            dispatcher.tick(time.time())
            event = watch.read_json(event_path)
            if not args.codex or event['delivery'] in {'done', 'failed_preserved', 'timeout_preserved'}:
                break
            if time.time() - began > config['diagnostic_timeout_sec'] + 20:
                raise RuntimeError('Artificial probe deadline')
            time.sleep(1)
        watch.atomic_json(args.output / 'result.json', {'initial': initial, 'final': final,
                           'event': event, 'actual_codex_requested': args.codex,
                           'research_run_started': False})
        print(event_path)
        print('notification=' + event['notification'] + '; delivery=' + event['delivery'])
        if args.codex and event['delivery'] != 'done':
            raise RuntimeError('Codex diagnostic probe failed; preserved evidence')
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)


if __name__ == '__main__':
    main()
