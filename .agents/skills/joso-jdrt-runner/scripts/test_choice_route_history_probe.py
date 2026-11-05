"""Small candidate/ownership contracts; native evidence remains separate."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / '04_プログラム'))
os.environ['JDRT_CHOICE_TOOLCHAIN_MANIFEST'] = str(ROOT / '04_プログラム/output/sumo/toolchains/native_lat_20261020a/toolchain.json')
from scripts.jdrt_choice_toolchain import resolve_choice_toolchain, load_choice_traci
load_choice_traci(resolve_choice_toolchain(require_manifest=True))
spec = importlib.util.spec_from_file_location('history_probe', Path(__file__).with_name('choice_route_history_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Connection:
    def __init__(self, source='c'):
        self.calls, self.source, self.stops, self.assigned = [], source, [1], []
        self.vehicle = SimpleNamespace(getRoadID=lambda _: self.source, isStopped=lambda _: True,
            getStops=lambda _: list(self.stops), resume=self.resume, replaceStop=self.replace_stop,
            setRouteID=self.assign, setStop=self.stop, getRoute=lambda _: self.assigned)
        self.route = SimpleNamespace(add=self.add)

    def resume(self, vehicle):
        self.calls.append('resume')

    def replace_stop(self, vehicle, index, edge, teleport):
        assert teleport == 0
        self.calls.append('remove_stop')
        self.stops.pop(index)

    def add(self, route_id, path):
        self.calls.append('add_route')
        self.assigned = list(path)

    def assign(self, vehicle, route_id):
        self.calls.append('assign_route_id')

    def stop(self, vehicle, target, **kwargs):
        self.calls.append('set_stop')
        self.target, self.stop_args = target, kwargs


class Contracts(unittest.TestCase):
    def test_order_target_and_unchanged_requested_path(self):
        t = Connection()
        requested = ['c', 'd']
        actual = probe.route_id_candidate(t, 'v', requested, {'d': (1, 100)}, 1000.0, 'fresh')
        self.assertEqual(actual, requested)
        self.assertEqual(requested, ['c', 'd'])
        self.assertEqual(t.calls, ['resume', 'remove_stop', 'add_route', 'assign_route_id', 'set_stop'])
        self.assertEqual(t.target, 'd')
        self.assertEqual(t.stop_args['pos'], 99)
        self.assertEqual(t.stop_args['laneIndex'], 1)

    def test_invalid_source_rejected_before_control(self):
        for source, path in [(':junction', [':junction', 'd']), ('b', ['c', 'd']), ('c', [])]:
            with self.subTest(source=source, path=path):
                t = Connection(source)
                with self.assertRaises(ValueError):
                    probe.route_id_candidate(t, 'v', path, {'d': (1, 100)}, 1000.0, 'fresh')
                self.assertEqual(t.calls, [])

    def test_invalid_stop_target_rejected_before_control(self):
        t = Connection()
        with self.assertRaises(ValueError):
            probe.route_id_candidate(t, 'v', ['c', 'd'], {'d': (1, .3)}, 1000.0, 'fresh')
        self.assertEqual(t.calls, [])

    def test_no_existing_probe_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'municipality_code': '08211', 'protocol': 'realtime_choice_v1', 'workspace': 'workspace'}))
            original = root / 'workspace/technical/prior'
            original.mkdir(parents=True)
            marker = original / 'manifest.json'
            marker.write_bytes(b'{"status":"COMPLETED"}')
            before = marker.read_bytes()
            with self.assertRaises(FileExistsError):
                probe.run(root, 'prior')
            self.assertEqual(marker.read_bytes(), before)

    def test_bad_technical_id_refused(self):
        with self.assertRaises(ValueError):
            probe.run(ROOT, '../reuse')


class DiagnosticNativeReceipt(unittest.TestCase):
    def test_scope_and_both_executable_hashes_are_required(self):
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            base, diagnostic, receipt_path = (folder / n for n in ('base.exe', 'diagnostic.exe', 'receipt.json'))
            base.write_bytes(b'original native')
            diagnostic.write_bytes(b'observation only native')
            receipt = {'purpose':'OBSERVATION_ONLY_NOT_ADOPTION',
                'status':'COMPILED_NOT_SIMULATED_NOT_READY', 'technical_ready':False,
                'core_adoption_permitted':False, 'original_inputs_unchanged':True,
                'original_exe_sha256':sha256(base.read_bytes()).hexdigest(),
                'binary':str(diagnostic), 'binary_sha256':sha256(diagnostic.read_bytes()).hexdigest()}
            receipt_path.write_text(json.dumps(receipt))
            self.assertEqual(probe.diagnostic_sumo({'sumo':base}, receipt_path), diagnostic)
            for field, bad in [('purpose','READY'),('status','READY'),('technical_ready',True),
                               ('core_adoption_permitted',True),('original_inputs_unchanged',False),
                               ('original_exe_sha256','changed'),('binary_sha256','changed')]:
                with self.subTest(field=field):
                    receipt_path.write_text(json.dumps({**receipt, field:bad}))
                    with self.assertRaises(ValueError):
                        probe.diagnostic_sumo({'sumo':base}, receipt_path)
            receipt_path.write_text(json.dumps(receipt))
            diagnostic.write_bytes(b'changed after receipt')
            with self.assertRaises(ValueError):
                probe.diagnostic_sumo({'sumo':base}, receipt_path)


if __name__ == '__main__':
    unittest.main()
