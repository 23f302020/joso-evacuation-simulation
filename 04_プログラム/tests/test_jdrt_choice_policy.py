"""Counterexamples for new policy contracts, independent of observed research outcomes."""
import math
import unittest
from decimal import Decimal

import networkx as nx

from scripts.jdrt_choice_policy import (
    candidate_checks, facility_first_destinations, request_transition,
    select_intents, unboarded_expired,
)


def graph(edges, directed=True):
    result = nx.DiGraph() if directed else nx.Graph()
    result.add_weighted_edges_from(edges, weight='length')
    nx.set_node_attributes(result, 1., 'length')
    return result


class DestinationTests(unittest.TestCase):
    def test_facility_precedes_closer_exit_and_terminal_tie_is_id_order(self):
        g = graph([('s', 'exit', 1), ('s', 'fb', 9), ('s', 'fa', 9)])
        terms = [{'terminal_id': 'exit0', 'kind': 'boundary_exit', 'edge_id': 'exit'},
                 {'terminal_id': 'b', 'kind': 'facility', 'edge_id': 'fb'},
                 {'terminal_id': 'a', 'kind': 'facility', 'edge_id': 'fa'}]
        row = facility_first_destinations([{'origin_id': 'o', 'edge_id': 's'}],
                                          {'passenger': g, 'pedestrian': g}, terms)[0]
        self.assertEqual(row['terminal_id'], 'a')
        self.assertEqual(row['selection_distance_m'], 9)

    def test_walk_facility_precedes_car_exit_and_direction_is_respected(self):
        car = graph([('s', 'exit', 1), ('facility', 's', 2)])
        walk = graph([('s', 'facility', 6)], directed=False)
        terms = [{'terminal_id': 'f', 'kind': 'facility', 'edge_id': 'facility'},
                 {'terminal_id': 'e', 'kind': 'boundary_exit', 'edge_id': 'exit'}]
        row = facility_first_destinations([{'origin_id': 'o', 'edge_id': 's'}],
                                          {'passenger': car, 'pedestrian': walk}, terms)[0]
        self.assertEqual((row['terminal_id'], row['selection_stage']), ('f', 2))
        self.assertEqual(row['car_route'], [])

    def test_route_tie_does_not_depend_on_edge_insertion_order(self):
        edges = [('s', 'z', 1), ('z', 'f', 1), ('s', 'a', 1), ('a', 'f', 1)]
        term = [{'terminal_id': 'f', 'kind': 'facility', 'edge_id': 'f'}]
        rows = []
        for sequence in (edges, list(reversed(edges))):
            g = graph(sequence)
            rows.append(facility_first_destinations([{'origin_id': 'o', 'edge_id': 's'}],
                        {'passenger': g, 'pedestrian': g}, term)[0])
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(rows[0]['car_route'], ['s', 'a', 'f'])

    def test_same_edge_unconnected_origin_and_duplicate_terminal_edge(self):
        g = graph([('s', 't', 2)])
        terms = [{'terminal_id': 'z', 'kind': 'facility', 'edge_id': 's'},
                 {'terminal_id': 'a', 'kind': 'facility', 'edge_id': 's'}]
        rows = facility_first_destinations([{'origin_id': 'o', 'edge_id': 's'},
                                            {'origin_id': 'p', 'edge_id': ''}],
                                           {'passenger': g, 'pedestrian': g}, terms)
        self.assertEqual((rows[0]['terminal_id'], rows[0]['car_route']), ('a', ['s']))
        self.assertEqual(rows[1]['terminal_id'], '')

    def test_decimal_equal_cost_paths_are_not_ordered_by_binary_roundoff(self):
        g = graph([('s', 'z', .15), ('z', 'f', .15), ('s', 'a', .1), ('a', 'f', .2)])
        row = facility_first_destinations([{'origin_id': 'o', 'edge_id': 's'}],
                {'passenger': g, 'pedestrian': g},
                [{'terminal_id': 'f', 'kind': 'facility', 'edge_id': 'f'}])[0]
        self.assertEqual(row['car_route'], ['s', 'a', 'f'])
        self.assertEqual(Decimal(row['selection_distance_exact_m']), Decimal('0.3'))

    def test_zero_weight_is_rejected_instead_of_looping(self):
        g = graph([('s', 'f', 0)])
        with self.assertRaises(ValueError):
            facility_first_destinations([], {'passenger': g, 'pedestrian': g}, [])


class RequestTests(unittest.TestCase):
    def test_rounding_by_type_nested_intents_and_permutation_invariance(self):
        people = [{'person_id': str(i), 'person_type': typ}
                  for i, typ in enumerate(['type3'] * 5 + ['type4'] * 3 + ['type1'] * 2)]
        low = select_intents(people, 7, .1)
        high = select_intents(people, 7, .5)
        self.assertLessEqual(low, high)
        self.assertEqual(high, select_intents(list(reversed(people)), 7, .5))
        self.assertEqual(len(high), 5)
        self.assertTrue(all(people[int(pid)]['person_type'] != 'type1' for pid in high))

    def test_deadline_equality_cancels_only_before_boarding(self):
        for status in ('waiting_origin', 'assigned_origin'):
            self.assertFalse(unboarded_expired(status, 9.5, 10))
            self.assertTrue(unboarded_expired(status, 10, 10))
        for status in ('boarding', 'onboard', 'travelling_walk'):
            self.assertFalse(unboarded_expired(status, 20, 10))

    def test_served_requires_complete_board_and_alight_sequence(self):
        status = 'none'
        for event in ('received', 'accepted', 'boarding_started', 'boarded',
                      'alighting_started', 'alighted'):
            status = request_transition(status, event)
        self.assertEqual(status, 'served')
        for event in ('accepted', 'timeout', 'alighted', 'horizon'):
            with self.assertRaises(ValueError):
                request_transition(status, event)

    def test_failure_and_horizon_do_not_allow_origin_fallback_after_boarding(self):
        self.assertEqual(request_transition('accepted', 'vehicle_failed'), 'cancelled_vehicle_failure')
        for status in ('boarding', 'onboard', 'alighting'):
            self.assertEqual(request_transition(status, 'vehicle_failed'), 'failed_after_boarding')
            self.assertEqual(request_transition(status, 'horizon'), 'time_limit')
            with self.assertRaises(ValueError):
                request_transition(status, 'timeout')


class CandidateTests(unittest.TestCase):
    def check(self, **kwargs):
        args = dict(now=0, pickup_sec=1, delivery_sec=2, deadline=20, horizon=10,
                    boarding_sec=3, alighting_sec=4, margin_sec=5)
        args.update(kwargs)
        return candidate_checks(**args)

    def test_horizon_equality_allowed_pickup_deadline_equality_rejected(self):
        self.assertEqual(self.check()['reason'], 'eligible')
        self.assertEqual(self.check(deadline=1)['reason'], 'pickup_deadline')
        self.assertEqual(self.check(horizon=9.5)['reason'], 'horizon')

    def test_forecast_gate_includes_alighting_and_margin_and_is_strict(self):
        self.assertEqual(self.check(forecast_remaining_sec=15)['reason'], 'forecast_gate')
        self.assertEqual(self.check(forecast_remaining_sec=15.5)['reason'], 'eligible')
        self.assertEqual(self.check()['required_sec'], 15)
        self.assertIsNone(self.check()['forecast_gate_pass'])

    def test_no_route_is_infinite_and_not_reclassified_as_forecast_rejection(self):
        result = self.check(pickup_sec=math.inf, forecast_remaining_sec=math.inf)
        self.assertEqual(result['reason'], 'no_pickup_route')
        self.assertFalse(result['forecast_gate_applicable'])
        self.assertEqual(self.check(delivery_sec=math.inf)['reason'], 'no_delivery_route')
        with self.assertRaises(ValueError):
            self.check(delivery_sec=math.nan)


if __name__ == '__main__':
    unittest.main()
