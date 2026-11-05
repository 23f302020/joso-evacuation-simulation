import hashlib
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from choice_native_braking_probe import make_routes, verify_sources


class BrakingProbeContracts(unittest.TestCase):
    def setUp(self):
        self.plan = dict(car_route=['a', 'b'], walk_route=['c', 'b'],
                         car_depart_pos_m=7., car_depart_lane='1', car_depart_speed='max',
                         walk_depart_pos_m=2., walk_speed_mps=1., walk_speed_factor=.9)
        self.car = dict(id='car', vClass='passenger', length='4.5', minGap='2.5')

    def test_only_person_presence_changes_between_pair(self):
        absent = ET.fromstring(make_routes(self.plan, self.car, False))
        present = ET.fromstring(make_routes(self.plan, self.car, True))
        person = present.find('person')
        self.assertIsNotNone(person)
        self.assertIsNone(absent.find('person'))
        present.remove(person)
        self.assertEqual(ET.tostring(absent), ET.tostring(present))
        self.assertEqual(absent.find('vType').attrib, self.car)

    def test_negative_or_nonfinite_position_rejected_without_clamping(self):
        for value in (-1., float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_routes({**self.plan, 'car_depart_pos_m': value}, self.car, True)

    def test_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'input.xml'
            path.write_bytes(b'original')
            sources = {'input.xml': hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(verify_sources(root, sources), sources)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verify_sources(root, sources)

    def test_source_outside_project_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            verify_sources(Path(directory), {'../elsewhere': '0' * 64})


if __name__ == '__main__':
    unittest.main()
