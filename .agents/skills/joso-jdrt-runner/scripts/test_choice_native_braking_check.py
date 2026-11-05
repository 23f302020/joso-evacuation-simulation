import copy
import math
import unittest

from choice_native_braking_check import check_warning


class NativeBrakingConsistency(unittest.TestCase):
    def setUp(self):
        self.line = ("Warning: Vehicle 'artificial' performs emergency braking on lane 'a_1' "
                     "with decel=7.00, wished=3.00, severity=1.00, time=4.00.")
        self.frames = [dict(time_sec=3.75, speed_mps=4.5, distance_m=98.75),
                       dict(time_sec=4., speed_mps=5., distance_m=100.),
                       dict(time_sec=4.25, speed_mps=3.25, distance_m=100.8125)]
        for frame in self.frames:
            frame.update(actor_id='artificial', lane_id='a_1', kind='car',
                         phase='after_step_before_control', decel_mps2=3.)
        self.properties = dict(decel=3., emergencyDecel=7.)

    def check(self, line=None, frames=None, properties=None):
        return check_warning(line or self.line, self.frames if frames is None else frames,
                             .25, properties or self.properties, .001, 1.)

    def test_source_consistent_match_is_never_adoptable(self):
        result = self.check()
        self.assertEqual(result['status'], 'DIAGNOSTIC_MATCH')
        self.assertEqual(result['derived_acceleration_mps2'], -7.)
        self.assertFalse(result['core_adoption_permitted'])

    def test_actor_identity_is_generic_not_whitelisted(self):
        frames = copy.deepcopy(self.frames)
        for frame in frames:
            frame['actor_id'] = 'another_actor'
        self.assertEqual(self.check(self.line.replace('artificial', 'another_actor'), frames)['status'],
                         'DIAGNOSTIC_MATCH')

    def test_warning_mutations_are_rejected(self):
        for old, new in [('artificial', 'other'), ('a_1', 'b_1'), ('7.00', '6.00'),
                         ('wished=3.00', 'wished=2.00'), ('severity=1.00', 'severity=0.80'),
                         ('time=4.00', 'time=4.25')]:
            with self.subTest(old=old):
                self.assertEqual(self.check(self.line.replace(old, new))['status'], 'INCONSISTENT')

    def test_missing_or_duplicate_clock_is_rejected(self):
        for frames in (self.frames[1:], [self.frames[0], self.frames[1], self.frames[1]]):
            with self.subTest(frames=frames):
                self.assertEqual(self.check(frames=frames)['status'], 'INCONSISTENT')

    def test_new_manoeuvre_condition_is_required(self):
        frames = copy.deepcopy(self.frames)
        frames[0]['speed_mps'] = 7.
        self.assertEqual(self.check(frames=frames)['status'], 'INCONSISTENT')

    def test_emergency_bound_is_not_inferred_from_warning(self):
        self.assertEqual(self.check(properties=dict(decel=3., emergencyDecel=6.))['status'], 'INCONSISTENT')

    def test_distance_change_is_checked_independently(self):
        frames = copy.deepcopy(self.frames)
        frames[-1]['distance_m'] += .1
        self.assertEqual(self.check(frames=frames)['status'], 'INCONSISTENT')

    def test_nonfinite_and_wrong_phase_are_rejected(self):
        for key, value in [('speed_mps', math.nan), ('distance_m', math.inf), ('phase', 'after_control_before_step')]:
            frames = copy.deepcopy(self.frames)
            frames[-1][key] = value
            with self.subTest(key=key):
                self.assertEqual(self.check(frames=frames)['status'], 'INCONSISTENT')


if __name__ == '__main__':
    unittest.main()
