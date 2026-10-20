"""Artificial request endpoints only, never research simulation results."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name('G6_要求待ち・打切り_集計.py')
spec = importlib.util.spec_from_file_location('choice_request_analysis', SOURCE)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def pair(pid, status, received='0', **times):
    p = {'person_id': pid, 'person_type': 'type4', 'selected_jdrt': 'True',
         'status': 'time_limit', 'mode': 'walk', 'origin_ped_closed_wait_sec': '0', 'origin_vehicle_closed_wait_sec': '0'}
    q = {'request_id': 'q_' + pid, 'person_id': pid, 'status': status, 'deadline_sec': '10',
         'person_final_status': p['status'], 'person_final_mode': p['mode'], 'cancel_reason': '',
         **{k: '' for k in ['accepted_sec', 'boarding_started_sec', 'boarded_sec',
                           'alighting_started_sec', 'alighted_sec', 'cancel_sec', 'fallback_sec']},
         'received_sec': received, **times}
    return p, q


class RequestContracts(unittest.TestCase):
    def test_cancel_and_horizon_are_distinct_and_receipt_zero_is_valid(self):
        p, q = pair('a', 'cancelled_timeout', cancel_sec='10', fallback_sec='10')
        p2, q2 = pair('b', 'time_limit', received='4')
        rows, summaries, distribution = module.request_summary([q, q2], [p, p2], [], 20)
        self.assertEqual([x['wait_to_boarding_start_observed_sec'] for x in rows], [10, 16])
        self.assertEqual([x['wait_right_censored_at_H'] for x in rows], [False, True])
        total = next(x for x in summaries if x['group'] == 'all')
        self.assertEqual((total['requests'], total['fallback_attempted'], total['horizon_right_censored_preboarding']), (2, 1, 1))
        self.assertEqual(sum(x['count'] for x in distribution if x['group'] == 'all'), 2)

    def test_boarding_at_zero_and_incomplete_service_do_not_censor_completed_wait(self):
        p, q = pair('a', 'time_limit', boarding_started_sec='0')
        rows, _, _ = module.request_summary([q], [p], [], 9)
        self.assertEqual(rows[0]['wait_to_boarding_start_observed_sec'], 0)
        self.assertFalse(rows[0]['wait_right_censored_at_H'])
        self.assertEqual(rows[0]['boarding_duration_observed_sec'], 9)
        self.assertFalse(rows[0]['boarding_completed'])

    def test_input_rejection_needs_its_actual_event(self):
        p, q = pair('a', 'rejected_input')
        with self.assertRaisesRegex(RuntimeError, 'unique native event'):
            module.request_summary([q], [p], [], 20)
        event = {'event': 'request_state', 'person_id': 'a', 'request_id': 'q_a',
                 'after': 'rejected_input', 'time_sec': 0}
        rows, _, _ = module.request_summary([q], [p], [event], 20)
        self.assertEqual(rows[0]['wait_to_boarding_start_observed_sec'], 0)
        self.assertFalse(rows[0]['wait_right_censored_at_H'])

    def test_served_request_is_not_automatically_person_admission(self):
        p, q = pair('a', 'served', boarding_started_sec='1', boarded_sec='3',
                    alighting_started_sec='5', alighted_sec='7')
        p['status'] = q['person_final_status'] = 'capacity_rejected'
        p['origin_ped_closed_wait_sec'] = '2'  # Exposure can extend through boarding.
        rows, summaries, _ = module.request_summary([q], [p], [], 20)
        total = next(x for x in summaries if x['group'] == 'all')
        self.assertEqual((total['request_served'], total['person_admitted']), (1, 0))
        self.assertEqual(rows[0]['origin_ped_closed_unboarded_including_boarding_sec'], 2)
        self.assertGreater(rows[0]['origin_ped_closed_unboarded_including_boarding_sec'], rows[0]['wait_to_boarding_start_observed_sec'])

    def test_missing_requests_and_boarding_plus_fallback_are_rejected(self):
        p, q = pair('a', 'time_limit', boarding_started_sec='1', fallback_sec='2')
        with self.assertRaisesRegex(RuntimeError, 'Missing or extra'):
            module.request_summary([], [p], [], 20)
        with self.assertRaisesRegex(RuntimeError, 'cancellation/fallback'):
            module.request_summary([q], [p], [], 20)

    def test_empty_R0_requests_have_explicit_zero_denominators(self):
        rows, summaries, distribution = module.request_summary([], [], [], 20)
        self.assertEqual((rows, distribution), ([], []))
        self.assertTrue(all(x['requests'] == 0 and x['observed_wait_mean_sec'] is None for x in summaries))


if __name__ == '__main__':
    unittest.main(verbosity=2)
