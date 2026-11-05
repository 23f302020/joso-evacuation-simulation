"""Migration and receipt contracts; native behavior is checked separately."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
try:
    import choice_native_guard_readback as reader
except ImportError:
    reader = None


class ReadbackContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(reader, 'Reusable current-series native readback is unimplemented')

    def test_exact_file_set_and_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'raw').write_bytes(b'raw')
            hashes = {'raw': hashlib.sha256(b'raw').hexdigest()}
            self.assertEqual(reader.verify_files(folder, hashes), 1)
            (folder / 'raw').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                reader.verify_files(folder, hashes)
            (folder / 'raw').write_bytes(b'raw')
            (folder / 'extra').write_bytes(b'extra')
            with self.assertRaises(ValueError):
                reader.verify_files(folder, hashes)

    def test_complete_unique_case_role_product(self):
        entries = [{'case': c, 'role': r} for c in ('a', 'b')
                   for r in ('control', 'patched', 'trace')]
        self.assertEqual(len(reader.pair_entries(entries, ['a', 'b'])), 6)
        for changed in (entries[:-1], entries + [entries[0]],
                        entries + [{'case': 'foreign', 'role': 'trace'}]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                reader.pair_entries(changed, ['a', 'b'])
        with self.assertRaises(ValueError):
            reader.pair_entries(entries, ['a', 'a'])

    def test_partial_or_adoptable_collection_is_rejected(self):
        manifest = {'status': 'COMPLETED', 'research_adoption_permitted': False,
                    'technical_ready': False, 'native_regression_complete': False,
                    'cases_requested': ['a']}
        plan = {'status': 'PREPARED_NOT_EXECUTED', 'research_adoption_permitted': False,
                'cases': [{'id': 'a'}]}
        reader.verify_scope(manifest, plan)
        for key, value in [('status', 'RUNNING'), ('technical_ready', True),
                           ('research_adoption_permitted', True),
                           ('cases_requested', ['different'])]:
            bad = deepcopy(manifest)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                reader.verify_scope(bad, plan)


if __name__ == '__main__':
    unittest.main()
