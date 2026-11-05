"""Temporary/mock orchestration evidence only; no native physical PASS claim."""
import unittest

import choice_native_regression as target


class ReceiptContracts(unittest.TestCase):
    def test_discontinuity_is_recomputed_from_raw_without_fixed_displacement(self):
        receipt = {'purpose': 'old_remaining',
                   'before': {'edge_id': 'a', 'lane_position_m': 2, 'xy': [3, 4], 'stage_length_m': 7},
                   'after': {'edge_id': 'a', 'lane_position_m': 2, 'xy': [6, 8], 'stage_length_m': 7}}
        self.assertEqual(target.receipt_difference(receipt)['changed_keys'], ['xy'])


if __name__ == '__main__':
    unittest.main()
