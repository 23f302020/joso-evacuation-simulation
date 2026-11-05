import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('stop_trace', Path(__file__).with_name('choice_native_stop_index_trace.py'))
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


class TraceContract(unittest.TestCase):
    def test_only_observation_added_before_original_branch_lf_crlf(self):
        for newline in (b'\n', b'\r\n'):
            with self.subTest(newline=newline):
                original = newline.join([b'void f() {',
                    b'    if (hasDeparted() && stop.edge > myRoute->begin()) {', b'        old_body();', b'    }', b'}'])
                patched = trace.instrument(original)
                begin = patched.index(b'    std::cerr')
                end = patched.index(b'    if (hasDeparted()')
                self.assertEqual(patched[:begin] + patched[end:], original)
                self.assertNotIn(b'routeIndex >=', patched)
                self.assertIn(b'past_index=', patched)
                self.assertIn(b'std::endl;', patched)

    def test_missing_or_duplicate_anchor_refused(self):
        marker = b'    if (hasDeparted() && stop.edge > myRoute->begin()) {'
        for raw in (b'changed source', marker+b'\n'+marker):
            with self.assertRaises(ValueError):
                trace.instrument(raw)

    def test_already_instrumented_source_refused(self):
        raw = trace.instrument(b'    if (hasDeparted() && stop.edge > myRoute->begin()) {')
        with self.assertRaises(ValueError):
            trace.instrument(raw)


if __name__ == '__main__':
    unittest.main()
