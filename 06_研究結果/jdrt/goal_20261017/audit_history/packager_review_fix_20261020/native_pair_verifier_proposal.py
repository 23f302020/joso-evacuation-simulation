"""DRAFT ONLY: not integrated, not validated; no packaging permission."""
def verify_pair(proof, project_root, track):
    """Recompute paired source/build identity from primary files, never booleans."""
    reference = proof.get('pair_evidence')
    if not isinstance(reference, dict):
        raise ValueError('Paired primary build evidence required')
    pair_path = track(reference)
    pair = read_json(pair_path)
    registered_path = Path(project_root) / '06_研究結果/jdrt/goal_20261017/audit_history/walk_native_proposal_20261019/proposal_manifest.json'
    registered = read_json(registered_path)
    if (pair.get('schema') != 'isolated_native_pair_v1' or pair.get('source_commit') != proof.get('source_commit')
            or set(pair.get('builds', {})) != {'control', 'patched'}):
        raise ValueError('Invalid paired primary build schema')
    patch_path = track(pair['patch'])
    if sha(patch_path) != registered['patch_sha256']:
        raise ValueError('Pair patch differs from registered patch')
    native = registered['target']
    if native != 'src/microsim/transportables/MSPModel_Striping.cpp':
        raise ValueError('Unexpected registered native source')
    trees, metadata, dependencies = {}, {}, {}
    roles = pair['builds']
    for role, build in roles.items():
        source_root = Path(build['source_root']).resolve(strict=True)
        build_root = Path(build['build_root']).resolve(strict=True)
        if not source_root.is_dir() or not build_root.is_dir() or source_root == build_root:
            raise ValueError('Distinct source/build directories required')
        tree = {}
        for path in source_root.rglob('*'):
            if path.is_symlink() or path.is_junction():
                raise ValueError('Pair source tree contains a link')
            if path.is_file():
                name = path.relative_to(source_root).as_posix()
                tree[name] = sha(track({'path': path, 'sha256': sha(regular(path))}))
        expected = registered['official_before_sha256' if role == 'control' else 'proposed_sha256']
        if tree.get(native) != expected:
            raise ValueError('Pair native source differs from registered role')
        trees[role] = tree
        files = build['files']
        required = {'cmake', 'compiler_c', 'compiler_cxx', 'xerces_static', 'zlib_static', 'zlib_h', 'zconf_h',
                    'cache', 'config', 'sumo_flags', 'sumo_link', 'sumo_link_libs',
                    'netconvert_flags', 'netconvert_link', 'netconvert_link_libs'}
        if set(files) != required:
            raise ValueError('Incomplete paired compiler/dependency/configuration files')
        paths = {name: track(item) for name, item in files.items()}
        dependencies[role] = {name: sha(paths[name]) for name in
                              ('cmake', 'compiler_c', 'compiler_cxx', 'xerces_static', 'zlib_static', 'zlib_h', 'zconf_h')}
        expected_paths = {'cache': 'CMakeCache.txt', 'config': 'src/config.h'}
        for target in ('sumo', 'netconvert'):
            for label, filename in (('flags', 'flags.make'), ('link', 'link.txt'), ('link_libs', 'linkLibs.rsp')):
                expected_paths[target + '_' + label] = 'src/CMakeFiles/' + target + '.dir/' + filename
        if any(paths[key] != (build_root / name).resolve() for key, name in expected_paths.items()):
            raise ValueError('Pair metadata is not from the declared build directory')

        def normalized(text):
            for supplied, resolved, token in ((build['source_root'], source_root, '<SOURCE>'),
                                               (build['build_root'], build_root, '<BUILD>')):
                for value in sorted({str(supplied), str(resolved)}, key=len, reverse=True):
                    for spelling in {value.replace('\\', '/'), value.replace('/', '\\')}:
                        text = re.sub(re.escape(spelling), lambda match: token, text, flags=re.I)
            return text.replace('\r\n', '\n')

        metadata[role] = {key: normalized(paths[key].read_text(encoding='utf-8')) for key in expected_paths}
        cache = {}
        for line in paths['cache'].read_text(encoding='utf-8').splitlines():
            if line and not line.startswith(('#', '//')) and ':' in line and '=' in line:
                key, value = line.split('=', 1)
                cache[key.split(':', 1)[0]] = value
        for key, expected_path in (('CMAKE_HOME_DIRECTORY', source_root), ('CMAKE_CACHEFILE_DIR', build_root),
                                   ('CMAKE_C_COMPILER', paths['compiler_c']), ('CMAKE_CXX_COMPILER', paths['compiler_cxx'])):
            if Path(cache.get(key, '')).resolve() != expected_path:
                raise ValueError('Pair cache source/build/compiler differs from primary files')
        state = read_json(track(build['state']))
        if (state.get('schema') != 'isolated_native_build_v1'
                or state.get('status') != 'COMPILED_VERSION_CHECKED_NOT_SIMULATED'
                or not state.get('commands') or any(type(c.get('exit_code')) is not int or c['exit_code'] != 0
                                                   for c in state['commands'])):
            raise ValueError('Paired build state is not wholly successful')
        commands = [c['command'] for c in state['commands']]
        if not any('--build' in c and Path(c[c.index('--build') + 1]).resolve() == build_root
                   and '--target' in c and {'sumo', 'netconvert'} <= set(c) for c in commands):
            raise ValueError('Pair build command does not select both declared targets')
        if not any('-S' in c and Path(c[c.index('-S') + 1]).resolve() == source_root
                   and '-B' in c and Path(c[c.index('-B') + 1]).resolve() == build_root for c in commands):
            raise ValueError('Pair configure command does not select declared roots')
        binaries = build['binaries']
        if set(binaries) != {'sumo', 'netconvert'}:
            raise ValueError('Both paired native binaries required')
        checked_binaries = {name: track(item) for name, item in binaries.items()}
        if any(path != (build_root / 'src' / (name + '.exe')).resolve() for name, path in checked_binaries.items()):
            raise ValueError('Paired executable is outside its declared target')
        observed = {str(Path(item['path']).resolve()): item['sha256'] for item in state.get('binaries', [])}
        if len(observed) != 2 or any(observed.get(str(path)) != sha(path) for path in checked_binaries.values()):
            raise ValueError('Paired executable differs from terminal build state')
        for command in state['commands']:
            track({'path': command['log'], 'sha256': command['log_sha256'], 'bytes': command['log_bytes']})
        if role == proof['role']:
            selected = {str(Path(item['path']).resolve()): item['sha256'] for item in proof['binaries']}
            if state != proof['state'] or selected != observed:
                raise ValueError('Selected provenance differs from its paired build')
    if set(trees['control']) != set(trees['patched']):
        raise ValueError('Paired source trees have different file sets')
    if {name for name in trees['control'] if trees['control'][name] != trees['patched'][name]} != {native}:
        raise ValueError('Paired source differences exceed the registered native patch')
    if dependencies['control'] != dependencies['patched'] or metadata['control'] != metadata['patched']:
        raise ValueError('Paired compiler/dependency/configuration/flags/link contents differ')
    return pair_path


