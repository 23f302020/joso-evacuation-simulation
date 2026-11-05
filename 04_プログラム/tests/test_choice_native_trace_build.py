"""File/build-plan contracts; no mocked result is a native regression PASS."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_trace_build as build
from choice_pair_sources import source_tree


class TraceBuildContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.destination = self.root / 'original', self.root / 'diagnostic'
        cpp = self.source / 'src/microsim/transportables/MSPModel_Striping.cpp'
        cpp.parent.mkdir(parents=True)
        proposal = ROOT / '06_研究結果/jdrt/goal_20261017/audit_history/walk_native_proposal_20261019'
        cpp.write_bytes((proposal / 'proposed/src/microsim/transportables/MSPModel_Striping.cpp').read_bytes())
        (self.source / 'other.txt').write_bytes(b'original\r\n')
        self.expected = source_tree(self.source)

    def test_fresh_copy_changes_only_generated_observation_source(self):
        receipt = build.prepare_source(self.source, self.destination, self.expected)
        self.assertEqual(source_tree(self.source), self.expected)
        actual = source_tree(self.destination)
        self.assertEqual(set(actual), set(self.expected))
        self.assertEqual([n for n in actual if actual[n] != self.expected[n]], [build.NATIVE])
        self.assertEqual(receipt['original_files'], len(self.expected))
        build.verify_source(self.source, self.destination, self.expected)

    def test_existing_destination_and_changed_original_fail_before_copy(self):
        self.destination.mkdir()
        with self.assertRaises(ValueError):
            build.prepare_source(self.source, self.destination, self.expected)
        missing = self.root / 'must_not_create'
        (self.source / 'other.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            build.prepare_source(self.source, missing, self.expected)
        self.assertFalse(missing.exists())

    def test_missing_extra_and_trace_body_changes_are_detected(self):
        build.prepare_source(self.source, self.destination, self.expected)
        for kind in ('missing', 'extra', 'trace'):
            with self.subTest(kind=kind):
                other = self.destination / 'other.txt'
                native = self.destination / build.NATIVE
                old, old_native = other.read_bytes(), native.read_bytes()
                extra = self.destination / 'injected.txt'
                if kind == 'missing': other.unlink()
                elif kind == 'extra': extra.write_bytes(b'extra')
                else: native.write_bytes(old_native.replace(b'"jdrtLatGuard"', b'"forged"'))
                with self.assertRaises(ValueError):
                    build.verify_source(self.source, self.destination, self.expected)
                other.write_bytes(old)
                native.write_bytes(old_native)
                if extra.exists(): extra.unlink()

    def test_original_mutation_after_copy_is_detected(self):
        build.prepare_source(self.source, self.destination, self.expected)
        (self.source / 'other.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            build.verify_source(self.source, self.destination, self.expected)

    def test_configure_replaces_only_source_and_build_operands(self):
        prior = ['cmake', '-S', 'old/source', '-B', 'old/build', '-G', 'MinGW Makefiles',
                 '-DCOMPILE_DEFINITIONS=XERCES_STATIC_LIBRARY;HAVE_VERSION_H']
        actual = build.configure_command(prior, self.source, self.destination)
        self.assertEqual(actual, [*prior[:2], self.source.as_posix(), '-B', self.destination.as_posix(), *prior[5:]])
        self.assertEqual(prior[2], 'old/source')
        for invalid in (prior + ['-B', 'duplicate'], ['cmake', '-S'], ['cmake', '-B', 'only']):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build.configure_command(invalid, self.source, self.destination)


if __name__ == '__main__':
    unittest.main()
