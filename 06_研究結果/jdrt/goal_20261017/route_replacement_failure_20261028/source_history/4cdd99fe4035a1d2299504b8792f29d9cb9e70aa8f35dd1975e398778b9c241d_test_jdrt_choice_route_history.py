"""Artificial contracts for the independent past-closure delivery audit."""
import csv
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import jdrt_realtime_choice_validate as validator


class RouteHistoryFixtureContracts(unittest.TestCase):
    def audit(self, mutation=None):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            inputs, folder = root / 'inputs', root / 'run'
            inputs.mkdir()
            folder.mkdir()
            (inputs / 'manifest.json').write_text(json.dumps({
                'fixture_case': 'delivery_past_closure'}), encoding='utf-8')
            hazard = [{'edge_id': 'g0', 'mode': 'passenger', 'closure_sec': 120}]
            requests = [{'vehicle_id': 'bus', 'status': 'served',
                         'boarding_started_sec': 70, 'boarded_sec': 370}]
            actors = [dict(actor_id='bus', time_sec=61, road_id='g0',
                           lane_position_m=50, distance_m=50, route_index=0, route_version=1),
                      dict(actor_id='bus', time_sec=370.5, road_id='e0',
                           lane_position_m=20, distance_m=100, route_index=0, route_version=2)]
            events = [dict(event='drt_route', time_sec=60, vehicle_id='bus',
                           route=['g0', 'e0'], requested_remaining_route=['g0', 'e0']),
                      dict(event='drt_route', time_sec=370, vehicle_id='bus',
                           source_edge='e0', source_lane_position=20, source_distance_m=100,
                           route=['e0', 'e1', 'e2'], requested_remaining_route=['e0', 'e1', 'e2'],
                           source_route_index=0, route_version=2)]
            if mutation:
                mutation(hazard, requests, actors, events)
            for path, data in [(inputs / 'hazard.csv', hazard),
                               (folder / 'request_results.csv', requests)]:
                with path.open('w', encoding='utf-8', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(data[0]))
                    writer.writeheader()
                    writer.writerows(data)
            with gzip.open(folder / 'actor_observations.csv.gz', 'wt', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(actors[0]))
                writer.writeheader()
                writer.writerows(actors)
            with patch.object(validator, 'ROOT', root):
                return validator.audit_fixture_timing(folder,
                    {'purpose': 'fixture', 'input_directory': 'inputs', 'step_sec': .5},
                    {'operation': {'boarding_sec': 300}}, events)

    def test_registered_suite_requires_past_closure_delivery(self):
        self.assertIn('delivery_past_closure', validator.REQUIRED_FIXTURE_CASES)

    def test_actual_history_and_remaining_delivery_are_required(self):
        result = self.audit()
        self.assertTrue(result['applicable'])
        self.assertEqual(result['status'], 'PASS')

    def test_closure_outside_boarding_is_rejected(self):
        result = self.audit(lambda h, q, a, e: h[0].update(closure_sec=500))
        self.assertEqual(result['status'], 'INVALID')

    def test_retained_closed_prefix_is_rejected(self):
        result = self.audit(lambda h, q, a, e: e[-1].update(route=['g0', 'e0', 'e1', 'e2']))
        self.assertEqual(result['status'], 'INVALID')

    def test_reentry_position_and_distance_jump_is_rejected(self):
        result = self.audit(lambda h, q, a, e: a[-1].update(distance_m=400, lane_position_m=80))
        self.assertEqual(result['status'], 'INVALID')


if __name__ == '__main__':
    unittest.main()
