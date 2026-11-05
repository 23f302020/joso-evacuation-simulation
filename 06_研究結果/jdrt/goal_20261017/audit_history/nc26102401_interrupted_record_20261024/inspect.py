"""Preserve the observed interrupted record; no research mutation or replay."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path.cwd().resolve()
OUT = Path(__file__).resolve().parent
RUN = 'nc26102401'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


cfg_path = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'
cfg = read(cfg_path)
workspace = ROOT / cfg['workspace']
operation = workspace / 'driver_logs' / (RUN + '.finish')
state = read(operation / 'operation.json')
lock = workspace / 'driver_logs/writer.lock'
owner = read(lock)
query = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^sumo'} | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine) | ConvertTo-Json -Compress"
response = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', query],
                          capture_output=True, text=True, encoding='utf-8', check=True)
processes = json.loads(response.stdout or '[]')
if isinstance(processes, dict):
    processes = [processes]
assert not any(p['ProcessId'] in (state['pid'], owner['pid'], 28452) for p in processes)
assert not any(RUN in (p.get('CommandLine') or '') and
               ('realtime_choice_cell.py' in (p.get('CommandLine') or '') or
                'choice_finish_cell.py' in (p.get('CommandLine') or '')) for p in processes)
assert state['status'] == 'RUNNING' and state['phase'] == 'record'
assert [c['status'] for c in state['commands']] == ['COMPLETED', 'PASS']
assert state['record_attempted'] and state['formal_record_result'] is None
manifest = workspace / 'runs' / RUN / 'manifest.json'
m = read(manifest)
assert m['status'] == 'COMPLETED' and m['parameter_sha256'] == digest(cfg_path)
assert all(digest(ROOT / name) == value for name, value in m['implementation_sha256'].items())
validation = ROOT / state['commands'][1]['validation_report']
v = read(validation)
assert digest(validation) == state['validation_report_sha256']
assert v['status'] == 'PASS' and v['core_adoption_permitted'] is True
assert v['manifest_sha256'] == digest(manifest)
ledger = [json.loads(s) for s in (ROOT / cfg['record_files'][-1]).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
assert len(ledger) == 7 and not any(row['run_id'] == RUN for row in ledger)
assert not list((workspace / 'record_transactions').glob(RUN + '_*'))
marker = '<!-- choice_record:' + RUN + ' -->'
assert all(marker not in (ROOT / p).read_text(encoding='utf-8-sig') for p in cfg['record_files'][:-1])
before = OUT / 'before02'
before.mkdir(exist_ok=False)
preserved = {}
paths = [cfg_path, manifest, lock, validation, *operation.iterdir(),
         *(ROOT / p for p in cfg['record_files'])]
for path in paths:
    if not path.is_file():
        continue
    name = path.relative_to(ROOT)
    raw = path.read_bytes()
    target = before / (sha256(raw).hexdigest() + path.suffix)
    if target.exists():
        assert target.read_bytes() == raw
        preserved[name.as_posix()] = digest(path)
        continue
    with target.open('xb') as stream:
        stream.write(raw)
    assert digest(target) == digest(path)
    preserved[name.as_posix()] = digest(path)
report = {'at_jst': datetime.now().astimezone().isoformat(),
          'status': 'ORPHAN_PRECOMMIT_RECORD_CONFIRMED', 'run_id': RUN,
          'original_operation': state, 'orphan_writer': owner, 'process_inventory': processes,
          'formal_rows_before': len(ledger), 'new_run_marker_counts_all_zero': True,
          'run_transactions_before': [], 'original_logs_empty': {
              name: (operation / name).stat().st_size for name in ('record.stdout.log', 'record.stderr.log')},
          'common5_current': True, 'independent_validation_original_pass': True,
          'preserved_sha256': preserved,
          'termination_cause': 'UNDETERMINED; missing original session and absent owners are observed, not a timeout',
          'observation_gap': 'last saved operation 08:41:15; reentry17:00; interval monitoring not asserted',
          'next_authorized_operation': 'dedicated recover-writer with reason, then dedicated record only; no core or standalone validate replay',
          'ACE': ['err-00001', 'err-00002'], 'parent_model_actual': 'UNVERIFIED',
          'previous_goal_turn': 'PROGRESS: current process absence and unfinished formal record established'}
with (OUT / 'diagnosis.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'status': report['status'], 'run_id': RUN,
                  'preserved_files': len(preserved), 'old_writer_pid': owner['pid']}, ensure_ascii=False))
