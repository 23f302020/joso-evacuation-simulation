"""Technical-only entry point for registered realtime_choice_v1; no core launch command."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from realtime_choice_cell import pid_alive
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    probe = sub.add_parser('probe')
    probe.add_argument('--run-id', required=True)
    fixture = sub.add_parser('fixture')
    fixture.add_argument('--run-id', required=True)
    fixture.add_argument('--case')
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / '04_プログラム'))
    params = json.loads((root / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    workspace = root / params['workspace']
    records = []
    for path in sorted((workspace / 'technical').glob('*/manifest.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('status') == 'RUNNING':
            record['pid_alive'] = pid_alive(record['pid'])
        records.append(record)
    if args.command == 'status':
        result = {'protocol': params['protocol'], 'technical_probes': records, 'core_ready': False}
    else:
        if any(r['status'] == 'RUNNING' for r in records):
            raise RuntimeError('Resolve existing RUNNING probe before another launch')
        for category in ('smoke', 'runs'):
            for path in (workspace / category).glob('*/manifest.json'):
                if json.loads(path.read_text(encoding='utf-8'))['status'] == 'RUNNING':
                    raise RuntimeError('Resolve RUNNING ' + category + ' before a technical launch')
        start = time.monotonic()
        try:
            if args.command == 'fixture':
                from scripts.jdrt_choice_fixtures import run_suite
                result = run_suite(args.run_id, args.case)
            else:
                from scripts.jdrt_choice_sumo_probe import run_probe
                result = run_probe(args.run_id)
        except BaseException as exc:
            log(workspace, args.command, {'run_id': args.run_id, 'error_type': type(exc).__name__,
                                         'error': str(exc), 'duration_sec': time.monotonic() - start})
            raise
    log(workspace, args.command, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def log(workspace, command, result):
    directory = workspace / 'driver_logs'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'operations.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
                                 'command': command, 'result': result}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
