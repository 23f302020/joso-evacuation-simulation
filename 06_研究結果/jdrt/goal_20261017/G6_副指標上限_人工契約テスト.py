"""Artificial registered-secondary contracts; no native or core artifact reads."""
import importlib.util
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name('G6_副指標・理論上限_集計.py')
spec = importlib.util.spec_from_file_location('choice_secondary_analysis_tests', SOURCE)
secondary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secondary)


def proof():
    return {'conditions': dict.fromkeys(['initially_empty', 'serial_one_person', 'all_available_at_zero',
        'full_processing_times', 'no_vehicle_time_reset'], True)}


def config():
    return {'operation': {'fleet_count': 1, 'pooling': False, 'boarding_sec': 300, 'alighting_sec': 300},
            'simulation': {'duration_sec': 1200}}


def service(pid, start):
    person = {'person_id': pid, 'status': 'admitted', 'mode': 'drt', 'person_type': 'type4'}
    request = {'person_id': pid, 'status': 'served', 'vehicle_id': 'v', 'deadline_sec': str(start + 1),
        'boarding_started_sec': str(start), 'boarded_sec': str(start + 300),
        'alighting_started_sec': str(start + 300), 'alighted_sec': str(start + 600)}
    return person, request


class SecondaryContracts(unittest.TestCase):
    def test_missing_native_distance_is_not_zero_total_and_empty_is_subset(self):
        rows = [{'vehicle_id': 'v1', 'kind': 'drt', 'status': 'idle', 'distance_m': '',
            'observed_distance_m': '7', 'observed_empty_distance_m': '2'},
            {'vehicle_id': 'v2', 'kind': 'drt', 'status': 'stranded', 'distance_m': '0',
            'observed_distance_m': '0', 'observed_empty_distance_m': '0'}]
        drt = secondary.vehicle_summary(rows)[1]
        self.assertEqual((drt['native_distance_known_sum_m'], drt['native_distance_complete_sum_m'],
            drt['native_distance_missing_vehicles']), (0, None, 1))
        self.assertEqual((drt['observed_distance_sum_m'], drt['observed_empty_distance_sum_m']), (7, 2))
        rows[0]['observed_empty_distance_m'] = '8'
        with self.assertRaisesRegex(RuntimeError, 'Empty distance exceeds'):
            secondary.vehicle_summary(rows)

    def test_cycle_stage_all_candidates_and_zero_candidate_cycles(self):
        cycles = [{'cycle': '1', 'stages': '2', 'free_start': '2', 'pending_start': '2', 'candidate_rows': '5', 'accepted': '1'},
                  {'cycle': '2', 'stages': '0', 'free_start': '1', 'pending_start': '0', 'candidate_rows': '0', 'accepted': '0'}]
        candidates = []
        for stage, count in [(1, 4), (2, 1)]:
            for index in range(count):
                candidates.append({'cycle': '1', 'stage': str(stage), 'reason': 'eligible' if stage == 1 else 'pickup_deadline',
                    'decision': 'selected' if stage == 1 and index == 0 else 'not_selected',
                    **dict.fromkeys(['pickup_route', 'delivery_route', 'pickup_before_deadline', 'completion_within_horizon',
                                     'gate_applicable', 'gate_pass'], 'True')})
        summary, all_cycles, stages = secondary.candidate_summary(iter(candidates), iter(cycles), 'R1')
        self.assertEqual(summary, {'dispatch_cycles': 2, 'zero_candidate_cycles': 1, 'candidate_rows': 5, 'selected': 1})
        self.assertEqual(len(all_cycles), 2)
        self.assertEqual([r['candidate_rows'] for r in stages], [4, 1])
        self.assertEqual(json.loads(stages[1]['exclusive_reason_counts']), {'pickup_deadline': 1})
        with self.assertRaisesRegex(RuntimeError, 'candidate accounting'):
            secondary.candidate_summary(candidates[:-1], cycles, 'R1')
        self.assertEqual(secondary.candidate_summary([], [], 'R0')[0]['dispatch_cycles'], 0)

    def test_roads_preserve_zero_parked_raw_vs_traffic_and_closed_entry_counts(self):
        base = {'time_sec': '0', 'mode': 'drt', 'closed': 'False', 'count': '0', 'traffic_count': '0',
            'mean_speed_mps': '', 'traffic_mean_speed_mps': '', 'halting_count': '0', 'traffic_halting_count': '0',
            'parked_count': '0', 'reentry_pending_count': '0', 'unplaced_reentry_count': '0'}
        observations = [dict(base, edge_id='e0'), dict(base, edge_id='e1', count='1', mean_speed_mps='0', parked_count='1')]
        transitions = [{'mode': 'passenger', 'kind': 'closed_entry', 'ambiguous': 'True'}]
        road, transition = secondary.road_summary(observations, transitions)
        self.assertEqual((road[0]['road_rows'], road[0]['count_sum'], road[0]['traffic_count_sum'],
            road[0]['zero_raw_count_rows'], road[0]['zero_traffic_count_rows']), (2, 1, 0, 1, 2))
        self.assertEqual(road[0]['raw_speed_observed_actor_samples'], 1)
        self.assertEqual(sum(r['count'] for r in transition), 1)
        self.assertEqual(sum(r['count'] for r in transition if r['kind'] == 'closed_entry' and r['ambiguous']), 1)

    def test_facility_upper_retains_disconnected_type4_and_shared_capacity(self):
        people = [{'person_id': str(i), 'person_type': 'type4', 'origin_id': 'o'} for i in range(3)]
        people += [{'person_id': 'exit', 'person_type': 'type4', 'origin_id': 'x'}]
        people += [{'person_id': 'no_terminal', 'person_type': 'type4', 'origin_id': 'none'}]
        destinations = [{'origin_id': 'o', 'terminal_id': 'f', 'car_route': '[]', 'walk_route': '[]', 'walk_length_m': ''},
                        {'origin_id': 'x', 'terminal_id': 'x', 'car_route': '["e"]', 'walk_route': '[]', 'walk_length_m': ''},
                        {'origin_id': 'none', 'terminal_id': '', 'car_route': '[]', 'walk_route': '[]', 'walk_length_m': ''}]
        terminals = {'f': {'kind': 'facility', 'capacity': '2'}, 'x': {'kind': 'exit', 'capacity': '0'}}
        output = secondary.structural_bounds(people, destinations, terminals, 3000)
        self.assertEqual((output[0]['type4_fixed'], output[0]['fixed_assignment_capacity_upper'],
            output[0]['registered_passenger_route_present']), (3, 2, 0))
        self.assertEqual(output[-1]['fixed_assignment_capacity_upper'], 2)
        cfg = config()
        workload = secondary.workload([{'intent_u05': 'True'}, {'intent_u05': 'True'}, {'intent_u05': 'False'}], 'u05', cfg)
        self.assertEqual((workload['intended_requests'], workload['rho_service_only']), (2, 1))

    def test_floor_bound_delayed_availability_and_failed_time_never_add_capacity(self):
        self.assertEqual(secondary.service_bound(1200, [0, 0], 300, 300,
            initially_empty=True, serial_one_person=True), 4)
        self.assertEqual(secondary.service_bound(1200, [300, 0], 300, 300,
            initially_empty=True, serial_one_person=True), 3)
        self.assertEqual(secondary.service_bound(900, [0, 0], 300, 300,
            initially_empty=True, serial_one_person=True), 2)  # Idle remainders cannot be pooled between vehicles.
        for empty, serial in [(False, True), (True, False)]:
            with self.assertRaisesRegex(RuntimeError, 'assumptions'):
                secondary.service_bound(1200, [0], 300, 300, initially_empty=empty, serial_one_person=serial)

    def test_complete_serial_services_bound_only_direct_admission_not_fallback(self):
        p1, q1 = service('p1', 0); p2, q2 = service('p2', 600)
        fallback = {'person_id': 'fallback', 'status': 'admitted', 'mode': 'walk', 'person_type': 'type4'}
        result = secondary.direct_service_accounting([q1, q2], [p1, p2, fallback], config(), 'R1', proof())
        self.assertEqual((result['successful_drt_services'], result['direct_drt_admitted'],
            result['service_only_completion_upper']), (2, 2, 2))
        self.assertEqual(sum(p['status'] == 'admitted' for p in [p1, p2, fallback]), 3)
        self.assertEqual(secondary.direct_service_accounting([], [fallback], config(), 'R0', proof())['service_only_completion_upper'], 0)

    def test_overlap_partial_horizon_short_processing_and_pooling_counterexamples_refuse(self):
        p1, q1 = service('p1', 0); p2, q2 = service('p2', 599)
        with self.assertRaisesRegex(RuntimeError, 'overlap'):
            secondary.direct_service_accounting([q1, q2], [p1, p2], config(), 'R1', proof())
        _, late = service('p1', 601)
        with self.assertRaisesRegex(RuntimeError, 'observation/deadline'):
            secondary.direct_service_accounting([late], [p1], config(), 'R1', proof())
        short = dict(q1, boarded_sec='299')
        with self.assertRaisesRegex(RuntimeError, 'full processing'):
            secondary.direct_service_accounting([short], [p1], config(), 'R1', proof())
        cfg = config(); cfg['operation']['pooling'] = True
        with self.assertRaisesRegex(RuntimeError, 'Unestablished'):
            secondary.direct_service_accounting([q1], [p1], cfg, 'R1', proof())


if __name__ == '__main__':
    unittest.main(verbosity=2)
