import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from ace_local import HEADER, apply_delta, digest, load_backend, read_state, validate_delta


class DeltaContract(unittest.TestCase):
    def setUp(self):
        self.playbook = '## OTHERS\n[oth-00001] helpful=0 harmful=0 :: original\n'
        self.ledger = '## JD-artificial-01 — synthetic evidence\nObserved result.\n'
        self.delta = {
            'base_sha256': digest(self.playbook),
            'operations': [{'type': 'ADD', 'section': 'OTHERS',
                            'content': 'Check phase before comparing timestamps.',
                            'evidence': ['JD-artificial-01']}],
            'bullet_tags': [],
        }

    def test_evidence_backed_add_is_accepted(self):
        validate_delta(self.delta, self.playbook, self.ledger)

    def test_stale_base_is_rejected(self):
        self.delta['base_sha256'] = digest('old')
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_missing_evidence_is_rejected(self):
        self.delta['operations'][0]['evidence'] = ['JD-missing']
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_empty_evidence_is_rejected(self):
        self.delta['operations'][0]['evidence'] = []
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_newline_cannot_inject_a_new_bullet(self):
        self.delta['operations'][0]['content'] += '\n[oth-00002] helpful=9 harmful=0 :: fake'
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_unsupported_operation_is_rejected(self):
        self.delta['operations'][0]['type'] = 'DELETE'
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_unknown_fields_are_rejected(self):
        self.delta['operations'][0]['command'] = 'anything'
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_unknown_bullet_tag_is_rejected(self):
        self.delta['bullet_tags'] = [{'id': 'oth-99999', 'tag': 'helpful',
                                      'evidence': ['JD-artificial-01']}]
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_duplicate_tag_is_rejected(self):
        tag = {'id': 'oth-00001', 'tag': 'helpful', 'evidence': ['JD-artificial-01']}
        self.delta['bullet_tags'] = [tag, copy.deepcopy(tag)]
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_duplicate_evidence_in_one_item_is_rejected(self):
        self.delta['operations'][0]['evidence'] *= 2
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)

    def test_repeated_add_in_same_delta_is_rejected(self):
        self.delta['operations'] *= 2
        with self.assertRaises(ValueError):
            validate_delta(self.delta, self.playbook, self.ledger)


class InstalledUpstreamContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = load_backend()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state_dir = Path(self.temp.name) / 'state'
        self.ledger = '## JD-artificial-01 — synthetic result\n'
        self.delta = {'base_sha256': digest(HEADER), 'operations': [
            {'type': 'ADD', 'section': 'OTHERS', 'content': 'Check the output.',
             'evidence': ['JD-artificial-01']}], 'bullet_tags': []}

    def test_real_upstream_add_and_hash_chain(self):
        state = apply_delta(self.delta, self.state_dir, self.ledger, self.backend)
        self.assertIn('Check the output. [evidence: JD-artificial-01]', state['playbook'])
        self.assertEqual(read_state(self.state_dir)[0], state['playbook'])
        self.assertEqual(read_state(self.state_dir)[2], 1)

    def test_stale_update_preserves_first_snapshot(self):
        apply_delta(self.delta, self.state_dir, self.ledger, self.backend)
        before = (self.state_dir / '000001.json').read_bytes()
        with self.assertRaises(ValueError):
            apply_delta(self.delta, self.state_dir, self.ledger, self.backend)
        self.assertEqual((self.state_dir / '000001.json').read_bytes(), before)
        self.assertFalse((self.state_dir / 'writer.lock').exists())

    def test_existing_writer_blocks_update(self):
        self.state_dir.mkdir()
        lock = self.state_dir / 'writer.lock'
        lock.write_text('other writer')
        with self.assertRaises(FileExistsError):
            apply_delta(self.delta, self.state_dir, self.ledger, self.backend)
        self.assertEqual(lock.read_text(), 'other writer')

    def test_partial_snapshot_fails_closed(self):
        self.state_dir.mkdir()
        (self.state_dir / '000001.json').write_text('{partial')
        with self.assertRaises(json.JSONDecodeError):
            read_state(self.state_dir)

    def test_same_evidence_cannot_inflate_rating(self):
        state = apply_delta(self.delta, self.state_dir, self.ledger, self.backend)
        # Derive the upstream ID rather than hardcoding its section slug.
        bullet_id = next(self.backend.parse_playbook_line(line)['id']
            for line in state['playbook'].splitlines() if self.backend.parse_playbook_line(line))
        tag = {'base_sha256': digest(state['playbook']), 'operations': [], 'bullet_tags': [
            {'id': bullet_id, 'tag': 'helpful', 'evidence': ['JD-artificial-01']}]}
        state = apply_delta(tag, self.state_dir, self.ledger, self.backend)
        self.assertIn('helpful=1 harmful=0', state['playbook'])
        tag['base_sha256'] = digest(state['playbook'])
        with self.assertRaises(ValueError):
            apply_delta(tag, self.state_dir, self.ledger, self.backend)
        self.assertEqual(read_state(self.state_dir)[2], 2)

    def test_repeated_add_on_new_base_is_rejected(self):
        state = apply_delta(self.delta, self.state_dir, self.ledger, self.backend)
        self.delta['base_sha256'] = digest(state['playbook'])
        with self.assertRaises(ValueError):
            apply_delta(self.delta, self.state_dir, self.ledger, self.backend)

    def test_outbound_network_is_denied(self):
        with self.assertRaisesRegex(RuntimeError, 'forbids network'):
            socket.create_connection(('127.0.0.1', 9))

    def test_subprocess_is_denied(self):
        with self.assertRaisesRegex(RuntimeError, 'forbids network'):
            subprocess.run([sys.executable, '-c', 'print(1)'], check=True)

    def test_finance_evaluator_not_imported(self):
        self.assertFalse(any(name.startswith('eval.finance') for name in sys.modules))


if __name__ == '__main__':
    unittest.main()
