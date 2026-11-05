"""Bind a native pair to primary build artifacts; never run or package it."""
from pathlib import Path
import os
import re

from choice_pair_metadata import FILES, cache_entries, compare_metadata
from choice_pair_sources import source_tree, verify_sources
from choice_shared_stop_policy import POLICY as STOP_INDEX_POLICY, shared_stop_patch

POLICY = Path('06_研究結果/jdrt/goal_20261017/audit_history/native_pair_policy_20261020/policy.json')
TOOLS = {'cmake': 'CMAKE_COMMAND', 'compiler_c': 'CMAKE_C_COMPILER',
         'compiler_cxx': 'CMAKE_CXX_COMPILER', 'make': 'CMAKE_MAKE_PROGRAM',
         'ar': 'CMAKE_AR', 'ld': 'CMAKE_LINKER', 'ranlib': 'CMAKE_RANLIB',
         'xerces_static': 'XercesC_LIBRARY_RELEASE', 'zlib_static': 'ZLIB_LIBRARY'}


def assert_pair_unchanged(pair):
    """Recheck file sets as well as bytes across the packaging copy window."""
    for root, expected in pair['tree_snapshots'].items():
        if source_tree(root) != expected:
            raise ValueError('Paired source/header file set or bytes changed during packaging')


def verify_pair(proof, project_root, track, read_json, sha, pe_imports):
    """Hash both roles and recompute source/metadata identity, never trust booleans.

    track retains each primary file's expected hash for packaging's before/after
    copy checks. This is artifact provenance, not a reproducible-build or physics test.
    """
    if not isinstance(proof.get('pair_evidence'), dict):
        raise ValueError('Paired primary build evidence required')
    evidence = set()
    def observed(item, preserve=True):
        path = track(item)
        if preserve:
            evidence.add(path)
        return path
    pair_path = observed(proof['pair_evidence'])
    pair = read_json(pair_path)
    if (pair.get('schema') != 'isolated_native_pair_v1' or set(pair.get('builds', {})) != {'control', 'patched'}
            or pair.get('source_commit') != proof.get('source_commit')):
        raise ValueError('Complete paired primary build schema required')
    policy_path = observed(pair['policy'])
    allowed_schema = {(Path(project_root) / POLICY).resolve(): 'approved_native_pair_policy_v1',
                      (Path(project_root) / STOP_INDEX_POLICY).resolve(): 'approved_native_pair_stop_index_policy_v1'}.get(policy_path)
    if allowed_schema is None:
        raise ValueError('Pair policy must be the reviewed project policy')
    policy = read_json(policy_path)
    if (policy.get('schema') != allowed_schema
            or policy.get('source_commit') != pair['source_commit']):
        raise ValueError('Approved pair policy commit/schema differs')
    additional_patches = (shared_stop_patch(policy, pair['source_commit'], project_root, observed, read_json, sha)
                          if allowed_schema == 'approved_native_pair_stop_index_policy_v1' else {})
    archive = observed(policy['archive'], preserve=False)
    prepared = read_json(observed(policy['preparation']))
    proposal = read_json(observed(policy['proposal']))
    native_patch = observed(policy['native_patch'])
    shared = policy['shared_patch']
    shared_patch = observed(shared)
    if (sha(native_patch) != proposal['patch_sha256']
            or prepared.get('source_commit') != pair['source_commit']):
        raise ValueError('Registered patch/source commit differs')
    roots, builds, values, dependencies, states, configure_commands, binary_ids = {}, {}, {}, {}, {}, {}, {}
    declared_roots = {}
    tree_snapshots = {}
    for role, entry in pair['builds'].items():
        state = read_json(observed(entry['state']))
        states[role] = state
        claim_key = 'patch_applied_sha256' if role == 'patched' else 'control_native_source_sha256'
        expected_key = 'proposed_sha256' if role == 'patched' else 'official_before_sha256'
        if state.get(claim_key) != proposal[expected_key]:
            raise ValueError('Build native source claim differs from registered role')
        commands = state.get('commands')
        if (state.get('schema') != 'isolated_native_build_v1'
                or state.get('status') != 'COMPILED_VERSION_CHECKED_NOT_SIMULATED'
                or not isinstance(commands, list) or not commands
                or any(not isinstance(c, dict) or type(c.get('exit_code')) is not int or c['exit_code'] != 0
                       or not isinstance(c.get('command'), list) or not c['command']
                       or any(not isinstance(a, str) for a in c['command']) for c in commands)):
            raise ValueError('Every paired build command must be terminal and successful')
        if additional_patches:
            if (state.get('role') != 'ISOLATED_STOP_INDEX_REPAIR_CANDIDATE_NOT_ADOPTED'
                    or state.get('base_role') != role or state.get('child_pid') is not None
                    or any(state.get(key) is not False for key in ('simulation_allowed',
                        'research_cli_switch_allowed', 'technical_ready', 'research_adoption_permitted'))
                    or [c.get('phase') for c in commands] != ['diagnostic_configure', 'diagnostic_sumo_build',
                        'sumo_diagnostic_imports', 'sumo_diagnostic_version',
                        'netconvert_diagnostic_imports', 'netconvert_diagnostic_version']):
                raise ValueError('Explicit repaired role and all six original build commands required')
        for c in commands:
            observed({'path': c['log'], 'sha256': c['log_sha256'], 'bytes': c['log_bytes']})
        configurations = [c['command'] for c in commands if '-S' in c['command'] and '-B' in c['command']]
        if len(configurations) != 1:
            raise ValueError('Unique paired configure command required')
        configure = configurations[0]
        declared_roots[role] = (configure[configure.index('-S') + 1], configure[configure.index('-B') + 1])
        source = Path(configure[configure.index('-S') + 1]).resolve()
        build = Path(configure[configure.index('-B') + 1]).resolve()
        if source == build or source != Path(prepared[role + '_source_root']).resolve():
            raise ValueError('Configured source differs from prepared role')
        roots[role], builds[role] = source, build
        if set(entry.get('metadata', {})) != set(FILES) or set(entry.get('tools', {})) != set(TOOLS):
            raise ValueError('All ten metadata and compiler/static-dependency files required')
        paths = {name: observed(ref) for name, ref in entry['metadata'].items()}
        if any(path != (build / name).resolve() for name, path in paths.items()):
            raise ValueError('Metadata is outside its declared configured build')
        values[role] = {name: path.read_text(encoding='utf-8') for name, path in paths.items()}
        cache = cache_entries(values[role]['CMakeCache.txt'])
        tools = {name: observed(ref, preserve=False) for name, ref in entry['tools'].items()}
        for name, key in TOOLS.items():
            if key not in cache or Path(cache[key][1]).resolve() != tools[name]:
                raise ValueError('Cache compiler/tool/static dependency does not bind primary file: ' + name)
        if (Path(cache.get('CMAKE_HOME_DIRECTORY', ('', ''))[1]).resolve() != source
                or Path(cache.get('CMAKE_CACHEFILE_DIR', ('', ''))[1]).resolve() != build
                or Path(configure[0]).resolve() != tools['cmake']):
            raise ValueError('Cache/configure source/build/cmake path differs')
        normalized = list(configure)
        normalized[normalized.index('-S') + 1] = '<SOURCE>'
        normalized[normalized.index('-B') + 1] = '<BUILD>'
        configure_commands[role] = normalized
        combined = [c['command'] for c in commands if '--build' in c['command'] and '--target' in c['command']]
        if (len(combined) != 1 or Path(combined[0][0]).resolve() != tools['cmake']
                or Path(combined[0][combined[0].index('--build') + 1]).resolve() != build
                or combined[0][combined[0].index('--target') + 1:][:2] != ['sumo', 'netconvert']):
            raise ValueError('Combined native build command does not bind declared targets/build')
        header = observed(entry['version_header'])
        version = state.get('custom_version')
        if (not isinstance(version, str) or not version or header != (build / 'src/version.h').resolve()
                or not re.fullmatch(rb'#define VERSION_STRING "' + re.escape(version.encode()) + rb'"\r?\n?', header.read_bytes())):
            raise ValueError('Generated version header does not bind this build')
        binaries = state.get('binaries', [])
        if len(binaries) != 2:
            raise ValueError('Both native targets required in terminal build state')
        binary_ids[role] = {}
        for name in ('sumo', 'netconvert'):
            expected = (build / 'src' / (name + '.exe')).resolve()
            matches = [item for item in binaries if Path(item['path']).resolve() == expected]
            if len(matches) != 1:
                raise ValueError('Terminal executable is not the declared build target')
            item = matches[0]
            actual = observed(item, preserve=False)
            versions = [c for c in commands if c['command'] == [str(item['path']), '--version']]
            if additional_patches:
                if len(versions) != 1 or versions[0]['phase'] != name + '_diagnostic_version':
                    raise ValueError('Original version command is not bound to the repaired target')
                version_ref = {'path': versions[0]['log'], 'sha256': versions[0]['log_sha256'],
                               'bytes': versions[0]['log_bytes']}
            else:
                if type(item.get('clean_path_version_exit_code')) is not int or item['clean_path_version_exit_code'] != 0:
                    raise ValueError('Native version invocation failed')
                if (len(versions) != 1 or Path(versions[0]['log']).resolve() != Path(item['version_log']).resolve()
                        or versions[0]['log_sha256'] != item['version_log_sha256']):
                    raise ValueError('Version log/command is not bound to the actual target executable')
                version_ref = {'path': item['version_log'], 'sha256': item['version_log_sha256']}
            log = observed(version_ref)
            if version not in log.read_text(encoding='utf-8'):
                raise ValueError('Version log differs from generated build identity')
            pe_imports(actual)
            binary_ids[role][str(actual)] = item['sha256']
        loader_path = observed(entry['loader'])
        loader = read_json(loader_path)
        loaded_builds = {Path(binary['path']).parent.parent.resolve() for binary in loader.get('binaries', [])}
        if (loaded_builds != {build}
                or ('build_directory' in loader and Path(loader['build_directory']).resolve() != build)
                or loader['state_sha256'] != sha(observed(entry['state']))
                or len(loader.get('binaries', [])) != 2):
            raise ValueError('Loader evidence is not bound to the terminal paired build')
        required_loader_files = {'build_state.snapshot.bin', *(name + suffix for name in ('sumo', 'netconvert')
                                 for suffix in ('_objdump.log', '_clean_version.stdout', '_clean_version.stderr'))}
        if set(loader.get('files_sha256', {})) != required_loader_files:
            raise ValueError('Complete loader primary logs and state snapshot required')
        for name, digest in loader['files_sha256'].items():
            if Path(name).name != name or name in ('.', '..'):
                raise ValueError('Unsafe loader evidence filename')
            observed({'path': loader_path.parent / name, 'sha256': digest})
        if (loader_path.parent / 'build_state.snapshot.bin').read_bytes() != observed(entry['state']).read_bytes():
            raise ValueError('Loader state snapshot differs from paired terminal state')
        system = (Path(os.environ['SystemRoot']) / 'System32').resolve()
        seen = set()
        for binary in loader['binaries']:
            path = Path(binary['path']).resolve()
            if (path in seen or binary_ids[role].get(str(path)) != binary['sha256']
                    or type(binary.get('clean_version_returncode')) is not int or binary['clean_version_returncode'] != 0):
                raise ValueError('Loader executable/version differs from paired binary')
            seen.add(path)
            name = path.stem
            if (version not in (loader_path.parent / (name + '_clean_version.stdout')).read_text(encoding='utf-8')
                    or (loader_path.parent / (name + '_clean_version.stderr')).read_bytes()):
                raise ValueError('Clean loader version logs differ from successful version identity')
            raw_imports, current = [], None
            for line in (loader_path.parent / (name + '_objdump.log')).read_text(encoding='utf-8').splitlines():
                match = re.search(r'DLL Name:\s*(\S+)', line)
                if match:
                    current = {'name': match[1], 'symbols': []}
                    raw_imports.append(current)
                elif current is not None:
                    match = re.fullmatch(r'\s*[0-9a-f]+\s+\d+\s+(\S+)\s*', line)
                    if match:
                        current['symbols'].append(match[1])
            imports = binary.get('imports', [])
            if (sorted(row['name'].lower() for row in imports) != pe_imports(path)
                    or [{'name': row['name'], 'symbols': row['symbols']} for row in imports] != raw_imports):
                raise ValueError('Loader import coverage differs from actual executable')
            for row in imports:
                if (type(row.get('system_only_load_error')) is not int or row['system_only_load_error'] != 0
                        or row.get('missing_symbols') != [] or not row.get('symbols')
                        or Path(row.get('loaded_module_path', '')).parent.resolve() != system):
                    raise ValueError('Loader system module/export evidence failed')
        headers = {}
        for label, key in [('xerces', 'XercesC_INCLUDE_DIR'), ('zlib', 'ZLIB_INCLUDE_DIR')]:
            include = Path(cache[key][1]).resolve(strict=True)
            tree = source_tree(include)
            tree_snapshots[str(include)] = tree
            extended = Path('\\\\?\\' + str(include)) if os.name == 'nt' else include
            for name, digest in tree.items():
                ref = entry['headers'].get(label + '/' + name)
                if not ref or not os.path.samefile(ref['path'], extended / name):
                    raise ValueError('Dependency header inventory does not bind include root')
                path = observed(ref, preserve=False)
                if sha(path) != digest:
                    raise ValueError('Header bytes changed during pair verification')
                headers[label + '/' + name] = digest
        if set(headers) != set(entry['headers']):
            raise ValueError('Missing/extra dependency header proof')
        dependencies[role] = {'tools': {name: sha(path) for name, path in tools.items()}, 'headers': headers}
        dirs = observed(entry['target_directories'])
        cmake = (source / 'src/utils/CMakeLists.txt').read_text(encoding='utf-8')
        if (dirs != (build / 'CMakeFiles/TargetDirectories.txt').resolve()
                or cache.get('CMAKE_DISABLE_FIND_PACKAGE_FOX', ('', ''))[1] != 'TRUE'
                or cache.get('CMAKE_GENERATOR') != ('INTERNAL', 'MinGW Makefiles')
                or '#define HAVE_FOX' in values[role]['src/config.h']
                or '/* #undef HAVE_FOX */' not in values[role]['src/config.h']
                or '/src/utils/tests/' in dirs.read_text().replace('\\', '/')
                or 'if (FOX_FOUND)\n    add_subdirectory(foxtools)\n    add_subdirectory(gui)\n    add_subdirectory(tests)\nendif ()' not in cmake):
            raise ValueError('Missing-file non-GUI exclusion no longer holds for current build')
    if roots['control'] == roots['patched'] or builds['control'] == builds['patched']:
        raise ValueError('Control/patched source and build roots must be distinct')
    if configure_commands['control'] != configure_commands['patched'] or dependencies['control'] != dependencies['patched']:
        raise ValueError('Paired configure arguments/compiler/static dependencies differ')
    compared = compare_metadata(values['patched'], values['control'],
                                declared_roots['patched'], declared_roots['control'])
    if not compared['equal']:
        raise ValueError('Paired build metadata differs: ' + repr(compared['different_files']))
    patches = {proposal['target']: {'path': str(native_patch), 'sha256': proposal['patch_sha256'],
        'before_sha256': proposal['official_before_sha256'], 'after_sha256': proposal['proposed_sha256'],
        'roles': ['patched']}, 'src/CMakeLists.txt': {**shared, 'path': str(shared_patch), 'roles': ['control', 'patched']}}
    if patches.keys() & additional_patches.keys():
        raise ValueError('Shared stop-history repair overlaps an existing patch target')
    patches.update(additional_patches)
    sources = verify_sources(archive, pair['source_commit'], roots, prepared['source_sha256'],
                             patches, policy['allowed_missing'])
    tree_snapshots.update({str(roots[role]): tree for role, tree in sources['source_sha256'].items()})
    # Preserve every primary hash across the packager's validation/copy window.
    for role, tree in sources['source_sha256'].items():
        root = Path('\\\\?\\' + str(roots[role])) if os.name == 'nt' else roots[role]
        for name, digest in tree.items():
            observed({'path': root / name, 'sha256': digest}, preserve=False)
    role = proof.get('role')
    selected = {str(Path(item['path']).resolve()): item['sha256'] for item in proof.get('binaries', [])}
    if role not in states or states[role] != proof.get('state') or selected != binary_ids[role]:
        raise ValueError('Selected native provenance differs from its actual paired build')
    return {'pair_path': pair_path, 'policy_path': policy_path, 'evidence_files': sorted(evidence),
            'tree_snapshots': tree_snapshots,
            'source_files_per_role': sources['source_files_per_role'], 'metadata_pairs': len(FILES),
            'dependency_tools': len(TOOLS), 'dependency_headers': len(dependencies['control']['headers']),
            'selected_role': role, 'native_behavior_verified': False, 'core_ready': False}
