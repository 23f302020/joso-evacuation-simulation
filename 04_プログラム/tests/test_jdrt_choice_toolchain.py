"""Pinned toolchain tests use artificial files/modules; no native process starts."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import jdrt_choice_toolchain as toolchain


class ToolchainContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root / 'toolchain.json'
        self.files = {'bin/sumo.exe': b'sumo-control', 'builder/netconvert.exe': b'netconvert',
                      'bin/dependency.dll': b'controlled dependency',
                      'tools/traci/__init__.py': b'from . import _vehicle\n',
                      'tools/traci/_vehicle.py': b'version = "synthetic"\n',
                      'tools/traci/lazy.py': b'value = 1\n',
                      'tools/sumolib/__init__.py': b'version = "synthetic"\n',
                      'source_build_provenance.txt': b'synthetic source/build evidence'}
        for name, data in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.document = {'schema_version': 1,
                         'files': {name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()},
                         'roles': {'sumo': 'bin/sumo.exe', 'netconvert': 'builder/netconvert.exe',
                                   'traci_init': 'tools/traci/__init__.py', 'sumolib_init': 'tools/sumolib/__init__.py'},
                         'provenance': {'source_build': 'synthetic fixture, never a usable toolchain'}}
        self.write_manifest()
        self.environment = patch.dict(os.environ, {toolchain.MANIFEST_ENV: str(self.manifest)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.previous_bytecode = sys.dont_write_bytecode
        self.addCleanup(setattr, sys, 'dont_write_bytecode', self.previous_bytecode)

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.document), encoding='utf-8')

    def clean_modules(self):
        previous = {name: value for name, value in sys.modules.items()
                    if name.split('.')[0] in ('traci', 'sumolib')}
        for name in previous:
            del sys.modules[name]
        def restore():
            for name in list(sys.modules):
                if name.split('.')[0] in ('traci', 'sumolib'):
                    del sys.modules[name]
            sys.modules.update(previous)
        self.addCleanup(restore)

    def test_exact_roles_ignore_legacy_discovery(self):
        with patch.object(toolchain, 'resolve_sumo_binary', side_effect=AssertionError('legacy fallback')):
            selected = toolchain.resolve_choice_toolchain()
        self.assertEqual(selected['sumo'], (self.root / self.document['roles']['sumo']).resolve())
        self.assertEqual(selected['netconvert'], (self.root / self.document['roles']['netconvert']).resolve())

    def test_absent_selection_retains_legacy_discovery(self):
        with patch.dict(os.environ):
            del os.environ[toolchain.MANIFEST_ENV]
            binary = self.root / 'installed/sumo.exe'
            with patch.object(toolchain, 'resolve_sumo_binary', return_value=binary) as resolver:
                selected = toolchain.resolve_choice_toolchain()
            resolver.assert_called_once_with()
            self.assertEqual(selected, {'sumo': binary, 'netconvert': binary.parent / 'netconvert.exe'})
            with patch.object(toolchain, 'resolve_sumo_binary', side_effect=AssertionError('legacy fallback')):
                with self.assertRaisesRegex(ValueError, 'core/READY requires'):
                    toolchain.resolve_choice_toolchain(require_manifest=True)

    def test_explicit_empty_missing_and_invalid_manifest_never_fall_back(self):
        for value in ('', str(self.root / 'missing.json'), str(self.root / 'bin/sumo.exe')):
            with self.subTest(value=value), patch.dict(os.environ, {toolchain.MANIFEST_ENV: value}), patch.object(
                    toolchain, 'resolve_sumo_binary', side_effect=AssertionError('legacy fallback')):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    toolchain.resolve_choice_toolchain()

    def test_duplicate_manifest_keys_are_rejected(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            toolchain.resolve_choice_toolchain()

    def test_schema_version_requires_the_registered_integer(self):
        for value in (True, '1', 2):
            with self.subTest(version=value):
                self.document['schema_version'] = value
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, 'schema'):
                    toolchain.resolve_choice_toolchain()

    def test_preflight_refuses_unpinned_toolchain_before_creating_evidence(self):
        path = toolchain.ROOT / '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'
        spec = importlib.util.spec_from_file_location('toolchain_preflight_guard_test', path)
        skill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(skill)
        with patch.dict(os.environ):
            del os.environ[toolchain.MANIFEST_ENV]
            with self.assertRaisesRegex(ValueError, 'core/READY requires'):
                skill.ChoiceController.preflight(None, 'unused-suite', 'unused-report')

    def test_path_traversal_absolute_and_noncanonical_paths_are_rejected(self):
        for name in ('../outside.dll', '/outside.dll', 'C:/outside.dll', 'bin\\sumo.exe', 'bin/../bin/sumo.exe', './bin/sumo.exe'):
            with self.subTest(name=name):
                self.document['files'] = {name: hashlib.sha256(b'x').hexdigest()}
                self.write_manifest()
                with self.assertRaises(ValueError):
                    toolchain.resolve_choice_toolchain()

    def test_changed_binary_dependency_and_source_proof_are_rejected(self):
        for name in ('bin/sumo.exe', 'builder/netconvert.exe', 'bin/dependency.dll', 'source_build_provenance.txt', 'tools/traci/_vehicle.py'):
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(self.files[name] + b'changed')
                with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                    toolchain.resolve_choice_toolchain()
                path.write_bytes(self.files[name])

    def test_unlisted_dependency_and_bytecode_are_rejected(self):
        path = self.root / 'bin/unlisted.dll'
        path.write_bytes(b'additional runtime')
        with self.assertRaisesRegex(ValueError, 'unlisted'):
            toolchain.resolve_choice_toolchain()
        path.unlink()
        name = 'tools/traci/__pycache__/__init__.pyc'
        path = self.root / name
        path.parent.mkdir()
        path.write_bytes(b'bytecode')
        self.document['files'][name] = toolchain.sha(path)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'bytecode'):
            toolchain.resolve_choice_toolchain()

    def test_real_imports_match_roles_and_never_write_bundle_bytecode(self):
        self.clean_modules()
        selected = toolchain.resolve_choice_toolchain()
        traci = toolchain.load_choice_traci(selected)
        before = toolchain.choice_runtime_fingerprint(selected, traci)
        # Lazy imports after the initial loader must also preserve the bundle.
        __import__('traci.lazy')
        after = toolchain.choice_runtime_fingerprint()
        self.assertEqual(before, after)
        self.assertEqual(Path(traci.__file__).resolve(), selected['traci_init'])
        self.assertFalse(list(self.root.rglob('*.pyc')))
        self.assertEqual(before['toolchain_files_sha256'], self.document['files'])
        self.assertEqual(before['toolchain_manifest_sha256'], toolchain.sha(self.manifest))
        self.assertEqual(before['choice_toolchain_helper'], toolchain.sha(Path(toolchain.__file__)))

    def test_cached_foreign_package_or_submodule_is_rejected(self):
        self.clean_modules()
        for name in ('traci', 'sumolib', 'traci._vehicle'):
            with self.subTest(name=name), patch.dict(sys.modules, {name: types.SimpleNamespace(__file__=__file__)}):
                with self.assertRaisesRegex(ValueError, 'outside pinned'):
                    toolchain.load_choice_traci(toolchain.resolve_choice_toolchain())

    def test_selected_package_role_cannot_be_replaced_by_another_bound_file(self):
        self.clean_modules()
        selected = toolchain.resolve_choice_toolchain()
        with patch.dict(sys.modules, {'traci': types.SimpleNamespace(__file__=str(self.root / 'tools/traci/_vehicle.py'))}):
            with self.assertRaisesRegex(ValueError, 'differs from selected role'):
                toolchain.load_choice_traci(selected)

    def test_manifest_provenance_or_role_mutation_invalidates_selection_and_fingerprint(self):
        self.clean_modules()
        selected = toolchain.resolve_choice_toolchain()
        traci = toolchain.load_choice_traci(selected)
        original = toolchain.choice_runtime_fingerprint(selected, traci)
        self.document['provenance']['source_build'] += ' changed'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'selection changed'):
            toolchain.choice_runtime_fingerprint(selected, traci)
        self.assertNotEqual(original, toolchain.choice_runtime_fingerprint())
        self.document['roles']['sumo'] = 'builder/netconvert.exe'
        self.write_manifest()
        self.assertNotEqual(original, toolchain.choice_runtime_fingerprint())

    def test_helper_source_is_part_of_runtime_gate(self):
        self.clean_modules()
        original = toolchain.choice_runtime_fingerprint()
        path = self.root.parent / (self.root.name + '_helper.py')
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text('changed resolver bytes\n', encoding='utf-8')
        with patch.object(toolchain, '__file__', str(path)):
            changed = toolchain.choice_runtime_fingerprint()
        self.assertNotEqual(original['choice_toolchain_helper'], changed['choice_toolchain_helper'])

    def test_fixture_netconvert_uses_exact_role_without_starting_native_process(self):
        from scripts import jdrt_choice_fixtures as fixtures
        selected = toolchain.resolve_choice_toolchain()
        result = Mock(stdout='', stderr='')
        result.check_returncode.side_effect = RuntimeError('stop before reading generated network')
        with patch.object(fixtures, 'ROOT', self.root), patch.object(fixtures, 'resolve_choice_toolchain', return_value=selected), patch.object(
                fixtures, 'load_choice_traci'), patch.object(fixtures, 'choice_runtime_fingerprint', return_value={}), patch.dict(
                sys.modules, {'sumolib': types.ModuleType('sumolib')}), patch.object(fixtures.subprocess, 'run', return_value=result) as process:
            with self.assertRaisesRegex(RuntimeError, 'stop before'):
                fixtures.prepare('walk_reroute', 'unique-id', {'workspace': 'isolated'})
        self.assertEqual(process.call_args.args[0][0], str(selected['netconvert']))


if __name__ == '__main__':
    unittest.main()
