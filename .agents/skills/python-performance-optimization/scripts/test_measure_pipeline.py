import importlib.util
from pathlib import Path
import unittest
import json
import tempfile


spec = importlib.util.spec_from_file_location('measure_pipeline', Path(__file__).with_name('measure_pipeline.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TimingTests(unittest.TestCase):
    def test_unknown_and_reversed_times_are_not_zero(self):
        self.assertIsNone(module.seconds(None, '2026-01-01T00:00:00+09:00'))
        self.assertIsNone(module.seconds('2026-01-01T00:01:00+09:00', '2026-01-01T00:00:00+09:00'))
        self.assertIsNone(module.seconds('2026-01-01T00:00:00', '2026-01-01T00:01:00'))

    def test_timezone_normalization(self):
        self.assertEqual(module.seconds('2026-01-01T09:00:00+09:00', '2026-01-01T00:01:00+00:00'), 60)

    def test_pid_reuse_does_not_produce_cpu_rate(self):
        old = {'pid': 3, 'created': 'a', 'cpu_sec': 10}
        new = {'pid': 3, 'created': 'b', 'cpu_sec': 20}
        self.assertIsNone(module.cpu_percent(old, new, 10))
        new['created'] = 'a'
        self.assertEqual(module.cpu_percent(old, new, 10), 100)

    def test_nested_operation_duration(self):
        row = {'at_jst': '2026-01-01T09:01:00+09:00', 'command': 'validate',
               'result': {'duration_sec': 60, 'result': {'run_id': 'synthetic', 'status': 'PASS'}}}
        result = module.operation_timing(row)
        self.assertEqual(result['duration_sec'], 60)
        self.assertEqual(result['run_id'], 'synthetic')
        self.assertEqual(module.seconds(result['inferred_start'], result['end']), 60)
        self.assertIsNone(module.operation_timing({'command': 'validate', 'result': {}})['duration_sec'])

    def test_invalid_durations_are_unknown(self):
        for duration in (-1, float('nan'), float('inf'), '10'):
            result = module.operation_timing({'result': {'duration_sec': duration}})
            self.assertIsNone(result['duration_sec'])
            self.assertIsNone(result['inferred_start'])

    def test_partial_history_line_is_preserved_as_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'driver_logs').mkdir()
            path = root / 'driver_logs/operations.jsonl'
            raw = json.dumps({'command': 'record', 'result': {'duration_sec': 3, 'result': {'run_id': 'fake'}}}) + '\n{"partial"'
            path.write_text(raw, encoding='utf-8')
            result = module.history(root)
            self.assertEqual(result['operations'][0]['run_id'], 'fake')
            self.assertEqual(result['errors'][0]['line'], 2)
            self.assertEqual(path.read_text(encoding='utf-8'), raw)


if __name__ == '__main__':
    unittest.main()
