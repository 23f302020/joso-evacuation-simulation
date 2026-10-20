"""Registered choice-cell orchestration. Smoke/check only until full preflight exists."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    check = commands.add_parser('check')
    check.add_argument('--run-id', required=True)
    smoke = commands.add_parser('smoke')
    smoke.add_argument('--run-id', required=True)
    smoke.add_argument('--cell-id', required=True)
    smoke.add_argument('--end-sec', type=int, default=1800)
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / '04_プログラム'))
    param = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
    parameters = json.loads(param.read_text(encoding='utf-8'))
    workspace = root / parameters['workspace']
    manifests = list((workspace / 'runs').glob('*/manifest.json')) + list((workspace / 'smoke').glob('*/manifest.json'))
    records = [json.loads(path.read_text(encoding='utf-8')) for path in manifests]
    def alive(record):
        try:
            os.kill(record['pid'], 0)
            return True
        except ProcessLookupError:
            return False
    if args.command == 'status':
        result = {'protocol': parameters['protocol'], 'registered_cells': len(parameters['cells']),
                  'running': [{**r, 'pid_alive': alive(r)} for r in records if r['status'] == 'RUNNING'],
                  'smoke_completed': [r['run_id'] for r in records if r['purpose'] == 'smoke' and r['status'] == 'COMPLETED'],
                  'failed': [r['run_id'] for r in records if r['status'] == 'FAILED'],
                  'core_ready': False, 'core_start_available': False}
    elif args.command == 'check':
        matches = [path for path, record in zip(manifests, records) if record['run_id'] == args.run_id]
        if len(matches) != 1:
            raise ValueError('Run ID is missing or ambiguous')
        result = json.loads(matches[0].read_text(encoding='utf-8'))
        result['pid_alive'] = alive(result) if result['status'] == 'RUNNING' else False
        progress = matches[0].parent / 'progress.json'
        if progress.exists():
            result['progress'] = json.loads(progress.read_text(encoding='utf-8'))
    else:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', args.run_id):
            raise ValueError('Use a simple unique run ID')
        if any(r['status'] == 'RUNNING' for r in records):
            raise RuntimeError('Resolve RUNNING manifest before another smoke')
        technical = (workspace / 'technical').glob('*/manifest.json')
        if any(json.loads(path.read_text(encoding='utf-8'))['status'] == 'RUNNING' for path in technical):
            raise RuntimeError('Resolve RUNNING technical probe before smoke')
        from scripts.jdrt_realtime_choice import run
        start = time.monotonic()
        try:
            result = run(args.cell_id, args.run_id, purpose='smoke', smoke_end=args.end_sec)
        except BaseException as error:
            log(workspace, args.command, {'run_id': args.run_id, 'error_type': type(error).__name__,
                                         'error': str(error), 'duration_sec': time.monotonic() - start})
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
