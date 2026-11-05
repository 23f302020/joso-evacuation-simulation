import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from measurement_coverage import coverage, run


BASE = datetime(2020, 1, 1, tzinfo=timezone.utc)


def at(seconds):
    return (BASE + timedelta(seconds=seconds)).isoformat()


def sample(seconds, pid=7, created=None, cpu=None):
    return {'observed_at': at(seconds), 'processes': [
        {'pid': pid, 'created': created or at(-10),
         'cpu_sec': seconds if cpu is None else cpu}]}


def stage(start=0, end=120):
    return {'name': 'artificial', 'pid': 7, 'created': at(-10),
            'start': at(start), 'end': at(end)}


class CoverageContracts(unittest.TestCase):
    def test_contiguous(self):
        self.assertEqual(coverage([[sample(0), sample(60), sample(120)]], stage())['covered_seconds'], 120)

    def test_long_gap_not_filled(self):
        self.assertEqual(coverage([[sample(0), sample(121), sample(180)]], stage(0, 180))['covered_seconds'], 59)

    def test_failed_sample_not_bridged(self):
        rows = [sample(0), {'observed_at': at(60), 'error': 'TimeoutExpired'}, sample(120)]
        self.assertEqual(coverage([rows], stage())['covered_seconds'], 0)

    def test_same_pid_new_creation_not_counted(self):
        rows = [sample(0), sample(60, created=at(30)), sample(120, created=at(30))]
        self.assertEqual(coverage([rows], stage())['covered_seconds'], 0)

    def test_wrong_pid_not_counted(self):
        self.assertEqual(coverage([[sample(0, pid=8), sample(120, pid=8)]], stage())['covered_seconds'], 0)

    def test_overlap_not_double_counted(self):
        rows = [sample(0), sample(60), sample(120)]
        self.assertEqual(coverage([rows, copy.deepcopy(rows)], stage())['covered_seconds'], 120)

    def test_clip_to_stage(self):
        self.assertEqual(coverage([[sample(0), sample(120)]], stage(30, 90))['covered_seconds'], 60)

    def test_cpu_reset_and_nonfinite_not_counted(self):
        for value in (-1, float('nan'), float('inf')):
            with self.subTest(value=value):
                self.assertEqual(coverage([[sample(0), sample(120, cpu=value)]], stage())['covered_seconds'], 0)

    def test_unknown_creation_not_inferred(self):
        rows = [sample(0), sample(120)]
        del rows[1]['processes'][0]['created']
        self.assertEqual(coverage([rows], stage())['covered_seconds'], 0)

    def test_invalid_or_naive_stage_clock_refused(self):
        for field, value in [('start', '2020-01-01T00:00:00'), ('end', at(-1))]:
            with self.subTest(field=field):
                definition = stage()
                definition[field] = value
                with self.assertRaises(ValueError):
                    coverage([[sample(0), sample(120)]], definition)

    def test_exact_120_boundary_is_valid(self):
        self.assertEqual(coverage([[sample(0), sample(120)]], stage())['covered_seconds'], 120)


class SnapshotContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root/'source'
        self.source.mkdir()
        self.evidence = self.root/'point.json'
        self.evidence.write_text('{}', encoding='utf-8')
        self.stages = self.root/'stages.json'
        self.definitions = {'schema': 'pipeline_stage_definitions_v1', 'run_id': 'artificial',
                            'registration_id': 'artificial', 'stages': [stage()],
                            'evidence': {'point.json': sha256(self.evidence.read_bytes()).hexdigest()}}
        self.stages.write_text(json.dumps(self.definitions), encoding='utf-8')
        (self.source/'state.json').write_text(json.dumps({'schema':'pipeline_measurement_v1','samples':999}), encoding='utf-8')
        (self.source/'samples.jsonl').write_text('\n'.join(json.dumps(sample(i)) for i in (0,60,120))+'\n', encoding='utf-8')
        self.output = self.root/'07_監視システム/verification/new'

    def test_snapshot_keeps_raw_input_and_does_not_trust_state_count(self):
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        result = run(self.root, [self.source], self.stages, self.output)
        self.assertEqual(result['status'], 'OBSERVATION_COVERAGE_ONLY')
        self.assertEqual(result['stages'][0]['covered_seconds'], 120)
        self.assertEqual(result['sources'][0]['samples'], 3)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.source.iterdir()})
        for name, raw in before.items():
            self.assertEqual((self.output/'0'/name).read_bytes(), raw)

    def test_output_reuse_refused(self):
        run(self.root, [self.source], self.stages, self.output)
        before = (self.output/'report.json').read_bytes()
        with self.assertRaises(FileExistsError):
            run(self.root, [self.source], self.stages, self.output)
        self.assertEqual((self.output/'report.json').read_bytes(), before)

    def test_changed_stage_evidence_refused(self):
        self.evidence.write_text('{"changed":true}', encoding='utf-8')
        with self.assertRaises(ValueError):
            run(self.root, [self.source], self.stages, self.output)
        self.assertFalse((self.output/'report.json').exists())

    def test_research_workspace_write_refused(self):
        output = self.root/'04_プログラム/output/sumo/regions/08211/experiments/new'
        with self.assertRaises(ValueError):
            run(self.root, [self.source], self.stages, output)
        self.assertFalse(output.exists())

    def test_partial_jsonl_preserved_and_not_reported_success(self):
        with (self.source/'samples.jsonl').open('a', encoding='utf-8') as stream:
            stream.write('{"partial":')
        with self.assertRaises(json.JSONDecodeError):
            run(self.root, [self.source], self.stages, self.output)
        self.assertEqual((self.output/'0/samples.jsonl').read_bytes(), (self.source/'samples.jsonl').read_bytes())
        self.assertFalse((self.output/'report.json').exists())


if __name__ == '__main__':
    unittest.main()
