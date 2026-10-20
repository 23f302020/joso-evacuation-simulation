"""Registered choice-series lifecycle with independently bound start evidence."""
import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
import hashlib
import subprocess
import shutil


def stamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def file_sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.2)


@contextmanager
def single_writer(workspace):
    directory = workspace / 'driver_logs'
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'writer.lock'
    if (directory / 'recovery.lock').exists():
        raise RuntimeError('Administrative writer recovery is in progress')
    with lock.open('x', encoding='utf-8') as stream:
        json.dump({'pid': os.getpid(), 'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat()}, stream)
    try:
        yield
    finally:
        lock.unlink()


def record_six_files(root, parameters, entry, text, already_locked=False):
    """Write only an independently accepted core entry; preserve a recovery journal.

    A caught failure restores exact original bytes. A process/machine crash is
    deliberately not called atomic: its PREPARED journal blocks subsequent starts
    until the six files are reconciled by the dedicated recovery path.
    """
    if (entry.get('purpose') != 'core' or entry.get('validation_status') != 'PASS'
            or entry.get('protocol') != parameters['protocol']):
        raise ValueError('Only validated core entries may be recorded')
    run_id = entry['run_id']
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id):
        raise ValueError('Invalid record run ID')
    paths = [root / name for name in parameters['record_files']]
    if (len(paths) != 6 or len(set(paths)) != 6 or paths[-1].suffix != '.jsonl'
            or any(not p.resolve().is_relative_to(root.resolve()) for p in paths)):
        raise ValueError('Exactly five local documents and one ledger are required')
    workspace = root / parameters['workspace']
    marker = '<!-- choice_record:' + run_id + ' -->'
    with (nullcontext() if already_locked else single_writer(workspace)):
        journals = workspace / 'record_transactions'
        journals.mkdir(parents=True, exist_ok=True)
        for pending in journals.glob('*/journal.json'):
            if json.loads(pending.read_text(encoding='utf-8'))['status'] == 'PREPARED':
                raise RuntimeError('Unresolved record journal blocks writes: ' + str(pending))
        ledger = [json.loads(line) for line in paths[-1].read_text(encoding='utf-8').splitlines() if line.strip()] if paths[-1].exists() else []
        if (len({r['run_id'] for r in ledger}) != len(ledger)
                or len({r['cell_id'] for r in ledger}) != len(ledger)
                or any(r['protocol'] != parameters['protocol'] for r in ledger)):
            raise RuntimeError('Duplicate or foreign research ledger entry')
        prior = next((r for r in ledger if r['run_id'] == run_id), None)
        if prior is not None and any(prior.get(k) != entry.get(k) for k in
                ('protocol', 'cell_id', 'implementation_sha256', 'input_manifest_sha256', 'manifest_sha256')):
            raise RuntimeError('Existing recorded identity differs from validation')
        if any(r['cell_id'] == entry['cell_id'] and r['run_id'] != run_id for r in ledger):
            raise RuntimeError('Registered cell already has another accepted run')
        if prior is not None and all(p.exists() and marker in p.read_text(encoding='utf-8') for p in paths[:-1]):
            return {'status': 'ALREADY_RECORDED', 'run_id': run_id}
        original = {p: p.read_bytes() if p.exists() else None for p in paths}
        block = '\n\n' + marker + '\n' + text.strip() + '\n'
        planned = {}
        for path in paths[:-1]:
            old = path.read_text(encoding='utf-8') if path.exists() else ''
            if marker in old:
                planned[path] = original[path]
            elif path.name == 'context.md':
                boundary = '\n<!-- AGENT_CURRENT_END -->'
                if old.count(boundary) != 1:
                    raise RuntimeError('Current context boundary is missing or ambiguous')
                planned[path] = old.replace(boundary, block + boundary, 1).encode('utf-8')
            else:
                planned[path] = (old + block).encode('utf-8')
        planned[paths[-1]] = (original[paths[-1]] or b'') + (
            (json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8') if prior is None else b'')
        transaction = journals / (run_id + '_' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
        transaction.mkdir(exist_ok=False)
        journal = {'status': 'PREPARED', 'run_id': run_id, 'pid': os.getpid(), 'files': []}
        digest = lambda value: hashlib.sha256(value).hexdigest()
        for i, (path, contents) in enumerate(original.items()):
            backup = str(i) + '.before'
            if contents is not None:
                (transaction / backup).write_bytes(contents)
            after = str(i) + '.planned'
            (transaction / after).write_bytes(planned[path])
            journal['files'].append({'path': path.relative_to(root).as_posix(), 'existed': contents is not None,
                                     'backup': backup if contents is not None else None,
                                     'sha256_before': digest(contents) if contents is not None else None,
                                     'planned': after, 'sha256_planned': digest(planned[path])})
        journal_path = transaction / 'journal.json'
        save_json(journal_path, journal)
        try:
            for path in paths[:-1]:
                if planned[path] == original[path]:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(planned[path].decode('utf-8'), encoding='utf-8', newline='')
            if prior is None:
                paths[-1].parent.mkdir(parents=True, exist_ok=True)
                with paths[-1].open('a', encoding='utf-8', newline='') as stream:
                    stream.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n')
            saved = [json.loads(line) for line in paths[-1].read_text(encoding='utf-8').splitlines() if line.strip()]
            if (sum(r['run_id'] == run_id for r in saved) != 1
                    or not all(marker in p.read_text(encoding='utf-8') for p in paths[:-1])
                    or any(p.read_bytes() != planned[p] for p in paths)):
                raise RuntimeError('Six-file record verification failed')
            journal.update(status='COMMITTED', sha256_after={p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in paths})
            save_json(journal_path, journal)
        except BaseException as error:
            for path, contents in original.items():
                if contents is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_bytes(contents)
            journal.update(status='ROLLED_BACK', error_type=type(error).__name__, error=str(error),
                           rollback_verified=all((p.read_bytes() == data if data is not None else not p.exists())
                                                 for p, data in original.items()))
            save_json(journal_path, journal)
            raise
    return {'status': 'RECORDED', 'run_id': run_id, 'transaction': transaction.relative_to(root).as_posix()}


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError('A positive process ID is required')
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    handle = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE, no termination right
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists
            return False
        raise ctypes.WinError(error)
    try:
        status = api.WaitForSingleObject(handle, 0)
        if status == 0x102:  # WAIT_TIMEOUT: still running
            return True
        if status == 0:  # WAIT_OBJECT_0: exited
            return False
        raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(handle)


def reserved_executor_identity(launcher_pid, executor_pid, parent_pid, windows):
    """Windows venv redirectors keep a launcher alive above the actual Python."""
    return (all(isinstance(value, int) and value > 0 for value in (launcher_pid, executor_pid, parent_pid))
            and (executor_pid == launcher_pid or (windows and parent_pid == launcher_pid)))


class ChoiceController:
    def __init__(self, root):
        self.root = root.resolve()
        self.param = self.root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
        self.parameters = json.loads(self.param.read_text(encoding='utf-8'))
        self.workspace = self.root / self.parameters['workspace']
        self.logs = self.workspace / 'driver_logs'
        self.logs.mkdir(parents=True, exist_ok=True)

    def implementation(self):
        return {name: file_sha(self.root / name) for name in self.parameters['execution']['implementation_files']}

    def records(self):
        return [(path, json.loads(path.read_text(encoding='utf-8')))
                for category in ('runs', 'smoke') for path in sorted((self.workspace / category).glob('*/manifest.json'))]

    def ledger(self):
        path = self.root / self.parameters['record_files'][-1]
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
        cells = {c['cell_id'] for c in self.parameters['cells']}
        if (len({r['run_id'] for r in rows}) != len(rows) or len({r['cell_id'] for r in rows}) != len(rows)
                or any(r['protocol'] != self.parameters['protocol'] or r['purpose'] != 'core'
                       or r['validation_status'] != 'PASS' or r['cell_id'] not in cells for r in rows)):
            raise RuntimeError('Duplicate, unvalidated or foreign research ledger entry')
        return rows

    def find(self, run_id, purpose=None):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id):
            raise ValueError('Invalid run ID')
        paths = [self.workspace / 'runs' / run_id / 'manifest.json',
                 self.workspace / 'smoke' / run_id / 'manifest.json',
                 self.workspace / 'technical' / run_id / 'execution/manifest.json']
        matches = [(p, json.loads(p.read_text(encoding='utf-8'))) for p in paths if p.is_file()]
        if len(matches) != 1 or (purpose is not None and matches[0][1]['purpose'] != purpose):
            raise ValueError('Run ID is missing, ambiguous or has another purpose')
        return matches[0]

    def process_inventory(self):
        if os.name != 'nt':
            return []
        command = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('sumo.exe','sumo-gui.exe') -or "
                   "($_.Name -like 'python*' -and $_.CommandLine -like '*realtime_choice_cell.py*execute*') } | "
                   "Select-Object ProcessId,Name | ConvertTo-Json -Compress")
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, check=True)
        data = json.loads(result.stdout) if result.stdout.strip() else []
        return data if isinstance(data, list) else [data]

    def pending_journals(self):
        result = []
        for directory in (self.workspace / 'record_transactions').glob('*'):
            if not directory.is_dir():
                continue
            path = directory / 'journal.json'
            if not path.exists() or json.loads(path.read_text(encoding='utf-8'))['status'] == 'PREPARED':
                result.append(directory.name)
        return result

    def status(self, inspect_processes=False):
        records, ledger = self.records(), self.ledger()
        pending_journals = self.pending_journals()
        pending_runs = set()
        for name in pending_journals:
            path = self.workspace / 'record_transactions' / name / 'journal.json'
            pending_runs.add(json.loads(path.read_text(encoding='utf-8')).get('run_id') if path.exists() else name.rsplit('_', 1)[0])
        by_id = {m['run_id']: (path, m) for path, m in records}
        if len(by_id) != len(records):
            raise RuntimeError('Ambiguous run IDs')
        recorded, partial, bad_identity = set(), [], []
        current = self.implementation()
        for row in ledger:
            if row['run_id'] in pending_runs:
                partial.append(row['run_id'])
                continue
            marker = '<!-- choice_record:' + row['run_id'] + ' -->'
            matched = by_id.get(row['run_id'])
            proof = self.root / row['validation_report']
            valid = (matched is not None and matched[1]['purpose'] == 'core'
                and matched[1]['cell_id'] == row['cell_id'] and matched[1]['status'] == 'COMPLETED'
                and file_sha(matched[0]) == row['manifest_sha256']
                and row['implementation_sha256'] == current
                and proof.is_file() and file_sha(proof) == row['validation_report_sha256'])
            if not valid:
                bad_identity.append(row['run_id'])
                continue
            validation = json.loads(proof.read_text(encoding='utf-8'))
            if validation['status'] != 'PASS' or validation['core_adoption_permitted'] is not True:
                bad_identity.append(row['run_id'])
                continue
            complete = True
            for name in self.parameters['record_files'][:-1]:
                path = self.root / name
                text = path.read_text(encoding='utf-8') if path.exists() else ''
                if path.name == 'context.md':
                    text = text.split('\n<!-- AGENT_CURRENT_END -->')[0]
                complete &= marker in text
            if complete:
                recorded.add(row['run_id'])
            else:
                partial.append(row['run_id'])
        running = [m['run_id'] for _, m in records if m['status'] == 'RUNNING']
        for path in (self.workspace / 'technical').glob('*/manifest.json'):
            m = json.loads(path.read_text(encoding='utf-8'))
            if m.get('status') == 'RUNNING':
                running.append(m['run_id'])
        launch_holds = []
        for path in self.logs.glob('*.state.json'):
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['run_id'] not in by_id and not (self.logs / (state['run_id'] + '.diagnosis.json')).exists():
                launch_holds.append(state['run_id'])
        cores = [m for _, m in records if m['purpose'] == 'core']
        unresolved = [m['run_id'] for m in cores if m['status'] in ('FAILED', 'INVALID')
                      and not (self.logs / (m['run_id'] + '.diagnosis.json')).exists()]
        unrecorded = [m['run_id'] for m in cores if m['status'] == 'COMPLETED' and m['run_id'] not in recorded]
        accepted_cells = {row['cell_id'] for row in ledger if row['run_id'] in recorded}
        foreign = []
        for sibling in self.workspace.parent.iterdir():
            if not sibling.is_dir() or sibling == self.workspace:
                continue
            for pattern in ('runs/*/manifest.json', 'smoke/*/manifest.json', 'technical/*/manifest.json'):
                for path in sibling.glob(pattern):
                    m = json.loads(path.read_text(encoding='utf-8'))
                    if m.get('status') == 'RUNNING':
                        foreign.append(path.relative_to(self.root).as_posix())
        return {'protocol': self.parameters['protocol'], 'registered_cells': len(self.parameters['cells']),
                'recorded_cells': len(accepted_cells), 'running': running, 'unrecorded': unrecorded,
                'partial_records': partial, 'record_identity_mismatch': bad_identity,
                'unresolved_failures': unresolved, 'unresolved_launches': launch_holds,
                'pending_record_journals': pending_journals,
                'foreign_running_manifests': foreign,
                'next_cell': next((c for c in self.parameters['cells'] if c['cell_id'] not in accepted_cells), None),
                'smoke_completed': [m['run_id'] for _, m in records if m['purpose'] == 'smoke' and m['status'] == 'COMPLETED'],
                'failed': [m['run_id'] for _, m in records if m['status'] == 'FAILED'],
                'active_native_processes': self.process_inventory() if inspect_processes else [],
                'core_ready': False, 'core_start_available': False}

    def assert_idle(self, allow_unrecorded=False, allow_journals=False):
        state = self.status(inspect_processes=True)
        keys = ['running', 'record_identity_mismatch', 'unresolved_failures', 'unresolved_launches',
                'active_native_processes', 'foreign_running_manifests']
        if not allow_unrecorded:
            keys += ['unrecorded', 'partial_records']
        if not allow_journals:
            keys += ['pending_record_journals']
        blocked = {key: state[key] for key in keys if state[key]}
        if blocked:
            raise RuntimeError('Current work blocks mutation: ' + json.dumps(blocked, ensure_ascii=False))
        return state

    def ready(self):
        from scripts.jdrt_realtime_choice_validate import verify_preflight_receipt
        path = self.workspace / 'preflight_ready.json'
        if not path.is_file():
            return False
        checks = verify_preflight_receipt(json.loads(path.read_text(encoding='utf-8')), self.parameters)
        return bool(checks) and all(checks.values())

    def launch(self, run_id):
        """Reserve one new ID before creating its detached executor."""
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', run_id):
            raise ValueError('Use a new simple run ID of at most 40 characters')
        with single_writer(self.workspace):
            state = self.assert_idle()
            if state['next_cell'] is None:
                return {'status': 'ALL_RECORDED'}
            if not self.ready():
                raise RuntimeError('Current independent READY evidence required')
            receipt = json.loads((self.workspace / 'preflight_ready.json').read_text(encoding='utf-8'))
            reserve = json.loads((self.root / receipt['evidence']['storage']).read_text(encoding='utf-8'))
            if shutil.disk_usage(self.workspace).free < reserve['one_run_reserve_bytes']:
                raise RuntimeError('Insufficient free storage for the next complete run')
            path = self.logs / (run_id + '.state.json')
            if path.exists() or any((self.workspace / name / run_id).exists() for name in ('runs', 'smoke', 'technical')):
                raise RuntimeError('Run ID has already been used')
            cell = state['next_cell']
            command = [sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--project-root', str(self.root),
                       'execute', '--run-id', run_id, '--cell-id', cell['cell_id']]
            launch = {'run_id': run_id, 'cell_id': cell['cell_id'], 'purpose': 'core', 'status': 'PREPARED',
                      'at_jst': stamp(), 'pid': None, 'parent_pid': os.getpid(), 'command': command,
                      'implementation_sha256': self.implementation(), 'ready_sha256': file_sha(self.workspace / 'preflight_ready.json')}
            save_json(path, launch)
            try:
                with (self.logs / (run_id + '.stdout.log')).open('xb') as stdout, (self.logs / (run_id + '.stderr.log')).open('xb') as stderr:
                    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                    child = subprocess.Popen(command, cwd=self.root, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                             creationflags=flags, start_new_session=os.name != 'nt')
                launch.update(status='LAUNCHED', pid=child.pid)
                save_json(path, launch)
            except BaseException as error:
                # PREPARED remains a hold until explicit recovery, even when Popen failed.
                launch.update(error_type=type(error).__name__, error=str(error))
                save_json(path, launch)
                raise
            return {'status': 'STARTED', 'run_id': run_id, 'cell_id': cell['cell_id'], 'pid': child.pid,
                    'state_path': path.relative_to(self.root).as_posix()}

    def execute(self, run_id, cell_id):
        path = self.logs / (run_id + '.state.json')
        # Parent writes the child PID immediately after Popen; wait at most 10s.
        for _ in range(100):
            launch = json.loads(path.read_text(encoding='utf-8'))
            if launch['status'] == 'LAUNCHED':
                break
            time.sleep(.1)
        launcher_pid = launch['pid']
        if (launch['status'] != 'LAUNCHED'
                or not reserved_executor_identity(launcher_pid, os.getpid(), os.getppid(), os.name == 'nt')
                or not pid_alive(launcher_pid) or launch['run_id'] != run_id
                or launch['cell_id'] != cell_id or launch['purpose'] != 'core'
                or launch['implementation_sha256'] != self.implementation()
                or launch['ready_sha256'] != file_sha(self.workspace / 'preflight_ready.json')):
            raise RuntimeError('Executor is not the reserved child with current source/evidence')
        launch.update(launcher_pid=launcher_pid, executor_pid=os.getpid(), executor_parent_pid=os.getppid(),
                      pid=os.getpid(), executor_started_at_jst=stamp())
        save_json(path, launch)
        from scripts.jdrt_realtime_choice import run
        return run(cell_id, run_id, purpose='core')

    def recover_launch(self, run_id, reason):
        if not reason.strip() or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', run_id):
            raise ValueError('A simple run ID and reason are required')
        with single_writer(self.workspace):
            path = self.logs / (run_id + '.state.json')
            raw = path.read_bytes()
            state = json.loads(raw)
            if ((state.get('pid') is not None and pid_alive(state['pid']))
                    or pid_alive(state['parent_pid']) or self.process_inventory()
                    or any(m['run_id'] == run_id for _, m in self.records())):
                raise RuntimeError('Launch is live or already has a manifest; use run recovery where appropriate')
            archive = self.logs / (run_id + '.' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.original_state.json')
            archive.write_bytes(raw)
            diagnosis = {'run_id': run_id, 'status': 'FAILED_LAUNCH_PRESERVED', 'reason': reason, 'at_jst': stamp(),
                         'original_state': archive.relative_to(self.root).as_posix(), 'sha256': file_sha(archive)}
            save_json(self.logs / (run_id + '.diagnosis.json'), diagnosis)
            return diagnosis

    def preflight(self, suite_id, counterexample_report):
        """Recompute prerequisite proofs; never fabricate technical PASS receipts."""
        from scripts import jdrt_realtime_choice_validate as verifier
        with single_writer(self.workspace):
            self.assert_idle()
            attempt = self.workspace / 'preflight' / datetime.now().strftime('%Y%m%dT%H%M%S%f')
            attempt.mkdir(parents=True, exist_ok=False)
            input_proof = verifier.validate_inputs()
            input_path = attempt / 'input.json'
            save_json(input_path, input_proof)
            modules = ['tests.test_jdrt_choice_' + name for name in ('skill', 'validate', 'runtime', 'policy')]
            unit_path = attempt / 'unit.json'
            program = (
                'import json,sys,unittest\n'
                'def flatten(s):\n'
                ' for t in s:\n'
                '  if isinstance(t,unittest.TestSuite): yield from flatten(t)\n'
                '  else: yield t.id()\n'
                's=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[2:])\n'
                'ids=list(flatten(s))\n'
                'r=unittest.TextTestRunner(verbosity=2).run(s)\n'
                'v={"status":"PASS" if r.wasSuccessful() and not r.skipped else "FAIL",'
                '"tests_run":r.testsRun,"test_ids":ids,"skipped":[(t.id(),x) for t,x in r.skipped],'
                '"failures":[(t.id(),x) for t,x in r.failures+r.errors]}\n'
                'open(sys.argv[1],"x",encoding="utf-8").write(json.dumps(v,ensure_ascii=False,indent=2))\n'
                'sys.exit(0 if v["status"]=="PASS" else 1)\n')
            with (attempt / 'unit.stdout.log').open('xb') as stdout, (attempt / 'unit.stderr.log').open('xb') as stderr:
                tested = subprocess.run([sys.executable, '-X', 'utf8', '-c', program, str(unit_path), *modules],
                                        cwd=self.root / '04_プログラム', stdout=stdout, stderr=stderr)
            unit = json.loads(unit_path.read_text(encoding='utf-8'))
            unit.update(at_jst=stamp(), process_exit_code=tested.returncode, implementation_sha256=self.implementation(),
                        test_source_sha256={'04_プログラム/' + name.replace('.', '/') + '.py':
                            file_sha(self.root / '04_プログラム' / (name.replace('.', '/') + '.py')) for name in modules})
            save_json(unit_path, unit)
            suite_path = self.workspace / 'technical' / suite_id / 'manifest.json'
            suite = json.loads(suite_path.read_text(encoding='utf-8'))
            fixture_proofs = [self.validate(row['child_run_id'], 'fixture') for row in suite['cases']]
            smokes = []
            current = self.implementation()
            for cell in self.parameters['cells']:
                if cell['seed'] != self.parameters['seeds'][0]:
                    continue
                choices = [(path, m) for path, m in self.records() if m['purpose'] == 'smoke'
                           and m['cell_id'] == cell['cell_id'] and m['status'] == 'COMPLETED'
                           and m['implementation_sha256'] == current]
                if not choices:
                    raise RuntimeError('Missing current smoke: ' + cell['cell_id'])
                path, m = max(choices, key=lambda row: row[1]['finished_at_jst'])
                smokes.append(self.validate(m['run_id'], 'smoke'))
            proofs = fixture_proofs + smokes
            storage_path = attempt / 'storage.json'
            storage = self.storage_proof(smokes)
            save_json(storage_path, storage)
            counterexample_path = (self.root / counterexample_report).resolve()
            if not counterexample_path.is_relative_to(self.root):
                raise ValueError('Counterexample evidence must be local')
            evidence = {'input': input_path.relative_to(self.root).as_posix(),
                        'unit': unit_path.relative_to(self.root).as_posix(),
                        'storage': storage_path.relative_to(self.root).as_posix(),
                        'fixture_manifest': suite_path.relative_to(self.root).as_posix(),
                        'counterexamples': counterexample_path.relative_to(self.root).as_posix(),
                        'fixture_validations': [v['validation_report'] for v in fixture_proofs],
                        'smoke_validations': [v['validation_report'] for v in smokes]}
            bound = {}
            def bind(path):
                path = path.resolve()
                if not path.is_relative_to(self.root):
                    raise ValueError('Evidence escapes workspace')
                name = path.relative_to(self.root).as_posix()
                if name not in bound:
                    bound[name] = file_sha(path)
            for label, names in evidence.items():
                for name in names if isinstance(names, list) else [names]:
                    bind(self.root / name)
            for v in proofs:
                mp, m = self.find(v['run_id'], v['purpose'])
                bind(mp)
                folder = mp.parent
                bind(self.root / m['parameter_path'])
                inputs = self.root / m['input_directory']
                bind(inputs / 'manifest.json')
                im = json.loads((inputs / 'manifest.json').read_text(encoding='utf-8'))
                for name in im['artifacts']:
                    bind(inputs / name)
                for name in im['source_sha256']:
                    bind(self.root / name)
                for name in m['output_sha256']:
                    bind(folder / name)
                for name in m['implementation_sha256']:
                    bind(folder / 'implementation' / name)
            passed = (input_proof['status'] == unit['status'] == storage['status'] == 'PASS'
                      and all(v['status'] == 'PASS' for v in proofs))
            receipt = {'status': 'READY' if passed else 'NOT_READY', 'created_at_jst': stamp(),
                       'protocol': self.parameters['protocol'], 'parameter_sha256': file_sha(self.param),
                       'input_manifest_sha256': input_proof['input_manifest_sha256'],
                       'implementation_sha256': current, 'runtime_sha256': verifier.runtime_fingerprint(),
                       'verifier_dependencies': verifier.verifier_dependencies(), 'evidence': evidence,
                       'evidence_sha256': bound,
                       'checks': {name: passed for name in set(self.parameters['acceptance_gates']) |
                                  {'unit_tests', 'six_file_record_transaction', 'storage_and_single_writer'}}}
            receipt['independent_receipt_checks'] = verifier.verify_preflight_receipt(receipt, self.parameters)
            if not all(receipt['independent_receipt_checks'].values()):
                receipt['status'] = 'NOT_READY'
            save_json(attempt / 'receipt.json', receipt)
            if receipt['status'] == 'READY':
                target = self.workspace / 'preflight_ready.json'
                if target.exists():
                    (attempt / 'previous_ready.json').write_bytes(target.read_bytes())
                save_json(target, receipt)
            return {'status': receipt['status'], 'report': (attempt / 'receipt.json').relative_to(self.root).as_posix(),
                    'checks': receipt['independent_receipt_checks']}

    def storage_proof(self, smokes):
        """Conservative measured scaling; reserve one run, disclose all-run projection."""
        import csv
        from math import ceil
        inputs = self.workspace / self.parameters['input_directory']
        population = sum(1 for _ in csv.DictReader((inputs / ('common_realization_seed' + str(self.parameters['seeds'][0]) + '.csv')).open(encoding='utf-8')))
        bounds, sources = [], []
        for proof in smokes:
            path, m = self.find(proof['run_id'], 'smoke')
            folder = path.parent
            with (folder / 'person_results.csv').open(encoding='utf-8') as stream:
                cohort = sum(1 for _ in csv.DictReader(stream))
            observed = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
            # Fourfold headroom for longer routes/strings/event rates; never
            # call this a mathematical bound on gzip or a guarantee for all70.
            estimate = ceil(observed * population / max(cohort, 1)
                            * self.parameters['simulation']['duration_sec'] / m['end_sec'] * 4)
            bounds.append(estimate)
            sources.append({'run_id': m['run_id'], 'bytes': observed, 'cohort': cohort, 'end_sec': m['end_sec'],
                            'manifest_sha256': file_sha(path), 'scaled_bytes_with_headroom': estimate})
        reserve = max(bounds, default=0) + 5 * 1024 ** 3
        free = shutil.disk_usage(self.workspace).free
        # The enclosing preflight owns writer.lock; nested acquisition must fail.
        writer_ok = False
        try:
            with single_writer(self.workspace):
                pass
        except FileExistsError:
            writer_ok = True
        remaining = len(self.parameters['cells']) - self.status()['recorded_cells']
        return {'status': 'PASS' if bounds and free >= reserve and writer_ok else 'FAIL', 'at_jst': stamp(),
                'implementation_sha256': self.implementation(), 'parameter_sha256': file_sha(self.param),
                'population': population, 'free_bytes': free, 'one_run_reserve_bytes': reserve,
                'remaining_runs': remaining, 'remaining_projection_bytes': reserve * remaining,
                'all_remaining_projected_fit': free >= reserve * remaining, 'writer_checks_pass': writer_ok,
                'policy': 'rolling_one_run_reserve_rechecked_before_each_start_preserve_all_outputs',
                'limitation': 'empirical scaled estimate with 4x headroom and 5GiB reserve; not a gzip worst-case proof',
                'sources': sources}

    def check(self, run_id):
        path, m = self.find(run_id)
        progress = path.parent / 'progress.json'
        return {'run_id': run_id, 'status': m['status'], 'pid_alive': pid_alive(m['pid']) if m['status'] == 'RUNNING' else False,
                'progress': json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else None,
                'error': m.get('error')}

    def validate(self, run_id, purpose='core'):
        self.find(run_id, purpose)
        from scripts.jdrt_realtime_choice_validate import validate_run
        return validate_run(run_id, purpose)

    def record(self, run_id):
        with single_writer(self.workspace):
            self.assert_idle(allow_unrecorded=True)
            path, m = self.find(run_id, 'core')
            v = self.validate(run_id, 'core')
            if v['status'] != 'PASS' or v['core_adoption_permitted'] is not True:
                raise RuntimeError('Formal independent core validation PASS required')
            if m['implementation_sha256'] != self.implementation() or file_sha(path) != v['manifest_sha256']:
                raise RuntimeError('Source identity changed before record')
            proof = self.root / v['validation_report']
            entry = {'protocol': self.parameters['protocol'], 'purpose': 'core', 'run_id': run_id,
                     'cell_id': m['cell_id'], 'scenario': m['scenario'], 'seed': m['seed'],
                     'destination_policy': m['destination_policy'], 'demand_level': m['demand_level'],
                     'validation_status': 'PASS', 'validation_report': v['validation_report'],
                     'validation_report_sha256': file_sha(proof), 'manifest_sha256': v['manifest_sha256'],
                     'input_manifest_sha256': m['input_manifest_sha256'], 'implementation_sha256': m['implementation_sha256'],
                     'recorded_at_jst': stamp(), 'primary': v['components']['person_tables']}
            p = entry['primary']
            text = (f"### {run_id}（{entry['recorded_at_jst']}正式記録）\n\n"
                    f"protocol={entry['protocol']}、cell={entry['cell_id']}、{entry['scenario']}、seed={entry['seed']}。"
                    f"独立検証PASS・研究採用可。人物{p['people']}、要求{p['requests']}。"
                    f"主指標の施設受入={p['primary_admitted']}/{p['primary_denominator']}、"
                    f"退出{p['primary_boundary_exit_separate']}は別計上。全登録セル完了前に方向解釈しない。\n"
                    f"一次検証：`{v['validation_report']}`。次の1件は専用CLI statusを参照。")
            return record_six_files(self.root, self.parameters, entry, text, already_locked=True)

    def recover_record(self, transaction_id, reason):
        if not reason.strip() or Path(transaction_id).name != transaction_id:
            raise ValueError('A local transaction ID and reason are required')
        with single_writer(self.workspace):
            # A crash can leave the ledger itself as partial JSON. Do not parse
            # it before the independently hashed six-file journal is restored.
            if self.process_inventory() or any(m['status'] == 'RUNNING' and pid_alive(m['pid']) for _, m in self.records()):
                raise RuntimeError('A live executor blocks record recovery')
            directory = self.workspace / 'record_transactions' / transaction_id
            journal_path = directory / 'journal.json'
            journal = json.loads(journal_path.read_text(encoding='utf-8'))
            if journal['status'] != 'PREPARED' or pid_alive(journal['pid']):
                raise RuntimeError('Only an orphaned PREPARED transaction can be restored')
            if [r['path'] for r in journal['files']] != self.parameters['record_files']:
                raise RuntimeError('Journal targets differ from registered record files')
            restore = {}
            for row in journal['files']:
                path = self.root / row['path']
                if not path.resolve().is_relative_to(self.root):
                    raise RuntimeError('Journal target escapes workspace')
                planned = directory / row['planned']
                if planned.parent != directory or file_sha(planned) != row['sha256_planned']:
                    raise RuntimeError('Planned record bytes are missing or changed')
                before = None
                if row['existed']:
                    backup = directory / row['backup']
                    if backup.parent != directory or file_sha(backup) != row['sha256_before']:
                        raise RuntimeError('Record backup bytes changed')
                    before = backup.read_bytes()
                current = path.read_bytes() if path.exists() else None
                if current is not None and current != before and not planned.read_bytes().startswith(current):
                    raise RuntimeError('Record target contains an unrelated change; preserve for reconciliation')
                restore[path] = before
            observed = directory / ('recovery_' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
            observed.mkdir(exist_ok=False)
            for i, (path, before) in enumerate(restore.items()):
                if path.exists():
                    (observed / (str(i) + '.observed')).write_bytes(path.read_bytes())
                if before is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_bytes(before)
            journal.update(status='RECOVERED_ROLLBACK', recovered_at_jst=stamp(), reason=reason,
                           rollback_verified=all(p.read_bytes() == b if b is not None else not p.exists() for p, b in restore.items()))
            save_json(journal_path, journal)
            return {'status': 'RECOVERED_ROLLBACK', 'transaction': transaction_id, 'run_id': journal['run_id']}

    def recover_writer(self, reason):
        if not reason.strip():
            raise ValueError('A recovery reason is required')
        administrative = self.logs / 'recovery.lock'
        with administrative.open('x', encoding='utf-8') as stream:
            json.dump({'pid': os.getpid(), 'at_jst': stamp()}, stream)
        try:
            path = self.logs / 'writer.lock'
            raw = path.read_bytes()
            owner = json.loads(raw)
            if pid_alive(owner['pid']):
                raise RuntimeError('Writer owner is still alive')
            if self.process_inventory():
                raise RuntimeError('Native/executor process is still active')
            archive = self.logs / ('writer_' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.preserved.json')
            archive.write_bytes(raw)
            if path.read_bytes() != raw:
                raise RuntimeError('Writer changed during recovery')
            path.unlink()
            save_json(archive.with_suffix('.diagnosis.json'), {'reason': reason, 'recovered_at_jst': stamp(), 'original': archive.name})
            return {'status': 'ORPHAN_WRITER_PRESERVED', 'archive': archive.relative_to(self.root).as_posix()}
        finally:
            administrative.unlink()

    def recover_run(self, run_id, reason, reject=False):
        if not reason.strip():
            raise ValueError('A recovery reason is required')
        with single_writer(self.workspace):
            path, m = self.find(run_id)
            if any(r['run_id'] == run_id for r in self.ledger()):
                raise RuntimeError('An accepted run cannot be recovered or rejected')
            if pid_alive(m['pid']) or self.process_inventory():
                raise RuntimeError('Run/native process is still alive')
            if (not reject and m['status'] != 'RUNNING') or (reject and m['status'] == 'RUNNING'):
                raise RuntimeError('Recover requires orphan RUNNING; reject requires a stopped run')
            original = self.logs / (run_id + '.' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.original_manifest.json')
            original.write_bytes(path.read_bytes())
            m.update(status='INVALID' if reject else 'FAILED', finished_at_jst=stamp(),
                     error_type='RejectedAfterValidation' if reject else 'RecoveredOrphan', error=reason)
            save_json(path, m)
            save_json(self.logs / (run_id + '.diagnosis.json'), {'run_id': run_id, 'at_jst': stamp(), 'reason': reason,
                'original_manifest': original.relative_to(self.root).as_posix(), 'original_sha256': file_sha(original),
                'preserved_manifest_sha256': file_sha(path), 'disposition': 'preserved; new run ID required'})
            return {'status': m['status'] + '_PRESERVED', 'run_id': run_id}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    start_next = commands.add_parser('start-next')
    start_next.add_argument('--run-id', required=True)
    execute = commands.add_parser('execute', help=argparse.SUPPRESS)
    execute.add_argument('--run-id', required=True)
    execute.add_argument('--cell-id', required=True)
    preflight = commands.add_parser('preflight')
    preflight.add_argument('--suite-id', required=True)
    preflight.add_argument('--counterexamples', required=True)
    record = commands.add_parser('record')
    record.add_argument('--run-id', required=True)
    for name in ('recover', 'reject', 'recover-launch'):
        sub = commands.add_parser(name)
        sub.add_argument('--run-id', required=True)
        sub.add_argument('--reason', required=True)
    journal = commands.add_parser('recover-record')
    journal.add_argument('--transaction-id', required=True)
    journal.add_argument('--reason', required=True)
    writer = commands.add_parser('recover-writer')
    writer.add_argument('--reason', required=True)
    check = commands.add_parser('check')
    check.add_argument('--run-id', required=True)
    validate = commands.add_parser('validate')
    validate.add_argument('--run-id', required=True)
    validate.add_argument('--purpose', choices=('core', 'smoke', 'fixture'), default='core')
    smoke = commands.add_parser('smoke')
    smoke.add_argument('--run-id', required=True)
    smoke.add_argument('--cell-id', required=True)
    smoke.add_argument('--end-sec', type=int, default=1800)
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / '04_プログラム'))
    controller = ChoiceController(root)
    start = time.monotonic()
    result = None
    try:
        if args.command == 'status':
            result = controller.status(inspect_processes=True)
            result['core_ready'] = controller.ready()
            result['core_start_available'] = result['core_ready'] and result['next_cell'] is not None and not any(
                result[k] for k in ('running', 'unrecorded', 'partial_records', 'record_identity_mismatch',
                'unresolved_failures', 'unresolved_launches', 'active_native_processes', 'foreign_running_manifests',
                'pending_record_journals')) and not (controller.logs / 'writer.lock').exists()
        elif args.command == 'check':
            result = controller.check(args.run_id)
        elif args.command == 'validate':
            result = controller.validate(args.run_id, args.purpose)
        elif args.command == 'record':
            result = controller.record(args.run_id)
        elif args.command == 'start-next':
            result = controller.launch(args.run_id)
        elif args.command == 'execute':
            result = controller.execute(args.run_id, args.cell_id)
        elif args.command == 'preflight':
            result = controller.preflight(args.suite_id, args.counterexamples)
        elif args.command in ('recover', 'reject'):
            result = controller.recover_run(args.run_id, args.reason, reject=args.command == 'reject')
        elif args.command == 'recover-launch':
            result = controller.recover_launch(args.run_id, args.reason)
        elif args.command == 'recover-record':
            result = controller.recover_record(args.transaction_id, args.reason)
        elif args.command == 'recover-writer':
            result = controller.recover_writer(args.reason)
        elif args.command == 'smoke':
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', args.run_id):
                raise ValueError('Use a simple unique smoke ID of at most 40 characters')
            with single_writer(controller.workspace):
                controller.assert_idle()
                from scripts.jdrt_realtime_choice import run
                result = run(args.cell_id, args.run_id, purpose='smoke', smoke_end=args.end_sec)
    except BaseException as error:
        result = {'run_id': getattr(args, 'run_id', None), 'error_type': type(error).__name__, 'error': str(error)}
        raise
    finally:
        log(controller.workspace, args.command, {'duration_sec': time.monotonic() - start, 'result': result})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command in ('validate', 'preflight') and result['status'] not in ('PASS', 'READY'):
        raise SystemExit(1)


def log(workspace, command, result):
    directory = workspace / 'driver_logs'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'operations.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
                                 'command': command, 'result': result}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
