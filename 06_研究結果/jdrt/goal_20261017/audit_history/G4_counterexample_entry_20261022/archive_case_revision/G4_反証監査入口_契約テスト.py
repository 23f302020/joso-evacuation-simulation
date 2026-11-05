"""Synthetic audit-entry contracts; no native execution or research acceptance."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('G4_正式検証器_表会計候補試験.py')
spec = importlib.util.spec_from_file_location('choice_counterexample_entry', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EntryContracts(unittest.TestCase):
    def test_current_id_and_in_memory_hash_change_leave_primary_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'implementation.py'
            other = Path(directory) / 'other.txt'
            source.write_bytes(b'# artificial implementation\n')
            other.write_bytes(b'artificial original\n')
            original = source.read_bytes(), other.read_bytes()
            actual_sha, other_sha = audit.validator.file_sha(source), audit.validator.file_sha(other)

            def fake_validate(run_id, purpose):
                self.assertEqual((run_id, purpose), ('fresh_suite_c01', 'fixture'))
                self.assertNotEqual(audit.validator.file_sha(source), actual_sha)
                self.assertEqual(audit.validator.file_sha(other), other_sha)
                return {'status': 'INVALID', 'checks': {'all_bound_bytes_before': False}}

            with patch.object(audit.validator, 'audit_run_tables', side_effect=fake_validate) as validator:
                result = audit.current_implementation_sha_counterexample('fresh_suite_c01', source)
            self.assertEqual(validator.call_count, 1)
            self.assertEqual(result['status'], 'INVALID')
            self.assertEqual((source.read_bytes(), other.read_bytes()), original)
            self.assertEqual(audit.validator.file_sha(source), actual_sha)

    def test_missing_evidence_is_not_sha_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'implementation.py'
            source.write_bytes(b'# artificial\n')
            with patch.object(audit.validator, 'audit_run_tables', return_value={'status': 'INVALID', 'checks': {}}):
                with self.assertRaisesRegex(AssertionError, 'SHA gate'):
                    audit.current_implementation_sha_counterexample('fresh_suite_c01', source)

    def test_nonrejected_or_unrelated_failure_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'implementation.py'
            source.write_bytes(b'# artificial\n')
            for result in [{'status': 'INCOMPLETE', 'checks': {'all_bound_bytes_before': False}},
                           {'status': 'INVALID', 'checks': {'all_bound_bytes_before': True}}]:
                with self.subTest(result=result), patch.object(audit.validator, 'audit_run_tables', return_value=result):
                    with self.assertRaisesRegex(AssertionError, 'SHA gate'):
                        audit.current_implementation_sha_counterexample('fresh_suite_c01', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
