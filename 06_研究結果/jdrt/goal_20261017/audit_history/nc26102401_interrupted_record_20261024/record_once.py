"""Explicit one-off precommit recovery through the unchanged dedicated record CLI."""
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path.cwd().resolve()
directory = Path(__file__).resolve().parent
run_id = 'nc26102401'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
digest = lambda p: sha256(p.read_bytes()).hexdigest()
cfg_path = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
cfg = read(cfg_path)
workspace = root / cfg['workspace']
old = workspace / 'driver_logs' / (run_id + '.finish/operation.json')
original = read(old)
diagnosis = read(directory / 'diagnosis.json')
assert diagnosis['status'] == 'ORPHAN_PRECOMMIT_RECORD_CONFIRMED'
assert original['phase'] == 'record' and original['formal_record_result'] is None
assert not (workspace / 'driver_logs/writer.lock').exists()
assert not list((workspace / 'record_transactions').glob(run_id + '_*'))
assert all(digest(root / p) == diagnosis['preserved_sha256'][p] for p in cfg['record_files'])
assert digest(cfg_path) == original['config_sha256']
assert os.environ.get('JDRT_CHOICE_TOOLCHAIN_MANIFEST')
state_path = directory / 'recovery_operation.json'
state = {'kind': 'explicit_orphan_precommit_record_recovery_v1', 'run_id': run_id,
         'pid': os.getpid(), 'status': 'RUNNING', 'phase': 'record',
         'started_at_jst': datetime.now().astimezone().isoformat(),
         'config_sha256': digest(cfg_path), 'source_sha256': digest(Path(__file__)),
         'original_operation': old.relative_to(root).as_posix(),
         'original_operation_sha256': digest(old),
         'diagnosis': (directory / 'diagnosis.json').relative_to(root).as_posix(),
         'diagnosis_sha256': digest(directory / 'diagnosis.json'),
         'validation_report_sha256': original['validation_report_sha256'],
         'record_attempted': True, 'formal_record_result': None, 'next_start_performed': False}
with state_path.open('x', encoding='utf-8') as stream:
    json.dump(state, stream, ensure_ascii=False, indent=2)


def save():
    state['observed_at_jst'] = datetime.now().astimezone().isoformat()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def invoke(command):
    state['phase'] = command
    save()
    args = [sys.executable, '-B', '-X', 'utf8',
            str(root / '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'),
            '--project-root', str(root), command]
    if command == 'record':
        args += ['--run-id', run_id]
    with (directory / (command + '.stdout.log')).open('xb') as out, \
            (directory / (command + '.stderr.log')).open('xb') as err:
        child = subprocess.Popen(args, stdout=out, stderr=err, cwd=root,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        state['child_launcher_pid'] = child.pid
        state['child_command'] = args
        save()
        code = child.wait()
    state[command + '_exit_code'] = code
    save()
    assert code == 0, command + ' failed; original preserved, no automatic retry'
    return read(directory / (command + '.stdout.log'))


try:
    result = invoke('record')
    assert result['run_id'] == run_id and result['status'] == 'RECORDED'
    state['formal_record_result'] = result['status']
    state['record_files_sha256'] = {p: digest(root / p) for p in cfg['record_files']}
    save()
    status = invoke('status')
    assert status['recorded_cells'] == diagnosis['formal_rows_before'] + 1
    for key in ('running', 'unrecorded', 'partial_records', 'record_identity_mismatch',
                'unresolved_failures', 'unresolved_launches', 'pending_record_journals',
                'foreign_running_manifests', 'active_native_processes'):
        assert not status[key], key
    assert digest(old) == state['original_operation_sha256']
    state['status'] = 'RECORDED_VERIFIED'
    state['finished_at_jst'] = datetime.now().astimezone().isoformat()
    save()
    print(json.dumps({'status': state['status'], 'run_id': run_id,
                      'recorded_cells': status['recorded_cells']}, ensure_ascii=False))
except BaseException as error:
    state.update(status='FAILED_PRESERVED', error_type=type(error).__name__, error=str(error))
    save()
    raise
