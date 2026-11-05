"""Artificial paired primary files; no compiler, native process or core."""
import copy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / '.agents/skills/joso-jdrt-runner/scripts'
sys.path.insert(0, str(SCRIPTS))
import choice_pair_proof as target
import choice_pair_metadata as metadata
import choice_package_toolchain as io

POLICY = '06_研究結果/jdrt/goal_20261017/audit_history/native_pair_policy_20261020/policy.json'


class PairContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commit = 'a' * 40
        self.validated = {}
        self.deps = self.root / 'deps'
        self.cache_tools = {'cmake': 'CMAKE_COMMAND', 'compiler_c': 'CMAKE_C_COMPILER',
            'compiler_cxx': 'CMAKE_CXX_COMPILER', 'make': 'CMAKE_MAKE_PROGRAM',
            'ar': 'CMAKE_AR', 'ld': 'CMAKE_LINKER', 'ranlib': 'CMAKE_RANLIB',
            'xerces_static': 'XercesC_LIBRARY_RELEASE', 'zlib_static': 'ZLIB_LIBRARY'}
        tool_names = {'cmake': 'cmake.exe', 'compiler_c': 'gcc.exe', 'compiler_cxx': 'g++.exe',
                      'make': 'make.exe', 'ar': 'ar.exe', 'ld': 'ld.exe', 'ranlib': 'ranlib.exe',
                      'xerces_static': 'libxerces-c.a', 'zlib_static': 'libz.a'}
        tools = {key: self.put(self.deps / tool_names[key], key.encode()) for key in self.cache_tools}
        for name in ('xerces', 'zlib'):
            self.put(self.deps / name / 'include/header.h', (name + ' header').encode())
        original = {'CMakeLists.txt': b'project(fake)\n', 'src/native.cpp': b'old\n',
                    'src/CMakeLists.txt': b'link_old\n', 'src/utils/CMakeLists.txt':
                    b'if (FOX_FOUND)\n    add_subdirectory(foxtools)\n    add_subdirectory(gui)\n    add_subdirectory(tests)\nendif ()\n'}
        self.archive = self.root / ('sumo-' + self.commit + '.zip')
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, raw in original.items(): z.writestr('sumo-' + self.commit + '/' + name, raw)
        self.proposal = {'target': 'src/native.cpp', 'official_before_sha256': self.digest(b'old\n'),
                         'proposed_sha256': self.digest(b'new\n')}
        patch_refs = {}
        for name, after in [('src/native.cpp', b'new\n'), ('src/CMakeLists.txt', b'link_new\n')]:
            diff = ''.join(difflib.unified_diff(original[name].decode().splitlines(True),
                after.decode().splitlines(True), fromfile='a/' + name, tofile='b/' + name)).encode()
            patch_refs[name] = self.put(self.root / (Path(name).name + '.patch'), diff)
        self.proposal['patch_sha256'] = patch_refs['src/native.cpp']['sha256']
        self.proposal['patch'] = patch_refs['src/native.cpp']
        self.proposal_path = self.root / 'proposal.json'
        self.save(self.proposal_path, self.proposal)
        self.prepared = {'source_sha256': {}, 'source_commit': self.commit}
        self.pair = {'schema': 'isolated_native_pair_v1', 'source_commit': self.commit, 'builds': {}}
        self.states = {}
        for role in ('control', 'patched'):
            source, build = self.root / role / 'source', self.root / role / 'build'
            self.prepared[role + '_source_root'] = str(source)
            self.prepared['source_sha256'][role] = {}
            for name, raw in original.items():
                if name == 'src/native.cpp' and role == 'patched': raw = b'new\n'
                if name == 'src/CMakeLists.txt': raw = b'link_new\n'
                self.prepared['source_sha256'][role][name] = self.put(source / name, raw)['sha256']
            cache = ''.join(key + ':FILEPATH=' + tools[name]['path'].replace('\\', '/') + '\n'
                            for name, key in self.cache_tools.items())
            cache += ('CMAKE_HOME_DIRECTORY:INTERNAL=' + source.as_posix() + '\n'
                'CMAKE_CACHEFILE_DIR:INTERNAL=' + build.as_posix() + '\n'
                'ENABLE_PYTHON_BINDINGS:BOOL=OFF\nCMAKE_GENERATOR:INTERNAL=MinGW Makefiles\n'
                'CMAKE_DISABLE_FIND_PACKAGE_FOX:UNINITIALIZED=TRUE\n'
                'XercesC_INCLUDE_DIR:PATH=' + (self.deps / 'xerces/include').as_posix() + '\n'
                'ZLIB_INCLUDE_DIR:PATH=' + (self.deps / 'zlib/include').as_posix() + '\n')
            files = {name: self.put(build / name, cache.encode() if name == 'CMakeCache.txt' else
                     b'/* #undef HAVE_FOX */\n' if name == 'src/config.h' else b'unchanged flags/link\n')
                     for name in metadata.FILES}
            version = 'fake-version-' + role
            header = self.put(build / 'src/version.h', ('#define VERSION_STRING "' + version + '"\n').encode())
            dirs = self.put(build / 'CMakeFiles/TargetDirectories.txt', b'non-GUI selected targets\n')
            commands, binaries = [], []
            for phase, command in [('configure', [tools['cmake']['path'], '-S', str(source), '-B', str(build), '-DFAKE=ON']),
                ('build', [tools['cmake']['path'], '--build', str(build), '--target', 'sumo', 'netconvert'])]:
                log = self.put(build / (phase + '.log'), (phase + ' done').encode())
                commands.append({'command': command, 'exit_code': 0, 'log': log['path'],
                                 'log_sha256': log['sha256'], 'log_bytes': log['bytes']})
            for name in ('sumo', 'netconvert'):
                binary = self.put(build / ('src/' + name + '.exe'), (role + name).encode())
                log = self.put(build / (name + '_version.log'), version.encode())
                binaries.append({**binary, 'version_log': log['path'], 'version_log_sha256': log['sha256'],
                                 'clean_path_version_exit_code': 0})
                commands.append({'command': [binary['path'], '--version'], 'exit_code': 0,
                    'log': log['path'], 'log_sha256': log['sha256'], 'log_bytes': log['bytes']})
            self.states[role] = {'schema': 'isolated_native_build_v1',
                'status': 'COMPILED_VERSION_CHECKED_NOT_SIMULATED', 'custom_version': version,
                'patch_applied_sha256': self.proposal['proposed_sha256'],
                'control_native_source_sha256': self.proposal['official_before_sha256'],
                'zlib_dependency': {'files': [tools['zlib_static']]},
                'commands': commands, 'binaries': binaries}
            state_path = build / 'state.json'
            self.save(state_path, self.states[role])
            loader = {'build_directory': str(build), 'state_sha256': self.item(state_path)['sha256'],
                'binaries': [{**b, 'clean_version_returncode': 0, 'imports': [{'name': 'kernel32.dll',
                    'symbols': ['ArtificialSymbol'], 'missing_symbols': [], 'system_only_load_error': 0,
                    'loaded_module_path': str(Path(os.environ['SystemRoot']) / 'System32/kernel32.dll')}]} for b in binaries],
                'files_sha256': {}}
            self.put(build / 'build_state.snapshot.bin', state_path.read_bytes())
            for name in ('sumo', 'netconvert'):
                self.put(build / (name + '_clean_version.stdout'), version.encode())
                self.put(build / (name + '_clean_version.stderr'), b'')
                self.put(build / (name + '_objdump.log'), b'DLL Name: kernel32.dll\n 123 1 ArtificialSymbol\n')
            loader['files_sha256'] = {p.name: self.item(p)['sha256'] for p in build.iterdir()
                if p.name.endswith(('.stdout', '.stderr', '_objdump.log', '.snapshot.bin'))}
            loader_path = build / 'loader.json'
            self.save(loader_path, loader)
            headers = {name + '/header.h': self.item(self.deps / name / 'include/header.h')
                       for name in ('xerces', 'zlib')}
            self.pair['builds'][role] = {'state': self.item(state_path), 'metadata': files,
                'tools': copy.deepcopy(tools), 'headers': headers, 'version_header': header,
                'target_directories': dirs, 'loader': self.item(loader_path)}
        self.snapshot_path = self.root / 'preparation.json'
        self.save(self.snapshot_path, self.prepared)
        self.policy = {'schema': 'approved_native_pair_policy_v1', 'source_commit': self.commit,
            'archive': self.item(self.archive), 'preparation': self.item(self.snapshot_path),
            'proposal': self.item(self.proposal_path), 'native_patch': patch_refs['src/native.cpp'],
            'shared_patch': {**patch_refs['src/CMakeLists.txt'], 'before_sha256': self.digest(b'link_old\n'),
                             'after_sha256': self.digest(b'link_new\n')}, 'allowed_missing': []}
        self.policy_path = self.root / POLICY
        self.save(self.policy_path, self.policy)
        self.pair['policy'] = self.item(self.policy_path)
        self.pair_path = self.root / 'pair.json'
        self.selected = 'patched'

    def digest(self, data): return hashlib.sha256(data).hexdigest()
    def item(self, path): return {'path': str(path), 'sha256': self.digest(path.read_bytes()), 'bytes': path.stat().st_size}
    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.item(path)
    def save(self, path, data): self.put(path, json.dumps(data).encode())
    def update_state(self, role):
        path = Path(self.pair['builds'][role]['state']['path'])
        self.save(path, self.states[role])
        self.pair['builds'][role]['state'] = self.item(path)
        loader_path = Path(self.pair['builds'][role]['loader']['path'])
        loader = json.loads(loader_path.read_bytes())
        loader['state_sha256'] = self.item(path)['sha256']
        snapshot = loader_path.parent / 'build_state.snapshot.bin'
        snapshot.write_bytes(path.read_bytes())
        loader['files_sha256'][snapshot.name] = self.item(snapshot)['sha256']
        self.save(loader_path, loader)
        self.pair['builds'][role]['loader'] = self.item(loader_path)
    def verify(self):
        self.save(self.pair_path, self.pair)
        proof = {'role': self.selected, 'source_commit': self.commit,
                 'pair_evidence': self.item(self.pair_path), 'state': self.states[self.selected],
                 'binaries': self.states[self.selected]['binaries']}
        def track(item):
            p = io.checked(item); self.validated[p] = item['sha256']; return p
        return target.verify_pair(proof, self.root, track, io.read_json, io.sha, lambda p: ['kernel32.dll'])

    def test_valid_pair_both_selected_roles(self):
        for role in ('control', 'patched'):
            self.selected = role
            self.assertFalse(self.verify()['native_behavior_verified'])

    def test_missing_pair_evidence_rejected(self):
        with self.assertRaises(ValueError):
            target.verify_pair({}, self.root, io.checked, io.read_json, io.sha, lambda p: [])

    def test_partner_binary_replaced_even_with_fresh_state_hash_rejected(self):
        item = self.states['control']['binaries'][0]
        replacement = self.put(self.root / 'unrelated/sumo.exe', b'unrelated')
        item.update(replacement)
        self.update_state('control')
        with self.assertRaises(ValueError): self.verify()

    def test_metadata_outside_declared_build_rejected(self):
        self.pair['builds']['control']['metadata']['src/config.h'] = self.put(self.root / 'foreign/config.h', b'/* #undef HAVE_FOX */\n')
        with self.assertRaises(ValueError): self.verify()

    def test_flags_cache_and_link_difference_not_hidden_by_true_booleans(self):
        for name in ('src/CMakeFiles/sumo.dir/flags.make', 'src/CMakeFiles/sumo.dir/linkLibs.rsp', 'CMakeCache.txt'):
            item = self.pair['builds']['control']['metadata'][name]
            p = Path(item['path']); before = p.read_bytes()
            self.pair['builds']['control']['metadata'][name] = self.put(p, before + b'EXTRA:STRING=changed\n')
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify()
            self.pair['builds']['control']['metadata'][name] = self.put(p, before)

    def test_compiler_or_static_dependency_swapped_rejected(self):
        for name in ('compiler_cxx', 'zlib_static'):
            old = self.pair['builds']['control']['tools'][name]
            self.pair['builds']['control']['tools'][name] = self.put(self.root / ('foreign/' + name), b'foreign')
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify()
            self.pair['builds']['control']['tools'][name] = old

    def test_configure_roots_or_flags_and_failed_command_rejected(self):
        original = copy.deepcopy(self.states['control'])
        for kind in ('source_root', 'flags', 'failed'):
            self.states['control'] = copy.deepcopy(original)
            if kind == 'source_root': self.states['control']['commands'][0]['command'][2] = str(self.root / 'foreign')
            elif kind == 'flags': self.states['control']['commands'][0]['command'][-1] = '-DFAKE=OFF'
            else: self.states['control']['commands'][-1]['exit_code'] = 1
            self.update_state('control')
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.verify()

    def test_version_header_or_version_command_binding_rejected(self):
        self.states['control']['commands'][-1]['command'][0] = str(self.root / 'foreign.exe')
        self.update_state('control')
        with self.assertRaises(ValueError): self.verify()

    def test_missing_system_export_or_foreign_loader_path_rejected(self):
        entry = self.pair['builds']['control']
        path = Path(entry['loader']['path'])
        original = json.loads(path.read_bytes())
        for kind in ('missing_symbol', 'foreign_path', 'omitted_import'):
            loader = copy.deepcopy(original)
            if kind == 'missing_symbol': loader['binaries'][0]['imports'][0]['missing_symbols'] = ['ArtificialSymbol']
            elif kind == 'foreign_path': loader['binaries'][0]['imports'][0]['loaded_module_path'] = str(self.root / 'kernel32.dll')
            else: loader['binaries'][0]['imports'] = []
            self.save(path, loader); entry['loader'] = self.item(path)
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.verify()

    def test_loader_primary_files_and_symbol_coverage_required(self):
        entry = self.pair['builds']['control']
        path = Path(entry['loader']['path']); original = json.loads(path.read_bytes())
        for kind in ('missing_raw', 'extra_symbol'):
            loader = copy.deepcopy(original)
            if kind == 'missing_raw': loader['files_sha256'].pop('sumo_objdump.log')
            else: loader['binaries'][0]['imports'][0]['symbols'] = ['ForgedSymbol']
            self.save(path, loader); entry['loader'] = self.item(path)
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.verify()

    def test_loader_root_derived_from_both_bound_executables_when_old_field_absent(self):
        entry = self.pair['builds']['patched']; path = Path(entry['loader']['path'])
        loader = json.loads(path.read_bytes()); loader.pop('build_directory')
        self.save(path, loader); entry['loader'] = self.item(path)
        self.assertFalse(self.verify()['native_behavior_verified'])

    def packaging_inputs(self):
        from test_choice_package_toolchain import fake_pe
        contents = {'tools/traci/__init__.py': b'from . import _vehicle\n',
            'tools/traci/_vehicle.py': b'value=1\n', 'tools/sumolib/__init__.py': b'value=1\n',
            'AUTHORS': b'authors', 'LICENSE': b'license', 'NOTICE.md': b'notice'}
        inventory = []
        with zipfile.ZipFile(self.archive, 'a') as archive:
            for name, raw in contents.items():
                archive.writestr('sumo-' + self.commit + '/' + name, raw)
                for role in self.states:
                    source = Path(self.prepared[role + '_source_root'])
                    self.prepared['source_sha256'][role][name] = self.put(source / name, raw)['sha256']
                inventory.append({'relative_path': name, 'bytes': len(raw),
                    'archive_sha256': self.digest(raw), 'source_sha256': self.digest(raw)})
        self.save(self.snapshot_path, self.prepared)
        self.policy.update(archive=self.item(self.archive), preparation=self.item(self.snapshot_path))
        self.save(self.policy_path, self.policy); self.pair['policy'] = self.item(self.policy_path)
        tools = Path(self.prepared['control_source_root']) / 'tools'
        inventory_path = self.root / 'inventory.json'
        self.save(inventory_path, {'schema': 'official_python_tools_inventory_v1',
            'source_root': str(tools.parent), 'source_commit': self.commit, 'files': inventory,
            'all_official_bytes_match': True, 'missing': [], 'mismatched': [], 'extra_package_files': []})
        for role, state in self.states.items():
            for binary in state['binaries']:
                binary.update(self.put(Path(binary['path']), fake_pe()))
            self.update_state(role)
            loader_path = Path(self.pair['builds'][role]['loader']['path'])
            loader = json.loads(loader_path.read_bytes())
            for row, binary in zip(loader['binaries'], state['binaries']): row.update(binary)
            self.save(loader_path, loader); self.pair['builds'][role]['loader'] = self.item(loader_path)
        self.save(self.pair_path, self.pair)
        role = self.selected; entry = self.pair['builds'][role]; state = self.states[role]
        files = [self.item(inventory_path), self.item(self.archive), entry['version_header'],
                 *entry['metadata'].values(), *entry['tools'].values()]
        proof = {'schema': 'isolated_native_provenance_v1', 'role': role, 'source_commit': self.commit,
            'custom_version': state['custom_version'], 'source_scope': 'artificial contract test only',
            'simulation_executed': False, 'research_cli_switched': False, 'pair_evidence': self.item(self.pair_path),
            'state': state, 'files': files,
            'source_comparison': {'untrusted_boolean': True}, 'patched_control_comparison': {
                'configure_equal_except_source_build_paths': True, 'zlib_dependency_identical': True,
                'flags': {name: {'compiler_defines_and_flags_equal': True, 'link_command_equal': True}
                          for name in ('sumo', 'netconvert')}},
            'binaries': [{**row, 'pe_imports': ['kernel32.dll']} for row in state['binaries']]}
        proof_path = self.root / 'native_provenance.json'; self.save(proof_path, proof)
        binaries = {Path(b['path']).stem: Path(b['path']) for b in state['binaries']}
        return (tools, binaries['sumo'], binaries['netconvert'], proof_path, inventory_path,
                self.root / '04_プログラム/output/sumo/toolchains/new', self.root)

    def test_packager_uses_pair_verifier_and_preserves_primary_receipts(self):
        args = self.packaging_inputs()
        manifest = io.package(*args)
        self.assertTrue((manifest.parent / 'evidence/native_pair.json').is_file())
        self.assertTrue((manifest.parent / 'evidence/native_pair_policy.json').is_file())

    def test_packager_rejects_partner_metadata_change_before_destination(self):
        args = self.packaging_inputs()
        entry = self.pair['builds']['control']['metadata']['src/config.h']
        Path(entry['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError): io.package(*args)
        self.assertFalse(args[5].exists())

    def test_packager_preserves_failure_when_partner_source_changes_during_copy(self):
        args = self.packaging_inputs(); original = io.shutil.copyfile
        def change(source, destination):
            result = original(source, destination)
            if Path(source) == args[1]:
                (Path(self.prepared['control_source_root']) / 'src/native.cpp').write_bytes(b'changed')
            return result
        with patch.object(io.shutil, 'copyfile', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed'): io.package(*args)
        self.assertTrue((args[5] / 'FAILED.json').is_file())
        self.assertFalse((args[5] / 'toolchain.json').exists())

    def test_packager_rejects_new_partner_source_file_during_copy(self):
        args = self.packaging_inputs(); original = io.shutil.copyfile
        def change(source, destination):
            result = original(source, destination)
            if Path(source) == args[1]:
                (Path(self.prepared['control_source_root']) / 'extra.cpp').write_bytes(b'added')
            return result
        with patch.object(io.shutil, 'copyfile', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed'): io.package(*args)
        self.assertTrue((args[5] / 'FAILED.json').is_file())
        self.assertFalse((args[5] / 'toolchain.json').exists())

    def test_source_or_approved_policy_reference_cannot_be_silently_replaced(self):
        ref = self.pair['builds']['control']['state']
        Path(ref['path']).write_bytes(Path(ref['path']).read_bytes() + b' ')
        with self.assertRaises(ValueError): self.verify()

    def test_build_native_source_claim_must_match_registered_role(self):
        self.states['patched']['patch_applied_sha256'] = self.proposal['official_before_sha256']
        self.update_state('patched')
        with self.assertRaises(ValueError): self.verify()


if __name__ == '__main__': unittest.main()
