"""Current primary source audit only; no packaging, native execution or READY."""
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
GOAL = Path(__file__).parent
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
from choice_package_toolchain import checked, read_json, sha
import choice_pair_sources
import choice_pair_metadata

ST = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
snapshot_path = ST / 'control_source_preparation_20261020.json'
snapshot = read_json(snapshot_path)
proposal_path = GOAL / 'audit_history/walk_native_proposal_20261019/proposal_manifest.json'
proposal = read_json(checked({'path': proposal_path, 'sha256': snapshot['registered_proposal_sha256']}))
states = {role: read_json(ST / name / 'build_state.json')
          for role, name in [('patched', 'attempt08_20261020'), ('control', 'control02_20261020')]}
roots, builds, exclusion_checks = {}, {}, {}
for role, state in states.items():
    if state['status'] != 'COMPILED_VERSION_CHECKED_NOT_SIMULATED':
        raise ValueError('Source audit requires both builds stopped and terminal')
    configs = [c for c in state['commands'] if '-S' in c['command'] and '-B' in c['command']]
    if len(configs) != 1 or configs[0]['exit_code'] != 0:
        raise ValueError('Unique successful configure required')
    args = configs[0]['command']
    roots[role] = Path(args[args.index('-S') + 1])
    builds[role] = Path(args[args.index('-B') + 1])
    if roots[role].resolve() != Path(snapshot[role + '_source_root']).resolve():
        raise ValueError('Source root differs from prepared snapshot')
    cache = choice_pair_metadata.cache_entries((builds[role] / 'CMakeCache.txt').read_text())
    config = (builds[role] / 'src/config.h').read_text()
    targets = (builds[role] / 'CMakeFiles/TargetDirectories.txt').read_text().replace('\\', '/')
    cmake = (roots[role] / 'src/utils/CMakeLists.txt').read_text()
    exclusion_checks[role] = {
        'FOX_find_disabled': cache.get('CMAKE_DISABLE_FIND_PACKAGE_FOX') == ('UNINITIALIZED', 'TRUE'),
        'MinGW_generator': cache.get('CMAKE_GENERATOR') == ('INTERNAL', 'MinGW Makefiles'),
        'HAVE_FOX_undefined': '#define HAVE_FOX' not in config and '/* #undef HAVE_FOX */' in config,
        'tests_guarded_by_FOX': 'if (FOX_FOUND)\n    add_subdirectory(foxtools)\n    add_subdirectory(gui)\n    add_subdirectory(tests)\nendif ()' in cmake,
        'no_generated_utils_tests_target': '/src/utils/tests/' not in targets,
    }
    if not all(exclusion_checks[role].values()):
        raise ValueError('Selected build no longer excludes missing FOX tests: ' + repr(exclusion_checks[role]))
repair = states['patched']['cmake_link_repair']
if states['control']['cmake_link_repair'] != repair:
    raise ValueError('Shared build repair references differ')
patches = {proposal['target']: {
    'path': str(GOAL / 'audit_history/walk_native_proposal_20261019/preserve_aborted_walk_raw_lateral.patch'),
    'sha256': proposal['patch_sha256'], 'before_sha256': proposal['official_before_sha256'],
    'after_sha256': proposal['proposed_sha256'], 'roles': ['patched']},
    'src/CMakeLists.txt': {
    'path': str(ST / 'attempt07_20261020/cmake_link.patch'), 'sha256': repair['patch_sha256'],
    'before_sha256': repair['before_sha256'], 'after_sha256': repair['after_sha256'],
    'roles': ['control', 'patched']}}
classification_path = GOAL / 'native_source_missing_files_classification_20261020.json'
classification = read_json(classification_path)
expected_missing = ['build_config/debian/tests/control', 'build_config/debian/tests/parade',
    'src/utils/tests/CMakeLists.txt', 'src/utils/tests/InternalTest.cpp', 'src/utils/tests/InternalTest.h',
    'src/utils/tests/InternalTestStep.cpp', 'src/utils/tests/InternalTestStep.h']
if classification['missing'] != expected_missing:
    raise ValueError('Reviewed missing-file scope changed')
archive_path = checked({'path': ST / ('downloads/sumo-' + snapshot['source_commit'] + '.zip'),
                        'sha256': snapshot['archive_sha256']})
result = choice_pair_sources.verify_sources(archive_path, snapshot['source_commit'], roots,
    snapshot['source_sha256'], patches, expected_missing)
result.update({'at_jst': datetime.now().astimezone().isoformat(),
    'scope': 'all current extracted source bytes versus official ZIP, two exact applied diffs; not build/EXE or physics proof',
    'snapshot': {'path': str(snapshot_path), 'sha256': sha(snapshot_path)},
    'source_archive': {'path': str(archive_path), 'sha256': sha(archive_path)},
    'proposal': {'path': str(proposal_path), 'sha256': sha(proposal_path)},
    'classification': {'path': str(classification_path), 'sha256': sha(classification_path)},
    'current_missing_file_exclusion_checks': exclusion_checks,
    'helper_sha256': sha(Path(choice_pair_sources.__file__)),
    'source_roots': {role: str(path) for role, path in roots.items()}})
out = GOAL / ('native_pair_sources_' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.json')
with out.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps({'report': str(out), 'source_files_per_role': result['source_files_per_role'],
    'build_scope_missing': result['build_scope_missing'], 'current_source_bytes_reverified': True,
    'build_and_executable_binding_verified': False, 'core_ready': False}, ensure_ascii=False))
