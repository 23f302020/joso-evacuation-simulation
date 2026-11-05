"""Compare archived source hashes with ZIP bytes; not a current-state/READY gate."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile
import hashlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
from choice_package_toolchain import checked, read_json, sha

ST = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
snapshot_path = ST / 'control_source_preparation_20261020.json'
snapshot = read_json(snapshot_path)
if snapshot['status'] != 'PREPARED_NOT_BUILT':
    raise ValueError('Need completed source preparation')
proposal_path = Path(__file__).parent / 'audit_history/walk_native_proposal_20261019/proposal_manifest.json'
proposal = read_json(proposal_path)
repair_path = ST / 'attempt08_20261020/previous_build_state.json'
repair = read_json(repair_path)['cmake_link_repair']
archive_path = checked({'path': ST / ('downloads/sumo-' + snapshot['source_commit'] + '.zip'),
                        'sha256': snapshot['archive_sha256']})
before = checked({'path': ST / 'attempt07_20261020/CMakeLists.before.bin', 'sha256': repair['before_sha256']})
patch = checked({'path': ST / 'attempt07_20261020/cmake_link.patch', 'sha256': repair['patch_sha256']})
trees = snapshot['source_sha256']
if set(trees) != {'control', 'patched'} or set(trees['control']) != set(trees['patched']):
    raise ValueError('Source snapshot file sets differ')
native = proposal['target']
if {name for name in trees['control'] if trees['control'][name] != trees['patched'][name]} != {native}:
    raise ValueError('Pair differences exceed registered native source')
rows, unexpected, members = [], [], set()
prefix = 'sumo-' + snapshot['source_commit'] + '/'
with zipfile.ZipFile(archive_path) as archive:
    for entry in archive.infolist():
        if entry.is_dir() or not entry.filename.startswith(prefix):
            continue
        name = entry.filename[len(prefix):]
        if name != 'CMakeLists.txt' and not name.startswith(('src/', 'build_config/')):
            continue
        if name in members:
            raise ValueError('Duplicate archive build-scope member')
        members.add(name)
        original = hashlib.sha256(archive.read(entry)).hexdigest()
        expected = {'control': original, 'patched': original}
        if name == native:
            if original != proposal['official_before_sha256']:
                raise ValueError('ZIP native source differs from registered base')
            expected['patched'] = proposal['proposed_sha256']
        elif name == 'src/CMakeLists.txt':
            if original != sha(before):
                raise ValueError('Original CMake source differs from preserved repair base')
            expected = {'control': repair['after_sha256'], 'patched': repair['after_sha256']}
        observed = {role: trees[role].get(name) for role in trees}
        if all(value is not None for value in observed.values()) and observed != expected:
            unexpected.append(name)
        rows.append({'path': name, 'official_sha256': original, 'expected_sha256': expected,
                     'observed_snapshot_sha256': observed})
actual = {name for name in trees['control'] if name == 'CMakeLists.txt' or name.startswith(('src/', 'build_config/'))}
missing = sorted(members - actual)
extra = sorted(actual - members)
report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'action': 'archived_native_source_baseline_comparison',
          'snapshot': {'path': str(snapshot_path), 'sha256': sha(snapshot_path)},
          'proposal_sha256': sha(proposal_path), 'repair_state_sha256': sha(repair_path),
          'source_archive_sha256': sha(archive_path), 'shared_build_patch_sha256': sha(patch),
          'scope': ['CMakeLists.txt', 'src/', 'build_config/'], 'archive_scope_files': len(members),
          'snapshot_scope_files': len(actual), 'pair_file_count': len(trees['control']),
          'missing_extracted_files': missing, 'extra_extracted_files': extra, 'unexpected_modifications': unexpected,
          'rows': rows, 'point_snapshot_only': True, 'current_source_bytes_reverified': False,
          'core_ready': False, 'simulation_allowed': False, 'formal_adoption_permitted': False,
          'missing_file_classification': 'unclassified: inspect actual target inclusion before acceptance'}
out = Path(__file__).parent / ('native_source_snapshot_audit_' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.json')
with out.open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps({'report': str(out), 'archive_scope': len(members), 'snapshot_scope': len(actual),
                  'missing': missing, 'extra': extra, 'unexpected': unexpected}, ensure_ascii=False))
if extra or unexpected:
    raise SystemExit(1)
