"""Static observability-patch contracts; these do not exercise native guards."""
import hashlib
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_trace_source as trace


class TraceSourceContracts(unittest.TestCase):
    def setUp(self):
        proposal = ROOT / '06_研究結果/jdrt/goal_20261017/audit_history/walk_native_proposal_20261019'
        self.original = (proposal / 'proposed/src/microsim/transportables/MSPModel_Striping.cpp').read_bytes()

    def test_pure_insertions_restore_exact_original_and_preserve_rng_calls(self):
        instrumented = trace.instrument(self.original)
        self.assertNotEqual(instrumented, self.original)
        self.assertEqual(trace.restore(instrumented), self.original)
        self.assertEqual(instrumented.count(b'RandHelper::'), self.original.count(b'RandHelper::'))
        self.assertEqual(instrumented.count(b'myPosLat = previousState->getPosLat();'), 1)
        self.assertLess(instrumented.index(b'#include <config.h>'), instrumented.index(b'#include <limits>'))
        trace.verify(self.original, instrumented)

    def test_instrumentation_is_bound_to_the_exact_generator(self):
        instrumented = trace.instrument(self.original)
        for old, new in [(b'myPosLat = previousState->getPosLat();', b'myPosLat = 0;'),
                         (b'"jdrtLatGuard"', b'"forgedTrace"')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                trace.verify(self.original, instrumented.replace(old, new))

    def test_unpatched_ambiguous_or_already_instrumented_source_is_rejected(self):
        anchor = b'    const PState* previousState = nullptr;'
        for source in [self.original.replace(anchor, b''),
                       self.original.replace(anchor, anchor + b'\n' + anchor),
                       self.original + b'\0', trace.instrument(self.original)]:
            with self.subTest(sha=hashlib.sha256(source).hexdigest()), self.assertRaises(ValueError):
                trace.instrument(source)

    def test_trace_fields_and_evaluation_sites_are_explicit(self):
        data = trace.instrument(self.original)
        for field in [b'input_lat', b'input_unspecified', b'legacy', b'prior_type', b'prior_arrived',
                      b'prior_person', b'old_lane_null', b'old_pos', b'old_lat', b'new_dir', b'inherited', b'final_lat']:
            self.assertIn(b'"' + field + b'"', data)
        self.assertEqual(data.count(b'// JDRT_TRACE_BEGIN '), 5)
        blocks = re.findall(rb'(?ms)^[ \t]*// JDRT_TRACE_BEGIN [a-z_]+\r?\n(.*?)^[ \t]*// JDRT_TRACE_END [a-z_]+\r?\n', data)
        self.assertEqual(len(blocks), 5)
        for block in blocks:
            for forbidden in (b'moveToXY', b'RandHelper::'):
                self.assertNotIn(forbidden, block)
            self.assertIsNone(re.search(rb'\b(?:myPosLat|myDir)\s*=(?!=)', block))

    def test_crlf_source_round_trips_without_normalizing_original_bytes(self):
        source = self.original.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        instrumented = trace.instrument(source)
        self.assertEqual(trace.restore(instrumented), source)
        trace.verify(source, instrumented)

    def test_missing_trace_end_marker_is_rejected(self):
        instrumented = trace.instrument(self.original)
        changed = instrumented.replace(b'// JDRT_TRACE_END candidate', b'// removed end')
        with self.assertRaises(ValueError): trace.restore(changed)
        with self.assertRaises(ValueError): trace.verify(self.original, changed)


if __name__ == '__main__':
    unittest.main()
