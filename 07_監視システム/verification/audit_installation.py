"""Read-only installation audit; stores a new receipt, never adopts research data."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import watch

config = watch.read_json(BASE / 'config.json')
runtime = Path(config['runtime'])
state = watch.read_json(runtime / 'state.json')
identity = watch.process_identity(state['monitor_pid'])
source = hashlib.sha256((BASE / 'watch.py').read_bytes()).hexdigest()
assert identity == state['monitor_identity'] and identity['state'] == 'alive'
assert time.time() - state['observed_epoch'] < 40
assert source == state['monitor_source_sha256']

tests = (BASE / 'verification/tests_final19.txt').read_text(encoding='utf-8')
assert re.search(r'Ran 19 tests', tests) and re.search(r'\bOK\b', tests)
smoke = watch.read_json(BASE / 'verification/smoke05/result.json')
assert smoke['event']['delivery'] == 'done' and smoke['event']['notification'] == 'submitted'
stream = BASE / 'verification/smoke05/events' / (smoke['event']['id'] + '.stdout.log')
items = [json.loads(line) for line in stream.read_text(encoding='utf-8').splitlines() if line.startswith('{')]
assert all(x.get('item', {}).get('type') in {None, 'agent_message'} for x in items)
assert any(x.get('type') == 'turn.completed' for x in items)
rescue = watch.read_json(BASE / 'verification/restart_rescue_after.json')
assert rescue['old_pid'] != rescue['new_pid'] and rescue['identity_matches']

command = '[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); Export-ScheduledTask -TaskName JDRT-SimulationWatch'
result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                        capture_output=True, check=True, timeout=20)
task = ET.fromstring(result.stdout.decode('utf-8-sig'))
ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
interval = task.findtext('.//t:TimeTrigger/t:Repetition/t:Interval', namespaces=ns)
instances = task.findtext('.//t:MultipleInstancesPolicy', namespaces=ns)
assert interval == 'PT1M' and instances == 'IgnoreNew'
assert task.find('.//t:LogonTrigger', ns) is not None

edits = watch.read_json(BASE / 'verification/document_edits.json')
outside = {}
for entry in edits:
    original = (BASE / 'verification/originals' / (entry['before_sha256'] + '.bin')).read_bytes()
    current = (BASE.parent / entry['path']).read_bytes()
    delta = len(current) - len(original)
    at = next((i for i, (a, b) in enumerate(zip(original, current)) if a != b), len(original))
    outside[entry['path']] = delta >= 0 and original[:at] == current[:at] and original[at:] == current[at + delta:]
assert all(outside.values()), outside

files = list(BASE.glob('*.py')) + list(BASE.glob('*.ps1')) + [BASE / 'README.md']
for path in BASE.glob('*.py'):
    ast.parse(path.read_text(encoding='utf-8'))
for path in files:
    data = path.read_bytes()
    assert b'\x00' not in data
    assert all(not line.endswith((b' ', b'\t')) for line in data.splitlines())

now = datetime.now(timezone.utc)
receipt = {'schema': 'simulation_watch_installation_audit_v1', 'at_utc': now.isoformat(),
           'monitor_pid': state['monitor_pid'], 'identity_matches': True, 'loaded_source_matches': True,
           'monitor_source_sha256': source, 'targets': len(state['targets']),
           'active_targets': sum(v.get('status') in watch.ACTIVE for v in state['targets'].values()),
           'events': len(list((runtime / 'events').glob('*.json'))), 'tests': 19,
           'artificial_notification': 'submitted_not_viewed_confirmation', 'artificial_codex': 'done_no_tool_calls',
           'scheduled_rescue_interval': interval, 'multiple_instances': instances,
           'scheduled_recovery_verified': True, 'canonical_outside_insertions_unchanged': outside,
           'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
           'research_run_started_by_installation': False, 'formal_acceptance': False,
           'limitations': ['no new research core run', 'no native-child/full-accounting acceptance audit',
                           'no desktop-chat posting', 'no external dead-host monitor', 'HTML not visually inspected']}
destination = BASE / 'verification' / ('final_verification_' + now.strftime('%Y%m%dT%H%M%S%f') + '.json')
watch.atomic_json(destination, receipt)
print(destination)
print('PASS: live identity/source, 19 tests, event roundtrip, scheduled rescue, eight byte-preserving document additions')
