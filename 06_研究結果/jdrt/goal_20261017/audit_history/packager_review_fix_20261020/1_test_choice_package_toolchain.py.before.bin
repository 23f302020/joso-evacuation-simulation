"""Artificial PE/package/proof fixtures only; no compiler or SUMO runs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.agents/skills/joso-jdrt-runner/scripts/choice_package_toolchain.py'


def fake_pe():
    data = bytearray(1024)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<HH', data, 132, 0x8664, 1)
    struct.pack_into('<H', data, 148, 240)
    struct.pack_into('<H', data, 152, 0x20b)
    struct.pack_into('<I', data, 152 + 108, 16)
    struct.pack_into('<II', data, 152 + 120, 4096, 40)
    struct.pack_into('<IIII', data, 400, 512, 4096, 512, 512)
    struct.pack_into('<IIIII', data, 512, 0, 0, 0, 4160, 0)
    data[576:589] = b'KERNEL32.dll\0'
    return bytes(data)


class PackagingContracts(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('choice_packager_test', SCRIPT)
        self.packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.packager)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.tools = self.root / 'source/tools'
        contents = {'tools/traci/__init__.py': b'from . import _vehicle\n',
                    'tools/traci/_vehicle.py': b'value = 1\n',
                    'tools/sumolib/__init__.py': b'value = 1\n',
                    'AUTHORS': b'authors', 'LICENSE': b'license', 'NOTICE.md': b'notice'}
        inventory = []
        for name, data in contents.items():
            path = self.tools.parent / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            inventory.append({'relative_path': name, 'archive_sha256': self.digest(data),
                              'source_sha256': self.digest(data), 'bytes': len(data)})
        self.inventory = self.root / 'tools_inventory.json'
        self.inventory.write_text(json.dumps({'schema': 'official_python_tools_inventory_v1',
            'source_root': str(self.tools.parent), 'source_commit': 'a' * 40, 'files': inventory,
            'all_official_bytes_match': True, 'missing': [], 'mismatched': [], 'extra_package_files': []}))
        self.sumo = self.root / 'sumo.exe'
        self.netconvert = self.root / 'netconvert.exe'
        binaries = []
        for binary in (self.sumo, self.netconvert):
            binary.write_bytes(fake_pe())
            log = binary.with_suffix('.log')
            log.write_text('Eclipse SUMO Version 1.26.0-test')
            binaries.append({**self.item(binary), 'clean_path_version_exit_code': 0,
                'version_log': str(log), 'version_log_sha256': self.digest(log.read_bytes()),
                'pe_imports': ['KERNEL32.dll']})
        build_log = self.root / 'build.log'
        build_log.write_text('Built target sumo\nBuilt target netconvert\n')
        self.proof = self.root / 'native_provenance.json'
        self.document = {'schema': 'isolated_native_provenance_v1', 'role': 'patched',
            'source_commit': 'a' * 40,
            'custom_version': '1.26.0-test', 'simulation_executed': False, 'research_cli_switched': False,
            'source_scope': 'mock source, never an actual native-build proof',
            'files': [self.item(self.inventory)], 'binaries': binaries,
            'state': {'schema': 'isolated_native_build_v1',
                'status': 'COMPILED_VERSION_CHECKED_NOT_SIMULATED', 'patch_applied_sha256': 'b' * 64,
                'zlib_dependency': {'files': [self.item(build_log)]},
                'commands': [{'command': ['cmake', '--build', 'mock', '--target', 'sumo', 'netconvert'],
                              'exit_code': 0, 'log': str(build_log), 'log_bytes': build_log.stat().st_size}]}}
        for name in ('cmake.exe', 'gcc.exe', 'g++.exe', 'libxerces-c.a', 'CMakeCache.txt',
                     'config.h', 'version.h', 'sumo-' + 'a' * 40 + '.zip'):
            path = self.root / name
            if name.endswith('.zip'):
                with zipfile.ZipFile(path, 'w') as archive:
                    for relative, data in contents.items():
                        archive.writestr('sumo-' + 'a' * 40 + '/' + relative, data)
            else:
                path.write_bytes(b'artificial proof artifact: ' + name.encode())
            self.document['files'].append(self.item(path))
        self.write_proof()
        self.destination = self.project / '04_プログラム/output/sumo/toolchains/new'

    def digest(self, data):
        return hashlib.sha256(data).hexdigest()

    def item(self, path):
        return {'path': str(path), 'sha256': self.digest(path.read_bytes()), 'bytes': path.stat().st_size}

    def write_proof(self):
        self.proof.write_text(json.dumps(self.document))

    def package(self):
        return self.packager.package(self.tools, self.sumo, self.netconvert, self.proof,
                                     self.inventory, self.destination, self.project)

    def test_complete_inventory_and_original_proof_bytes(self):
        manifest = self.package()
        document = json.loads(manifest.read_text())
        self.assertEqual(set(document), {'schema_version', 'files', 'roles', 'provenance'})
        self.assertEqual(document['schema_version'], 1)
        self.assertEqual((manifest.parent / 'evidence/native_provenance.json').read_bytes(), self.proof.read_bytes())
        actual = {p.relative_to(manifest.parent).as_posix(): self.digest(p.read_bytes())
                  for p in manifest.parent.rglob('*') if p.is_file() and p != manifest}
        self.assertEqual(document['files'], actual)
        self.assertEqual(document['roles']['sumo'], 'bin/sumo.exe')
        self.assertFalse(list(manifest.parent.rglob('*.pyc')))

    def test_destination_is_never_reused_or_research_run(self):
        self.package()
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.package()
        self.destination = self.project / '04_プログラム/output/sumo/regions/08211/run'
        with self.assertRaisesRegex(ValueError, 'toolchains'):
            self.package()
        self.assertFalse(self.destination.exists())

    def test_modified_missing_and_extra_source_are_rejected(self):
        path = self.tools / 'traci/_vehicle.py'
        original = path.read_bytes()
        for mode in ('modified', 'missing', 'extra', 'bytecode'):
            with self.subTest(mode=mode):
                extra = self.tools / ('traci/extra.py' if mode == 'extra' else 'traci/cache.pyc')
                if mode == 'modified':
                    path.write_bytes(b'changed')
                elif mode == 'missing':
                    path.unlink()
                else:
                    extra.write_bytes(b'extra')
                with self.assertRaises(ValueError):
                    self.package()
                path.write_bytes(original)
                extra.unlink(missing_ok=True)

    def test_binary_sha_imports_and_success_evidence_are_required(self):
        for field, value in (('sha256', '0' * 64), ('pe_imports', ['unexpected.dll']),
                             ('clean_path_version_exit_code', 1)):
            with self.subTest(field=field):
                original = self.document['binaries'][0][field]
                self.document['binaries'][0][field] = value
                self.write_proof()
                with self.assertRaises(ValueError):
                    self.package()
                self.document['binaries'][0][field] = original
        self.document['state']['status'] = 'FAILED_PRESERVED'
        self.write_proof()
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.package()

    def test_partial_failure_is_preserved_without_success_manifest(self):
        with patch.object(self.packager.shutil, 'copyfile', side_effect=OSError('injected copy failure')):
            with self.assertRaises(OSError):
                self.package()
        self.assertTrue((self.destination / 'FAILED.json').is_file())
        self.assertFalse((self.destination / 'toolchain.json').exists())
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.package()

    def test_real_imports_twice_and_runtime_mutation_or_unlisted_file_rejected(self):
        manifest = self.package()
        previous = {name: module for name, module in sys.modules.items()
                    if name.split('.')[0] in ('traci', 'sumolib')}
        for name in previous:
            del sys.modules[name]
        original_bytecode = sys.dont_write_bytecode
        def restore():
            for name in list(sys.modules):
                if name.split('.')[0] in ('traci', 'sumolib'):
                    del sys.modules[name]
            sys.modules.update(previous)
            sys.dont_write_bytecode = original_bytecode
        self.addCleanup(restore)
        with patch.dict(os.environ):
            result = self.packager.verify(manifest, ROOT)
            self.assertEqual(result['status'], 'IMPORTS_VERIFIED_NOT_SIMULATED')
            self.assertEqual(result['modules']['traci'], str((manifest.parent / 'tools/traci/__init__.py').resolve()))
            self.assertFalse(list(manifest.parent.rglob('*.pyc')))
            extra = manifest.parent / 'extra.dll'
            extra.write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'unlisted'):
                self.packager.verify(manifest, ROOT)
            extra.unlink()
            (manifest.parent / 'bin/sumo.exe').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                self.packager.verify(manifest, ROOT)

    def test_non_os_import_is_rejected_from_actual_pe_bytes(self):
        data = bytearray(fake_pe())
        data[576:589] = b'notan-os.dll\0'
        self.sumo.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'Non-OS DLL'):
            self.packager.pe_imports(self.sumo)

    def test_control_requires_matching_source_flags_and_dependencies(self):
        self.document['role'] = 'control'
        self.write_proof()
        with self.assertRaisesRegex(ValueError, 'Control source/flags/dependency'):
            self.package()
        self.document['source_comparison'] = {'mock_unpatched_source': True}
        self.document['patched_control_comparison'] = {
            'configure_equal_except_source_build_paths': True, 'zlib_dependency_identical': True,
            'flags': {name: {'compiler_defines_and_flags_equal': True, 'link_command_equal': True}
                      for name in ('sumo', 'netconvert')}}
        self.write_proof()
        manifest = self.package()
        self.assertEqual(json.loads(manifest.read_text())['provenance']['role'], 'control')

    def test_proof_mutation_during_copy_is_preserved_as_failure(self):
        original = self.packager.shutil.copyfile
        def changed(source, target):
            result = original(source, target)
            if Path(source) == self.sumo:
                self.proof.write_bytes(self.proof.read_bytes() + b' ')
            return result
        with patch.object(self.packager.shutil, 'copyfile', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.package()
        self.assertTrue((self.destination / 'FAILED.json').exists())
        self.assertFalse((self.destination / 'toolchain.json').exists())

    def test_inventory_cannot_hide_modified_official_zip_member(self):
        item = next(item for item in self.document['files'] if item['path'].endswith('.zip'))
        path = Path(item['path'])
        with zipfile.ZipFile(path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        members['sumo-' + 'a' * 40 + '/tools/traci/_vehicle.py'] = b'archive changed'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        item.update(self.item(path))
        self.write_proof()
        with self.assertRaisesRegex(ValueError, 'ZIP member differs'):
            self.package()


if __name__ == '__main__':
    unittest.main()
