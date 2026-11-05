"""Sequential registered choice cells through existing, unchanged skill gates.

Never resumes an existing sequence, retries a scientific command, recovers,
deletes, kills, changes inputs, or declares the research goal complete.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
BASE = '.agents/skills/joso-jdrt-runner/scripts/'
CONFIG = '04_プログラム/config/jdrt_realtime_choice_v1.json'
GOAL = '06_研究結果/jdrt/goal_20261017'
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


def require_idle(status, count, cell):
    require(all(key in status and status[key] == [] for key in HOLDS),
            'Unresolved or missing status hold; preserve and stop')
    require(status.get('recorded_cells') == count and status.get('next_cell') == cell
            and status.get('core_ready') is True
            and status.get('core_start_available') is True,
            'Current count, ordered next cell and fresh READY/start permission required')


def require_observer(status):
    age = status.get('observation_age_sec')
    require(status.get('monitor_identity_matches') is True
            and status.get('monitor_process', {}).get('state') == 'alive'
            and type(age) in (int, float) and math.isfinite(age) and 0 <= age <= 120,
            'Independent observer identity/liveness/freshness not proven')


def finish_order(invoke, run_id):
    invoke('finish', run_id)
    invoke('readback', run_id)
    invoke('sync', run_id)


def require_readback(proof, cfg, count, ledger):
    require(proof.get('status') == 'RECORD7_PRIMARY_READBACK_PASS'
            and proof.get('registration_id') == cfg['registration_id']
            and proof.get('recorded_cells') == count == len(ledger)
            and bool(ledger) and proof.get('formal_row') == ledger[-1]
            and proof.get('run_id') == ledger[-1]['run_id']
            and [row.get('cell_id') for row in ledger]
                == [cell['cell_id'] for cell in cfg['cells'][:count]]
            and len({row['run_id'] for row in ledger}) == count
            and all(row.get('protocol') == cfg['protocol']
                    and row.get('registration_id') == cfg['registration_id'] for row in ledger)
            and proof.get('six_document_single_markers') is True
            and proof.get('unique_current_registration_ledger') is True
            and proof.get('source_common5_current') is True
            and proof.get('all_status_holds_clear_at_finish') is True
            and proof.get('original_and_record_validation_components_differ') == [],
            'Previous complete seven-file readback and actual ordered ledger required')


def terminal_process_absent(identity, expected):
    require(identity.get('state') in ('alive', 'absent'), 'Core process identity is unknown')
    if identity['state'] == 'absent':
        return True
    require(expected is not None and identity == expected,
            'Core PID was reused or original creation identity was not observed')
    return False


def require_scope(count, cells, total):
    require(type(count) is int and type(cells) is int
            and cells == 1 and count > 0 and count < total,
            'Exactly one cell per invocation; parent must recheck the goal before the next cell')


class Sequence:
    def __init__(self, root, sequence_id, prefix, count, cells, prior_readback):
        self.root = Path(root).resolve()
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,40}', sequence_id)
                and re.fullmatch(r'[A-Za-z0-9_-]{1,36}', prefix), 'Simple new IDs required')
        self.cfg = read(self.root / CONFIG)
        require(self.cfg['protocol'] == 'realtime_choice_v1'
                and self.cfg.get('municipality_code') == '08211'
                and self.cfg.get('registration_id'), 'Registered choice series only')
        self.workspace = self.local(self.cfg['workspace'])
        require_scope(count, cells, len(self.cfg['cells']))
        require(os.environ.get('JDRT_CHOICE_TOOLCHAIN_MANIFEST'), 'Explicit selected toolchain required')
        self.prior_readback = self.local(prior_readback)
        self.count, self.cells, self.prefix = count, cells, prefix
        names = [CONFIG, *self.cfg['execution']['implementation_files'],
                 BASE + 'choice_core_sequence.py', BASE + 'choice_finish_cell.py',
                 BASE + 'choice_record_readback.py', BASE + 'choice_monitor.py',
                 BASE + 'choice_sync_status.py', BASE + 'status_progress.py',
                 '07_監視システム/watch.py']
        self.pins = {name: digest(self.local(name)) for name in names}
        self.operation = self.workspace / 'driver_logs/core_sequences' / sequence_id
        self.operation.mkdir(parents=True, exist_ok=False)
        self.evidence = self.local(GOAL) / 'core_sequence_evidence' / sequence_id
        self.evidence.mkdir(parents=True, exist_ok=False)
        self.serial = 0
        self.state = {'status': 'RUNNING', 'pid': os.getpid(),
                      'registration_id': self.cfg['registration_id'],
                      'sequence_id': sequence_id, 'expected_initial_recorded': count,
                      'maximum_new_cells': cells, 'pins': self.pins,
                      'run_prefix': prefix, 'initial_readback': self.prior_readback.as_posix(),
                      'initial_readback_sha256': digest(self.prior_readback),
                      'completed': [], 'active': None, 'goal_complete': False}
        self.save()

    def local(self, name):
        path = (self.root / name).resolve()
        require(path.is_relative_to(self.root), 'Path escapes project')
        return path

    def save(self):
        self.state['at_jst'] = datetime.now().astimezone().isoformat()
        temporary = self.operation / 'state.tmp'
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for attempt in range(5):
            try:
                temporary.replace(self.operation / 'state.json')
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.2)

    def event(self, action, **values):
        row = {'at_jst': datetime.now().astimezone().isoformat(),
               'action': action, 'sequence_id': self.state['sequence_id'], **values}
        for path in (self.local(GOAL) / 'operations.jsonl', self.workspace / 'driver_logs/monitoring.jsonl'):
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    def command(self, script, arguments, parse=True):
        require(all(digest(self.local(p)) == value for p, value in self.pins.items()),
                'Pinned source/config changed; no subsequent command permitted')
        self.serial += 1
        label = str(self.serial).zfill(4)
        command = [sys.executable, '-B', '-X', 'utf8', str(self.local(script)), *arguments]
        out, err = self.operation / (label + '.stdout.log'), self.operation / (label + '.stderr.log')
        self.state['command'] = {'argv': command, 'stdout': out.as_posix(), 'stderr': err.as_posix()}
        self.save()
        with out.open('xb') as stdout, err.open('xb') as stderr:
            child = subprocess.Popen(command, cwd=self.root, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr,
                                     env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.state['command']['launcher_pid'] = child.pid
            self.save()
            # A caller/observation timeout never retries, kills or replaces this child.
            code = child.wait()
        self.state['command']['exit_code'] = code
        self.save()
        require(code == 0, 'Command failed; inspect its original logs, never replay automatically')
        require(all(digest(self.local(p)) == value for p, value in self.pins.items()),
                'Pinned source/config changed during command')
        return read(out) if parse else None

    def cli(self, command, *args):
        return self.command(BASE + 'realtime_choice_cell.py',
                            ['--project-root', str(self.root), command, *args])

    def ledger(self):
        path = self.local(self.cfg['record_files'][-1])
        return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]

    def observer(self, run_id=None):
        status = self.command('07_監視システム/watch.py', ['status'])
        require_observer(status)
        # Inspect the same daemon's current target, not its notification/AI delivery.
        state = read(Path(status['runtime']) / 'state.json')
        require(state.get('monitor_source_sha256') == self.pins['07_監視システム/watch.py']
                and state.get('monitor_identity') == status['monitor_process'],
                'Observer state source/process differs from the live daemon proof')
        if run_id is None:
            return True
        path = self.workspace / 'runs' / run_id / 'manifest.json'
        target = state['targets'].get(str(path))
        if target is None or target.get('state_sha256') != digest(path):
            return False  # New/terminal manifest has not yet been discovered.
        manifest = read(path)
        require(target.get('target_id') == run_id and target.get('pid') == manifest['pid']
                and target.get('protocol') == self.cfg['protocol']
                and target.get('purpose') == 'core' and target.get('flags') == []
                and target.get('status') == manifest['status']
                and target.get('source') == str(path),
                'Independent target identity/anomaly hold')
        if manifest['status'] == 'RUNNING':
            process = target.get('process', {})
            binding = target.get('command_verified_binding', {})
            require(process.get('state') == 'alive' and process.get('pid') == manifest['pid']
                    and type(process.get('created')) is int
                    and binding == {'kind': 'direct', 'command_target_id': run_id},
                    'Same live core creation and exact daemon command binding required')
            old = self.state['active'].get('process_identity')
            require(old is None or old == process, 'Observed core creation changed')
            self.state['active']['process_identity'] = process
            self.save()
        observed = datetime.fromisoformat(target['observed_at_utc'])
        age = (datetime.now().astimezone() - observed).total_seconds()
        require(0 <= age <= 120, 'Independent target observation is stale')
        return True

    def sync(self):
        self.command(BASE + 'choice_sync_status.py', ['--apply'])
        self.command(BASE + 'status_progress.py', ['--apply'], parse=False)
        self.command(BASE + 'status_progress.py', ['--check'], parse=False)

    def process_identity(self, pid):
        # Reuse the deployed Windows handle/FILETIME probe, without starting a monitor.
        spec = importlib.util.spec_from_file_location('choice_sequence_watch', self.local('07_監視システム/watch.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.process_identity(pid)

    def wait_started(self, run_id):
        manifest_path = self.workspace / 'runs' / run_id / 'manifest.json'
        launcher = self.state['active']['launch']['pid']
        identities = {}
        verified = set()
        while not manifest_path.is_file():
            launch = read(self.workspace / 'driver_logs' / (run_id + '.state.json'))
            require(launch.get('status') == 'LAUNCHED' and launch.get('run_id') == run_id
                    and launch.get('cell_id') == self.state['active']['cell']['cell_id']
                    and launch.get('purpose') == 'core', 'Reserved startup state changed')
            pid = launch.get('executor_pid', launch.get('pid'))
            if 'executor_pid' in launch:
                require(launch.get('launcher_pid') == launcher
                        and (pid == launcher or launch.get('executor_parent_pid') == launcher),
                        'Executor is not the reserved launcher/child')
            else:
                require(pid == launcher, 'Reserved launcher PID changed')
            identity = self.process_identity(pid)
            if identity.get('state') == 'absent' and manifest_path.is_file():
                break  # Same observed exit/manifest publication boundary, never relaunch.
            require(identity.get('state') == 'alive', 'Reserved startup process absent/unknown; preserve')
            old = identities.get(pid)
            require(old is None or old == identity, 'Reserved startup PID was reused')
            if old is None:
                identities[pid] = identity
                self.state['active']['startup_processes'] = list(identities.values())
                self.save()
            if pid not in verified:
                try:
                    matched = self.command_matches(pid, run_id)
                except subprocess.TimeoutExpired:
                    self.event('choice_sequence_startup_observation_timeout', run_id=run_id, pid=pid)
                    time.sleep(1)
                    continue  # Observe the same creation again, never repeat start-next.
                require(matched, 'Reserved startup command identity unproven')
                verified.add(pid)
                self.state['active']['startup_command_verified_pids'] = sorted(verified)
                self.save()
            # Import/initialization can be slow. A live owned process is not a timeout failure.
            time.sleep(1)
        manifest = read(manifest_path)
        require(manifest.get('run_id') == run_id and manifest.get('purpose') == 'core'
                and manifest.get('cell_id') == self.state['active']['cell']['cell_id']
                and manifest.get('protocol') == self.cfg['protocol']
                and manifest.get('registration_id') == self.cfg['registration_id'],
                'Initial manifest is not the reserved registered core')
        if manifest['pid'] in identities:
            self.state['active']['process_identity'] = identities[manifest['pid']]
        self.save()

    def command_matches(self, pid, run_id):
        spec = importlib.util.spec_from_file_location('choice_sequence_start_watch', self.local('07_監視システム/watch.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.command_matches(pid, run_id)

    def finish_action(self, action, run_id):
        self.state['phase'] = action
        self.save()
        if action == 'finish':
            result = self.command(BASE + 'choice_finish_cell.py',
                                  ['--project-root', str(self.root), '--run-id', run_id])
            require(result.get('status') == 'RECORDED_VERIFIED' and result.get('run_id') == run_id,
                    'Original finish is not successfully terminal for the same run')
        elif action == 'readback':
            output = self.evidence / (run_id + '_record7_readback.json')
            self.command(BASE + 'choice_record_readback.py',
                         ['--project-root', str(self.root), '--run-id', run_id, '--output', str(output)])
            proof = read(output)
            require(proof.get('run_id') == run_id, 'Readback belongs to another run')
            require_readback(proof, self.cfg, self.count + 1, self.ledger())
            self.prior_readback = output
        elif action == 'sync':
            self.sync()
        else:
            raise RuntimeError('Unknown finish action')

    def wait_core(self, run_id):
        discovery = time.monotonic()
        while True:
            result = self.command(BASE + 'choice_monitor.py', ['--run-id', run_id])
            require(result.get('anomaly_flags') == []
                    and result.get('status') in ('RUNNING', 'COMPLETED')
                    and (result['status'] != 'RUNNING' or result.get('pid_alive') is True),
                    'Core monitor anomaly; preserve and stop subsequent starts')
            while not self.observer(run_id):
                require(time.monotonic() - discovery < 60, 'Independent target discovery remains unproven')
                time.sleep(5)
            discovery = time.monotonic()
            if result['status'] == 'COMPLETED':
                manifest = read(self.workspace / 'runs' / run_id / 'manifest.json')
                while True:
                    identity = self.process_identity(manifest['pid'])
                    if terminal_process_absent(identity, self.state['active'].get('process_identity')):
                        self.event('choice_sequence_core_process_terminal', run_id=run_id, identity=identity)
                        break
                    require(time.monotonic() - discovery < 60,
                            'Same core remains alive after completed manifest; preserve and inspect')
                    time.sleep(1)
                return
            time.sleep(60)

    def run(self):
        try:
            for _ in range(self.cells):
                require_readback(read(self.prior_readback), self.cfg, self.count, self.ledger())
                cell = self.cfg['cells'][self.count]
                status = self.cli('status')
                require(status.get('registered_cells') == len(self.cfg['cells']), 'Registered cell count changed')
                require_idle(status, self.count, cell)
                self.observer()
                run_id = self.prefix + str(self.count + 1).zfill(2)
                self.state.update(active={'run_id': run_id, 'cell': cell}, phase='start')
                self.save()
                self.event('choice_sequence_fact_forcing_gate', run_id=run_id, cell=cell,
                           gate={'1': 'Existing dedicated CLI and unchanged registered helpers only',
                                 '2': 'start-next/check/validate/record/readback/status; one core at a time',
                                 '3': 'Registered primary artifacts, seven-file record, new operation logs',
                                 '4': '最終ゴールに到達するまで行ってください。'})
                started = self.cli('start-next', '--run-id', run_id)
                require(started.get('status') == 'STARTED' and started.get('run_id') == run_id
                        and started.get('cell_id') == cell['cell_id'],
                        'New start did not return its exact identity')
                self.state['active']['launch'] = started
                self.state['phase'] = 'startup'
                self.save()
                self.wait_started(run_id)
                self.state['phase'] = 'core'
                self.save()
                self.sync()
                self.wait_core(run_id)
                finish_order(self.finish_action, run_id)
                self.count += 1
                after = self.cli('status')
                require(after['recorded_cells'] == self.count
                        and all(after[key] == [] for key in HOLDS), 'Postrecord status hold')
                self.state['completed'].append({'run_id': run_id, 'cell': cell,
                                                'readback': self.prior_readback.as_posix()})
                self.state['active'] = None
                self.save()
                self.event('choice_sequence_cell_recorded', run_id=run_id, recorded_cells=self.count)
            self.state.update(status='COMPLETED_REGISTERED_SCOPE_PENDING_ANALYSIS', goal_complete=False)
            self.save()
            return self.state
        except BaseException as error:
            self.state.update(status='FAILED_PRESERVED', error_type=type(error).__name__, error=str(error),
                              child_may_still_be_running=True, goal_complete=False)
            self.save()
            self.event('choice_sequence_stopped_preserved', error_type=type(error).__name__, error=str(error))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--sequence-id', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--expected-recorded', required=True, type=int)
    parser.add_argument('--max-cells', required=True, type=int)
    parser.add_argument('--prior-readback', required=True)
    args = parser.parse_args()
    value = Sequence(args.project_root, args.sequence_id, args.prefix,
                     args.expected_recorded, args.max_cells, args.prior_readback).run()
    print(json.dumps({'status': value['status'], 'completed': len(value['completed']),
                      'goal_complete': False}, ensure_ascii=False))
