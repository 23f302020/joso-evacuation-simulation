"""Independent sparse verifier contracts, without research outcome constants."""
import math
import random
import unittest
import json
import tempfile
import csv
import gzip
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


class NativeWalkingContracts(unittest.TestCase):
    def fixture(self, root, maximum=1., factor=.8):
        folder, inputs = root / 'run', root / 'inputs'
        folder.mkdir()
        inputs.mkdir()
        def table(path, records, fields=None):
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'wt', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields or list(records[0]))
                writer.writeheader()
                writer.writerows(records)
        (inputs / 'manifest.json').write_text(json.dumps({'depot_edge': 'a'}))
        (inputs / 'graphs.json').write_text(json.dumps({'passenger': {'nodes': {'a': {}, 'b': {}}, 'edges': [['a', 'b', {}]]}}))
        (inputs / 'bounded.net.xml').write_text('<net><edge id="a"><lane id="a_0" length="1" allow="pedestrian"/></edge><edge id="b"><lane id="b_0" length="30" allow="pedestrian"/></edge></net>')
        (folder / 'types.rou.xml').write_text('<routes><vType id="walk_type4" vClass="pedestrian" maxSpeed="' + str(maximum) + '"/></routes>')
        (folder / 'tripinfo.xml').write_text('<tripinfos><personinfo id="walker" type="walk_type4@walker" speedFactor="' + format(factor, '.2f') + '"/></tripinfos>')
        table(inputs / 'hazard.csv', [], ['edge_id', 'mode', 'closure_sec'])
        table(inputs / 'place_positions.csv', [{'kind': 'terminal', 'place_id': 'destination', 'pedestrian_pos_m': '20'}])
        table(inputs / 'terminals.csv', [{'terminal_id': 'destination', 'edge_id': 'b'}])
        table(inputs / 'origins.csv', [], ['origin_id', 'edge_id'])
        person = {'person_id': 'walker', 'person_type': 'type4', 'terminal_id': 'destination', 'initial_mode': 'walk',
                  'mode': 'walk', 'arrival_sec': '', 'walk_model_passed_m': '.2', 'walk_plan_length_m': '8', 'walk_budget_lead_m': '0'}
        table(folder / 'person_results.csv', [person])
        table(folder / 'vehicle_results.csv', [], ['vehicle_id', 'kind', 'status'])
        actors = [{'time_sec': str(t), 'actor_id': 'walker', 'kind': 'walk', 'road_id': 'a',
                   'observation_kind': 'onroad', 'lane_position_m': str(.2 + (t - .5) * .4),
                   'x': str(.2 + (t - .5) * .4), 'y': '0', 'speed_mps': '.4'} for t in (.5, 1., 1.5)]
        table(folder / 'actor_observations.csv.gz', actors)
        table(folder / 'transitions.csv.gz', [], ['time_upper_sec'])
        speed = {'enforced_stage_speed_mps': maximum, 'person_type_max_mps': maximum,
                 'person_max_mps': min(maximum, maximum * factor), 'person_speed_factor': factor,
                 'person_type_id': 'walk_type4@walker'}
        initial = {'event': 'walk_plan', 'person_id': 'walker', 'time_sec': 0., 'stage': 'initial',
                   'route': ['a', 'b'], 'depart_pos': 0., 'arrival_pos': 20., 'sumo_plan_length_m': 9.,
                   'model_passed_m': 0., 'speed_integral_m': 0., **speed}
        reroute = {**initial, 'time_sec': .5, 'stage': 'reroute', 'depart_pos': .2,
                   'sumo_plan_length_m': 8., 'previous_plan_m': 9., 'old_remaining_m': 8.8,
                   'signed_progress_m': 9. - 8.8, 'model_passed_m': 9. - 8.8, 'speed_integral_m': .2}
        def snapshot(length):
            return {'edge_id': 'a', 'lane_position_m': .2, 'xy': [.2, 0.], 'stage_edges': ['a', 'b'],
                    'stage_arrival_pos_m': 20., 'stage_length_m': length}
        reroute['replacement_receipts'] = [{'purpose': purpose, 'stage_index': 0, 'requested_edges': ['a', 'b'],
            'requested_depart_pos_m': .2, 'requested_arrival_pos_m': 20., 'before': snapshot(before), 'after': snapshot(after)}
            for purpose, before, after in [('old_remaining', 9., 8.8), ('new_route', 8.8, 8.)]]
        events = [initial, {'event': 'walk_departure', 'person_id': 'walker', 'time_sec': 0., 'route': ['a', 'b'], 'length_m': 9.},
                  reroute, {'event': 'walk_reroute', 'person_id': 'walker', 'time_sec': .5, 'route': ['a', 'b']}]
        warning = "Warning: Invalid departPos 20.00 given for person 'walker' walking from edge 'a'. Using edge end instead.\n"
        (folder / 'sumo_errors.log').write_text(warning * 2)
        counts = {k: 0 for k in ('transition_rows', 'closed_entry_rows', 'ambiguous_transitions', 'teleports', 'collisions',
                                 'missing_vehicle_subscriptions', 'missing_person_subscriptions')}
        manifest = {'input_directory': 'inputs', 'step_sec': .5, 'end_sec': 1.5, 'sumo_version': [22, 'SUMO 1.26.0'],
                    'summary': {'counts': counts, 'sumo_errors': {'bytes': (folder / 'sumo_errors.log').stat().st_size,
                    'warning_count': 2, 'error_count': 0, 'handled_route_rejection_count': 0, 'unhandled_error_count': 0,
                    'collision_teleport_count': 0, 'gridlock_teleport_count': 0}}}
        return folder, manifest, {'population': {'walk_mps': {'type4': maximum}, 'walk_limit_m': 100}}, events

    def test_native_getter_factor_below_equal_above_one_and_type_speeds(self):
        for maximum in (.58, 1.):
            for factor in (.8, 1., 1.2):
                with self.subTest(maximum=maximum, factor=factor), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    folder, manifest, cfg, events = self.fixture(root, maximum, factor)
                    with patch.object(validator, 'ROOT', root):
                        report = validator.audit_movement_events(folder, manifest, cfg, events)
                    self.assertEqual(report['status'], 'PASS', report)

    def test_independent_stage_type_getter_factor_and_integral_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder, manifest, cfg, events = self.fixture(root)
            changes = [('person_max_mps', .9), ('person_type_max_mps', 2.), ('person_speed_factor', .9),
                       ('enforced_stage_speed_mps', 2.), ('speed_integral_m', 0.), ('old_remaining_m', 7.)]
            for key, value in changes:
                altered = deepcopy(events)
                altered[2][key] = value
                with self.subTest(key=key), patch.object(validator, 'ROOT', root):
                    self.assertEqual(validator.audit_movement_events(folder, manifest, cfg, altered)['status'], 'INVALID')
            (folder / 'types.rou.xml').write_text('<routes><vType id="walk_type4" vClass="pedestrian" maxSpeed="1" desiredMaxSpeed=".9"/></routes>')
            with patch.object(validator, 'ROOT', root):
                self.assertFalse(validator.audit_movement_events(folder, manifest, cfg, events)['checks']['walk_native_speed_contract'])

    def test_replacement_receipt_step_route_position_length_and_count_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder, manifest, cfg, events = self.fixture(root)
            for mutate in (lambda e: e['replacement_receipts'].pop(),
                           lambda e: e['replacement_receipts'][0]['after'].__setitem__('xy', [0., 0.]),
                           lambda e: e['replacement_receipts'][1]['after'].__setitem__('stage_length_m', 7.),
                           lambda e: e['replacement_receipts'][1].__setitem__('requested_edges', ['a']),
                           lambda e: e.__setitem__('time_sec', 1.)):
                altered = deepcopy(events)
                mutate(altered[2])
                with patch.object(validator, 'ROOT', root):
                    self.assertFalse(validator.audit_movement_events(folder, manifest, cfg, altered)['checks']['walk_stage_budget_recurrence'])

    def test_warning_requires_exact_receipts_native_version_and_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder, manifest, cfg, events = self.fixture(root)
            with patch.object(validator, 'ROOT', root):
                movement = validator.audit_movement_events(folder, manifest, cfg, events)
                audit = lambda m=manifest, proof=movement: validator.audit_native_logs(folder, m, events, {'removal_observations': {}}, proof)
                self.assertEqual(audit()['status'], 'PASS')
                self.assertEqual(audit(proof=None)['status'], 'INVALID')
                self.assertEqual(audit(m={**manifest, 'sumo_version': [22, 'SUMO 1.25.0']})['status'], 'INVALID')
                original = (folder / 'sumo_errors.log').read_text()
                for text in (original.splitlines()[0] + '\n', original + original,
                             original.replace("edge 'a'", "edge 'b'"), original.replace('20.00', '19.99'),
                             original + "Warning: Vehicle 'car' performs emergency braking.\n",
                             original + "Warning: Vehicle 'car' performs emergency stop.\n"):
                    (folder / 'sumo_errors.log').write_text(text)
                    self.assertFalse(audit()['checks']['all_warnings_evidence_classified'])

    def test_vehicle_first_turn_recomputed_from_lane_actor_graph_and_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder, manifest, cfg, _ = self.fixture(root)
            inputs = root / 'inputs'
            (inputs / 'graphs.json').write_text(json.dumps({'passenger': {'nodes': {'a': {}, 'b': {}, 'c': {}},
                'edges': [['a', 'b', {}], ['a', 'c', {}], ['c', 'b', {}]]}}))
            (inputs / 'bounded.net.xml').write_text('<net><edge id="a"><lane id="a_0" length="10" allow="pedestrian"/>'
                '<lane id="a_1" length="10" allow="passenger"/><lane id="a_2" length="10" allow="passenger"/></edge>'
                '<edge id="b"><lane id="b_1" length="30" allow="passenger"/></edge>'
                '<edge id="c"><lane id="c_1" length="20" allow="passenger"/></edge>'
                '<connection from="a" to="b" fromLane="2" toLane="1"/>'
                '<connection from="a" to="c" fromLane="1" toLane="1"/>'
                '<connection from="c" to="b" fromLane="1" toLane="1"/></net>')
            def table(path, records):
                opener = gzip.open if path.suffix == '.gz' else open
                with opener(path, 'wt', encoding='utf-8', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(records[0]))
                    writer.writeheader()
                    writer.writerows(records)
            table(folder / 'person_results.csv', [{'person_id': 'driver', 'vehicle_id': 'car', 'terminal_id': 'destination',
                'initial_mode': 'car', 'mode': 'car', 'arrival_sec': '', 'walk_model_passed_m': '0',
                'walk_plan_length_m': '0', 'walk_budget_lead_m': '0'}])
            table(folder / 'vehicle_results.csv', [{'vehicle_id': 'car', 'kind': 'car', 'status': 'time_limit'}])
            table(inputs / 'place_positions.csv', [{'kind': 'terminal', 'place_id': 'destination', 'car_pos_m': '20'}])
            actors = [{'time_sec': str(t), 'actor_id': 'car', 'kind': 'car', 'road_id': 'a', 'lane_id': 'a_1',
                'observation_kind': 'onroad', 'route_index': '0', 'lane_position_m': '9',
                'speed_mps': '4', 'decel_mps2': '2', 'stop_state': '0'} for t in (.5, 1., 1.5)]
            table(folder / 'actor_observations.csv.gz', actors)
            feasibility = {'event': 'vehicle_route_feasibility', 'vehicle_id': 'car', 'time_sec': .5,
                'source_kind': 'onroad_lane', 'source_reference_lane_id': 'a_1', 'native_parking_stop': None,
                'native_source': {'road_id': 'a', 'lane_id': 'a_1', 'lane_position_m': 9., 'speed_mps': 4.,
                    'decel_mps2': 2., 'stop_state': 0, 'route': ['a', 'b'], 'route_index': 0},
                'source_edge': 'a', 'source_lane_id': 'a_1', 'source_lane_position_m': 9., 'source_lane_length_m': 10.,
                'remaining_lane_m': 1., 'source_speed_mps': 4., 'source_decel_mps2': 2., 'step_sec': .5,
                'stopped': False, 'braking_room_m': 7., 'first_turn_constrained': True,
                'open_lane_successors': ['c'], 'requested_remaining_route': ['a', 'c', 'b'],
                'target_edge': 'b', 'target_position_m': 20.}
            events = [{'event': 'private_departure_requested', 'vehicle_id': 'car', 'time_sec': 0., 'route': ['a', 'b']},
                feasibility, {'event': 'private_reroute', 'vehicle_id': 'car', 'time_sec': .5, 'route': ['a', 'c', 'b'],
                'requested_remaining_route': ['a', 'c', 'b'], 'source_edge': 'a', 'source_lane_position': 9.}]
            with patch.object(validator, 'ROOT', root):
                baseline = validator.audit_movement_events(folder, manifest, cfg, events)
                self.assertEqual(baseline['status'], 'PASS', baseline)
                for key, value in [('first_turn_constrained', False), ('open_lane_successors', ['b', 'c']),
                                   ('braking_room_m', 0.), ('source_speed_mps', 0.), ('target_edge', 'c'),
                                   ('target_position_m', 19.), ('source_decel_mps2', 0.)]:
                    changed = deepcopy(events)
                    changed[1][key] = value
                    with self.subTest(key=key):
                        self.assertFalse(validator.audit_movement_events(folder, manifest, cfg, changed)['checks']['vehicle_first_turn_feasibility'])
                for omit, route in [(True, None), (False, ['a', 'b']), (False, [])]:
                    changed = deepcopy(events)
                    if omit:
                        changed.pop(1)
                    else:
                        changed[1]['requested_remaining_route'] = route
                        changed[2]['route'] = changed[2]['requested_remaining_route'] = route
                        if not route:
                            changed[2] = {'event': 'actor_removed', 'actor_id': 'car', 'mode': 'passenger',
                                          'reason': 'route_cut', 'time_sec': .5}
                    self.assertFalse(validator.audit_movement_events(folder, manifest, cfg, changed)['checks']['vehicle_first_turn_feasibility'])
                table(inputs / 'hazard.csv', [{'edge_id': 'c', 'mode': 'passenger', 'closure_sec': '1'}])
                self.assertFalse(validator.audit_movement_events(folder, manifest, cfg, events)['checks']['vehicle_first_turn_feasibility'])

    def test_parked_source_recomputed_from_actor_stop_net_and_prior_stop_target(self):
        actor = {'time_sec': '3', 'road_id': 'a', 'lane_id': '', 'lane_position_m': '9.95',
                 'speed_mps': '0', 'decel_mps2': '4.5', 'stop_state': '3', 'route_index': '1',
                 'observation_kind': 'parked', 'native_stop_lane_id': 'a_1',
                 'native_stop_start_pos_m': '9.9', 'native_stop_end_pos_m': '10', 'native_stop_flags': '1'}
        event = {'time_sec': 3., 'source_lane_id': '', 'source_kind': 'parked_stop',
                 'source_reference_lane_id': 'a_1', 'native_source': {'road_id': 'a', 'lane_id': '',
                     'lane_position_m': 9.95, 'speed_mps': 0., 'decel_mps2': 4.5,
                     'stop_state': 3, 'route': ['old', 'a'], 'route_index': 1},
                 'native_parking_stop': {'lane_id': 'a_1', 'start_pos_m': 9.9, 'end_pos_m': 10., 'flags': 1}}
        lanes = {'a_1': ('a', {'length': '10', 'allow': 'passenger'})}
        audit = lambda e=event, a=actor, pos=10.: validator.vehicle_source_contract(e, a, lanes, ['old', 'a'], pos)
        self.assertTrue(audit())
        for key, value in [('lane_id', 'a_1'), ('stop_state', '1'), ('speed_mps', '.1'),
                           ('native_stop_lane_id', 'unknown'), ('native_stop_flags', '0'),
                           ('native_stop_end_pos_m', '9.9'), ('lane_position_m', '10.1'),
                           ('observation_kind', 'missing')]:
            with self.subTest(key=key):
                self.assertFalse(audit(a={**actor, key: value}))
        self.assertFalse(audit(pos=9.))
        self.assertFalse(audit(e={**event, 'native_parking_stop': None}))
        self.assertFalse(audit(e={**event, 'source_reference_lane_id': 'unknown'}))
        for key, value in [('stop_state', 1), ('speed_mps', .1), ('lane_position_m', 9.8)]:
            changed = deepcopy(event)
            changed['native_source'][key] = value
            self.assertFalse(audit(changed, {**actor, key: str(value)}))
        changed = deepcopy(event)
        changed['native_parking_stop']['start_pos_m'] = 9.99
        changed_actor = {**actor, 'native_stop_start_pos_m': '9.99'}
        self.assertFalse(audit(changed, changed_actor))


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
                (root / ('ws/smoke/owned' + str(len(validator.REQUIRED_FIXTURE_CASES))) / 'actor.csv').write_text('changed raw evidence')
                self.assertFalse(all(validator.verify_preflight_receipt(receipt, cfg).values()))


if __name__ == '__main__':
    unittest.main()
