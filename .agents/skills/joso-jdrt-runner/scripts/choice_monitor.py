"""Read-only skill check plus detailed local monitoring; never start/recover/record."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / '06_研究結果/jdrt/goal_20261017'


def file_sha(path):
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', args.run_id):
        raise ValueError('Simple registered run ID required')
    cfg = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    workspace = ROOT / cfg['workspace']
    folder = workspace / 'runs' / args.run_id
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if m['protocol'] != cfg['protocol'] or m['purpose'] != 'core' or m['run_id'] != args.run_id:
        raise ValueError('Not this registered core series')
    now = datetime.now(timezone(timedelta(hours=9)))
    label = now.strftime('%Y%m%dT%H%M%S%f')
    destination = OUT / ('監視_' + args.run_id + '_' + label + '.json')
    command = [sys.executable, '-X', 'utf8', str(ROOT / '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'),
               '--project-root', str(ROOT), 'check', '--run-id', args.run_id]
    with destination.with_suffix('.check.stdout.log').open('xb') as so, destination.with_suffix('.check.stderr.log').open('xb') as se:
        executed = subprocess.run(command, cwd=ROOT, stdout=so, stderr=se)
    check = json.loads(destination.with_suffix('.check.stdout.log').read_text(encoding='utf-8-sig'))
    inputs = ROOT / m['input_directory']
    with (inputs / 'people.csv').open(encoding='utf-8', newline='') as stream:
        population = sum(1 for _ in csv.DictReader(stream))
    point = check.get('progress')
    integrity = {'input_manifest': file_sha(inputs / 'manifest.json') == m['input_manifest_sha256'],
                 'archived_READY': file_sha(folder / 'preflight_ready.json') == m['preflight_ready_sha256'],
                 **{name: file_sha(ROOT / name) == value for name, value in m['implementation_sha256'].items()}}
    flags = []
    if executed.returncode:
        flags.append('skill_check_command_failure')
    if not all(integrity.values()):
        flags.append('input_or_implementation_or_READY_SHA_mismatch')
    if check['status'] == 'RUNNING' and not check['pid_alive']:
        flags.append('orphan_RUNNING')
    if check['status'] in ('FAILED', 'INVALID') or check.get('error'):
        flags.append('terminal_failure_or_reported_error')
    if point:
        if sum(point['people_states'].values()) != population:
            flags.append('whole_population_accounting_mismatch')
        for key in ['teleports', 'collisions', 'closed_entry_rows', 'ambiguous_transitions',
                    'missing_vehicle_subscriptions', 'missing_person_subscriptions']:
            if point['counts'][key]:
                flags.append('nonzero_' + key)
    native = folder / 'sumo_errors.log'
    native_errors = sum(line.lstrip().startswith('Error:') for line in native.read_text(encoding='utf-8', errors='replace').splitlines())
    if native_errors:
        flags.append('native_SUMO_Error_lines')
    value = {'at_jst': now.isoformat(), 'action': 'detailed_same_core_monitor', 'run_id': args.run_id,
             'cell_id': m['cell_id'], 'pid': m['pid'], 'skill_check': check,
             'input_population_rows': population, 'integrity': integrity, 'anomaly_flags': flags,
             'manifest_sha256_at_observation': file_sha(folder / 'manifest.json'),
             'current_run_bytes': sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()),
             'free_bytes': shutil.disk_usage(ROOT).free, 'native_error_lines': native_errors,
             'native_log_bytes': native.stat().st_size,
             'driver_stderr_bytes': (workspace / 'driver_logs' / (args.run_id + '.stderr.log')).stat().st_size,
             'monitor_source_sha256': file_sha(Path(__file__)), 'formal_validation_or_adoption': False,
             'limitations': 'Observed progress snapshot and error prefixes only; formal validate required after completion'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    for path in [OUT / 'operations.jsonl', workspace / 'driver_logs/operations.jsonl', workspace / 'driver_logs/monitoring.jsonl']:
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    print(json.dumps({'status': check['status'], 'run_id': args.run_id, 'pid_alive': check['pid_alive'],
                      'sim_sec': point['time_sec'] if point else None, 'anomaly_flags': flags,
                      'report': destination.relative_to(ROOT).as_posix()}, ensure_ascii=False))
    return 1 if flags else 0


if __name__ == '__main__':
    raise SystemExit(main())
