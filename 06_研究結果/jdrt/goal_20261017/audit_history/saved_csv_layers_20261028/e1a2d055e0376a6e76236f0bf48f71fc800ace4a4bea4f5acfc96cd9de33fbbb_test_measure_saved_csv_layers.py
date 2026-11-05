import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('layers', Path(__file__).with_name('measure_saved_csv_layers.py'))
layers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layers)


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'workspace/runs/accepted'
        self.folder.mkdir(parents=True)
        self.payload = b'id,value\na,"line one\nline two"\nb,two\n'
        self.artifact = self.folder / 'actors.csv.gz'
        self.artifact.write_bytes(gzip.compress(self.payload))
        self.manifest = {'run_id': 'accepted', 'registration_id': 'current', 'purpose': 'core',
                         'status': 'COMPLETED',
                         'output_sha256': {'actors.csv.gz': layers.digest(self.artifact)}}
        self.cfg = {'protocol': 'realtime_choice_v1', 'municipality_code': '08211',
                    'registration_id': 'current', 'workspace': 'workspace', 'record_files': ['ledger.jsonl']}
        self.cfg_path = self.root / layers.CONFIG
        self.cfg_path.parent.mkdir(parents=True)
        self.output = self.root / layers.GOAL / 'probe.json'
        self.prepare()

    def prepare(self):
        self.cfg_path.write_text(json.dumps(self.cfg), encoding='utf-8')
        self.manifest_path = self.folder / 'manifest.json'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.row = {'run_id': 'accepted', 'registration_id': 'current', 'validation_status': 'PASS',
                    'manifest_sha256': layers.digest(self.manifest_path)}
        (self.root / 'ledger.jsonl').write_text(json.dumps(self.row)+'\n', encoding='utf-8')

    def test_complete_csv_rows_include_quoted_newline(self):
        report = layers.run(self.root, 'accepted', self.output)
        self.assertEqual(report['files'][0]['csv_rows'], 2)
        self.assertEqual(report['files'][0]['gzip_expanded_bytes'], len(self.payload))
        self.assertEqual(report['status'], 'COMPONENT_TIMING_ONLY')

    def test_primary_bytes_unchanged(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        layers.run(self.root, 'accepted', self.output)
        self.assertTrue(all(p.read_bytes() == value for p, value in before.items()))

    def test_existing_output_preserved(self):
        self.output.parent.mkdir(parents=True)
        self.output.write_bytes(b'prior evidence')
        with self.assertRaises(FileExistsError):
            layers.run(self.root, 'accepted', self.output)
        self.assertEqual(self.output.read_bytes(), b'prior evidence')

    def test_output_cannot_enter_run(self):
        with self.assertRaises(ValueError):
            layers.run(self.root, 'accepted', self.folder / 'probe.json')
        self.assertFalse((self.folder / 'probe.json').exists())

    def test_requires_accepted_unique_current_row(self):
        for rows in [[], [dict(self.row, registration_id='old')], [self.row, self.row],
                     [dict(self.row, validation_status='INVALID')]]:
            with self.subTest(rows=rows):
                (self.root/'ledger.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
                with self.assertRaises(ValueError):
                    layers.run(self.root, 'accepted', self.output)
                self.assertFalse(self.output.exists())

    def test_running_smoke_and_wrong_registration_refused(self):
        for key, value in [('status', 'RUNNING'), ('purpose', 'smoke'), ('registration_id', 'old')]:
            with self.subTest(key=key):
                original = self.manifest[key]
                self.manifest[key] = value
                self.prepare()
                with self.assertRaises(ValueError):
                    layers.run(self.root, 'accepted', self.output)
                self.manifest[key] = original

    def test_changed_artifact_fails_with_preserved_receipt(self):
        self.artifact.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            layers.run(self.root, 'accepted', self.output)
        self.assertEqual(json.loads(self.output.read_text())['status'], 'FAILED_PRESERVED')
        self.assertEqual(self.artifact.read_bytes(), b'changed')

    def test_artifact_escape_refused(self):
        self.manifest['output_sha256'] = {'../outside': 'unused'}
        self.prepare()
        with self.assertRaises(ValueError):
            layers.run(self.root, 'accepted', self.output)
        self.assertEqual(json.loads(self.output.read_text())['status'], 'FAILED_PRESERVED')

    def test_postread_mutation_refused(self):
        def mutate(path):
            path.write_bytes(gzip.compress(b'changed'))
            return 0
        with patch.object(layers, 'csv_rows', side_effect=mutate):
            with self.assertRaises(ValueError):
                layers.run(self.root, 'accepted', self.output)
        self.assertEqual(json.loads(self.output.read_text())['status'], 'FAILED_PRESERVED')


if __name__ == '__main__':
    unittest.main()
