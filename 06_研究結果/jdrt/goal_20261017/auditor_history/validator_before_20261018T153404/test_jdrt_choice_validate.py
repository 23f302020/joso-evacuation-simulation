"""Independent sparse verifier contracts, without research outcome constants."""
import math
import random
import unittest
import json
import tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch

import networkx as nx

from scripts.jdrt_realtime_choice_validate import IndependentCarTimes, independent_number, audit_run_tables
from scripts import jdrt_realtime_choice_validate as validator


class SparseVerifierContracts(unittest.TestCase):
    def test_partial_edges_backward_cycle_closed_and_unreachable(self):
        graph = {'nodes': {'a': {'length': 100, 'free_sec': 10},
                           'b': {'length': 200, 'free_sec': 20},
                           'c': {'length': 10, 'free_sec': 1}},
                 'edges': [('a', 'b', {}), ('b', 'a', {})]}
        audit = IndependentCarTimes(graph, set(), {}, ['a'], ['a', 'b', 'c'])
        self.assertEqual(audit.optimal('a', 'b', 80, 30, 'pickup'), 5)
        self.assertAlmostEqual(audit.optimal('a', 'a', 80, 20, 'pickup'), 24)
        self.assertAlmostEqual(audit.optimal('a', 'a', 20, 80, 'delivery'), 6)
        self.assertGreater(audit.optimal('a', 'a', 20, 21, 'pickup', 5), 20)
        self.assertTrue(math.isinf(audit.optimal('a', 'c', 20, 5, 'delivery')))
        closed = IndependentCarTimes(graph, {'b'}, {}, ['a'], ['a', 'b'])
        self.assertTrue(math.isinf(closed.optimal('a', 'a', 80, 20, 'pickup')))
        self.assertTrue(math.isinf(closed.optimal('a', 'b', 20, 30, 'delivery')))

    def test_compiled_paths_match_exhaustive_forward_oracle(self):
        randomizer = random.Random(6819)
        for iteration in range(6):
            names = [str(i) for i in range(12)]
            nodes = {name: {'length': randomizer.uniform(10, 500), 'free_sec': randomizer.uniform(1, 40)} for name in names}
            arcs = [(a, b, {}) for a in names for b in names if a != b and randomizer.random() < .25]
            closed = set(randomizer.sample(names, 2))
            observed = {name: (randomizer.uniform(.01, 25), 1) for name in names[::2]}
            audit = IndependentCarTimes({'nodes': nodes, 'edges': arcs}, closed, observed, names, names)
            graph = nx.DiGraph()
            graph.add_nodes_from(set(names) - closed)
            graph.add_edges_from((a, b) for a, b, _ in arcs if a not in closed and b not in closed)
            for mode in ('pickup', 'delivery'):
                weights = {name: nodes[name]['length'] / max(observed[name][0], .1)
                           if mode == 'pickup' and name in observed else nodes[name]['free_sec'] for name in names}
                for start in graph:
                    distance = nx.single_source_dijkstra_path_length(graph, start, weight=lambda a, b, d: weights[b])
                    for target in graph:
                        begin, end = nodes[start]['length'] * .8, nodes[target]['length'] * .2
                        if start == target:
                            # Enumerate every first arc, then a separate forward return search.
                            options = []
                            for neighbor in graph[start]:
                                back = nx.single_source_dijkstra_path_length(graph, neighbor, weight=lambda a, b, d: weights[b])
                                options.append(weights[neighbor] + back.get(start, math.inf))
                            base = min(options, default=math.inf)
                        else:
                            base = distance.get(target, math.inf)
                        expected = base + weights[start] * .2 - weights[target] * .8
                        actual = audit.optimal(start, target, begin, end, mode)
                        if math.isfinite(expected):
                            self.assertAlmostEqual(actual, expected, places=9)
                        else:
                            self.assertTrue(math.isinf(actual))

    def test_numeric_missingness_and_nonfinite_rejected(self):
        for kind, value in [('finite', ''), ('finite', 'nan'), ('finite', 'inf'),
                            ('infinite', '0'), ('not_applicable', 'nan'), ('unknown', '')]:
            with self.assertRaises(ValueError):
                independent_number({'x_kind': kind, 'x_sec': value}, 'x')
        self.assertIsNone(independent_number({'x_kind': 'not_applicable', 'x_sec': ''}, 'x'))
        self.assertEqual(independent_number({'x_kind': 'infinite', 'x_sec': ''}, 'x'), math.inf)

    def test_historical_core_and_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Historical'):
            audit_run_tables('not_started', purpose='core', require_current=False)
        for identifier in ('../outside', '.', '..', ''):
            with self.assertRaises(ValueError):
                audit_run_tables(identifier, purpose='fixture')


class TechnicalValidationBoundary(unittest.TestCase):
    def proof(self):
        return {'status': 'INCOMPLETE', 'historical_diagnostic': False, 'checks': {'owned_proof': True},
                'components': {name: {'status': 'PASS'} for name in ('person_tables', 'candidate_tables',
                    'road_snapshots', 'actor_stream', 'movement_events', 'native_logs', 'native_fixture_boundaries')},
                'pending': ['unimplemented_core_adoption']}

    def invoke(self, proof, purpose):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            param = root / 'parameters.json'
            param.write_text(json.dumps({'workspace': 'owned'}), encoding='utf-8')
            with patch.object(validator, 'ROOT', root), patch.object(validator, 'PARAM', param), patch.object(
                    validator, 'audit_run_tables', return_value=deepcopy(proof)):
                result = validator.validate_run('owned', purpose)
            saved = json.loads((root / result['validation_report']).read_text(encoding='utf-8'))
            self.assertEqual(saved, result)
            return result

    def test_complete_technical_pass_never_authorizes_core(self):
        for purpose in ('fixture', 'smoke'):
            result = self.invoke(self.proof(), purpose)
            self.assertEqual(result['status'], 'PASS')
            self.assertFalse(result['core_adoption_permitted'])
            self.assertFalse(result['technical_ready'])
        core = self.invoke(self.proof(), 'core')
        self.assertEqual(core['status'], 'INCOMPLETE')
        self.assertFalse(core['core_adoption_permitted'])

    def test_empty_historical_or_partial_proofs_fail_closed(self):
        for change in ({'checks': {}}, {'components': {}}, {'historical_diagnostic': True},
                       {'checks': {'owned_proof': False}}, {'components': {'person_tables': {'status': 'PASS'}}}):
            self.assertEqual(self.invoke({**self.proof(), **change}, 'smoke')['status'], 'INVALID')

    def test_core_needs_complete_integrity_and_archived_preflight_provenance(self):
        proof = self.proof()
        proof['checks']['core_preflight_provenance'] = True
        result = self.invoke(proof, 'core')
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['core_adoption_permitted'])
        proof['checks']['core_preflight_provenance'] = False
        self.assertEqual(self.invoke(proof, 'core')['status'], 'INVALID')


class PreflightProvenance(unittest.TestCase):
    def evidence(self, root):
        def save(name, value):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding='utf-8')
            return name
        cfg = {'protocol': 'owned', 'workspace': 'ws', 'input_directory': 'inputs', 'seeds': [1],
               'acceptance_gates': {'accounting': 0}, 'execution': {'implementation_files': ['owned.py']},
               'cells': [{'cell_id': 'owned_cell', 'seed': 1}]}
        param = root / 'parameters.json'
        save('parameters.json', cfg)
        save('owned.py', {})
        implementation = {'owned.py': validator.file_sha(root / 'owned.py')}
        save('ws/inputs/manifest.json', {'artifacts': {}, 'source_sha256': {}})
        inputs_sha = validator.file_sha(root / 'ws/inputs/manifest.json')
        factory = '04_プログラム/scripts/jdrt_choice_fixtures.py'
        counter_script = '06_研究結果/jdrt/goal_20261017/G4_正式検証器_表会計候補試験.py'
        save(factory, {})
        save(counter_script, {})
        source = save('owned_test.py', {})
        evidence = {'input': save('input.json', {'status': 'PASS', 'checks': {'owned': True},
                    'input_manifest_sha256': inputs_sha, 'validator_sha256': validator.file_sha(Path(validator.__file__))}),
                    'unit': save('unit.json', {'status': 'PASS', 'tests_run': 2, 'skipped': [],
                    'test_ids': ['owned.SixFileRecordContracts.commit', 'owned.LifecycleContracts.start'],
                    'implementation_sha256': implementation, 'test_source_sha256': {source: validator.file_sha(root / source)}}),
                    'storage': save('storage.json', {'status': 'PASS', 'implementation_sha256': implementation,
                    'parameter_sha256': validator.file_sha(param), 'free_bytes': 1000, 'one_run_reserve_bytes': 100,
                    'writer_checks_pass': True}), 'fixture_validations': [], 'smoke_validations': []}
        cases, baselines = [], []
        for index, case in enumerate((*validator.REQUIRED_FIXTURE_CASES, 'smoke')):
            purpose = 'smoke' if case == 'smoke' else 'fixture'
            run_id = 'owned' + str(index)
            directory = 'ws/smoke/' + run_id if purpose == 'smoke' else 'ws/technical/' + run_id + '/execution'
            save(directory + '/actor.csv', {'owned': 'raw'})
            save(directory + '/implementation/owned.py', {})
            m = {'status': 'COMPLETED', 'purpose': purpose, 'fixture_case': case, 'cell_id': 'owned_cell',
                 'parameter_path': 'parameters.json', 'parameter_sha256': validator.file_sha(param),
                 'input_directory': 'ws/inputs', 'input_manifest_sha256': inputs_sha,
                 'implementation_sha256': implementation,
                 'output_sha256': {'actor.csv': validator.file_sha(root / directory / 'actor.csv')}}
            mp = save(directory + '/manifest.json', m)
            proof = {'status': 'PASS', 'purpose': purpose, 'run_id': run_id, 'core_adoption_permitted': False,
                     'historical_diagnostic': False, 'implementation_sha256': implementation,
                     'runtime_sha256': {'owned': 'runtime'}, 'verifier_dependencies': {'owned': 'dependency'},
                     'manifest_sha256': validator.file_sha(root / mp), 'parameter_sha256': validator.file_sha(param),
                     'input_manifest_sha256': inputs_sha, 'checks': {'owned': True},
                     'components': {k: {'status': 'PASS'} for k in validator.RUN_COMPONENTS}}
            name = save(run_id + '.json', proof)
            evidence[purpose + '_validations'].append(name)
            if purpose == 'fixture':
                cases.append({'case': case, 'child_run_id': run_id, 'status': 'PASS'})
                baselines.append(proof)
        evidence['fixture_manifest'] = save('suite.json', {'run_id': 'owned_suite', 'status': 'COMPLETED',
            'research_adoption_permitted': False, 'factory_sha256': validator.file_sha(root / factory), 'cases': cases})
        evidence['counterexamples'] = save('counter.json', {'status': 'PASS', 'suite': 'owned_suite',
            'historical_diagnostic': False, 'primary_outputs_unchanged': True, 'counterexamples': [{'pass': True}],
            'fixture_components': baselines, 'validator_sha256': validator.file_sha(Path(validator.__file__)),
            'test_sha256': validator.file_sha(root / counter_script)})
        receipt = {'status': 'READY', 'protocol': cfg['protocol'], 'checks': {k: True for k in
            ('accounting', 'unit_tests', 'six_file_record_transaction', 'storage_and_single_writer')},
            'implementation_sha256': implementation, 'parameter_sha256': validator.file_sha(param),
            'input_manifest_sha256': inputs_sha, 'runtime_sha256': {'owned': 'runtime'},
            'verifier_dependencies': {'owned': 'dependency'}, 'evidence': evidence,
            'evidence_sha256': {p.relative_to(root).as_posix(): validator.file_sha(p) for p in root.rglob('*') if p.is_file()}}
        return cfg, param, receipt

    def test_current_chain_accepts_and_changed_or_missing_evidence_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg, param, receipt = self.evidence(root)
            with patch.object(validator, 'ROOT', root), patch.object(validator, 'PARAM', param), patch.object(
                    validator, 'runtime_fingerprint', return_value=receipt['runtime_sha256']), patch.object(
                    validator, 'verifier_dependencies', return_value=receipt['verifier_dependencies']):
                checks = validator.verify_preflight_receipt(receipt, cfg)
                self.assertTrue(all(checks.values()), checks)
                for key in ('unit', 'counterexamples', 'fixture_manifest'):
                    modified = deepcopy(receipt)
                    modified['evidence_sha256'].pop(modified['evidence'][key])
                    self.assertFalse(all(validator.verify_preflight_receipt(modified, cfg).values()))
                modified = deepcopy(receipt)
                modified['evidence']['smoke_validations'] = []
                self.assertFalse(all(validator.verify_preflight_receipt(modified, cfg).values()))
                (root / 'ws/smoke/owned21/actor.csv').write_text('changed raw evidence')
                self.assertFalse(all(validator.verify_preflight_receipt(receipt, cfg).values()))


if __name__ == '__main__':
    unittest.main()
