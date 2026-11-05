import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bench', Path(__file__).with_name('benchmark_csv_access.py'))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class ScanTests(unittest.TestCase):
    def test_reordered_header_quoted_text_and_blank_line(self):
        raw = 'edge_id,count,time_sec\n"a,b",2,0.5\n\n"複数\n行",3,1.5\n'
        for indexed in (False, True):
            self.assertEqual(bench.scan(io.StringIO(raw), indexed),
                             {'rows': 2, 'count_sum': 5, 'time_sum': 2.0})

    def test_header_only(self):
        for indexed in (False, True):
            self.assertEqual(bench.scan(io.StringIO('time_sec,count\n'), indexed)['rows'], 0)

    def test_bad_schema_or_ragged_rows_rejected(self):
        for raw in ('time_sec,count,count\n1,2,3\n', 'time_sec\n1\n',
                    'time_sec,count\n1\n', 'time_sec,count\n1,2,3\n'):
            for indexed in (False, True):
                with self.assertRaises(ValueError):
                    bench.scan(io.StringIO(raw), indexed)

    def test_nonfinite_and_invalid_count_rejected(self):
        for row in ('nan,1', 'inf,1', '1,no'):
            for indexed in (False, True):
                with self.assertRaises(ValueError):
                    bench.scan(io.StringIO('time_sec,count\n' + row), indexed)


if __name__ == '__main__':
    unittest.main()
