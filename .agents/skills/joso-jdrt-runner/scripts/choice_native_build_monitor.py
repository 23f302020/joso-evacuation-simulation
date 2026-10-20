"""Observe an isolated native build using independent CIM identities; no build or simulation actions."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from choice_monitor import ROOT, file_sha

FAILURE = {'FAILED', 'FAILED_PRESERVED'}
TERMINAL = {'COMPLETED', 'COMPILED_VERSION_CHECKED_NOT_SIMULATED', *FAILURE}
ACTION = 'isolated_native_build_monitor'


def creation_ms(value):
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.fullmatch(r'/Date\((-?\d+)(?:[+-]\d{4})?\)/', value)
        if match:
            return int(match[1])
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is not None:
            return round(parsed.timestamp() * 1000)
    raise ValueError('Missing or timezone-ambiguous process creation time')


def cim_process(pid):
    command = (f'Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" | '
               'Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,'
               '@{n="CreationDate";e={([DateTimeOffset]$_.CreationDate.ToUniversalTime()).ToUnixTimeMilliseconds()}} | '
               'ConvertTo-Json -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, text=True, check=True, timeout=30)
    return json.loads(result.stdout) if result.stdout.strip() else None


def identity(pid, expected, query):
    value = {'pid': pid, 'expected': expected, 'identity': 'unknown'}
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        value['error'] = 'Positive integer PID required'
        return value
    actual = query(pid)
    value['observed_cim'] = actual
    if actual is None:
        value['identity'] = 'absent'
        return value
    try:
        if creation_ms(expected['CreationDate']) != creation_ms(actual['CreationDate']):
            value['identity'] = 'reused'
        elif (expected['ProcessId'] != pid or actual['ProcessId'] != pid
              or not expected['CommandLine'] or not actual['CommandLine']
              or not expected['ExecutablePath'] or not actual['ExecutablePath']):
            value['error'] = 'Incomplete PID/command/executable identity'
        elif (expected['CommandLine'] != actual['CommandLine']
              or os.path.normcase(expected['ExecutablePath']) != os.path.normcase(actual['ExecutablePath'])
              or expected['ParentProcessId'] != actual['ParentProcessId']):
            value['identity'] = 'mismatched'
        else:
            value['identity'] = 'matched'
    except (KeyError, TypeError, ValueError) as error:
        value['error'] = str(error)
    return value


def log_evidence(path, terminal):
    size = path.stat().st_size
    with path.open('rb') as stream:
        stream.seek(max(0, size - 8192))
        tail = stream.read(8192).decode('utf-8', errors='replace')
    value = {'path': str(path), 'bytes': size, 'tail_max_bytes': 8192, 'tail': tail,
             'sha256': file_sha(path) if terminal else None,
             'sha256_policy': 'terminal_only; live logs may grow during observation'}
    return value


def previous_observation(path, state_path):
    if not path.exists():
        return None
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 512 * 1024))
        lines = stream.read().decode('utf-8', errors='replace').splitlines()
    for line in reversed(lines):
        try:
            value = json.loads(line)
            if value.get('action') == ACTION and value.get('state_path') == str(state_path):
                return value['at_utc']
        except (ValueError, KeyError):
            continue
    return None


def observe(state_path, query=cim_process):
    now = datetime.now(timezone.utc)
    flags = []
    value = {'action': ACTION, 'at_utc': now.isoformat(), 'at_jst': now.astimezone(timezone(timedelta(hours=9))).isoformat(),
             'state_path': str(state_path), 'anomaly_flags': flags,
             'downstream_start_permitted': False, 'simulation_allowed': False,
             'research_cli_switch_allowed': False, 'core_ready': False,
             'formal_validation_or_adoption': False, 'native_regression_verified': False,
             'research_core_manifest': 'not_applicable: isolated build; no research run is started',
             'independent_observation_interval_sec': 900,
             'orchestrator_state_update_is_independent_observation': False,
             'monitor_source_sha256': file_sha(Path(__file__))}
    raw = b''
    try:
        raw = state_path.read_bytes()
        from hashlib import sha256
        value['state_snapshot_sha256'] = sha256(raw).hexdigest()
        value['state_snapshot_bytes'] = len(raw)
        state = json.loads(raw.decode('utf-8-sig'))
        value['state_snapshot'] = state
        if (state['schema'] != 'isolated_native_build_v1' or not state['attempt_id']
                or state['status'] not in {'RUNNING', *TERMINAL} or not state['phase']):
            raise ValueError('Missing or unsupported isolated build schema/status/attempt/phase')
        terminal = state['status'] in TERMINAL
        value.update(status=state['status'], phase=state['phase'], attempt_id=state['attempt_id'],
                     started_at_jst=state['started_at_jst'], state_updated_at_jst=state.get('updated_at_jst'))
        started = datetime.fromisoformat(state['started_at_jst'])
        if started.tzinfo is None:
            raise ValueError('Build start time lacks timezone')
        value['seconds_from_build_start_to_this_observation'] = (now - started).total_seconds()
        if state.get('updated_at_jst'):
            updated = datetime.fromisoformat(state['updated_at_jst'])
            if updated.tzinfo is None:
                raise ValueError('State update time lacks timezone')
            value['state_update_age_sec'] = (now - updated).total_seconds()
        for key in ('simulation_allowed', 'research_cli_switch_allowed'):
            if state.get(key) is not False:
                flags.append('build_state_' + key + '_not_false')
        value['owner'] = identity(state['owner_pid'], state.get('owner_process_identity'), query)
        if not terminal and value['owner']['identity'] != 'matched':
            flags.append('nonterminal_owner_' + value['owner']['identity'])
        if value['owner']['identity'] in ('reused', 'mismatched'):
            flags.append('owner_identity_conflict')
        commands = state['commands']
        if not isinstance(commands, list):
            raise ValueError('commands must be a list')
        pid = state.get('child_pid')
        active = [item for item in commands if item.get('pid') == pid and item.get('phase') == state['phase']]
        if not terminal and len(active) != 1:
            flags.append('nonterminal_active_child_evidence_missing_or_ambiguous')
        elif len(active) == 1:
            item = active[0]
            value['child'] = identity(pid, item.get('process_identity'), query)
            if not terminal and (value['child']['identity'] != 'matched' or 'exit_code' in item):
                flags.append('nonterminal_child_' + value['child']['identity'] + '_or_already_exited')
            if value['child']['identity'] in ('reused', 'mismatched'):
                flags.append('child_identity_conflict')
            expected_child = item.get('process_identity')
            if not isinstance(expected_child, dict) or expected_child.get('ParentProcessId') != state['owner_pid']:
                flags.append('child_parent_not_build_owner')
        if state['status'] in FAILURE:
            flags.append('terminal_build_' + state['status'])
        paths = {str(item['log']) for item in commands if item.get('log')}
        if state.get('log'):
            paths.add(state['log'])
        value['logs'] = [log_evidence(Path(path), terminal) for path in sorted(paths)]
        value['disk'] = {str(path): {'free_bytes': shutil.disk_usage(path).free,
                                   'total_bytes': shutil.disk_usage(path).total}
                         for path in {state_path.parent, Path(state['staging'])}}
        value['state_bytes_unchanged_during_observation'] = state_path.read_bytes() == raw
        value['state_concurrency_note'] = 'A live orchestrator can legitimately update its state/logs while this reader observes.'
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        flags.append('missing_partial_or_ambiguous_build_evidence')
        value['observation_error'] = {'type': type(error).__name__, 'message': str(error)}
    return value, raw


def record(root, state_path, query=cim_process):
    out = root / '06_研究結果/jdrt/goal_20261017'
    cfg = json.loads((root / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8-sig'))
    logs = root / cfg['workspace'] / 'driver_logs'
    value, raw = observe(state_path, query)
    previous = previous_observation(logs / 'monitoring.jsonl', state_path)
    value['previous_independent_observation_at_utc'] = previous
    value['unobserved_interval_sec'] = ((datetime.fromisoformat(value['at_utc']) - datetime.fromisoformat(previous)).total_seconds()
                                        if previous else None)
    value['observation_coverage'] = 'Point observation only; no continuous monitoring is inferred between observations.'
    label = datetime.fromisoformat(value['at_jst']).strftime('%Y%m%dT%H%M%S%f')
    destination = out / ('nativebuild監視_' + label + '.json')
    snapshot = destination.with_suffix('.state.snapshot.bin')
    value.update(report=destination.relative_to(root).as_posix(), state_snapshot_file=snapshot.relative_to(root).as_posix())
    out.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    with snapshot.open('xb') as stream:
        stream.write(raw)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    line = json.dumps(value, ensure_ascii=False) + '\n'
    for path in (out / 'operations.jsonl', logs / 'operations.jsonl', logs / 'monitoring.jsonl'):
        with path.open('a', encoding='utf-8') as stream:
            stream.write(line)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    args = parser.parse_args()
    if not args.state.is_absolute():
        parser.error('--state requires an absolute JSON path')
    value = record(args.project_root.resolve(), args.state.resolve())
    print(json.dumps({key: value.get(key) for key in ('at_utc', 'at_jst', 'status', 'phase', 'owner', 'child', 'anomaly_flags', 'report')}, ensure_ascii=False))
    return int(bool(value['anomaly_flags']))


if __name__ == '__main__':
    raise SystemExit(main())
