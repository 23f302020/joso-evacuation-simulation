"""Artificial observation contracts; no evacuation outcome constants."""
import ast
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import unittest
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


if __name__ == '__main__':
    unittest.main()
