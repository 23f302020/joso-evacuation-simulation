"""Capture/recompute native pair primary files; no bundle, compiler or simulation."""
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
GOAL = Path(__file__).parent
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
from choice_package_toolchain import checked, read_json, sha, pe_imports
from choice_pair_metadata import FILES, cache_entries
from choice_pair_sources import source_tree
from choice_pair_proof import POLICY, TOOLS, verify_pair

ST = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
OUT = GOAL / 'audit_history' / ('native_pair_primary_' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
OUT.mkdir()
HELPERS = [ROOT / '.agents/skills/joso-jdrt-runner/scripts' / name for name in (
    'choice_package_toolchain.py', 'choice_pair_proof.py', 'choice_pair_sources.py', 'choice_pair_metadata.py')]
helper_sources = {str(path): sha(path) for path in HELPERS}


def item(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def save(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


try:
    state_paths = {'patched': ST / 'attempt08_20261020/build_state.json',
                   'control': ST / 'control02_20261020/build_state.json'}
    states = {role: read_json(path) for role, path in state_paths.items()}
    prepared_path = ST / 'control_source_preparation_20261020.json'
    prepared = read_json(prepared_path)
    proposal_path = GOAL / 'audit_history/walk_native_proposal_20261019/proposal_manifest.json'
    proposal = read_json(checked({'path': proposal_path, 'sha256': prepared['registered_proposal_sha256']}))
    archive = checked({'path': ST / ('downloads/sumo-' + prepared['source_commit'] + '.zip'),
                       'sha256': prepared['archive_sha256']})
    shared = states['patched']['cmake_link_repair']
    if shared != states['control']['cmake_link_repair']:
        raise ValueError('Shared repair identity differs')
    policy = {'schema': 'approved_native_pair_policy_v1', 'source_commit': prepared['source_commit'],
        'archive': item(archive), 'preparation': item(prepared_path), 'proposal': item(proposal_path),
        'native_patch': item(GOAL / 'audit_history/walk_native_proposal_20261019/preserve_aborted_walk_raw_lateral.patch'),
        'shared_patch': {**item(ST / 'attempt07_20261020/cmake_link.patch'),
                         'before_sha256': shared['before_sha256'], 'after_sha256': shared['after_sha256']},
        'allowed_missing': read_json(GOAL / 'native_source_missing_files_classification_20261020.json')['missing'],
        'scope': 'Same compiler/static dependencies/settings; registered native diff and shared Winsock CMake link repair only. Seven disclosed GUI/Debian-test omissions. No native correctness or READY claim.'}
    if (policy['native_patch']['sha256'] != proposal['patch_sha256']
            or policy['shared_patch']['sha256'] != shared['patch_sha256']):
        raise ValueError('Approved patch bytes changed')
    policy_path = ROOT / POLICY
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    if policy_path.exists():
        if read_json(policy_path) != policy:
            raise ValueError('Preserve existing policy; content differs')
    else:
        save(policy_path, policy)
    pair = {'schema': 'isolated_native_pair_v1', 'source_commit': prepared['source_commit'],
            'policy': item(policy_path), 'builds': {}}
    loaders = {'patched': GOAL / 'audit_history/native_loader_20261020T143548809307/diagnosis.json',
               'control': GOAL / 'audit_history/native_loader_20261020T145653495598/diagnosis.json'}
    for role, state in states.items():
        configure = [c['command'] for c in state['commands'] if '-S' in c['command'] and '-B' in c['command']]
        if len(configure) != 1:
            raise ValueError('Unique configure required')
        build = Path(configure[0][configure[0].index('-B') + 1])
        cache = cache_entries((build / 'CMakeCache.txt').read_text())
        headers = {}
        for label, key in [('xerces', 'XercesC_INCLUDE_DIR'), ('zlib', 'ZLIB_INCLUDE_DIR')]:
            include = Path(cache[key][1])
            for name in source_tree(include):
                headers[label + '/' + name] = item(include / name)
        pair['builds'][role] = {'state': item(state_paths[role]),
            'metadata': {name: item(build / name) for name in FILES},
            'tools': {name: item(cache[key][1]) for name, key in TOOLS.items()},
            'headers': headers, 'version_header': item(build / 'src/version.h'),
            'target_directories': item(build / 'CMakeFiles/TargetDirectories.txt'),
            'loader': item(loaders[role])}
    pair_path = OUT / 'pair.json'
    save(pair_path, pair)
    inventory = ST / 'attempt04_20261020/official_python_tools_inventory.json'
    proofs = {}
    for role, state in states.items():
        evidence = [item(policy_path), item(pair_path), item(prepared_path), item(proposal_path),
                    item(archive), item(inventory), policy['native_patch'], policy['shared_patch'],
                    pair['builds'][role]['state'], pair['builds'][role]['version_header'],
                    pair['builds'][role]['target_directories'],
                    *pair['builds'][role]['metadata'].values(), *pair['builds'][role]['tools'].values()]
        proofs[role] = {'schema': 'isolated_native_provenance_v1', 'role': role,
            'source_commit': prepared['source_commit'], 'custom_version': state['custom_version'],
            'state': state, 'files': evidence,
            'binaries': [{**entry, 'pe_imports': pe_imports(entry['path'])} for entry in state['binaries']],
            'pair_evidence': item(pair_path), 'simulation_executed': False, 'research_cli_switched': False,
            'source_scope': policy['scope']}
        save(OUT / (role + '_provenance.json'), proofs[role])
    validated = {}
    def track(ref):
        path = checked(ref)
        if path in validated and validated[path] != ref['sha256']:
            raise ValueError('Conflicting observed file hashes')
        validated[path] = ref['sha256']
        return path
    result = verify_pair(proofs['patched'], ROOT, track, read_json, sha, pe_imports)
    if any(sha(path) != expected for path, expected in validated.items()):
        raise ValueError('Primary evidence changed during verification')
    if any(sha(Path(path)) != expected for path, expected in helper_sources.items()):
        raise ValueError('Verification helpers changed while auditing primary files')
    result = {key: ([str(path) for path in value] if key == 'evidence_files' else str(value)
                    if isinstance(value, Path) else value) for key, value in result.items()}
    result.update(at_jst=datetime.now().astimezone().isoformat(), verified_primary_files=len(validated),
                  helper_sources_sha256=helper_sources,
                  verifier_sha256=sha(Path(sys.modules['choice_pair_proof'].__file__)),
                  simulation_executed=False, bundle_created=False, packager_integrated=False)
    save(OUT / 'verification.json', result)
    print(json.dumps({'out': str(OUT), **{key: result[key] for key in ('source_files_per_role',
        'metadata_pairs', 'dependency_tools', 'dependency_headers', 'verified_primary_files',
        'native_behavior_verified', 'core_ready')}}, ensure_ascii=False))
except BaseException as error:
    save(OUT / 'FAILED_PRESERVED.json', {'error': repr(error), 'simulation_executed': False,
         'bundle_created': False, 'core_ready': False})
    print(str(OUT))
    raise
