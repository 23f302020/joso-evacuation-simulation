"""Observe one technical fixture suite; never start, recover, validate or adopt."""
import argparse
import ast
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from choice_monitor import ROOT, OUT, file_sha


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inventory(folders):
    return {str(p): file_sha(p) for folder in folders for p in folder.rglob('*') if p.is_file()}


def select_child(parent, suite_id, technical):
    cases = next(ast.literal_eval(n.value) for n in ast.parse((parent / 'factory.py').read_text(encoding='utf-8')).body
                 if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CASES' for t in n.targets))
    children = sorted((p for p in technical.glob(suite_id + '_c*') if re.fullmatch(re.escape(suite_id) + r'_c\d{2}', p.name)),
                      key=lambda p: int(p.name.rsplit('_c', 1)[1]))
    if not children:
        raise ValueError('No actual child directory')
    child = children[-1]
    m = read(child / 'execution/manifest.json')
    index = int(child.name.rsplit('_c', 1)[1]) - 1
    if (m['purpose'] != 'fixture' or m['protocol'] != 'realtime_choice_fixture_v1'
            or m['run_id'] != child.name or m['research_adoption_permitted'] is not False
            or index < 0 or index >= len(cases) or m['fixture_case'] != cases[index]):
        raise ValueError('Foreign, ambiguous or non-fixture child')
    return child, m, children


def process(pid, started, suite_id):
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError('Positive suite PID required')
    command = (f'Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" | '
               'Select-Object ProcessId,CommandLine,@{n="created_at";e={$_.CreationDate.ToUniversalTime().ToString("o")}} | ConvertTo-Json -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, check=True)
    value = json.loads(result.stdout) if result.stdout.strip() else None
    if not value:
        return {'pid': pid, 'identity': 'absent'}
    created = datetime.fromisoformat(value['created_at'].replace('Z', '+00:00'))
    identity = ('reused' if created > datetime.fromisoformat(started) else 'matched'
                if suite_id in (value['CommandLine'] or '') and 'choice_technical.py' in value['CommandLine'] else 'ambiguous')
    return {'pid': pid, 'identity': identity, **value}


def raw_accounting(inputs, folder):
    with (inputs / 'people.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    states = {p['person_id']: 'not_ready' for p in rows}
    if len(states) != len(rows):
        raise ValueError('Duplicate input person ID')
    event_time = None
    for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        event = json.loads(line)
        event_time = max(event_time or 0, event['time_sec'])
        if event['event'] == 'person_state':
            if event['person_id'] not in states or states[event['person_id']] != event['before']:
                raise ValueError('Person-state chain mismatch')
            states[event['person_id']] = event['after']
    actor_time, actor_rows, actor_complete = None, 0, True
    try:
        with gzip.open(folder / 'actor_observations.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
            for row in csv.DictReader(stream):
                actor_time = max(actor_time or 0, float(row['time_sec']))
                actor_rows += 1
    except (EOFError, OSError, ValueError):
        actor_complete = False
    return {'population_rows': len(rows), 'person_states_from_events': dict(Counter(states.values())),
            'latest_event_time_sec': event_time, 'raw_actor_last_time_sec': actor_time, 'raw_actor_rows': actor_rows, 'raw_actor_complete': actor_complete}


def observe(root, suite_id, destination):
    cfg = read(root / '04_プログラム/config/jdrt_realtime_choice_v1.json')
    workspace = root / cfg['workspace']
    technical, flags = workspace / 'technical', []
    parent = technical / suite_id
    originals = inventory([parent, *technical.glob(suite_id + '_c*')])
    value = {'suite_id': suite_id, 'action': 'detailed_same_technical_suite_monitor', 'anomaly_flags': flags,
             'formal_validation_or_adoption': False, 'downstream_start_permitted': False,
             'free_bytes': shutil.disk_usage(root).free, 'monitor_source_sha256': file_sha(Path(__file__))}
    try:
        suite = read(parent / 'manifest.json')
        if (suite['protocol'] != 'realtime_choice_fixture_suite_v1' or suite['purpose'] != 'technical_fixture_suite'
                or suite['run_id'] != suite_id or suite['research_adoption_permitted'] is not False):
            raise ValueError('Not a technical fixture suite')
        value.update(suite_manifest=suite, suite_progress=read(parent / 'progress.json'), suite_progress_means='last_completed_case')
        child, m, children = select_child(parent, suite_id, technical)
        folder, inputs = child / 'execution', root / m['input_directory']
        value.update(actual_child_run_id=child.name, child_manifest=m)
        command = [sys.executable, '-X', 'utf8', str(root / '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'),
                   '--project-root', str(root), 'check', '--run-id', child.name]
        result = subprocess.run(command, cwd=root, capture_output=True)
        destination.with_suffix('.check.stdout.log').write_bytes(result.stdout)
        destination.with_suffix('.check.stderr.log').write_bytes(result.stderr)
        value.update(check_command=command, check_exit_code=result.returncode, skill_check=json.loads(result.stdout.decode('utf-8-sig')))
        if result.returncode or value['skill_check']['run_id'] != child.name or value['skill_check']['status'] != m['status']:
            flags.append('dedicated_check_failure_or_mismatch')
        value['child_progress'] = read(folder / 'progress.json')
        value['process'] = process(suite['pid'], suite['started_at_jst'], suite_id)
        if m['pid'] != suite['pid'] or value['process']['identity'] in ('ambiguous', 'reused'):
            flags.append('PID_identity_mismatch_or_ambiguous')
        if suite['status'] == 'RUNNING' and (value['process']['identity'] != 'matched' or not value['skill_check']['pid_alive']):
            flags.append('orphan_or_ambiguous_RUNNING')
        if suite['status'] == 'FAILED' or m['status'] == 'FAILED' or value['skill_check'].get('error'):
            flags.append('terminal_failure_or_reported_error')
        reported = {c['child_run_id'] for c in suite['cases']}
        if len([p for p in children if p.name not in reported]) > 1:
            flags.append('multiple_unreported_children')
        hashes = {'factory_archive': file_sha(parent / 'factory.py') == suite['factory_sha256'],
                  'input_manifest': file_sha(inputs / 'manifest.json') == m['input_manifest_sha256'],
                  'parameters': file_sha(root / m['parameter_path']) == m['parameter_sha256']}
        value['integrity'] = hashes
        expected = m['implementation_sha256']
        if set(expected) != set(cfg['execution']['implementation_files']):
            flags.append('common_five_set_mismatch')
        for name, sha in expected.items():
            hashes['current:' + name] = file_sha(root / name) == sha
            hashes['archive:' + name] = file_sha(folder / 'implementation' / name) == sha == m['implementation_archive_sha256'][name]
        for name, sha in read(inputs / 'manifest.json')['artifacts'].items():
            hashes['input:' + name] = file_sha(inputs / name) == sha
        for name, sha in read(inputs / 'manifest.json')['source_sha256'].items():
            hashes['input_source:' + name] = file_sha(root / name) == sha
        for name, sha in m.get('output_sha256', {}).items():
            hashes['output:' + name] = file_sha(folder / name) == sha
        value.update(integrity=hashes, output_sha_status='present' if m.get('output_sha256') else 'unfinalized_missing')
        if not all(hashes.values()):
            flags.append('SHA_mismatch')
        if m['status'] != 'RUNNING' and not m.get('output_sha256'):
            flags.append('terminal_output_SHA_missing')
        value['accounting'] = raw_accounting(inputs, folder)
        if not value['accounting']['raw_actor_complete']:
            flags.append('partial_raw_actor_stream')
        point = value['child_progress']
        value['heartbeat_progress_time_sec'], value['heartbeat_at_jst'] = point['time_sec'], point['at_jst']
        value['progress_is_final_sim_time'] = False
        if sum(point['people_states'].values()) != value['accounting']['population_rows']:
            flags.append('heartbeat_whole_population_mismatch')
        for key in ('teleports', 'collisions', 'closed_entry_rows', 'ambiguous_transitions', 'missing_vehicle_subscriptions', 'missing_person_subscriptions'):
            if point['counts'][key]:
                flags.append('nonzero_' + key)
        native = (folder / 'sumo_errors.log').read_text(encoding='utf-8', errors='replace').splitlines()
        value['native_prefix_counts'] = {prefix: sum(line.lstrip().startswith(prefix + ':') for line in native) for prefix in ('Error', 'Warning')}
        if value['native_prefix_counts']['Error']:
            flags.append('native_SUMO_Error_lines')
    except (OSError, ValueError, KeyError, TypeError, StopIteration, EOFError, subprocess.SubprocessError) as error:
        flags.append('missing_partial_or_ambiguous_evidence')
        value['observation_error'] = {'type': type(error).__name__, 'message': str(error)}
    value['original_sha256'] = originals
    value['current_suite_bytes'] = sum(Path(p).stat().st_size for p in originals if Path(p).exists())
    value['originals_unchanged'] = originals == inventory([parent, *technical.glob(suite_id + '_c*')])
    if not value['originals_unchanged'] and value.get('suite_manifest', {}).get('status') != 'RUNNING':
        flags.append('original_artifacts_changed_during_observation')
    return value, workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', args.suite_id):
        parser.error('Simple suite ID required')
    now = datetime.now(timezone(timedelta(hours=9)))
    destination = OUT / ('技術監視_' + args.suite_id + '_' + now.strftime('%Y%m%dT%H%M%S%f') + '.json')
    value, workspace = observe(ROOT, args.suite_id, destination)
    value.update(at_jst=now.isoformat(), report=destination.relative_to(ROOT).as_posix())
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    for path in (OUT / 'operations.jsonl', workspace / 'driver_logs/operations.jsonl', workspace / 'driver_logs/monitoring.jsonl'):
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    print(json.dumps(value, ensure_ascii=False))
    return int(bool(value['anomaly_flags']))


if __name__ == '__main__':
    raise SystemExit(main())
