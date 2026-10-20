"""Fail-closed runtime contracts without using observed evacuation outcomes."""
from pathlib import Path
import tempfile
import unittest
import json
from unittest.mock import patch, Mock
import sys
import types
import math
import csv
import gzip
import networkx as nx

from scripts import jdrt_realtime_choice as runtime


class RuntimeContracts(unittest.TestCase):
    def test_smoke_shortening_preserves_whole_vehicle_readiness(self):
        people = [{'person_id': 'driver', 'vehicle_id': 'car'},
                  {'person_id': 'walker', 'vehicle_id': ''},
                  {'person_id': 'passenger', 'vehicle_id': 'car'},
                  {'person_id': 'other_driver', 'vehicle_id': 'other'}]
        before = [dict(p) for p in people]
        ready = runtime.technical_ready_times(people)
        self.assertEqual(ready['driver'], ready['passenger'])
        self.assertNotEqual(ready['walker'], ready['driver'])
        self.assertNotEqual(ready['other_driver'], ready['driver'])
        self.assertTrue(all(0 <= value < 10 for value in ready.values()))
        self.assertEqual(before, people)

    def test_fixture_inputs_cannot_be_passed_to_core_or_smoke(self):
        parameters = {'workspace': 'isolated'}
        with patch.object(runtime, 'load_inputs', return_value=(parameters, Path('.'), {})):
            for purpose in ('core', 'smoke'):
                with self.assertRaisesRegex(ValueError, 'cannot enter'):
                    runtime.run('c', 'blocked', purpose=purpose, fixture_directory=Path('.'))

    def test_fixture_cannot_read_an_arbitrary_input_directory(self):
        parameters = {'workspace': 'isolated'}
        with patch.object(runtime, 'load_inputs', return_value=(parameters, Path('.'), {})):
            with self.assertRaisesRegex(ValueError, 'isolated'):
                runtime.run('c', 'blocked', purpose='fixture', fixture_directory=Path('.'))

    def test_fixture_must_use_separate_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'isolated/technical/id/fixture_inputs'
            folder.mkdir(parents=True)
            parameters = {'protocol': 'realtime_choice_v1', 'workspace': 'isolated',
                          'execution': {'implementation_files': []}}
            (folder / 'fixture_parameters.json').write_text(json.dumps(parameters), encoding='utf-8')
            with patch.object(runtime, 'ROOT', root), patch.object(runtime, 'load_inputs', return_value=(parameters, root, {})):
                with self.assertRaisesRegex(ValueError, 'fixture protocol'):
                    runtime.run('c', 'id', purpose='fixture', fixture_directory=folder)
            self.assertFalse((folder.parent / 'execution').exists())

    def test_positioned_car_partial_edges_and_backward_cycle(self):
        graph = nx.DiGraph()
        graph.add_node('a', length=100, free_sec=10)
        graph.add_node('b', length=200, free_sec=20)
        graph.add_edge('a', 'b')
        self.assertEqual(runtime.positioned_car_route(graph, 'a', 'b', 80, 30), (['a', 'b'], 5))
        self.assertEqual(runtime.positioned_car_route(graph, 'a', 'a', 20, 80), (['a'], 6))
        self.assertEqual(runtime.positioned_car_route(graph, 'a', 'a', 80, 20), ([], math.inf))
        graph.add_edge('b', 'a')
        self.assertEqual(runtime.positioned_car_route(graph, 'a', 'a', 80, 20), (['a', 'b', 'a'], 24))
        self.assertEqual(runtime.positioned_car_route(graph, 'a', 'a', 20, 21, minimum_advance=5)[0], ['a', 'b', 'a'])

    def test_positioned_walk_reverse_and_cross_edge_and_closed_endpoint(self):
        graph = nx.Graph()
        graph.add_edge(('a', 0), ('a', 1), length=100)
        graph.add_edge(('b', 0), ('b', 1), length=200)
        graph.add_edge(('a', 1), ('b', 0), length=0)
        original = set(graph)
        self.assertEqual(runtime.positioned_walk_route(graph, 'a', 'a', 80, 20), (['a'], 60))
        self.assertEqual(runtime.positioned_walk_route(graph, 'a', 'b', 80, 30), (['a', 'b'], 50))
        self.assertEqual(runtime.positioned_walk_route(graph, 'b', 'a', 30, 80), (['b', 'a'], 50))
        self.assertEqual(set(graph), original)
        graph.remove_nodes_from([('b', 0), ('b', 1)])
        self.assertEqual(runtime.positioned_walk_route(graph, 'a', 'b', 80, 30), ([], math.inf))
        with self.assertRaisesRegex(ValueError, 'outside'):
            runtime.positioned_walk_route(graph, 'a', 'a', 101, 10)

    def test_short_lane_uses_connected_detour_instead_of_adjacent_lane_turn(self):
        graph = self.lane_turn_graph()
        path, _, receipt = runtime.lane_constrained_car_route(
            graph, 'a', 'goal', 9.5, 5, 10, ['safe'], 10, 5, .5)
        self.assertEqual(path, ['a', 'safe', 'goal'])
        self.assertTrue(receipt['first_turn_constrained'])
        self.assertEqual(receipt['open_lane_successors'], ['safe'])
        self.assertEqual(runtime.positioned_car_route(graph, 'a', 'goal', 9.5, 5)[0],
                         ['a', 'adjacent_turn', 'goal'])

    @staticmethod
    def lane_turn_graph():
        graph = nx.DiGraph()
        for edge, cost in [('a', 1), ('adjacent_turn', 1), ('safe', 4), ('goal', 1)]:
            graph.add_node(edge, length=10, free_sec=cost)
        graph.add_edges_from([('a', 'adjacent_turn'), ('a', 'safe'),
                              ('adjacent_turn', 'goal'), ('safe', 'goal')])
        return graph

    def test_short_lane_closed_or_unconnected_detours_are_not_usable(self):
        for successors in ([], ['closed', 'pedestrian_only']):
            path, cost, receipt = runtime.lane_constrained_car_route(
                self.lane_turn_graph(), 'a', 'goal', 9.5, 5, 10, successors, 10, 5, .5)
            self.assertEqual(path, [])
            self.assertEqual(cost, math.inf)
            self.assertEqual(receipt['open_lane_successors'], [])

    def test_lane_braking_boundary_before_equal_after_and_step_effect(self):
        graph = self.lane_turn_graph()
        # v=2, decel=2, dt=.5 gives existing room 1+1+1=3m.
        for position, constrained in [(7.000001, True), (7, False), (6.999999, False)]:
            path, _, receipt = runtime.lane_constrained_car_route(
                graph, 'a', 'goal', position, 5, 10, ['safe'], 2, 2, .5)
            self.assertEqual(receipt['first_turn_constrained'], constrained)
            self.assertEqual(path[1], 'safe' if constrained else 'adjacent_turn')
        _, _, receipt = runtime.lane_constrained_car_route(
            graph, 'a', 'goal', 7, 5, 10, ['safe'], 2, 2, 1)
        self.assertTrue(receipt['first_turn_constrained'])

    def test_stopped_and_long_room_routes_allow_native_lane_planning(self):
        for position, speed, stopped in [(9.5, 0, True), (0, 2, False), (8, .1, False)]:
            path, _, receipt = runtime.lane_constrained_car_route(
                self.lane_turn_graph(), 'a', 'goal', position, 5, 10, ['safe'], speed, 2, .5, stopped)
            self.assertFalse(receipt['first_turn_constrained'])
            self.assertEqual(path[1], 'adjacent_turn')

    def test_parked_empty_lane_uses_only_native_stop_reference(self):
        connection, net = Mock(), Mock()
        vehicle = connection.vehicle
        for method, value in [('getRoadID', 'a'), ('getLaneID', ''), ('getLanePosition', 9.95),
                              ('getSpeed', 0.), ('getDecel', 4.5), ('getStopState', 3),
                              ('getRoute', ('old', 'a')), ('getRouteIndex', 1)]:
            getattr(vehicle, method).return_value = value
        stop = types.SimpleNamespace(lane='a_1', startPos=9.9, endPos=10., stopFlags=1)
        vehicle.getStops.return_value = (stop,)
        lane = net.getLane.return_value
        lane.getLength.return_value = 10.
        lane.getEdge.return_value.getID.return_value = 'a'
        lane.allows.return_value = True
        _, receipt = runtime.vehicle_path_source(connection, 'v', net)
        self.assertEqual(receipt['source_kind'], 'parked_stop')
        self.assertEqual(receipt['native_source']['lane_id'], '')
        self.assertEqual(receipt['source_reference_lane_id'], 'a_1')
        net.getLane.assert_called_once_with('a_1')
        for method, value in [('getStopState', 1), ('getStopState', 0), ('getSpeed', .1),
                              ('getLanePosition', 9.8), ('getLanePosition', 10.1),
                              ('getRoadID', 'other'), ('getRoute', ('a', 'other'))]:
            getter = getattr(vehicle, method)
            original = getter.return_value
            getter.return_value = value
            with self.subTest(method=method, value=value), self.assertRaises(ValueError):
                runtime.vehicle_path_source(connection, 'v', net)
            getter.return_value = original
        vehicle.getStops.return_value = ()
        with self.assertRaisesRegex(ValueError, 'lacks its native'):
            runtime.vehicle_path_source(connection, 'v', net)
        vehicle.getStops.return_value = (stop,)
        stop.stopFlags = 0
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            runtime.vehicle_path_source(connection, 'v', net)
        stop.stopFlags = 1
        lane.allows.return_value = False
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            runtime.vehicle_path_source(connection, 'v', net)
        lane.allows.return_value = True
        vehicle.getLaneID.return_value = 'a_1'
        vehicle.getStopState.return_value = 0
        vehicle.getStops.reset_mock()
        _, receipt = runtime.vehicle_path_source(connection, 'v', net)
        self.assertEqual(receipt['source_kind'], 'onroad_lane')
        self.assertIsNone(receipt['native_parking_stop'])
        vehicle.getStops.assert_not_called()

    def test_constrained_same_edge_backward_cycle_retains_forward_motion(self):
        graph = self.lane_turn_graph()
        graph.add_edge('safe', 'a')
        path, cost, _ = runtime.lane_constrained_car_route(
            graph, 'a', 'a', 9.5, 1, 10, ['safe'], 10, 5, .5)
        self.assertEqual(path, ['a', 'safe', 'a'])
        self.assertGreater(cost, 0)
        graph.remove_edge('safe', 'a')
        self.assertEqual(runtime.lane_constrained_car_route(
            graph, 'a', 'a', 9.5, 1, 10, ['safe'], 10, 5, .5)[0], [])

    def test_walk_replacement_receipt_records_native_api_arguments_and_positions(self):
        connection = Mock()
        before = types.SimpleNamespace(edges=['a', 'old'], arrivalPos=30, length=80)
        after = types.SimpleNamespace(edges=['a', 'new'], arrivalPos=30, length=90)
        requested = types.SimpleNamespace(edges=['a', 'new'], departPos=8, arrivalPos=30)
        connection.person.getStage.side_effect = [before, after]
        connection.person.getRoadID.return_value = 'a'
        connection.person.getLanePosition.return_value = 8
        connection.person.getPosition.return_value = (4, 5)
        receipt = runtime.replace_walk_stage_receipt(connection, 'p', 0, requested, 'new_route')
        self.assertEqual(receipt['before']['stage_edges'], ['a', 'old'])
        self.assertEqual(receipt['after']['stage_length_m'], 90)
        self.assertEqual(receipt['requested_depart_pos_m'], 8)
        connection.person.replaceStage.assert_called_once_with('p', 0, requested)

    def test_walk_replacement_receipt_rejects_native_position_change(self):
        connection = Mock()
        stage = types.SimpleNamespace(edges=['a'], departPos=8, arrivalPos=30, length=10)
        connection.person.getStage.return_value = stage
        connection.person.getRoadID.return_value = 'a'
        connection.person.getLanePosition.side_effect = [8, 0]
        connection.person.getPosition.return_value = (4, 5)
        with self.assertRaisesRegex(RuntimeError, 'moved the person'):
            runtime.replace_walk_stage_receipt(connection, 'p', 0, stage, 'new_route')

    def test_walk_calibration_uses_shared_native_interior_frame_and_rejects_sha_change(self):
        from scripts import jdrt_choice_fixtures as fixtures
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            execution, inputs = root / 'case/execution', root / 'case/fixture_inputs'
            execution.mkdir(parents=True)
            inputs.mkdir()
            (inputs / 'graphs.json').write_text(json.dumps({'pedestrian': {'nodes': {'d0': {'length': 10}}}}))
            runtime.write_csv(execution / 'person_results.csv', [{'person_id': 'a'}, {'person_id': 'b'}])
            fields = ['actor_id', 'time_sec', 'speed_mps', 'lane_position_m', 'road_id']
            with gzip.open(execution / 'actor_observations.csv.gz', 'wt', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for pid, at, position in [('a', 1.5, 5), ('b', 2.5, 5), ('a', 3.5, 5), ('b', 3.5, 5)]:
                    writer.writerow(dict(zip(fields, [pid, at, 1, position, 'd0'])))
            outputs = {p.name: runtime.sha(p) for p in execution.iterdir()}
            (execution / 'manifest.json').write_text(json.dumps({'status': 'COMPLETED', 'purpose': 'fixture',
                'run_id': 'calibration', 'output_sha256': outputs}))
            with patch.object(fixtures, 'ROOT', root):
                reference = fixtures.native_walk_reference(execution, .5)
                self.assertEqual(reference['source_time_sec'], 3.5)
                self.assertEqual(reference['closure_sec'], 4)
                self.assertEqual(set(reference['source_frames']), {'a', 'b'})
                (execution / 'person_results.csv').write_text('person_id\na\n')
                with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                    fixtures.native_walk_reference(execution, .5)

    def test_car_fixture_connections_use_passenger_lanes_after_sidewalk_insertion(self):
        from scripts import jdrt_choice_fixtures as fixtures
        lanes = {}
        for edge in ('g0', 'e0', 'e1', 'e2', 'd0', 'd1', 'd2', 's0', 's1'):
            for index in range(3 if edge in ('g0', 'e0') else 2):
                lane = Mock()
                lane.getID.return_value = f'{edge}_{index}'
                lane.getEdge.return_value.getID.return_value = edge
                lane.allows.return_value = index > 0
                lane.getOutgoing.return_value = []
                lanes[lane.getID()] = lane
        for first, second, source, target in fixtures.car_lane_connections():
            link = Mock()
            link.getToLane.return_value = lanes[f'{second}_{target}']
            lanes[f'{first}_{source}'].getOutgoing.return_value.append(link)
        net = Mock()
        net.getLane.side_effect = lanes.__getitem__
        fixtures.validate_car_lane_topology(net)
        graph = nx.DiGraph()
        graph.add_edges_from((lane.getEdge().getID(), link.getToLane().getEdge().getID())
            for lane in lanes.values() for link in lane.getOutgoing()
            if lane.allows('passenger') and link.getToLane().allows('passenger'))
        self.assertTrue(nx.has_path(graph, 'g0', 'e2'))
        graph.remove_node('e1')
        self.assertTrue(nx.has_path(graph, 'g0', 'e2'))
        original = lanes['e0_1'].getOutgoing.return_value
        lanes['e0_1'].getOutgoing.return_value = []
        with self.assertRaisesRegex(ValueError, 'lacks a declared passenger'):
            fixtures.validate_car_lane_topology(net)
        lanes['e0_1'].getOutgoing.return_value = original
        lanes['e1_1'].allows.return_value = False
        with self.assertRaisesRegex(ValueError, 'lacks a declared passenger'):
            fixtures.validate_car_lane_topology(net)
        lanes['e1_1'].allows.return_value = True
        extra = Mock()
        extra.getToLane.return_value = lanes['d0_1']
        lanes['e0_1'].getOutgoing.return_value = original + [extra]
        with self.assertRaisesRegex(ValueError, 'changed its short-lane'):
            fixtures.validate_car_lane_topology(net)

    def test_parking_and_reentry_do_not_become_traffic_speed(self):
        self.assertEqual(runtime.traffic_observation_state(3, True, False), 'parked')
        self.assertEqual(runtime.traffic_observation_state(0, False, True), 'reentry_pending')
        self.assertEqual(runtime.traffic_observation_state(0, False, False), 'missing')
        self.assertEqual(runtime.traffic_observation_state(1, True, False), 'onroad')
        self.assertEqual(runtime.traffic_observation_state(0, False, False, True), 'departure_pending')
        self.assertEqual(runtime.traffic_observation_state(0, True, False, True), 'onroad')

    def test_sumo_retained_route_prefix_is_returned_to_the_controller(self):
        connection = Mock()
        connection.vehicle.getRoadID.return_value = 'b'
        connection.vehicle.isStopped.return_value = False
        connection.vehicle.getStops.return_value = ()
        connection.vehicle.getRoute.return_value = ('a', 'b', 'c')
        constants = types.ModuleType('traci.constants')
        constants.STOP_PARKING = 1
        with patch.dict(sys.modules, {'traci.constants': constants}):
            actual = runtime.set_vehicle_route(connection, 'v', ['b', 'c'], {'c': (0, 100)}, 50)
        self.assertEqual(actual, ['a', 'b', 'c'])
        connection.vehicle.setRoute.assert_called_once_with('v', ['b', 'c'])

    def test_no_forecast_modes_do_not_even_iterate_future_table(self):
        class FutureTable:
            def __iter__(self):
                raise AssertionError('Future input accessed')
        for scenario in ('R0', 'R1'):
            self.assertIsNone(runtime.dispatch_forecast(scenario, FutureTable(), {}))

    def test_forecast_offset_is_only_applied_to_vehicle_native_times(self):
        hazard = [{'edge_id': 'a', 'mode': 'passenger', 'closure_sec': '300'},
                  {'edge_id': 'b', 'mode': 'pedestrian', 'closure_sec': '100'},
                  {'edge_id': 'c', 'mode': 'passenger', 'closure_sec': ''}]
        parameters = {'forecast': {'R2P0': {'scheduled_time_error_sec': 0},
                                    'R2P900': {'scheduled_time_error_sec': 900}}}
        perfect = runtime.dispatch_forecast('R2P0', hazard, parameters)
        delayed = runtime.dispatch_forecast('R2P900', hazard, parameters)
        self.assertEqual(set(perfect), {'a'})
        self.assertEqual(delayed['a'] - perfect['a'], parameters['forecast']['R2P900']['scheduled_time_error_sec'])

    def test_core_refuses_without_ready_receipt_before_making_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parameters = {'cells': [{'cell_id': 'c', 'scenario': 'R0', 'seed': 1}],
                          'workspace': 'isolated', 'execution': {'implementation_files': []}}
            with patch.object(runtime, 'ROOT', root), patch.object(runtime, 'load_inputs', return_value=(parameters, root, {})):
                with self.assertRaisesRegex(RuntimeError, 'READY'):
                    runtime.run('c', 'blocked', purpose='core')
            self.assertFalse((root / 'isolated/runs/blocked').exists())

    def test_empty_ready_checks_do_not_authorize_core(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / 'isolated'
            workspace.mkdir()
            (workspace / 'preflight_ready.json').write_text(json.dumps({'status': 'READY', 'checks': {}}), encoding='utf8')
            parameters = {'cells': [{'cell_id': 'c', 'scenario': 'R0', 'seed': 1}],
                          'workspace': 'isolated', 'execution': {'implementation_files': []}}
            with patch.object(runtime, 'ROOT', root), patch.object(runtime, 'load_inputs', return_value=(parameters, root, {})):
                with self.assertRaisesRegex(RuntimeError, 'READY'):
                    runtime.run('c', 'blocked', purpose='core')
            self.assertFalse((workspace / 'runs/blocked').exists())


if __name__ == '__main__':
    unittest.main()
