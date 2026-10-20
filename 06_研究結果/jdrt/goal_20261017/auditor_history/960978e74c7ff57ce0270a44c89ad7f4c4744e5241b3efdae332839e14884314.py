"""Synthetic analysis contracts; no SUMO and no research result writes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name('G6_主指標・事前登録差分_集計.py')
spec = importlib.util.spec_from_file_location('choice_primary_analysis', SOURCE)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class PrimaryContracts(unittest.TestCase):
    def test_zero_time_is_admitted_and_exit_retains_full_unadmitted_time(self):
        people = [
            {'person_id': 'p', 'person_type': 'type4', 'status': 'admitted', 'terminal_id': 'f',
             'admitted_sec': '0', 'arrival_sec': '0'},
            {'person_id': 'q', 'person_type': 'type4', 'status': 'boundary_exit', 'terminal_id': 'x',
             'admitted_sec': '', 'arrival_sec': '1'}]
        source = {p['person_id']: {'person_type': p['person_type']} for p in people}
        terms = {'f': {'kind': 'facility', 'capacity': '1'}, 'x': {'kind': 'exit', 'capacity': '0'}}
        values, _, counts = analysis.person_metrics(people, source, terms, 10)
        value = next(v for v in values if v['group'] == 'type4')
        self.assertEqual((value['denominator'], value['admitted'], value['boundary_exit']), (2, 1, 1))
        self.assertEqual(value['normalized_unadmitted_time'], .5)
        self.assertEqual(counts, {'f': 1})

    def test_exits_cannot_masquerade_as_admission_or_missing_person_disappear(self):
        p = {'person_id': 'p', 'person_type': 'type4', 'status': 'admitted',
             'terminal_id': 'x', 'admitted_sec': '2', 'arrival_sec': '2'}
        source = {'p': {'person_type': 'type4'}}
        terms = {'x': {'kind': 'exit', 'capacity': '10'}}
        with self.assertRaisesRegex(RuntimeError, 'Exit counted'):
            analysis.person_metrics([p], source, terms, 10)
        with self.assertRaisesRegex(RuntimeError, 'Population missing'):
            analysis.person_metrics([], source, terms, 10)

    def test_incomplete_set_fails_before_population_or_output_access(self):
        cfg = {'cells': [{'cell_id': 'a'}, {'cell_id': 'b'}], 'record_files': ['ledger.jsonl']}
        with tempfile.TemporaryDirectory(prefix='choice_analysis_contract_') as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, 'no formally recorded'):
                analysis.complete_records(root, cfg)
            (root / 'ledger.jsonl').write_text(json.dumps({'cell_id': 'a'}) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'complete registered set'):
                analysis.complete_records(root, cfg)
            self.assertEqual({p.name for p in root.iterdir()}, {'ledger.jsonl'})

    def test_R0_is_shared_and_percentage_points_have_correct_scale(self):
        cfg = {'seeds': [7], 'cells': [
            {'destination_policy': 'd', 'demand_level': None},
            {'destination_policy': 'd', 'demand_level': 'low'},
            {'destination_policy': 'd', 'demand_level': 'high'}],
            'analysis': {'primary_contrasts': ['R1-R0']}}
        def metric(level, scenario, admitted, run):
            return {'destination_policy': 'd', 'demand_level': level, 'scenario': scenario, 'seed': 7,
                    'run_id': run, 'denominator': 4, 'admitted': admitted, 'admitted_rate': admitted / 4,
                    'normalized_unadmitted_time': 1 - admitted / 4, 'boundary_exit': 0}
        values = [metric(None, 'R0', 1, 'reference'), metric('low', 'R1', 2, 'low'), metric('high', 'R1', 0, 'high')]
        pairs = analysis.paired_contrasts(values, cfg)
        self.assertEqual([p['right_run_id'] for p in pairs], ['reference', 'reference'])
        self.assertTrue(all(p['R0_reused_reference'] for p in pairs))
        self.assertEqual([p['admitted_percentage_point_difference'] for p in pairs], [25, -25])
        values[1]['denominator'] = 5
        with self.assertRaisesRegex(RuntimeError, 'denominators differ'):
            analysis.paired_contrasts(values, cfg)

    def test_complete_record_metadata_requires_all_components_and_unchanged_manifest(self):
        with tempfile.TemporaryDirectory(prefix='choice_analysis_complete_metadata_') as temp:
            root = Path(temp)
            def save(relative, value):
                p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(value), encoding='utf-8')
                return analysis.digest(p)
            cell = {'cell_id': 'c', 'scenario': 'R0', 'seed': 7, 'destination_policy': 'd', 'demand_level': None}
            cfg = {'cells': [cell], 'protocol': 'synthetic_contract', 'workspace': 'ws',
                   'record_files': ['context.md', 'ledger.jsonl'],
                   'execution': {'implementation_files': ['impl.py']}, 'simulation': {'duration_sec': 10}}
            (root / 'context.md').write_text('<!-- choice_record:r -->\n<!-- AGENT_CURRENT_END -->\n', encoding='utf-8')
            (root / 'impl.py').write_text('# synthetic metadata only\n', encoding='utf-8')
            impl = {'impl.py': analysis.digest(root / 'impl.py')}
            config_sha = save(analysis.CONFIG, cfg)
            manifest = {'run_id': 'r', **cell, 'purpose': 'core', 'protocol': cfg['protocol'],
                        'status': 'COMPLETED', 'implementation_sha256': impl,
                        'parameter_sha256': config_sha, 'end_sec': 10}
            manifest_sha = save('ws/runs/r/manifest.json', manifest)
            names = ['person_tables', 'candidate_tables', 'road_snapshots', 'actor_stream',
                     'movement_events', 'native_logs', 'native_fixture_boundaries']
            proof = {'run_id': 'r', 'purpose': 'core', 'status': 'PASS', 'core_adoption_permitted': True,
                     'pending': [], 'manifest_sha256': manifest_sha, 'implementation_sha256': impl,
                     'checks': {'integrity': True}, 'components': {k: {'status': 'PASS'} for k in names}}
            proof_sha = save('proof.json', proof)
            row = {**cell, 'run_id': 'r', 'protocol': cfg['protocol'], 'purpose': 'core',
                   'validation_status': 'PASS', 'implementation_sha256': impl,
                   'manifest_sha256': manifest_sha, 'validation_report': 'proof.json',
                   'validation_report_sha256': proof_sha}
            def ledger():
                (root / 'ledger.jsonl').write_text(json.dumps(row) + '\n', encoding='utf-8')
            ledger()
            self.assertEqual(len(analysis.complete_records(root, cfg)), 1)
            del proof['components']['native_logs']
            row['validation_report_sha256'] = save('proof.json', proof); ledger()
            with self.assertRaisesRegex(RuntimeError, 'Missing validation component'):
                analysis.complete_records(root, cfg)
            manifest['status'] = 'RUNNING'; save('ws/runs/r/manifest.json', manifest)
            with self.assertRaisesRegex(RuntimeError, 'still running'):
                analysis.complete_records(root, cfg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
