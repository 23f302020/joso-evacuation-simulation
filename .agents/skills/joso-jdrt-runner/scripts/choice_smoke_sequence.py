"""One-at-a-time skill CLI smoke/validate sequence; never launches research core."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / '06_研究結果/jdrt/goal_20261017'
PARAM = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'
CLI = ROOT / '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'


def stamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(prefix, audit_path):
    audit = json.loads((ROOT / audit_path).read_text(encoding='utf-8'))
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    workspace = ROOT / params['workspace']
    current = {p: sha(ROOT / p) for p in params['execution']['implementation_files']}
    if (audit['status'] != 'PASS' or audit['historical_diagnostic'] or not audit['primary_outputs_unchanged']
            or not all(p['pass'] for p in audit['counterexamples'])
            or any(p['implementation_sha256'] != current for p in audit['fixture_components'])):
        raise RuntimeError('Current independent suite/counterexample PASS required')
    state_path = OUT / (prefix + '_smoke_sequence.json')
    state = {'protocol': params['protocol'], 'purpose': 'technical_smoke_sequence', 'pid': __import__('os').getpid(),
             'status': 'RUNNING', 'started_at_jst': stamp(), 'implementation_sha256': current,
             'audit_path': audit_path, 'audit_sha256': sha(ROOT / audit_path), 'runner_sha256': sha(Path(__file__)),
             'research_adoption_permitted': False, 'completed': [], 'active': None}
    with state_path.open('x', encoding='utf-8') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
    def save():
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for attempt in range(6):
            try:
                temporary.replace(state_path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                # Windows file indexing/synchronization may briefly deny rename.
                # Never drop the checkpoint or start the next command on failure.
                time.sleep(.2)
    def record(action, **data):
        row = {'at_jst': stamp(), 'action': action, **data}
        for path in (OUT / 'operations.jsonl', workspace / 'driver_logs/monitoring.jsonl'):
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
    try:
        cells = [c for c in params['cells'] if c['seed'] == params['seeds'][0]]
        for index, cell in enumerate(cells, 1):
            if current != {p: sha(ROOT / p) for p in current}:
                raise RuntimeError('Frozen implementation changed')
            run_id = prefix + '_' + str(index).zfill(2)
            state['active'] = {'run_id': run_id, 'cell_id': cell['cell_id'], 'started_at_jst': stamp()}
            save()
            for command in ('smoke', 'validate'):
                args = [sys.executable, '-X', 'utf8', str(CLI), '--project-root', str(ROOT), command, '--run-id', run_id]
                args += ['--cell-id', cell['cell_id'], '--end-sec', '1800'] if command == 'smoke' else ['--purpose', 'smoke']
                with (OUT / (run_id + '_' + command + '.stdout.log')).open('xb') as stdout, (
                        OUT / (run_id + '_' + command + '.stderr.log')).open('xb') as stderr:
                    child = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
                    state['active'].update(command=command, pid=child.pid)
                    save()
                    record('smoke_sequence_command_start', run_id=run_id, command=command, pid=child.pid, cell=cell)
                    code = child.wait()
                record('smoke_sequence_command_end', run_id=run_id, command=command, exit_code=code)
                if code:
                    raise RuntimeError(command + ' failed: ' + run_id)
            manifest_path = workspace / 'smoke' / run_id / 'manifest.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            proof = json.loads((OUT / (run_id + '_validate.stdout.log')).read_text(encoding='utf-8'))
            if (manifest['status'] != 'COMPLETED' or manifest['implementation_sha256'] != current
                    or proof['status'] != 'PASS' or proof['core_adoption_permitted']
                    or proof['manifest_sha256'] != sha(manifest_path)):
                raise RuntimeError('Manifest/independent proof mismatch')
            state['completed'].append({'run_id': run_id, 'cell': cell, 'manifest_sha256': sha(manifest_path),
                                       'validation_report': proof['validation_report'], 'finished_at_jst': stamp()})
            state['active'] = None
            save()
        state.update(status='COMPLETED', finished_at_jst=stamp())
    except BaseException as error:
        state.update(status='FAILED', finished_at_jst=stamp(), error_type=type(error).__name__, error=str(error))
        record('smoke_sequence_failed_preserved', error_type=type(error).__name__, error=str(error), active=state['active'])
        raise
    finally:
        save()
    record('smoke_sequence_completed', count=len(state['completed']), state=state_path.relative_to(ROOT).as_posix())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--audit', required=True)
    args = parser.parse_args()
    main(args.prefix, args.audit)
