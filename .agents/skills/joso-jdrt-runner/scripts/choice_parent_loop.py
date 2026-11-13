"""Unattended parent loop for the registered choice series (SP-14). No AI is involved.

Each iteration calls ``choice_core_sequence.py --max-cells 1`` exactly once and judges success from
read-back artifacts (the sequence's state and stdout, the ordered ledger, the seven-file readback and
the post-record status that the sequence itself captured), never from the exit code alone.

The parent never calls the dedicated research CLI (its ``status`` appends to operations.jsonl), and
never retries, rejects, recovers, finishes, kills or re-runs anything. Any doubt stops the loop: the
stop reason, evidence, time and how far the iteration got are written atomically to
``<workspace>/driver_logs/parent_loop/stops/<stop_id>.json`` (mirrored to ``parent_stop.json``), one
``parent_stopped`` event is placed in the independent monitor's events folder (mail outbox path), and
the loop exits. Restart is: a human fixes things outside this program, records ``ack --reason``, and
starts the parent again. Completion of all registered cells (SP-06 §3.1) produces one
``all_complete`` event; analysis is never run here.
"""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
from hashlib import sha256
import shutil
import subprocess
import sys
import time
import uuid

import choice_core_sequence as core

SCRIPT = Path(__file__).resolve().parent / 'choice_core_sequence.py'
PARENT_DIR = 'driver_logs/parent_loop'
MONITOR_CONFIG = '07_監視システム/config.json'
WATCH = '07_監視システム/watch.py'
SETTINGS_SCHEMA = 'choice_parent_loop_settings_v1'
EXPECTED_STDOUT = {'status': 'COMPLETED_REGISTERED_SCOPE_PENDING_ANALYSIS', 'completed': 1, 'goal_complete': False}
EXIT_COMPLETE, EXIT_STOPPED, EXIT_UNACKED, EXIT_LOCKED, EXIT_USAGE = 0, 2, 3, 4, 64
ACTIVE_PHASES = ('starting', 'precheck', 'sequence_running', 'sequence_exited', 'postcheck')
NO_ACTION = 'none: no rerun, reject, recover, finish, kill or new start was performed by the parent'
DETAIL_PATTERNS = (
    ('Postrecord status hold', 'POSTRECORD_HOLD'), ('status hold', 'STATUS_HOLD'),
    ('observer gap exceeded', 'MONITOR_GAP_EXCEEDED'), ('target discovery', 'MONITOR_TARGET_NOT_DISCOVERED'),
    ('Independent observer', 'MONITOR_NOT_PROVEN'), ('Observer state', 'MONITOR_NOT_PROVEN'),
    ('Independent target', 'MONITOR_TARGET_ANOMALY'), ('Core monitor anomaly', 'CORE_ANOMALY'),
    ('Pinned source/config changed', 'PINNED_SHA_CHANGED'), ('seven-file readback', 'READBACK_MISMATCH'),
    ('Readback belongs', 'READBACK_MISMATCH'), ('Original finish', 'FINISH_NOT_RECORDED'),
    ('Command failed', 'CHILD_COMMAND_FAILED'), ('Same core remains alive', 'CORE_ALIVE_AFTER_COMPLETED'),
    ('PID', 'PROCESS_IDENTITY'), ('process identity', 'PROCESS_IDENTITY'), ('creation', 'PROCESS_IDENTITY'),
    ('Reserved startup', 'STARTUP_FAILED'), ('New start did not return', 'STARTUP_FAILED'),
    ('Initial manifest', 'STARTUP_FAILED'), ('ordered next cell', 'STATUS_NOT_READY'),
    ('Registered cell count changed', 'REGISTRATION_CHANGED'), ('Exactly one cell', 'SCOPE_REFUSED'),
    ('Explicit selected toolchain', 'TOOLCHAIN_ENV_MISSING'), ('Monitor stale_sec', 'MONITOR_CONFIG_INVALID'))


class ParentStop(Exception):
    """A deterministic stop condition: preserved, notified, never acted upon by the parent."""

    def __init__(self, code, reason, detail_code=None, **evidence):
        super().__init__(reason)
        self.code, self.reason, self.detail_code, self.evidence = code, reason, detail_code, evidence
        self.sequence = None

    def with_sequence(self, summary):
        self.sequence = summary
        return self


class UsageError(Exception):
    """Invalid invocation or settings; nothing has run, so no stop record is written."""


class ParentLock:
    """OS byte lock released on process death; the lock file itself is not ownership."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        if path.stat().st_size == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('Another parent loop owns this lock') from None

    def close(self):
        try:
            if os.name == 'nt':
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.stream.close()


def now_jst():
    return datetime.now().astimezone().isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(.2)


def create_exclusive(path, value):
    """Create a complete JSON file only if the name is unused; never overwrites. False if it exists."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)  # atomic create-if-absent on NTFS
        return True
    except FileExistsError:
        return False
    except OSError:  # file system without hard links: exclusive create, then the content
        try:
            with path.open('x', encoding='utf-8') as stream:
                stream.write(temporary.read_text(encoding='utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            return True
        except FileExistsError:
            return False
    finally:
        temporary.unlink(missing_ok=True)


def settings_digest(settings):
    return sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def settings_record(settings, source_path, reason, previous=None):
    return {'schema': 'choice_parent_loop_settings_record_v1', 'settings': settings,
            'sha256': settings_digest(settings), 'source_path': str(source_path or ''),
            'source_sha256': core.digest(Path(source_path)) if source_path else None,
            'saved_at_jst': now_jst(), 'reason': reason, 'previous_sha256': previous}


def classify_sequence_error(message):
    """Informational sub-code for the notification; the parent stops regardless of the class."""
    text = str(message or '')
    return next((code for pattern, code in DETAIL_PATTERNS if pattern in text), 'UNCLASSIFIED')


def load_settings(path, total):
    if path is None:
        return {'checkpoint_recorded_counts': []}  # D5: no checkpoint unless configured
    try:
        value = read_json(path)
    except (OSError, ValueError) as error:
        raise UsageError(f'Settings unreadable: {error}') from None
    if not isinstance(value, dict) or set(value) - {'schema', 'checkpoint_recorded_counts'} \
            or value.get('schema') != SETTINGS_SCHEMA:
        raise UsageError('Settings must be {"schema": "%s", "checkpoint_recorded_counts": [...]}' % SETTINGS_SCHEMA)
    counts = value.get('checkpoint_recorded_counts', [])
    if not isinstance(counts, list) or any(type(c) is not int or not 0 < c < total for c in counts) \
            or len(set(counts)) != len(counts):
        raise UsageError('checkpoint_recorded_counts must be distinct integers between 1 and registered-1')
    return {'checkpoint_recorded_counts': sorted(counts)}


def check_ledger(rows, cfg):
    cells = [cell['cell_id'] for cell in cfg['cells']]
    problems = []
    if len(rows) > len(cells):
        problems.append('more rows than registered cells')
    if [row.get('cell_id') for row in rows] != cells[:len(rows)]:
        problems.append('cells are not the registered prefix in order')
    if len({row.get('run_id') for row in rows}) != len(rows):
        problems.append('duplicate run_id')
    if not all(row.get('protocol') == cfg['protocol'] and row.get('registration_id') == cfg['registration_id']
               for row in rows):
        problems.append('foreign protocol/registration')
    if not all(row.get('validation_status') == 'PASS' for row in rows):
        problems.append('row without validation PASS')
    if problems:
        raise ParentStop('LEDGER_INVALID', 'Ledger is not the ordered PASS prefix of the registration',
                         problems=problems, ledger_rows=len(rows))


def nonempty_holds(status):
    return [key for key in core.HOLDS if key not in status or status[key] != []]


def sequence_summary(state):
    if not isinstance(state, dict):
        return None
    command = state.get('command') or {}
    argv = command.get('argv') or []
    return {**{key: state.get(key) for key in ('status', 'phase', 'error_type', 'error',
                                                  'child_may_still_be_running', 'goal_complete', 'observer_gap')},
            'active_run_id': (state.get('active') or {}).get('run_id'),
            'completed_run_ids': [item.get('run_id') for item in state.get('completed') or []],
            'last_command': {'script': Path(argv[4]).name if len(argv) > 4 else None,
                             'args': [a for a in argv[5:] if a != '--project-root'][:12],
                             'exit_code': command.get('exit_code'), 'stdout': command.get('stdout'),
                             'stderr': command.get('stderr')}}


class ParentLoop:
    def __init__(self, root, prefix, prior_readback=None, settings_path=None, *, monitor_config=None,
                 watch_path=None, runner=None, event_writer=None, monitor_check=None, mail_check=None,
                 probe=None, clock=None, python=None, completion_status=None):
        self.root = Path(root).resolve()
        self.cfg = read_json(self.root / core.CONFIG)
        self.workspace = (self.root / self.cfg['workspace']).resolve()
        self.directory = self.workspace / PARENT_DIR
        self.prefix = prefix
        self.prior_argument = prior_readback
        self.settings_path = settings_path
        self.monitor_config = Path(monitor_config) if monitor_config else self.root / MONITOR_CONFIG
        self.watch_path = Path(watch_path) if watch_path else self.root / WATCH
        self.runner = runner or self.default_runner
        self.event_writer = event_writer or self.default_event_writer
        self.monitor_check = monitor_check or self.default_monitor_check
        self.mail_check = mail_check or self.default_mail_check
        self.completion_status = Path(completion_status) if completion_status else None
        self.probe, self.clock = probe, clock or time.time
        self.python = python or sys.executable
        self.session_id = 'pl' + datetime.now().strftime('%Y%m%dT%H%M%S%f')
        self.stop_serial = 0
        self.iteration = None
        self.last_completed = None
        self.readback = None
        self._watch = None
        self.state = {}

    # ---------- shared helpers ----------
    def path(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise ParentStop('PATH_ESCAPE', 'Path escapes project', path=str(path))
        return path

    def log(self, action, **values):
        self.directory.mkdir(parents=True, exist_ok=True)
        row = {'at_jst': now_jst(), 'action': action, 'session_id': self.session_id, **values}
        with (self.directory / 'parent_operations.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    def save_state(self, **changes):
        self.state.update(changes, session_id=self.session_id, pid=os.getpid(), at_jst=now_jst(),
                          iteration=self.iteration, last_completed=self.last_completed)
        atomic_write(self.directory / 'parent_state.json', self.state)

    def step(self, name):
        self.iteration['steps_done'].append(name)
        self.save_state()

    def watch(self):
        if self._watch is None:
            spec = importlib.util.spec_from_file_location('choice_parent_watch', self.watch_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._watch = module
        return self._watch

    def ledger(self):
        try:
            text = self.path(self.cfg['record_files'][-1]).read_text(encoding='utf-8-sig')
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        except (OSError, ValueError) as error:
            raise ParentStop('LEDGER_INVALID', f'Ledger unreadable: {type(error).__name__}') from None
        check_ledger(rows, self.cfg)
        return rows

    # ---------- monitor and notification (defaults; injectable for tests) ----------
    def default_monitor_check(self):
        try:
            config = read_json(self.monitor_config)
            state = read_json(Path(config['runtime']) / 'state.json')
        except (OSError, ValueError, KeyError) as error:
            raise ParentStop('MONITOR_NOT_PROVEN', 'Monitor config/state unreadable',
                             'MONITOR_STATE_UNREADABLE', error_type=type(error).__name__) from None
        probe = self.probe or self.watch().process_identity
        identity = probe(state.get('monitor_pid'))
        status = {'observation_age_sec': self.clock() - state.get('observed_epoch', 0),
                  'monitor_process': identity,
                  'monitor_identity_matches': identity == state.get('monitor_identity')}
        try:
            core.require_observer(status)  # same 120 s / identity rule as the sequence itself
        except RuntimeError as error:
            raise ParentStop('MONITOR_NOT_PROVEN', str(error), 'MONITOR_STALE_OR_RESTARTED',
                             observation_age_sec=status['observation_age_sec'],
                             monitor_state=identity.get('state')) from None
        if state.get('monitor_source_sha256') != core.digest(self.watch_path):
            raise ParentStop('MONITOR_NOT_PROVEN', 'Running monitor source differs from watch.py on disk',
                             'MONITOR_SOURCE_SHA_MISMATCH')
        return {'observation_age_sec': status['observation_age_sec']}

    def default_event_writer(self, kind, target, evidence):
        config = read_json(self.monitor_config)
        # AI-less policy: these events never request AI diagnostics (delivery: not_applicable).
        return str(self.watch().save_event(Path(config['runtime']) / 'events', target, kind, evidence,
                                           ai_diagnostics=False))

    def default_mail_check(self):
        """Refuse unattended work when a stop could not reach the user (mail path broken)."""
        problems = []
        try:
            config = read_json(self.monitor_config)
            runtime = Path(config['runtime'])
        except (OSError, ValueError, KeyError) as error:
            raise ParentStop('MAIL_PATH_NOT_READY', 'Monitor config unreadable', 'MONITOR_CONFIG_UNREADABLE',
                             error_type=type(error).__name__) from None
        if config.get('mail_enabled') is not True:
            problems.append('mail_enabled is not true in the monitor config')
        if not config.get('mail_to'):
            problems.append('mail_to is missing in the monitor config')
        if config.get('mail_provider') == 'gmail_smtp':
            if not config.get('mail_sender'):
                problems.append('mail_sender is missing in the monitor config (gmail_smtp)')
            if not (runtime / 'smtp_secret.bin').exists():  # existence only: the secret is never read here
                problems.append('app password not saved (smtp_secret.bin missing; run smtp_mail.py setup)')
        lock = runtime / 'mail_worker.lock'
        if not lock.exists():
            problems.append('mail_worker.lock missing (mail worker not started)')
        else:
            try:
                ParentLock(lock).close()
                problems.append('mail worker not running (its lock is free)')
            except RuntimeError:
                pass  # held by the live worker
        expired = failed = retrying = uncertain = 0
        for path in sorted((runtime / 'outbox').glob('*.json')) if (runtime / 'outbox').exists() else []:
            try:
                message = read_json(path)
            except (OSError, ValueError):
                problems.append('outbox message unreadable: ' + path.name)
                continue
            state = message.get('state')
            expired += state == 'auth_expired'
            failed += state == 'failed_preserved'
            retrying += state == 'queued' and int(message.get('attempts') or 0) >= 3
            uncertain += state == 'uncertain_preserved'
        if expired:
            problems.append(f'{expired} outbox message(s) auth_expired (sign in again, then mail_worker.py resume)')
        if failed:
            problems.append(f'{failed} outbox message(s) failed_preserved (a notice never reached the user; '
                            'review, then mail_worker.py resume-unsent or move the file aside with a reason)')
        if retrying:
            problems.append(f'{retrying} outbox message(s) still retrying after 3+ attempts (network or server)')
        wanted = os.path.normcase(str(self.workspace / 'runs' / '*' / 'manifest.json'))
        if not any(os.path.normcase(str(Path(p))) == wanted for p in config.get('patterns') or []):
            problems.append('monitor patterns do not include this workspace runs/*/manifest.json')
        if problems:
            raise ParentStop('MAIL_PATH_NOT_READY', 'Mail/monitor path not ready; unattended stops would be silent',
                             problems=problems)
        # uncertain_preserved may well have been delivered (never resent): reported, not blocking.
        return {'mail_path': 'ready', 'uncertain_preserved': uncertain}

    def default_runner(self, argv, stdout_path, stderr_path, cwd):
        with open(stdout_path, 'xb') as stdout, open(stderr_path, 'xb') as stderr:
            child = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                     env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            # Record only (review D1): lets a human see later whether this child might still be alive.
            try:
                identity = (self.probe or self.watch().process_identity)(child.pid)
            except Exception as error:
                identity = {'state': 'unknown', 'error_type': type(error).__name__}
            if self.iteration is not None:
                self.iteration['child'] = {'pid': child.pid, 'created': identity.get('created'),
                                           'state': identity.get('state'), 'recorded_at_jst': now_jst()}
                try:
                    self.save_state()
                except Exception:
                    pass  # recording must never stop or kill the child
            # No timeout, kill or retry: the sequence may legitimately run for hours.
            return child.wait()

    # ---------- stop / acknowledge ----------
    def stop_paths(self):
        folder = self.directory / 'stops'
        return sorted(p for p in folder.glob('*.json') if p.name.count('.') == 1) if folder.exists() else []

    def unacknowledged(self):
        return [p.stem for p in self.stop_paths() if not p.with_name(p.stem + '.ack.json').exists()]

    def checkpoint_acknowledged(self, count):
        for path in self.stop_paths():
            record = read_json(path)
            if (record.get('code') == 'CHECKPOINT_REACHED'
                    and record.get('evidence', {}).get('recorded_cells') == count
                    and record.get('evidence', {}).get('registration_id') == self.cfg['registration_id']
                    and path.with_name(path.stem + '.ack.json').exists()):
                return True
        return False

    def notify_stop(self, record, path):
        """Place the parent_stopped event (idempotent per stop id). Never raises."""
        iteration = record.get('iteration') or {}
        sequence = record.get('sequence') or {}
        code, detail_code, stage = record.get('code'), record.get('detail_code'), sequence.get('phase')
        label = str(code) + (f'（{detail_code}）' if detail_code else '')
        where = ''.join(f' {key}={iteration[key]}' for key in ('run_id', 'cell_id') if iteration.get(key))
        evidence = {
            'target_id': 'choice_parent_loop', 'source': str(path) if path else '停止記録の書込みに失敗',
            'stop_id': record.get('stop_id'), 'code': code, 'detail_code': detail_code,
            'registration_id': self.cfg['registration_id'], 'run_id': iteration.get('run_id'),
            'cell_id': iteration.get('cell_id'), 'stage': stage,
            'status': (f'親ループ停止 {label}{where}' + (f' 段階={stage}' if stage else '')
                       + f"：{record.get('reason')}。再実行・reject・recoverはしていません。")[:900]}
        try:
            return {'event': str(self.event_writer('parent_stopped', 'choice-parent-stop:' + str(record.get('stop_id')),
                                                   evidence))}
        except Exception as error:
            return {'error_type': type(error).__name__, 'error': str(error)[:500]}

    def stop(self, code, reason, detail_code=None, evidence=None, sequence=None):
        record = {'schema': 'choice_parent_stop_v1', 'code': code,
                  'detail_code': detail_code, 'reason': reason, 'at_jst': now_jst(),
                  'session_id': self.session_id, 'parent_pid': os.getpid(),
                  'registration_id': self.cfg['registration_id'],
                  'evidence': evidence or {}, 'iteration': self.iteration, 'sequence': sequence,
                  'actions_taken': NO_ACTION}
        path = None
        try:
            for _ in range(1000):  # new names only: an existing (e.g. acknowledged) stop is never overwritten
                self.stop_serial += 1
                stop_id = f'{self.session_id}_{self.stop_serial:02d}'
                record.update(stop_id=stop_id, resume=(
                    'Fix the cause outside the parent (human decision), then run: '
                    f'choice_parent_loop.py ack --stop-id {stop_id} --reason "<why>" ; '
                    'then start the parent again with a new --prefix if the run ID was used'))
                candidate = self.directory / 'stops' / (stop_id + '.json')
                if create_exclusive(candidate, record):  # preservation first, notification second
                    path = candidate
                    break
            else:
                raise RuntimeError('No unused stop id')
        except BaseException:
            self.notify_stop(record, None)  # the user still hears about it; the parent then exits non-zero
            raise
        problems = {}
        for key, action in (('mirror_error', lambda: atomic_write(self.directory / 'parent_stop.json', record)),
                            ('state_error', lambda: self.save_state(phase='stopped', last_stop=stop_id))):
            try:
                action()
            except Exception as error:
                problems[key] = {'error_type': type(error).__name__, 'error': str(error)[:300]}
        notified = self.notify_stop(record, path)
        try:
            atomic_write(path.with_name(stop_id + '.notify.json'), {'at_jst': now_jst(), **notified, **problems})
            self.log('parent_stopped', stop_id=stop_id, code=code, detail_code=detail_code,
                     notification=notified, write_problems=problems)
        except Exception:
            pass  # a missing notify.json makes the next start notify again
        print(json.dumps({'status': 'STOPPED_PRESERVED', 'stop_id': stop_id, 'code': code,
                          'detail_code': detail_code}, ensure_ascii=False))
        return EXIT_STOPPED

    def renotify_unsent(self):
        """A preserved, unacknowledged stop without notify.json is notified again (event id is idempotent)."""
        for path in self.stop_paths():
            receipt = path.with_name(path.stem + '.notify.json')
            if receipt.exists() or path.with_name(path.stem + '.ack.json').exists():
                continue
            try:
                record = read_json(path)
            except (OSError, ValueError):
                record = {'stop_id': path.stem, 'code': 'STOP_RECORD_UNREADABLE', 'reason': 'stop record unreadable'}
            notified = self.notify_stop(record, path)
            try:
                atomic_write(receipt, {'at_jst': now_jst(), 'resent': True, **notified})
            except Exception:
                pass

    # ---------- per-iteration checks ----------
    def check_readback(self, path, count, ledger, code):
        try:
            proof = read_json(path)
            core.require_readback(proof, self.cfg, count, ledger)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
            raise ParentStop(code, f'Readback does not prove {count} recorded cells: {error}',
                             readback=str(path)) from None
        expected = self.cfg['cells'][count] if count < len(self.cfg['cells']) else None
        if proof.get('next_cell', 'missing') != expected:
            raise ParentStop(code, 'Readback next_cell is not the registered next cell', readback=str(path))

    def post_status(self, state, count):
        command = (state or {}).get('command') or {}
        argv = command.get('argv') or []
        if not argv or argv[-1] != 'status' or command.get('exit_code') != 0:
            raise ParentStop('POST_STATUS_UNAVAILABLE',
                             'The sequence did not end with a successful post-record status')
        try:
            status = read_json(command['stdout'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ParentStop('POST_STATUS_UNAVAILABLE',
                             f'Post-record status unreadable: {type(error).__name__}') from None
        return self.check_status(status, count)

    def check_status(self, status, count):
        if not isinstance(status, dict):
            raise ParentStop('POST_STATUS_UNAVAILABLE', 'Status output is not a JSON object')
        total = len(self.cfg['cells'])
        expected = self.cfg['cells'][count] if count < total else None
        holds = nonempty_holds(status)
        ready = count == total or (status.get('core_ready') is True and status.get('core_start_available') is True)
        if (holds or status.get('registered_cells') != total or status.get('recorded_cells') != count
                or status.get('next_cell') != expected or not ready):
            raise ParentStop('POST_STATUS_HOLD', 'Post-record status is not clear for the next registered cell',
                             nonempty_holds=holds, recorded_cells=status.get('recorded_cells'),
                             core_ready=status.get('core_ready'),
                             core_start_available=status.get('core_start_available'))
        return status

    def sequence_state(self, sequence_id):
        path = self.workspace / 'driver_logs/core_sequences' / sequence_id / 'state.json'
        try:
            return path, read_json(path)
        except (OSError, ValueError):
            return path, None

    def earlier_human_completion(self, ledger):
        path = self.directory / 'parent_complete.json'
        try:
            record = read_json(path) if path.exists() else None
        except (OSError, ValueError):
            return None
        if (record and record.get('provenance') == 'human_provided'
                and record.get('registration_id') == self.cfg['registration_id']
                and record.get('last_run_id') == ledger[-1]['run_id']):
            return record.get('human_evidence')
        return None

    def complete(self, ledger):
        """SP-06 §3.1: all five conditions at the same time, from evidence the sequence already made."""
        total = len(self.cfg['cells'])
        last = self.last_completed
        human = None
        try:
            if last and last.get('run_id') == ledger[-1]['run_id']:
                provenance, readback = 'parent_executed', last['readback']
                _, state = self.sequence_state(last['sequence_id'])
                if not (state and state.get('status') == EXPECTED_STDOUT['status']
                        and [c.get('run_id') for c in state.get('completed') or []] == [ledger[-1]['run_id']]):
                    raise ParentStop('COMPLETION_UNPROVEN', 'Last sequence state does not match the last ledger row')
                self.post_status(state, total)
            else:
                # Review F1: the last cell was finished outside the parent; accept only human-provided
                # evidence of the same strength (readback of all cells + a status output) and say so.
                provenance = 'human_provided'
                if self.prior_argument is not None and self.completion_status is not None:
                    readback, status_path, earlier = str(self.readback), self.completion_status, None
                else:
                    # A restart after an accepted human completion re-checks the same, unchanged files.
                    earlier = self.earlier_human_completion(ledger)
                    if earlier is None:
                        raise ParentStop('COMPLETION_UNPROVEN',
                                         'The last ledger row was not recorded by this parent: pass --prior-readback '
                                         '(readback of the last cell) and --completion-status (a status JSON a '
                                         'human saved after recording)')
                    readback, status_path = earlier['readback'], Path(earlier['completion_status'])
                try:
                    status = read_json(status_path)
                    human = {'readback': readback, 'readback_sha256': core.digest(Path(readback)),
                             'completion_status': str(status_path),
                             'completion_status_sha256': core.digest(Path(status_path))}
                except (OSError, ValueError) as error:
                    raise ParentStop('COMPLETION_UNPROVEN',
                                     f'Human completion evidence unreadable: {type(error).__name__}') from None
                if earlier and (human['readback_sha256'] != earlier.get('readback_sha256')
                                or human['completion_status_sha256'] != earlier.get('completion_status_sha256')):
                    raise ParentStop('COMPLETION_UNPROVEN', 'Human completion evidence changed since it was accepted')
                self.check_status(status, total)
            self.check_readback(readback, total, ledger, 'COMPLETION_UNPROVEN')
        except ParentStop as stop:
            if stop.code != 'COMPLETION_UNPROVEN':
                stop = ParentStop('COMPLETION_UNPROVEN', stop.reason, stop.code, **stop.evidence)
            raise stop from None
        record = {'schema': 'choice_parent_complete_v1', 'at_jst': now_jst(),
                  'registration_id': self.cfg['registration_id'], 'recorded_cells': total,
                  'last_run_id': ledger[-1]['run_id'], 'provenance': provenance,
                  'last_sequence_id': last['sequence_id'] if provenance == 'parent_executed' else None,
                  'last_readback': readback, 'human_evidence': human,
                  'scope': '登録範囲の実行と正式記録が完了（分析は未実施。研究ゴールの完了ではない）'}
        atomic_write(self.directory / 'parent_complete.json', record)
        self.save_state(phase='complete')
        evidence = {'target_id': 'choice_parent_loop', 'source': str(self.directory / 'parent_complete.json'),
                    'registration_id': self.cfg['registration_id'], 'recorded_cells': total,
                    'provenance': provenance,
                    'status': (f'登録範囲{total}セルの実行と正式記録が完了（分析は未実施）。出所：'
                               + ('親ループが実行' if provenance == 'parent_executed'
                                  else '最終セルは人が記録し、人が提供した読戻しとstatusで確認')
                               + '。詳細は専用CLIの記録を参照')}
        try:
            notified = {'event': str(self.event_writer('all_complete',
                                                       'choice-parent-complete:' + self.cfg['registration_id'],
                                                       evidence))}
        except Exception as error:
            notified = {'error_type': type(error).__name__, 'error': str(error)[:500]}
        atomic_write(self.directory / 'parent_complete.notify.json', {'at_jst': now_jst(), **notified})
        self.log('parent_all_complete', notification=notified)
        print(json.dumps({'status': 'COMPLETED_REGISTERED_SCOPE_PENDING_ANALYSIS',
                          'recorded_cells': total}, ensure_ascii=False))
        return EXIT_COMPLETE

    def iterate(self, count, ledger):
        sequence_id = f'{self.session_id}_{count + 1:02d}'
        run_id = self.prefix + str(count + 1).zfill(2)
        cell = self.cfg['cells'][count]
        self.iteration = {'recorded_before': count, 'sequence_id': sequence_id, 'run_id': run_id,
                          'cell_id': cell['cell_id'], 'prior_readback': str(self.readback),
                          'started_at_jst': now_jst(), 'steps_done': []}
        self.save_state(phase='precheck')
        self.step('ledger_checked')
        self.check_readback(self.readback, count, ledger, 'PRIOR_READBACK_INVALID')
        self.step('prior_readback_checked')
        self.iteration['monitor'] = self.monitor_check()
        self.step('monitor_checked')
        used = [str(p) for p in (self.workspace / 'driver_logs' / (run_id + '.state.json'),
                                 *(self.workspace / name / run_id for name in ('runs', 'smoke', 'technical')))
                if p.exists()]
        if used:
            raise ParentStop('RUN_ID_IN_USE', 'Next run ID already exists; start again with a new --prefix',
                             paths=used)
        sequence_dirs = [self.workspace / 'driver_logs/core_sequences' / sequence_id,
                         self.path(core.GOAL) / 'core_sequence_evidence' / sequence_id]
        if any(p.exists() for p in sequence_dirs):
            raise ParentStop('SEQUENCE_ID_IN_USE', 'Sequence ID already exists', sequence_id=sequence_id)
        self.step('ids_checked')
        try:
            self.iteration['disk_free_bytes'] = shutil.disk_usage(
                self.workspace if self.workspace.exists() else self.root).free
        except OSError:
            self.iteration['disk_free_bytes'] = None
        logs = self.directory / 'iterations'
        logs.mkdir(parents=True, exist_ok=True)
        stdout, stderr = logs / (sequence_id + '.stdout.log'), logs / (sequence_id + '.stderr.log')
        argv = [self.python, '-B', '-X', 'utf8', str(SCRIPT), '--project-root', str(self.root),
                '--sequence-id', sequence_id, '--prefix', self.prefix, '--expected-recorded', str(count),
                '--max-cells', '1', '--prior-readback', str(self.readback)]
        self.iteration.update(argv=argv, stdout=str(stdout), stderr=str(stderr))
        self.save_state(phase='sequence_running')
        self.step('sequence_launched')
        self.log('sequence_launched', sequence_id=sequence_id, run_id=run_id, cell_id=cell['cell_id'])
        code = self.runner(argv, stdout, stderr, self.root)
        self.iteration.update(exit_code=code, exited_at_jst=now_jst())
        self.save_state(phase='sequence_exited')
        self.step('sequence_exited')
        state_path, state = self.sequence_state(sequence_id)
        summary = sequence_summary(state)
        if code != 0:
            detail = classify_sequence_error(state.get('error')) if state else 'SEQUENCE_STATE_MISSING'
            raise ParentStop('SEQUENCE_FAILED', 'choice_core_sequence exited non-zero; preserved as is', detail,
                             exit_code=code, sequence_state=str(state_path), stdout=str(stdout),
                             stderr=str(stderr)).with_sequence(summary)
        self.save_state(phase='postcheck')
        try:
            printed = json.loads(stdout.read_text(encoding='utf-8-sig').strip())
        except (OSError, ValueError):
            printed = None
        if printed != EXPECTED_STDOUT:
            raise ParentStop('SEQUENCE_OUTPUT_UNEXPECTED', 'Sequence stdout is not the one-cell completion line',
                             stdout=str(stdout)).with_sequence(summary)
        self.step('stdout_checked')
        expected_readback = self.path(core.GOAL) / 'core_sequence_evidence' / sequence_id / (
            run_id + '_record7_readback.json')
        completed = (state or {}).get('completed') or []
        if not (state and state.get('status') == EXPECTED_STDOUT['status'] and state.get('active') is None
                and state.get('goal_complete') is False and len(completed) == 1
                and completed[0].get('run_id') == run_id
                and (completed[0].get('cell') or {}).get('cell_id') == cell['cell_id']
                and completed[0].get('readback')
                and Path(completed[0]['readback']).resolve() == expected_readback.resolve()):
            raise ParentStop('SEQUENCE_STATE_MISMATCH', 'Sequence state is not exactly this one recorded cell',
                             sequence_state=str(state_path)).with_sequence(summary)
        self.step('sequence_state_checked')
        try:
            after = self.ledger()
            if len(after) != count + 1 or after[-1].get('run_id') != run_id:
                raise ParentStop('LEDGER_MISMATCH', 'Ledger does not end with exactly this new run',
                                 ledger_rows=len(after))
            self.step('ledger_rechecked')
            self.check_readback(expected_readback, count + 1, after, 'READBACK_MISMATCH')
            self.step('readback_checked')
            self.post_status(state, count + 1)
            self.step('post_status_checked')
        except ParentStop as stop:
            raise stop.with_sequence(summary) from None
        self.readback = expected_readback
        self.last_completed = {'sequence_id': sequence_id, 'run_id': run_id, 'cell_id': cell['cell_id'],
                               'readback': str(expected_readback), 'state': str(state_path),
                               'recorded_cells': count + 1}
        self.log('cell_recorded_by_sequence', sequence_id=sequence_id, run_id=run_id, recorded_cells=count + 1)
        self.save_state(phase='idle')

    def require_stored_settings(self, settings):
        """Review F2: settings are fixed at the first run; a change needs ack --settings/--clear-settings."""
        path = self.directory / 'parent_settings.json'
        if not path.exists():
            atomic_write(path, settings_record(settings, self.settings_path, 'first run'))
            return
        try:
            stored = read_json(path)
        except (OSError, ValueError) as error:
            raise UsageError(f'Stored parent settings unreadable: {type(error).__name__}') from None
        if stored.get('sha256') != settings_digest(settings) or stored.get('settings') != settings:
            raise UsageError('Settings differ from the stored settings %s (stored: %s, given: %s). Pass the same '
                             '--settings, or change them only with ack --settings/--clear-settings and a reason'
                             % (path, json.dumps(stored.get('settings'), ensure_ascii=False),
                                json.dumps(settings, ensure_ascii=False)))

    # ---------- read-only readiness check ----------
    def preflight(self):
        """The conditions `run` checks up to its first sequence call, without starting, logging or writing.

        Covers the start checks (lock, stops, interrupted parent, settings, mail path) and the first
        iteration's prechecks (ledger, checkpoint, prior readback, monitor, next run ID when --prefix is
        given; the sequence ID is new per session). Ready only when all pass. Never runs the research CLI,
        never writes the parent state, settings or operations log; the lock is only probed.
        """
        checks = {}

        def attempt(name, function):
            try:
                checks[name] = {'ok': True, **(function() or {})}
            except ParentStop as stop:
                checks[name] = {'ok': False, 'code': stop.code, 'detail_code': stop.detail_code,
                                'reason': stop.reason, **stop.evidence}
            except Exception as error:
                checks[name] = {'ok': False, 'code': 'INTERNAL_ERROR', 'error_type': type(error).__name__}

        lock_path = self.directory / 'parent.lock'
        if lock_path.exists():
            try:
                ParentLock(lock_path).close()
                checks['parent_lock'] = {'ok': True}
            except RuntimeError:
                checks['parent_lock'] = {'ok': False, 'code': 'ANOTHER_PARENT_RUNNING'}
        else:
            checks['parent_lock'] = {'ok': True}
        pending = self.unacknowledged()
        checks['stops'] = {'ok': not pending, 'unacknowledged': pending}
        state_path = self.directory / 'parent_state.json'
        previous = None
        try:
            previous = read_json(state_path) if state_path.exists() else None
            interrupted = bool(previous and previous.get('phase') in ACTIVE_PHASES)
            checks['previous_parent'] = {'ok': not interrupted,
                                         'phase': previous.get('phase') if previous else None}
        except (OSError, ValueError) as error:
            checks['previous_parent'] = {'ok': False, 'code': 'STATE_UNREADABLE', 'error_type': type(error).__name__}
        total = len(self.cfg['cells'])
        progress = {}

        def settings_check():
            """Same rule as require_stored_settings, but read-only (the first run would store them)."""
            try:
                settings = load_settings(self.settings_path, total)
            except UsageError as error:
                raise ParentStop('USAGE_ERROR', str(error)) from None
            progress['settings'] = settings
            stored_path = self.directory / 'parent_settings.json'
            if not stored_path.exists():
                return {'stored': False}
            stored = read_json(stored_path)
            if stored.get('sha256') != settings_digest(settings) or stored.get('settings') != settings:
                raise ParentStop('USAGE_ERROR', 'Settings differ from the stored parent settings; pass the same '
                                 '--settings (a change needs ack --settings/--clear-settings with a reason)',
                                 stored=stored.get('settings'), given=settings)
            return {'stored': True, 'checkpoint_recorded_counts': settings['checkpoint_recorded_counts']}

        def ledger_check():
            ledger = self.ledger()
            count = len(ledger)
            result = {'recorded_cells': count, 'total_cells': total}
            if count == total:
                return result
            settings = progress.get('settings')
            if settings and count in settings['checkpoint_recorded_counts'] and not self.checkpoint_acknowledged(count):
                raise ParentStop('CHECKPOINT_REACHED', f'Configured checkpoint after {count} recorded cells '
                                 '(acknowledge it first)', **result)
            if self.prior_argument is not None:
                readback = (self.root / self.prior_argument).resolve()
            else:
                stored = ((previous or {}).get('last_completed') or {}).get('readback')
                readback = Path(stored) if stored else None
            if readback is None:
                raise ParentStop('USAGE_ERROR', '--prior-readback is required (no last completed cell stored)',
                                 **result)
            self.check_readback(readback, count, ledger, 'PRIOR_READBACK_INVALID')  # read-only
            result['prior_readback'] = str(readback)
            if self.prefix is not None:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', str(self.prefix)):
                    raise ParentStop('USAGE_ERROR', 'A simple new --prefix is required', **result)
                run_id = self.prefix + str(count + 1).zfill(2)
                used = [str(p) for p in (self.workspace / 'driver_logs' / (run_id + '.state.json'),
                                         *(self.workspace / name / run_id for name in ('runs', 'smoke', 'technical')))
                        if p.exists()]
                if used:
                    raise ParentStop('RUN_ID_IN_USE', 'Next run ID already exists; choose a new --prefix',
                                     paths=used, **result)
                result['next_run_id'] = run_id
            else:
                result['next_run_id'] = 'not checked (no --prefix given)'
            return result

        attempt('settings', settings_check)
        attempt('ledger', ledger_check)
        attempt('monitor', self.monitor_check)
        attempt('mail_path', self.mail_check)
        return {'ready': all(item['ok'] for item in checks.values()), 'checks': checks}

    # ---------- main loop ----------
    def run(self):
        try:
            lock = ParentLock(self.directory / 'parent.lock')
        except RuntimeError as error:
            print(json.dumps({'status': 'ANOTHER_PARENT_RUNNING', 'error': str(error)}))
            return EXIT_LOCKED
        try:
            return self._run()
        finally:
            lock.close()

    def _run(self):
        total = len(self.cfg['cells'])
        try:
            settings = load_settings(self.settings_path, total)
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', str(self.prefix or '')):
                raise UsageError('A simple new --prefix is required')
            self.require_stored_settings(settings)
        except UsageError as error:
            print(json.dumps({'status': 'USAGE_ERROR', 'error': str(error)}, ensure_ascii=False))
            return EXIT_USAGE
        self.renotify_unsent()
        pending = self.unacknowledged()
        if pending:
            print(json.dumps({'status': 'UNACKNOWLEDGED_STOP', 'stop_ids': pending,
                              'resume': 'choice_parent_loop.py ack --stop-id <id> --reason "<why>"'},
                             ensure_ascii=False))
            return EXIT_UNACKED
        state_path = self.directory / 'parent_state.json'
        try:
            previous = read_json(state_path) if state_path.exists() else None
            if previous:
                self.last_completed = previous.get('last_completed')
            if self.prior_argument is not None:
                self.readback = (self.root / self.prior_argument).resolve()
            elif self.last_completed:
                self.readback = Path(self.last_completed['readback'])
            if previous and previous.get('phase') in ACTIVE_PHASES:
                raise ParentStop('PREVIOUS_PARENT_INTERRUPTED',
                                 'A previous parent ended mid-iteration; nothing is resumed automatically',
                                 previous_state={key: previous.get(key) for key in
                                                 ('session_id', 'pid', 'phase', 'at_jst', 'iteration')})
            self.state = {'settings': settings, 'settings_path': str(self.settings_path or ''),
                          'prefix': self.prefix, 'started_at_jst': now_jst()}
            self.save_state(phase='starting')
            self.log('parent_started', prefix=self.prefix, settings=settings)
            self.state['mail_path'] = self.mail_check()  # review D2: never start while stops would be silent
            while True:
                self.iteration = None
                ledger = self.ledger()
                count = len(ledger)
                if count == total:
                    return self.complete(ledger)
                if count in settings['checkpoint_recorded_counts'] and not self.checkpoint_acknowledged(count):
                    raise ParentStop('CHECKPOINT_REACHED', f'Configured checkpoint after {count} recorded cells',
                                     recorded_cells=count, registration_id=self.cfg['registration_id'],
                                     last_run_id=ledger[-1]['run_id'] if ledger else None)
                if self.readback is None:
                    print(json.dumps({'status': 'USAGE_ERROR', 'error': '--prior-readback is required'}))
                    self.save_state(phase='idle')
                    return EXIT_USAGE
                self.iterate(count, ledger)
        except ParentStop as stop:
            return self.stop(stop.code, stop.reason, stop.detail_code, stop.evidence, stop.sequence)
        except KeyboardInterrupt:
            return self.stop('PARENT_INTERRUPTED', 'Parent interrupted; any child keeps running and is preserved')
        except Exception as error:
            return self.stop('INTERNAL_ERROR', f'Unexpected parent error: {error}'[:500],
                             evidence={'error_type': type(error).__name__})


def acknowledge(root, stop_id, reason, settings_path=None, clear_settings=False):
    """Record that a human reviewed one stop. Runs nothing and changes no research state.

    The only way to change the stored parent settings (review F2) is here, with the same reason:
    ``settings_path`` replaces them, ``clear_settings`` removes all checkpoints.
    """
    reason = (reason or '').strip()
    if not reason:
        raise ValueError('A non-empty reason is required')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(stop_id or '')):
        raise ValueError('Invalid stop id')
    if settings_path is not None and clear_settings:
        raise ValueError('Give either a new settings file or clear_settings, not both')
    root = Path(root).resolve()
    cfg = read_json(root / core.CONFIG)
    directory = (root / cfg['workspace']).resolve() / PARENT_DIR
    lock = ParentLock(directory / 'parent.lock')
    try:
        stop = directory / 'stops' / (stop_id + '.json')
        ack = stop.with_name(stop_id + '.ack.json')
        if not stop.exists():
            raise ValueError('No such stop')
        if ack.exists():
            raise ValueError('Stop already acknowledged')
        record = {'schema': 'choice_parent_ack_v1', 'stop_id': stop_id, 'reason': reason, 'at_jst': now_jst(),
                  'pid': os.getpid(), 'stop_sha256': core.digest(stop), 'settings_change': None}
        if settings_path is not None or clear_settings:
            try:
                new = (load_settings(settings_path, len(cfg['cells'])) if settings_path is not None
                       else {'checkpoint_recorded_counts': []})
            except UsageError as error:
                raise ValueError(str(error)) from None
            stored_path = directory / 'parent_settings.json'
            previous = read_json(stored_path).get('sha256') if stored_path.exists() else None
            stored = settings_record(new, settings_path, reason, previous)
            record['settings_change'] = {'previous_sha256': previous, 'new_sha256': stored['sha256'],
                                         'new_settings': new, 'source_path': stored['source_path'],
                                         'source_sha256': stored['source_sha256']}
        if not create_exclusive(ack, record):
            raise ValueError('Stop already acknowledged')
        if record['settings_change']:
            atomic_write(directory / 'parent_settings.json', stored)
            with (directory / 'settings_history.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'at_jst': record['at_jst'], 'stop_id': stop_id, 'reason': reason,
                                         **record['settings_change']}, ensure_ascii=False) + '\n')
        with (directory / 'parent_operations.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'at_jst': record['at_jst'], 'action': 'stop_acknowledged',
                                     'stop_id': stop_id, 'reason': reason,
                                     'settings_changed': bool(record['settings_change'])},
                                    ensure_ascii=False) + '\n')
        return record
    finally:
        lock.close()


def show(root):
    """Read-only view of the parent's own files (never calls the research CLI)."""
    root = Path(root).resolve()
    cfg = read_json(root / core.CONFIG)
    directory = (root / cfg['workspace']).resolve() / PARENT_DIR
    state = read_json(directory / 'parent_state.json') if (directory / 'parent_state.json').exists() else None
    stops = []
    for path in sorted((directory / 'stops').glob('*.json')) if (directory / 'stops').exists() else []:
        if path.name.count('.') == 1:
            record = read_json(path)
            stops.append({'stop_id': record['stop_id'], 'code': record['code'], 'detail_code': record['detail_code'],
                          'at_jst': record['at_jst'],
                          'acknowledged': path.with_name(path.stem + '.ack.json').exists()})
    return {'directory': str(directory), 'state': state, 'stops': stops,
            'complete': (directory / 'parent_complete.json').exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project-root', type=Path, default=core.ROOT)
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('run', help='Advance registered cells one per sequence call until done or stopped')
    run.add_argument('--prefix', required=True, help='New run-ID prefix (run ID = prefix + 2-digit cell number)')
    run.add_argument('--prior-readback', help='Readback JSON of the last recorded cell (default: parent state)')
    run.add_argument('--settings', type=Path, help='Optional choice_parent_loop_settings_v1 JSON (checkpoints)')
    run.add_argument('--monitor-config', type=Path, help='Monitor config.json (default: 07_監視システム)')
    run.add_argument('--completion-status', type=Path,
                     help='Status JSON a human saved after recording the last cell outside the parent')
    ack = sub.add_parser('ack', help='Acknowledge one stop with a reason (runs nothing)')
    ack.add_argument('--stop-id', required=True)
    ack.add_argument('--reason', required=True)
    change = ack.add_mutually_exclusive_group()
    change.add_argument('--settings', type=Path, help='Replace the stored parent settings (with this reason)')
    change.add_argument('--clear-settings', action='store_true', help='Remove all checkpoints (with this reason)')
    sub.add_parser('show', help='Print the parent state and stops (read-only)')
    pre = sub.add_parser('preflight', help='Check every start condition without starting anything (read-only)')
    pre.add_argument('--prefix', help='Planned run-ID prefix (checks the next run ID is unused)')
    pre.add_argument('--prior-readback', help='Readback JSON of the last recorded cell (default: parent state)')
    pre.add_argument('--settings', type=Path, help='Planned choice_parent_loop_settings_v1 JSON')
    pre.add_argument('--monitor-config', type=Path, help='Monitor config.json (default: 07_監視システム)')
    args = parser.parse_args()
    if args.action == 'preflight':
        sys.dont_write_bytecode = True  # watch.py is loaded to probe the monitor: leave no __pycache__
        result = ParentLoop(args.project_root, args.prefix, args.prior_readback, args.settings,
                            monitor_config=args.monitor_config).preflight()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result['ready'] else EXIT_STOPPED)
    if args.action == 'run':
        sys.exit(ParentLoop(args.project_root, args.prefix, args.prior_readback, args.settings,
                            monitor_config=args.monitor_config, completion_status=args.completion_status).run())
    if args.action == 'ack':
        try:
            print(json.dumps(acknowledge(args.project_root, args.stop_id, args.reason, args.settings,
                                         args.clear_settings), ensure_ascii=False))
        except (ValueError, RuntimeError) as error:
            print(json.dumps({'status': 'ACK_REFUSED', 'error': str(error)}, ensure_ascii=False))
            sys.exit(EXIT_USAGE)
        return
    print(json.dumps(show(args.project_root), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
