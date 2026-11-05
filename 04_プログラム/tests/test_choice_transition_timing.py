"""Artificial observation contracts; no evacuation outcome constants."""
import ast
import csv
import gzip
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch
import xml.etree.ElementTree as ET

from scripts import jdrt_realtime_choice as runtime
from scripts import jdrt_realtime_choice_validate as validator


def network(extra_internal=False, allow=None):
    permission = '' if allow is None else ' allow="' + allow + '"'
    more_edge = '<edge id=":out_1"><lane id=":out_1_0"/></edge>' if extra_internal else ''
    outgoing = ('<connection from=":out_0" to="b" fromLane="0" toLane="0" via=":out_1_0"/>'
                '<connection from=":out_1" to="b" fromLane="0" toLane="0"/>') if extra_internal else (
                '<connection from=":out_0" to="b" fromLane="0" toLane="0"/>')
    return ET.fromstring('''<net>
        <edge id="a"><lane id="a_0"/></edge>
        <edge id="short"><lane id="short_0"''' + permission + '''/></edge>
        <edge id="b"><lane id="b_0"/></edge>
        <edge id=":in_0"><lane id=":in_0_0"/></edge>
        <edge id=":out_0"><lane id=":out_0_0"/></edge>''' + more_edge + '''
        <connection from="a" to="short" fromLane="0" toLane="0" via=":in_0_0"/>
        <connection from=":in_0" to="short" fromLane="0" toLane="0"/>
        <connection from="short" to="b" fromLane="0" toLane="0" via=":out_0_0"/>
        ''' + outgoing + '</net>')


def frame(now, road, index):
    return {'time_sec': str(now), 'road_id': road, 'lane_id': road + '_0',
            'route_index': str(index), 'route_version': '0'}


class TransitionTimingTests(unittest.TestCase):
    def test_forward_and_reverse_internal_proofs_cover_each_chain_lane(self):
        net = network(extra_internal=True)
        forward = runtime.passenger_transition_links(net)
        reverse = validator.native_transition_backlinks(net)
        for lane in (':out_0_0', ':out_1_0'):
            road = lane.rsplit('_', 1)[0]
            row = frame(.5, road, 1)
            self.assertEqual(runtime.passenger_transition_source(['a', 'short', 'b'], road, lane, 1, forward), 'short')
            self.assertEqual(validator.verified_internal_source(['a', 'short', 'b'], row, reverse), 'short')

    def test_internal_before_short_edge_does_not_claim_it_passed(self):
        net = network()
        self.assertEqual(runtime.passenger_transition_source(['a', 'short', 'b'], ':in_0', ':in_0_0', 0,
                                                            runtime.passenger_transition_links(net)), 'a')
        self.assertEqual(validator.verified_internal_source(['a', 'short', 'b'], frame(.5, ':in_0', 0),
                                                           validator.native_transition_backlinks(net)), 'a')

    def test_occurrence_index_not_first_occurrence_of_repeated_edge(self):
        net = network()
        path = ['short', 'a', 'short', 'b']
        self.assertEqual(runtime.passenger_transition_source(path, ':out_0', ':out_0_0', 2,
                                                            runtime.passenger_transition_links(net)), 'short')
        self.assertEqual(validator.verified_internal_source(path, frame(.5, ':out_0', 2),
                                                           validator.native_transition_backlinks(net)), 'short')

    def test_unknown_or_incompatible_internal_proof_fails_closed(self):
        net = network()
        for road, index in ((':unknown_0', 1), (':out_0', 0), (':out_0', 2)):
            with self.subTest(road=road, index=index):
                with self.assertRaises(RuntimeError):
                    runtime.passenger_transition_source(['a', 'short', 'b'], road, road + '_0', index,
                                                        runtime.passenger_transition_links(net))
                with self.assertRaises(ValueError):
                    validator.verified_internal_source(['a', 'short', 'b'], frame(.5, road, index),
                                                       validator.native_transition_backlinks(net))

    def test_allow_all_is_passenger_but_pedestrian_only_is_not(self):
        self.assertIn(':out_0_0', runtime.passenger_transition_links(network(allow='all')))
        self.assertNotIn(':out_0_0', runtime.passenger_transition_links(network(allow='pedestrian')))
        with self.assertRaises(ValueError):
            validator.verified_internal_source(['a', 'short', 'b'], frame(.5, ':out_0', 1),
                                               validator.native_transition_backlinks(network(allow='pedestrian')))

    def generated(self, internal_upper, closure, skip_internal=False):
        source = ast.parse(Path(runtime.__file__).read_text(encoding='utf-8-sig'))
        definition = next(n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name == 'observe_transition')
        rows = []
        context = {'last': {}, 'latest_v': {}, 'tc': SimpleNamespace(VAR_ROUTE_INDEX='index'),
                   'vehicles': {'actor': {'status': 'travelling'}},
                   'true_times': {('short', 'passenger'): closure},
                   'transitions': SimpleNamespace(writerow=rows.append), 'counts': Counter()}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<actual runtime observer>', 'exec'), context)
        route = ['a', 'short', 'b']
        links = runtime.passenger_transition_links(network())
        for now, road, index in ((0, 'a', 0), (internal_upper, ':out_0', 1), (internal_upper + 1, 'b', 2)):
            context['latest_v']['actor'] = {'index': index}
            if skip_internal and road.startswith(':'):
                continue
            external = runtime.passenger_transition_source(route, road, road + '_0', index, links)
            context['observe_transition']('actor', 'passenger', external, now, route)
        return rows

    def test_actual_producer_gives_short_edge_early_upper(self):
        rows = self.generated(.5, 1)
        target = next(r for r in rows if r['to_edge'] == 'short')
        self.assertEqual((target['time_upper_sec'], target['kind']), (.5, 'transition'))

    def test_actual_late_and_exact_boundary_are_still_closed(self):
        for upper in (1, 1.5):
            with self.subTest(upper=upper):
                target = next(r for r in self.generated(upper, 1) if r['to_edge'] == 'short')
                self.assertEqual(target['kind'], 'closed_entry')

    def test_external_only_mutant_violates_independent_topological_bound(self):
        correct = next(r for r in self.generated(.5, 1) if r['to_edge'] == 'short')
        mutated = next(r for r in self.generated(.5, 1, skip_internal=True) if r['to_edge'] == 'short')
        # Outgoing internal is already observed at .5 in the artificial input.
        self.assertLessEqual(correct['time_upper_sec'], .5)
        self.assertGreater(mutated['time_upper_sec'], .5)
        self.assertNotEqual(correct['kind'], mutated['kind'])

    def test_native_arrival_explicit_final_index_is_not_previous_subscription(self):
        source = ast.parse(Path(runtime.__file__).read_text(encoding='utf-8-sig'))
        definition = next(n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name == 'observe_transition')
        rows = []
        context = {'last': {'actor': ('a', 0, 0)}, 'latest_v': {'actor': {'index': 0}},
                   'tc': SimpleNamespace(VAR_ROUTE_INDEX='index'), 'vehicles': {'actor': {'status': 'travelling'}},
                   'true_times': {}, 'transitions': SimpleNamespace(writerow=rows.append), 'counts': Counter()}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<actual runtime observer>', 'exec'), context)
        context['observe_transition']('actor', 'passenger', 'b', .5, ['a', 'short', 'b'], observed_index=2)
        self.assertEqual([r['to_edge'] for r in rows], ['short', 'b'])
        self.assertTrue(all(not r['ambiguous'] for r in rows))


class NativeTransitionFixtureTests(unittest.TestCase):
    def test_native_outgoing_frame_rejects_shared_external_only_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, output = root / 'inputs', root / 'execution'
            inputs.mkdir(); output.mkdir()
            net = network()
            for element in net.iter():
                for key, value in list(element.attrib.items()):
                    for old, new in (('short', 'e1'), ('a', 'e0'), ('b', 'e2')):
                        if value == old or value.startswith(old + '_'):
                            value = new + value[len(old):]
                            break
                    element.set(key, value)
            ET.ElementTree(net).write(inputs / 'bounded.net.xml')
            actors = [dict(frame(.5, 'e0', 0), actor_id='car', kind='car'),
                      dict(frame(1, ':out_0', 1), actor_id='car', kind='car'),
                      dict(frame(2.5, 'e2', 2), actor_id='car', kind='car')]
            with gzip.open(output / 'actor_observations.csv.gz', 'wt', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(actors[0])); writer.writeheader(); writer.writerows(actors)
            def transitions(upper):
                row = dict(time_lower_sec=.5, time_upper_sec=upper, actor_id='car', mode='passenger',
                           from_edge='e0', to_edge='e1', ambiguous=False, kind='transition')
                with gzip.open(output / 'transitions.csv.gz', 'wt', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
            ET.ElementTree(ET.fromstring('<tripinfos><tripinfo id="car" arrival="3"/></tripinfos>')).write(output / 'tripinfo.xml')
            events = [dict(event='private_departure_requested', vehicle_id='car', route=['e0', 'e1', 'e2'], time_sec=0)]
            source = dict(fixture_case='car_transition_calibration')
            with patch.object(validator, 'ROOT', root):
                transitions(1)
                good = validator.audit_transition_fixture(output, dict(input_directory='inputs'), {}, events, source)
                self.assertEqual(good['status'], 'PASS', good)
                transitions(2.5)
                bad = validator.audit_transition_fixture(output, dict(input_directory='inputs'), {}, events, source)
                self.assertEqual(bad['status'], 'INVALID', bad)
                self.assertFalse(bad['checks']['short_entry_upper_is_first_outgoing_frame'])
                # Vehicle tripinfo labels the start of the final .5s movement;
                # controller/native-arrival events label its end.
                with gzip.open(output / 'actor_observations.csv.gz', 'wt', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(actors[0])); writer.writeheader(); writer.writerows(actors[:-1])
                transitions(1)
                final = dict(time_lower_sec=1, time_upper_sec=3.5, actor_id='car', mode='passenger',
                             from_edge='e1', to_edge='e2', ambiguous=False, kind='transition')
                with gzip.open(output / 'transitions.csv.gz', 'at', newline='') as stream:
                    csv.DictWriter(stream, fieldnames=list(final)).writerow(final)
                arrival = validator.audit_transition_fixture(output, dict(input_directory='inputs', step_sec=.5), {},
                                                            events, dict(fixture_case='car_transition_arrival'))
                self.assertEqual(arrival['status'], 'PASS', arrival)


class NativeArrivalTailTests(unittest.TestCase):
    def topology(self):
        net = network()
        lengths = {'a': 10, 'short': .1, 'b': .1, ':in_0': 3, ':out_0': 5}
        for edge in net.findall('edge'):
            edge.find('lane').set('length', str(lengths[edge.attrib['id']]))
        return validator.native_arrival_topology(net)

    def test_native_internal_tail_and_multiple_skipped_externals(self):
        lanes, reverse = self.topology()
        path = ['a', 'short', 'b']
        row = dict(frame(1, ':out_0', 1), lane_position_m='4.8')
        trip = dict(arrivalLane='b_0', arrivalPos='.05')
        tail = validator.arrival_tail_distance(lanes, reverse, path, row, trip)
        self.assertAlmostEqual(tail['distance_m'], .25)
        self.assertEqual(tail['lane_path'], [':out_0_0', 'b_0'])
        before = dict(frame(1, 'a', 0), lane_position_m='9.9')
        self.assertAlmostEqual(validator.arrival_tail_distance(lanes, reverse, path, before, trip)['distance_m'], 8.25)

    def test_wrong_occurrence_or_missing_endpoint_is_not_proof(self):
        lanes, reverse = self.topology()
        for index, lane in ((0, 'b_0'), (1, 'unknown')):
            with self.subTest(index=index, lane=lane), self.assertRaises(ValueError):
                validator.arrival_tail_distance(lanes, reverse, ['a', 'short', 'b'],
                    dict(frame(1, ':out_0', index), lane_position_m='4.8'),
                    dict(arrivalLane=lane, arrivalPos='.05'))

    def test_different_possible_internal_lengths_are_rejected(self):
        lanes, reverse = self.topology()
        lanes[':out_0_0'] = (':out_0', 5., {'b_0', ':extra_0_0'})
        lanes[':extra_0_0'] = (':extra_0', 1., {'b_0'})
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            validator.arrival_tail_distance(lanes, reverse, ['a', 'short', 'b'],
                dict(frame(1, ':out_0', 1), lane_position_m='4.8'), dict(arrivalLane='b_0', arrivalPos='.05'))


if __name__ == '__main__':
    unittest.main()
