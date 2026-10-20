"""All-70 synthetic integration only. No SUMO, native validation, or real ledger access.

Synthetic PASS metadata exercises the analysis contract; it is never evidence
that research runs or native transitions satisfy adoption requirements.
"""
import contextlib
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('G6_主指標・事前登録差分_集計.py')
spec = importlib.util.spec_from_file_location('choice_integrated_analysis', SOURCE)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def save(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return analysis.digest(path)


def csv_file(root, name, rows, fields=None):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return analysis.digest(path)


def gzip_file(root, name, rows, fields):
    path = root / name
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    return analysis.digest(path)


def analyze_fixture(root):
    with patch.object(analysis, 'SECONDARY_PROOF', root / 'service_contract.json'):
        return analysis.analyze(root)


def mixed_requests():
    people, requests, events = [], [], []
    endpoints = [
        ('served', 'capacity_rejected', {'boarding_started_sec': '2', 'boarded_sec': '302',
            'alighting_started_sec': '400', 'alighted_sec': '700'}),
        ('cancelled_timeout', 'admitted', {'cancel_sec': '900', 'fallback_sec': '900'}),
        ('cancelled_vehicle_failure', 'boundary_exit', {'cancel_sec': '100', 'fallback_sec': '100'}),
        ('rejected_input', 'no_origin_connection', {}),
        ('time_limit', 'time_limit', {'received_sec': '900'}),
        ('failed_after_boarding', 'stranded_drt', {'boarding_started_sec': '20'}),
        ('time_limit', 'time_limit', {'boarding_started_sec': '900'})]
    for index, (qstatus, pstatus, times) in enumerate(endpoints):
        pid = 'p' + str(index)
        p = {'person_id': pid, 'person_type': 'type4', 'selected_jdrt': 'True',
             'status': pstatus, 'mode': 'walk', 'terminal_id': 'x' if pstatus == 'boundary_exit' else 'f',
             'arrival_sec': '950' if pstatus == 'admitted' else '200' if pstatus == 'boundary_exit' else '',
             'admitted_sec': '950' if pstatus == 'admitted' else '',
             'origin_ped_closed_wait_sec': str(index), 'origin_vehicle_closed_wait_sec': str(index * 2)}
        q = {'request_id': 'q' + str(index), 'person_id': pid, 'vehicle_id': 'synthetic_drt_0', 'status': qstatus, 'deadline_sec': '1000',
             'person_final_status': pstatus, 'person_final_mode': 'walk', 'cancel_reason': '',
             **{key: '' for key in ['accepted_sec', 'boarding_started_sec', 'boarded_sec',
                 'alighting_started_sec', 'alighted_sec', 'cancel_sec', 'fallback_sec']},
             'received_sec': '0', **times}
        if qstatus in ('rejected_input', 'failed_after_boarding'):
            events.append({'event': 'request_state', 'person_id': pid, 'request_id': q['request_id'],
                           'after': qstatus, 'time_sec': 0 if qstatus == 'rejected_input' else 30})
        people.append(p)
        requests.append(q)
    return people, requests, events


def all70_fixture(root):
    """Build independent artificial primary artifacts, retaining registered cell identities."""
    registered = json.loads((analysis.ROOT / analysis.CONFIG).read_text(encoding='utf-8'))
    cfg = {'cells': registered['cells'], 'seeds': registered['seeds'], 'protocol': 'synthetic_all70_contract',
           'workspace': 'ws', 'record_files': ['context.md', 'task.md', 'progress.md', 'a.md', 'b.md', 'ledger.jsonl'],
           'execution': {'implementation_files': ['impl.py']}, 'simulation': {'duration_sec': 1000},
           'analysis': registered['analysis'], 'demand_levels': registered['demand_levels'],
           'operation': {'fleet_count': 1, 'pooling': False, 'boarding_sec': 300, 'alighting_sec': 300},
           'population': {'walk_limit_m': 3000}}
    config_sha = save(root, analysis.CONFIG, cfg)
    (root / 'impl.py').write_text('# artificial implementation\n', encoding='utf-8')
    impl = {'impl.py': analysis.digest(root / 'impl.py')}
    save(root, 'service_contract.json', {'implementation_sha256': impl, 'conditions': dict.fromkeys(
        ['initially_empty', 'serial_one_person', 'all_available_at_zero', 'full_processing_times', 'no_vehicle_time_reset'], True)})
    people, requests, events = mixed_requests()
    inputs = 'inputs'
    artifacts = {'people.csv': csv_file(root, inputs + '/people.csv',
        [{'person_id': p['person_id'], 'person_type': p['person_type'], 'origin_id': 'o'} for p in people]),
        'terminals.csv': csv_file(root, inputs + '/terminals.csv', [
            {'terminal_id': 'f', 'kind': 'facility', 'capacity': '10'},
            {'terminal_id': 'x', 'kind': 'exit', 'capacity': '0'}])}
    for destination in registered['destination_policies']:
        name = 'destinations_' + destination + '.csv'
        artifacts[name] = csv_file(root, inputs + '/' + name, [{'origin_id': 'o', 'terminal_id': 'f',
            'car_route': '["e"]', 'walk_route': '["e"]', 'walk_length_m': '1'}])
    for seed in cfg['seeds']:
        name = 'common_realization_seed' + str(seed) + '.csv'
        artifacts[name] = csv_file(root, inputs + '/' + name,
            [{'person_id': p['person_id'], 'intent_u05': 'True', 'intent_u50': 'True'} for p in people])
    (root / 'source.txt').write_text('artificial input source\n', encoding='utf-8')
    input_sha = save(root, inputs + '/manifest.json', {'artifacts': artifacts,
        'source_sha256': {'source.txt': analysis.digest(root / 'source.txt')}})
    components = ['person_tables', 'candidate_tables', 'road_snapshots', 'actor_stream',
                  'movement_events', 'native_logs', 'native_fixture_boundaries']
    rows = []
    for index, cell in enumerate(cfg['cells']):
        run = 'synthetic_' + str(index)
        folder = 'ws/runs/' + run
        r0 = cell['scenario'] == 'R0'
        observed_people = [dict(p, selected_jdrt='False' if r0 else 'True',
            origin_ped_closed_wait_sec='0' if r0 else p['origin_ped_closed_wait_sec'],
            origin_vehicle_closed_wait_sec='0' if r0 else p['origin_vehicle_closed_wait_sec']) for p in people]
        outputs = {
            'person_results.csv': csv_file(root, folder + '/person_results.csv', observed_people),
            'request_results.csv': csv_file(root, folder + '/request_results.csv', [] if r0 else requests, list(requests[0])),
            'facility_results.csv': csv_file(root, folder + '/facility_results.csv',
                [{'terminal_id': 'f', 'capacity': '10', 'admitted': '1'}])}
        outputs['vehicle_results.csv'] = csv_file(root, folder + '/vehicle_results.csv', [] if r0 else [{
            'vehicle_id': 'synthetic_drt_0', 'kind': 'drt', 'status': 'idle', 'distance_m': '',
            'observed_distance_m': '10', 'observed_empty_distance_m': '4'}],
            ['vehicle_id', 'kind', 'status', 'distance_m', 'observed_distance_m', 'observed_empty_distance_m'])
        for name, fields in [
            ('candidates.csv.gz', ['cycle', 'stage', 'decision', 'reason', 'pickup_route', 'delivery_route',
                'pickup_before_deadline', 'completion_within_horizon', 'gate_applicable', 'gate_pass']),
            ('dispatch_cycles.csv.gz', ['cycle', 'time_sec', 'free_start', 'pending_start', 'stages', 'candidate_rows', 'accepted']),
            ('transitions.csv.gz', ['mode', 'kind', 'ambiguous'])]:
            outputs[name] = gzip_file(root, folder + '/' + name, [], fields)
        road = {'time_sec': '0', 'edge_id': 'e', 'mode': 'drt', 'closed': 'False', 'count': '0',
            'traffic_count': '0', 'mean_speed_mps': '', 'traffic_mean_speed_mps': '',
            **dict.fromkeys(['halting_count', 'traffic_halting_count', 'parked_count',
                            'reentry_pending_count', 'unplaced_reentry_count'], '0')}
        outputs['edge_observations.csv.gz'] = gzip_file(root, folder + '/edge_observations.csv.gz', [road], list(road))
        event_path = root / folder / 'events.jsonl'
        event_path.write_text('' if r0 else ''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
        outputs['events.jsonl'] = analysis.digest(event_path)
        outputs['preflight_ready.json'] = save(root, folder + '/preflight_ready.json', {'synthetic': True})
        archive = root / folder / 'implementation' / 'impl.py'
        archive.parent.mkdir(parents=True)
        archive.write_bytes((root / 'impl.py').read_bytes())
        manifest = {'run_id': run, **cell, 'purpose': 'core', 'protocol': cfg['protocol'],
            'status': 'COMPLETED', 'implementation_sha256': impl, 'parameter_sha256': config_sha,
            'end_sec': 1000, 'input_directory': inputs, 'input_manifest_sha256': input_sha,
            'output_sha256': outputs, 'preflight_ready_sha256': outputs['preflight_ready.json']}
        manifest_sha = save(root, folder + '/manifest.json', manifest)
        proof = {'run_id': run, 'purpose': 'core', 'status': 'PASS', 'core_adoption_permitted': True,
            'pending': [], 'manifest_sha256': manifest_sha, 'implementation_sha256': impl,
            'checks': {'artificial_contract_only': True}, 'components': {k: {'status': 'PASS'} for k in components}}
        proof['components']['person_tables'].update(primary_admitted=1, primary_denominator=len(people))
        proof_name = 'proof/' + run + '.json'
        proof_sha = save(root, proof_name, proof)
        rows.append({**cell, 'run_id': run, 'protocol': cfg['protocol'], 'purpose': 'core',
            'validation_status': 'PASS', 'implementation_sha256': impl, 'manifest_sha256': manifest_sha,
            'validation_report': proof_name, 'validation_report_sha256': proof_sha, 'input_manifest_sha256': input_sha})
    markers = ''.join('<!-- choice_record:' + r['run_id'] + ' -->\n' for r in rows)
    for name in cfg['record_files'][:-1]:
        (root / name).write_text(markers + '\n<!-- AGENT_CURRENT_END -->\n', encoding='utf-8')
    (root / cfg['record_files'][-1]).write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    return cfg, rows


class IntegratedContracts(unittest.TestCase):
    def test_all70_gate_precedes_helper_load_and_any_result_write(self):
        with tempfile.TemporaryDirectory(prefix='g6_all70_incomplete_') as temp:
            root = Path(temp)
            cfg, rows = all70_fixture(root)
            self.assertEqual(len(rows), 70)
            (root / 'ledger.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows[:-1]), encoding='utf-8')
            with patch.object(analysis, 'load_request_component', side_effect=AssertionError('premature helper')):
                with self.assertRaisesRegex(RuntimeError, 'complete registered set'):
                    analyze_fixture(root)
            self.assertFalse((root / '06_研究結果').exists())

    def test_complete_artificial_set_separates_wait_censoring_exit_and_zero_R0(self):
        with tempfile.TemporaryDirectory(prefix='g6_all70_complete_') as temp:
            root = Path(temp)
            cfg, _ = all70_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                target = analyze_fixture(root)
            primary = analysis.table(target / '全セル主指標.csv')
            self.assertEqual(len(primary), 70)
            self.assertTrue(all((r['admitted'], r['boundary_exit'], r['denominator']) == ('1', '1', '7') for r in primary))
            summaries = analysis.table(target / '全セル要求_段階待ち会計.csv')
            r0 = [r for r in summaries if r['scenario'] == 'R0']
            self.assertEqual(len(r0), 10 * 3)  # 2 D x 5 seeds, never duplicated by u.
            self.assertTrue(all(r['requests'] == '0' and r['observed_wait_mean_sec'] == '' for r in r0))
            total = next(r for r in summaries if r['scenario'] != 'R0' and r['group'] == 'all')
            self.assertEqual((total['requests'], total['request_served'], total['person_admitted'],
                total['fallback_attempted'], total['horizon_right_censored_preboarding']), ('7', '1', '1', '2', '1'))
            self.assertAlmostEqual(float(total['observed_wait_mean_sec']), 2022 / 7)
            self.assertEqual(float(total['origin_ped_closed_unboarded_including_boarding_sec_sum']), 21)
            self.assertEqual(float(total['origin_vehicle_closed_unboarded_including_boarding_sec_sum']), 42)
            details = analysis.table(target / '全要求_待ち段階明細.csv')
            self.assertEqual(len(details), 60 * 7)
            self.assertTrue(all(r['scenario'] != 'R0' for r in details))
            failures = [r for r in details if r['request_final_status'] == 'failed_after_boarding']
            self.assertTrue(all(r['boarding_duration_observed_sec'] == '10.0' and r['wait_right_censored_at_H'] == 'False' for r in failures))
            distribution = analysis.table(target / '全要求_終端別観測待ち分布.csv')
            self.assertEqual(sum(int(r['count']) for r in distribution if r['group'] == 'all'), 60 * 7)
            diagnostics = analysis.table(target / 'PAP診断差分_全seed.csv')
            self.assertEqual(len(diagnostics), 5 * (1 + 3 * 5))
            self.assertEqual(sum(r['scenario'] == 'R0' for r in diagnostics), 5)
            manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['request_analysis_source_sha256'], analysis.digest(analysis.REQUEST_SOURCE))
            self.assertEqual(len(manifest['remaining']), 3)
            self.assertEqual(len(manifest['output_sha256']), 19)
            self.assertEqual(manifest['secondary_analysis_source_sha256'], analysis.digest(analysis.SECONDARY_SOURCE))
            bounds = analysis.table(target / '全セル_DRT直接完了上限.csv')
            self.assertEqual(len(bounds), 70)
            self.assertTrue(all(r['service_only_completion_upper'] == ('0' if r['scenario'] == 'R0' else '1') for r in bounds))
            vehicles = analysis.table(target / '全車両_距離状態会計.csv')
            self.assertTrue(all(r['native_distance_complete_sum_m'] == '' for r in vehicles if r['kind'] == 'drt' and r['scenario'] != 'R0'))
            offered = analysis.table(target / 'D別seed_u_提供需要仕事量.csv')
            self.assertEqual(len(offered), 20)
            self.assertTrue(all('scenario' not in row and 'run_id' not in row for row in offered))
            self.assertEqual(analysis.table(target / '全候補cycle_stage_理由boolean会計.csv'), [])
            self.assertTrue(all(analysis.digest(target / k) == v for k, v in manifest['output_sha256'].items()))

    def test_changed_primary_artifact_is_rejected_before_result_output(self):
        with tempfile.TemporaryDirectory(prefix='g6_all70_tampered_') as temp:
            root = Path(temp)
            all70_fixture(root)
            with (root / 'ws/runs/synthetic_0/person_results.csv').open('a', encoding='utf-8') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(RuntimeError, 'source bytes changed before aggregation'):
                analyze_fixture(root)
            self.assertFalse((root / '06_研究結果').exists())

    def test_changed_helper_bytes_during_analysis_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='g6_all70_helper_tampered_') as temp:
            root = Path(temp)
            all70_fixture(root)
            helper = root / 'request_helper.py'
            helper.write_bytes(analysis.REQUEST_SOURCE.read_bytes())
            original_loader = analysis.load_request_component

            def mutate_after_load():
                module, expected = original_loader()
                helper.write_bytes(helper.read_bytes() + b'\n# artificial mid-analysis mutation\n')
                return module, expected

            with patch.object(analysis, 'REQUEST_SOURCE', helper), patch.object(analysis, 'load_request_component', mutate_after_load):
                with self.assertRaisesRegex(RuntimeError, 'Request analysis source changed'):
                    analyze_fixture(root)
            self.assertFalse((root / '06_研究結果').exists())

    def test_stale_frozen_service_source_proof_rejects_before_output(self):
        with tempfile.TemporaryDirectory(prefix='g6_all70_stale_proof_') as temp:
            root = Path(temp)
            all70_fixture(root)
            proof = json.loads((root / 'service_contract.json').read_text(encoding='utf-8'))
            proof['implementation_sha256']['impl.py'] = '0' * 64
            save(root, 'service_contract.json', proof)
            with self.assertRaisesRegex(RuntimeError, 'Frozen service-contract source changed'):
                analyze_fixture(root)
            self.assertFalse((root / '06_研究結果').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
