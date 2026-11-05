"""Artificial archive/source contracts; no native executable or research run."""
import difflib
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SOURCE = Path(__file__).resolve().parents[2] / '.agents/skills/joso-jdrt-runner/scripts/choice_pair_sources.py'
spec = importlib.util.spec_from_file_location('choice_pair_sources_test', SOURCE)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SourceContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.commit = 'a' * 40
        self.original = {'CMakeLists.txt': b'project(fake)\n',
                         'src/native.cpp': b'one\ntwo\nthree\n',
                         'src/CMakeLists.txt': b'link_old\n',
                         'src/other.h': b'header\n', 'tools/helper.py': b'pass\n',
                         'src/unused/test.cpp': b'not selected\n'}
        self.archive = self.base / 'official.zip'
        self.write_archive(self.original)
        self.roots = {role: self.base / role for role in ('control', 'patched')}
        self.patches = {}
        for name, after, roles in [('src/native.cpp', b'one\ntwo_new\nthree\n', ['patched']),
                                   ('src/CMakeLists.txt', b'link_new\n', ['control', 'patched'])]:
            before = self.original[name]
            diff = ''.join(difflib.unified_diff(before.decode().splitlines(True),
                after.decode().splitlines(True), fromfile='a/' + name, tofile='b/' + name)).encode()
            patch = self.base / (Path(name).name + '.patch')
            patch.write_bytes(diff)
            self.patches[name] = {'path': str(patch), 'sha256': digest(diff),
                                  'before_sha256': digest(before), 'after_sha256': digest(after),
                                  'roles': roles}
        self.allowed = ['src/unused/test.cpp']
        self.inventories = {}
        for role, root in self.roots.items():
            self.inventories[role] = {}
            for name, data in self.original.items():
                if name in self.allowed:
                    continue
                if name == 'src/CMakeLists.txt':
                    data = b'link_new\n'
                if name == 'src/native.cpp' and role == 'patched':
                    data = b'one\ntwo_new\nthree\n'
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                self.inventories[role][name] = digest(data)

    def write_archive(self, members):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, data in members.items():
                archive.writestr('sumo-' + self.commit + '/' + name, data)

    def verify(self):
        return target.verify_sources(self.archive, self.commit, self.roots,
                                     self.inventories, self.patches, self.allowed)

    def test_valid_pair_recomputed_from_current_bytes(self):
        result = self.verify()
        self.assertTrue(result['current_source_bytes_reverified'])

    def test_shared_unregistered_change_even_with_updated_inventories_rejected(self):
        for role, root in self.roots.items():
            (root / 'tools/helper.py').write_bytes(b'changed\n')
            self.inventories[role]['tools/helper.py'] = digest(b'changed\n')
        with self.assertRaises(ValueError):
            self.verify()

    def test_stale_inventory_rejected(self):
        (self.roots['control'] / 'src/other.h').write_bytes(b'changed\n')
        with self.assertRaises(ValueError):
            self.verify()

    def test_missing_or_extra_source_rejected(self):
        for operation in ('missing', 'extra'):
            with self.subTest(operation=operation):
                if operation == 'missing':
                    path = self.roots['control'] / 'src/other.h'
                    raw = path.read_bytes()
                    path.unlink()
                else:
                    path = self.roots['control'] / 'extra.txt'
                    path.write_bytes(b'extra')
                with self.assertRaises(ValueError):
                    self.verify()
                if operation == 'missing':
                    path.write_bytes(raw)
                else:
                    path.unlink()

    def test_missing_required_build_source_in_both_inventories_rejected(self):
        for role, root in self.roots.items():
            (root / 'src/other.h').unlink()
            self.inventories[role].pop('src/other.h')
        with self.assertRaises(ValueError):
            self.verify()

    def test_unapplied_patch_rejected_even_with_updated_inventory(self):
        name = 'src/native.cpp'
        data = self.original[name]
        (self.roots['patched'] / name).write_bytes(data)
        self.inventories['patched'][name] = digest(data)
        with self.assertRaises(ValueError):
            self.verify()

    def test_patch_tamper_and_forged_after_digest_rejected(self):
        entry = self.patches['src/native.cpp']
        entry['after_sha256'] = digest(self.original['src/native.cpp'])
        with self.assertRaises(ValueError):
            self.verify()

    def test_crlf_patch_transport_preserves_exact_lf_source_result(self):
        entry = self.patches['src/CMakeLists.txt']
        path = Path(entry['path'])
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        entry['sha256'] = digest(path.read_bytes())
        self.assertTrue(self.verify()['current_source_bytes_reverified'])

    def test_mixed_patch_transport_rejected(self):
        entry = self.patches['src/CMakeLists.txt']
        path = Path(entry['path'])
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n', 1))
        entry['sha256'] = digest(path.read_bytes())
        with self.assertRaises(ValueError):
            self.verify()

    def test_patch_must_apply_to_exact_base_and_match_declared_target(self):
        entry = self.patches['src/native.cpp']
        path = Path(entry['path'])
        for old, new in [(b'-two\n', b'-absent\n'), (b'a/src/native.cpp', b'a/src/other.h')]:
            raw = path.read_bytes()
            path.write_bytes(raw.replace(old, new))
            entry['sha256'] = digest(path.read_bytes())
            with self.assertRaises(ValueError):
                self.verify()
            path.write_bytes(raw)
            entry['sha256'] = digest(raw)

    def test_duplicate_or_traversal_archive_members_rejected(self):
        for name in ('src/other.h', '../escape.h'):
            with self.subTest(name=name):
                self.write_archive(self.original)
                with zipfile.ZipFile(self.archive, 'a') as archive:
                    archive.writestr('sumo-' + self.commit + '/' + name, b'fake')
                with self.assertRaises(ValueError):
                    self.verify()

    def test_same_source_root_and_invalid_role_rejected(self):
        self.roots['patched'] = self.roots['control']
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == '__main__':
    unittest.main()
