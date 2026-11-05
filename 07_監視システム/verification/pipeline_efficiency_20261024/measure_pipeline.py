"""Read-only pipeline measurement; never starts or records research runs."""
import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import time


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        return result if result.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def seconds(start, end):
    a, b = timestamp(start), timestamp(end)
    return (b - a).total_seconds() if a and b and b >= a else None


def cpu_percent(old, new, elapsed):
    if not old or elapsed <= 0 or (old['pid'], old['created']) != (new['pid'], new['created']):
        return None
    delta = new['cpu_sec'] - old['cpu_sec']
    return 100 * delta / elapsed if delta >= 0 else None


def operation_timing(row):
    wrapper = row.get('result', {})
    duration = wrapper.get('duration_sec')
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
        duration = None
    end = timestamp(row.get('at_jst'))
    result = wrapper.get('result', {})
    return {'command': row.get('command'), 'end': row.get('at_jst'),
            'duration_sec': duration,
            'inferred_start': (end - timedelta(seconds=duration)).isoformat() if end and duration is not None else None,
            'run_id': result.get('run_id'), 'status': result.get('status')}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def history(workspace):
    runs = []
    for path in sorted((workspace / 'runs').glob('*/manifest.json')):
        m = read(path)
        runs.append({'run_id': m['run_id'], 'cell_id': m.get('cell_id'), 'status': m['status'],
                     'start': m.get('started_at_jst'), 'end': m.get('finished_at_jst'),
                     'compute_elapsed_sec': seconds(m.get('started_at_jst'), m.get('finished_at_jst')),
                     'manifest_sha256': sha256(path.read_bytes()).hexdigest()})
    operations, errors = [], []
    log = workspace / 'driver_logs/operations.jsonl'
    if log.exists():
        with log.open(encoding='utf-8-sig') as stream:
            for number, line in enumerate(stream, 1):
                try:
                    row = json.loads(line)
                    if row.get('command') in ('execute', 'validate', 'record', 'start-next'):
                        operations.append(operation_timing(row))
                except (ValueError, TypeError, AttributeError):
                    errors.append({'line': number, 'error': 'unreadable_operation'})
    return {'runs': runs, 'operations': operations, 'errors': errors,
            'note': 'Elapsed includes sleep/interruptions; inferred starts use command-end minus duration. Missing times remain null.'}


# Raw command lines are used locally to classify phases, never saved.
QUERY = r'''
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$mem=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$cpu=Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
$disk=Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"
$processes=@(Get-CimInstance Win32_Process -Filter "Name like 'python%' OR Name like 'sumo%'" | ForEach-Object {
 $phase='unattributed'; $run=$null; $cmd=$_.CommandLine
 if($cmd -match 'realtime_choice_cell\.py' -and $cmd -match '(?:^|\s)(execute|validate|record|start-next)(?:\s|$)'){$phase=$Matches[1]}
 elseif($_.Name -like 'sumo*'){$phase='native_unattributed'}
 if($cmd -match '--run-id\s+"?([A-Za-z0-9_-]+)'){$run=$Matches[1]}
 [pscustomobject]@{pid=$_.ProcessId;created=$_.CreationDate.ToUniversalTime().ToString('o');name=$_.Name;phase=$phase;run_id=$run;cpu_sec=([double]$_.KernelModeTime+[double]$_.UserModeTime)/1e7;working_bytes=[double]$_.WorkingSetSize;private_bytes=[double]$_.PrivatePageCount;read_bytes=[double]$_.ReadTransferCount;write_bytes=[double]$_.WriteTransferCount}
})
[pscustomobject]@{query_cpu_sec=(Get-Process -Id $PID).CPU;logical_processors=[Environment]::ProcessorCount;cpu_percent=$cpu.PercentProcessorTime;available_mib=$mem.AvailableMBytes;pages_input_sec=$mem.PagesInputPersec;pages_output_sec=$mem.PagesOutputPersec;disk_bytes_sec=$disk.DiskBytesPersec;disk_queue=$disk.AvgDiskQueueLength;processes=$processes} | ConvertTo-Json -Depth 4 -Compress
'''


def collect(workspace):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', QUERY],
                            capture_output=True, text=True, encoding='utf-8', timeout=20,
                            creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    sample = json.loads(result.stdout)
    sample['runs'] = []
    for path in (workspace / 'runs').glob('*/manifest.json'):
        try:
            m = read(path)
            run = {key: m.get(key) for key in ('run_id', 'status', 'pid', 'started_at_jst', 'finished_at_jst')}
            if m['status'] == 'RUNNING':
                try:
                    progress = read(path.with_name('progress.json'))
                    run['progress'] = {key: progress.get(key) for key in ('at_jst', 'time_sec', 'wall_sec')}
                except (OSError, ValueError) as error:
                    run['progress_error'] = type(error).__name__
            sample['runs'].append(run)
        except (OSError, ValueError) as error:
            sample['runs'].append({'run_id': path.parent.name, 'error': type(error).__name__})
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=86400)
    parser.add_argument('--interval', type=float, default=60)
    parser.add_argument('--history-only', action='store_true')
    args = parser.parse_args()
    if args.interval < 30 or args.seconds <= 0:
        parser.error('interval must be >=30 and seconds >0')
    root, output = args.project_root.resolve(), args.output.resolve()
    cfg = read(root / '04_プログラム/config/jdrt_realtime_choice_v1.json')
    workspace = (root / cfg['workspace']).resolve()
    if output.is_relative_to(workspace) or workspace.is_relative_to(output):
        parser.error('measurement output must be separate from research workspace')
    output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        temporary = output / (name + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(output / name)
    save('history.json', history(workspace))
    state = {'schema': 'pipeline_measurement_v1', 'pid': os.getpid(), 'status': 'HISTORY_ONLY' if args.history_only else 'RUNNING',
             'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
             'started_at': datetime.now().astimezone().isoformat(), 'interval_sec': args.interval,
             'planned_seconds': args.seconds, 'samples': 0, 'failures': 0,
             'limitations': ['CPU percent per process: 100=one logical CPU', 'Python/SUMO processes may belong to other work; phase is a command-name hint, not research ownership proof',
                            'Sampled memory maxima are lower bounds, not exact peaks', 'No temperature sensor or user responsiveness measurement',
                            'Missing/failed observations are not zero; long gaps may include sleep']}
    save('state.json', state)
    if args.history_only:
        return
    start = time.monotonic()
    previous, previous_at = {}, None
    with (output / 'samples.jsonl').open('x', encoding='utf-8', buffering=1) as stream:
        while time.monotonic() - start < args.seconds:
            begin = time.monotonic()
            cpu_begin = time.process_time()
            sample = {'observed_at': datetime.now().astimezone().isoformat()}
            try:
                sample.update(collect(workspace))
                now = time.monotonic()
                for process in sample['processes']:
                    process['cpu_percent_one_core'] = cpu_percent(previous.get(process['pid']), process, now - previous_at) if previous_at else None
                previous = {p['pid']: p for p in sample['processes']}
                previous_at = now
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                sample['error'] = type(error).__name__
                state['failures'] += 1
            sample['collection_wall_sec'] = time.monotonic() - begin
            sample['collector_python_cpu_sec'] = time.process_time() - cpu_begin
            stream.write(json.dumps(sample, ensure_ascii=False) + '\n')
            state.update(samples=state['samples'] + 1, last_observed_at=sample['observed_at'])
            save('state.json', state)
            time.sleep(max(0, min(args.interval - (time.monotonic() - begin), args.seconds - (time.monotonic() - start))))
    state.update(status='COMPLETED', finished_at=datetime.now().astimezone().isoformat())
    save('state.json', state)


if __name__ == '__main__':
    main()
