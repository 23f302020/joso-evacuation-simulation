"""Finish one completed Joso choice core through the unchanged dedicated CLI.

No simulation/start/recovery operation. An existing operation directory is a
hold: follow its owner/evidence instead of replaying validation or recording.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
CONFIG = '04_プログラム/config/jdrt_realtime_choice_v1.json'
CLI = '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'
HOLDS = ('running', 'unrecorded', 'partial_records', 'record_identity_mismatch',
         'unresolved_failures', 'unresolved_launches', 'pending_record_journals',
         'foreign_running_manifests', 'active_native_processes')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def local(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root), 'Evidence escapes project root')
    return path


def other_validation_owner(root, run_id):
    """Conservative local check, including relative dedicated-CLI commands."""
    shell = shutil.which('pwsh') or shutil.which('powershell')
    require(os.name == 'nt' and shell, 'Windows process ownership proof required')
    query = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
             "@(Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
             "Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress")
    output = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command', query],
                            capture_output=True, text=True, encoding='utf-8', check=True,
                            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(output.stdout or '[]')
    rows = rows if isinstance(rows, list) else [rows]
    target = re.compile(r'--run-id\s+"?' + re.escape(run_id) + r'"?(?=\s|$)')
    return any('realtime_choice_cell.py' in (row.get('CommandLine') or '').lower()
               and re.search(r'(?<!\S)(validate|record)(?!\S)', row.get('CommandLine') or '')
               and target.search(row.get('CommandLine') or '') for row in rows)


def call_cli(root, operation, run_id, command):
    require(command in ('check', 'validate', 'record', 'status'), 'Unsupported finish command')
    args = [sys.executable, '-B', '-X', 'utf8', str(root / CLI), '--project-root', str(root), command]
    if command != 'status':
        args += ['--run-id', run_id]
    if command == 'validate':
        args += ['--purpose', 'core']
    stdout, stderr = operation / (command + '.stdout.log'), operation / (command + '.stderr.log')
    with stdout.open('xb') as out, stderr.open('xb') as err:
        child = subprocess.Popen(args, cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        (operation / (command + '.pid.json')).write_text(json.dumps(
            {'launcher_pid': child.pid, 'command': args, 'at_jst': datetime.now().astimezone().isoformat()},
            ensure_ascii=False, indent=2), encoding='utf-8')
        # No timeout, kill, retry or detached replacement on observation loss.
        code = child.wait()
    require(code == 0, command + ' failed; preserve and inspect original logs')
    return read(stdout)


def finish(root, run_id):
    root = Path(root).resolve()
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,40}', run_id), 'A simple existing run ID is required')
    config_path = root / CONFIG
    cfg = read(config_path)
    require(cfg['protocol'] == 'realtime_choice_v1' and cfg.get('registration_id'), 'Registered choice only')
    workspace = local(root, cfg['workspace'])
    operation = workspace / 'driver_logs' / (run_id + '.finish')
    try:
        operation.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise RuntimeError('Existing finish operation; follow its owner/evidence, do not replay') from error
    state = {'run_id': run_id, 'pid': os.getpid(), 'status': 'RUNNING', 'commands': [],
             'helper_sha256': digest(Path(__file__)), 'config_sha256': digest(config_path),
             'formal_record_result': None, 'record_attempted': False, 'next_start_performed': False}

    def save():
        state['observed_at_jst'] = datetime.now().astimezone().isoformat()
        temporary = operation / 'operation.tmp'
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(operation / 'operation.json')

    save()
    try:
        manifest_path = workspace / 'runs' / run_id / 'manifest.json'
        manifest = read(manifest_path)
        manifest_sha = digest(manifest_path)
        require(manifest['status'] == 'COMPLETED' and manifest['purpose'] == 'core'
                and manifest['run_id'] == run_id and manifest['protocol'] == cfg['protocol']
                and manifest['registration_id'] == cfg['registration_id']
                and manifest['cell_id'] in {row['cell_id'] for row in cfg['cells']},
                'A completed current-registration core is required')
        records = [local(root, name) for name in cfg['record_files']]
        require(len(records) == len(set(records)) == 7, 'Current seven-file record contract required')
        if records[-1].exists():
            require(not any(json.loads(line).get('run_id') == run_id
                for line in records[-1].read_text(encoding='utf-8-sig').splitlines() if line.strip()),
                'Already has a ledger row; inspect canonical status instead of revalidating')

        def invoke(command):
            require(digest(config_path) == state['config_sha256']
                    and digest(Path(__file__)) == state['helper_sha256']
                    and digest(manifest_path) == manifest_sha, 'Owner source/config/manifest changed')
            require(not other_validation_owner(root, run_id), 'Another validate/record owns this run')
            state['phase'] = command
            if command == 'record':
                state['record_attempted'] = True
            save()
            value = call_cli(root, operation, run_id, command)
            state['commands'].append({'command': command, 'status': value.get('status'),
                'run_id': value.get('run_id'), 'validation_report': value.get('validation_report')})
            save()
            return value

        checked = invoke('check')
        require(checked['run_id'] == run_id and checked['status'] == 'COMPLETED'
                and checked['pid_alive'] is False, 'Terminal core identity not confirmed')
        validated = invoke('validate')
        require(validated['run_id'] == run_id and validated['purpose'] == 'core'
                and validated['status'] == 'PASS' and validated['core_adoption_permitted'] is True,
                'Independent core PASS/adoption permission required')
        report = local(root, validated['validation_report'])
        original = read(report)
        require(original['run_id'] == run_id and original['purpose'] == 'core' and original['status'] == 'PASS'
                and original['core_adoption_permitted'] is True, 'Validation original differs')
        state['validation_report_sha256'] = digest(report)
        state['fact_forcing_gate'] = {
            '1': 'Dedicated CLI record reads the same core and independent validator; no source edits.',
            '2': 'Existing record API only; no start/recover operation.',
            '3': cfg['record_files'],
            '4': '2回以上重複する作業はスキル化し、記録は思考が少ないため、モデルを下げるか試行量を下げるようにしたい。'}
        save()
        recorded = invoke('record')
        state['formal_record_result'] = recorded.get('status')
        save()
        require(recorded['run_id'] == run_id and recorded['status'] in ('RECORDED', 'ALREADY_RECORDED'),
                'Dedicated record did not finish')
        marker = '<!-- choice_record:' + run_id + ' -->'
        for path in records[:-1]:
            text = path.read_text(encoding='utf-8-sig')
            if path.name == 'context.md':
                text = re.split(r'(?m)^<!-- AGENT_CURRENT_END -->\s*$', text, maxsplit=1)[0]
            require(marker in text, 'Missing current record marker: ' + str(path))
        ledger = [json.loads(line) for line in records[-1].read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        require(all(row['protocol'] == cfg['protocol'] and row['registration_id'] == cfg['registration_id']
                    for row in ledger), 'Foreign ledger registration')
        require(len({row['run_id'] for row in ledger}) == len(ledger)
                and len({row['cell_id'] for row in ledger}) == len(ledger), 'Duplicate ledger identity')
        matching = [row for row in ledger if row['run_id'] == run_id]
        require(len(matching) == 1 and matching[0]['cell_id'] == manifest['cell_id'], 'Missing/mismatched ledger row')
        status = invoke('status')
        require(status['recorded_cells'] == len(ledger) and not any(status[key] for key in HOLDS),
                'Dedicated status retains an unresolved hold; record may already be committed')
        state.update(status='RECORDED_VERIFIED', record_files_sha256={str(p.relative_to(root)): digest(p) for p in records})
        save()
        return {'status': state['status'], 'run_id': run_id,
                'operation': (operation / 'operation.json').relative_to(root).as_posix(),
                'next_start_performed': False}
    except BaseException as error:
        state.update(status='FAILED_PRESERVED', error_type=type(error).__name__, error=str(error))
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    print(json.dumps(finish(args.project_root, args.run_id), ensure_ascii=False))
