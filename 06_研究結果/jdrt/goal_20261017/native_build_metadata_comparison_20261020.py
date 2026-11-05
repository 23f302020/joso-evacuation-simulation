"""Snapshot/compare actual build metadata; never declare a native pair ready."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/joso-jdrt-runner/scripts'))
import choice_pair_metadata

ST = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
GOAL = Path(__file__).parent
OUT = GOAL / 'audit_history' / ('native_metadata_pair_' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
OUT.mkdir()
states = {'patched': ST / 'attempt08_20261020/build_state.json', 'control': ST / 'control02_20261020/build_state.json'}
files = choice_pair_metadata.FILES
values = {}
roots = {}
statuses = {}
rows = []
for role, state_file in states.items():
    raw_state = state_file.read_bytes()
    state = json.loads(raw_state)
    statuses[role] = state['status']
    configured = [entry for entry in state['commands'] if '-S' in entry['command'] and '-B' in entry['command']]
    if len(configured) != 1 or configured[0]['exit_code'] != 0:
        raise ValueError('Need exactly one successful configuration per role')
    args = configured[0]['command']
    source, build = (Path(args[args.index(key) + 1]) for key in ('-S', '-B'))
    roots[role] = (str(source), str(build))
    role_out = OUT / role
    role_out.mkdir()
    (role_out / 'state.snapshot.bin').write_bytes(raw_state)
    normalized = {}
    for index, name in enumerate(files):
        path = build / name
        raw = path.read_bytes()
        (role_out / (str(index) + '_' + Path(name).name)).write_bytes(raw)
        normalized[name] = raw.decode('utf-8')
        rows.append({'role': role, 'path': str(path), 'relative_path': name,
                     'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    values[role] = normalized
verified = choice_pair_metadata.compare_metadata(values['patched'], values['control'], roots['patched'], roots['control'])
comparison = {name: name not in verified['different_files'] for name in files}
report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'files': rows, 'comparison': comparison,
          'different_files': [name for name, equal in comparison.items() if not equal],
          'canonicalizer': verified,
          'canonicalizer_sha256': hashlib.sha256(Path(choice_pair_metadata.__file__).read_bytes()).hexdigest(),
          'normalization': 'Declared root paths and EOL; typed cache entries, compiler path spellings/types, empty Python reason only with native Python bindings OFF',
          'build_statuses': statuses,
          'control_may_still_be_building': statuses['control'] in ('RUNNING', 'STARTING'),
          'state_snapshots_are_point_observations': True,
          'paired_executable_proof_completed': False, 'core_ready': False, 'simulation_executed': False}
with (OUT / 'comparison.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps({'report': str(OUT / 'comparison.json'), 'different_files': report['different_files'],
                  'metadata_file_pairs': len(files)}, ensure_ascii=False))
