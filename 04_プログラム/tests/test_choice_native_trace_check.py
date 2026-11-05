"""Artificial false-proof counterexamples, separate from real native evidence."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_trace_check as check


class TraceCheckContracts(unittest.TestCase):
    def row(self):
        return dict(seq='1', sim_step='500', person='p&0', current_edge='e0',
                    current_edge_normal='1', new_lane='e0_0', new_pos='4.5', new_dir='1',
                    input_lat='-9000', input_unspecified='1', input_random='0', legacy='0',
                    stages='3', remaining='2', new_departed='500', prior_evaluated='1',
                    prior_type='3', prior_edge_null='0', prior_edge='e0', edge_same='1',
                    prior_arrived='500', time_same='1', state_evaluated='1', state_null='0',
                    person_same='1', prior_person='p&0', old_lane_null='0', old_lane='e0_0',
                    lane_same='1', old_pos='4.5', position_same='1', old_lat='0.64',
                    inherited='1', final_lat='0.64', final_dir='1')

    def derive(self, row):
        # Artificial sentinels; the real caller must bind values to native source.
        return check.derive(row, unspecified=-9000., random=-8000., walking_type=3)

    def test_inheritance_is_derived_and_raw_lateral_and_new_direction_preserved(self):
        row = self.row()
        self.assertEqual(self.derive(row)['branch'], 'inherit')
        for field, forged in [('inherited', '0'), ('old_lat', '0.63'), ('final_dir', '-1'),
                              ('time_same', '0'), ('position_same', '0'), ('prior_person', 'other')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.derive({**row, field: forged})
        self.assertEqual(self.derive({**row, 'new_dir': '-1', 'final_dir': '-1'})['branch'], 'inherit')

    def initial(self, **changes):
        row = self.row()
        optional = ['prior_evaluated','prior_type','prior_edge_null','prior_edge','edge_same',
                    'prior_arrived','time_same','state_evaluated','state_null','person_same',
                    'prior_person','old_lane_null','old_lane','lane_same','old_pos','position_same','old_lat']
        for key in optional: row.pop(key)
        return {**row, 'stages':'2', 'inherited':'0', 'final_lat':'1.28', **changes}

    def test_default_explicit_random_legacy_are_distinguished_without_synthetic_native_pass(self):
        for row, branch in [(self.initial(), 'default'),
                            (self.initial(input_lat='0.2', input_unspecified='0'), 'explicit'),
                            (self.initial(input_lat='-8000', input_unspecified='0', input_random='1'), 'random'),
                            (self.initial(legacy='1'), 'legacy')]:
            with self.subTest(branch=branch): self.assertEqual(self.derive(row)['branch'], branch)
        with self.assertRaises(ValueError): self.derive(self.initial(input_unspecified='0'))

    def test_skipped_guards_cannot_supply_fabricated_values(self):
        with self.assertRaises(ValueError): self.derive({**self.initial(), 'prior_type':'3'})
        row = self.row()
        for key in ('person_same','prior_person','old_lane_null','old_lane','lane_same','old_pos','position_same','old_lat'):
            row.pop(key)
        row.update(state_null='1', inherited='0', final_lat='1.28')
        self.assertEqual(self.derive(row)['branch'], 'default')
        with self.assertRaises(ValueError): self.derive({**row, 'old_lat':'0.64'})

    def test_missing_nonfinite_nonboolean_and_extra_fields_fail(self):
        row = self.row()
        for field, value in [('old_lat',None),('new_pos','NaN'),('legacy','true'),('seq','0'),
                             ('remaining','5'),('new_departed','500.0')]:
            other = dict(row)
            if value is None: other.pop(field)
            else: other[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): self.derive(other)
        with self.assertRaises(ValueError): self.derive({**row, 'unexpected':'1'})

    def test_raw_rows_preserve_xml_entities_and_require_full_sequence(self):
        raw=b'Step #0\n<jdrtLatGuard seq="1" person="p&amp;0"/>\nWarning: kept\n<jdrtLatGuard seq="2" person="q"/>\n'
        rows=check.parse(raw)
        self.assertEqual([r['person'] for r in rows], ['p&0','q'])
        self.assertIn(b'Warning: kept',raw)
        for bad in [b'',raw+b'<jdrtLatGuard seq="3"',raw.replace(b'seq="2"',b'seq="3"'),
                    raw.replace(b'person="q"',b'person="q" person="x"')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError): check.parse(bad)


if __name__ == '__main__':
    unittest.main()
