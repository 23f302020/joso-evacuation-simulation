"""Historical primary-artifact integration and in-memory counterexamples only."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '04_プログラム'))
from scripts import jdrt_realtime_choice_validate as validator


def main():
    cfg = json.loads(validator.PARAM.read_text(encoding='utf-8'))
    technical = ROOT / cfg['workspace'] / 'technical'
    suite = json.loads((technical / 'cf26101710/manifest.json').read_text(encoding='utf-8'))
    baseline, signatures = [], {}
    for case in suite['cases']:
        report = validator.audit_run_tables(case['child_run_id'], 'fixture', require_current=False)
        baseline.append(report)
        folder = technical / case['child_run_id'] / 'execution'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        for filename in manifest['output_sha256']:
            signatures[folder / filename] = validator.file_sha(folder / filename)
    assert all(r['status'] == 'INCOMPLETE' and not r['core_adoption_permitted']
               and all(c['status'] == 'PASS' for c in r['components'].values()) for r in baseline), [
                   {'run': r['run_id'], 'error': r.get('error'), 'failures': {
                       k: v['examples'] for k, v in r['components'].items() if v['status'] != 'PASS'}}
                   for r in baseline if r['status'] != 'INCOMPLETE']
    current_rejection = validator.audit_run_tables(suite['cases'][0]['child_run_id'], 'fixture')
    assert current_rejection['status'] == 'INVALID' and not current_rejection['checks']['all_bound_bytes_before']
    original_rows, original_stream = validator.rows, validator.stream_rows
    results = []

    def mutate_first(records, field, value, predicate=lambda r: True):
        row = next(r for r in records if predicate(r))
        row[field] = value(row[field]) if callable(value) else value

    cases = [
        ('population_missing', 12, 'common_realization.csv', 'person',
         lambda r: r.pop(), 'complete_population'),
        ('population_duplicate', 12, 'person_results.csv', 'person',
         lambda r: r.append(deepcopy(r[0])), 'unique_tables'),
        ('source_attribute_corrupted', 1, 'common_realization.csv', 'person',
         lambda r: mutate_first(r, 'ready_sec', lambda v: str(int(v) + 1)), 'common_realization_and_attributes'),
        ('request_omitted', 8, 'request_results.csv', 'person',
         lambda r: r.pop(), 'request_set'),
        ('boarding_duration_corrupted', 8, 'request_results.csv', 'person',
         lambda r: mutate_first(r, 'boarded_sec', lambda v: str(float(v) - 1)), 'request_lifecycle'),
        ('shared_capacity_account_corrupted', 12, 'facility_results.csv', 'person',
         lambda r: mutate_first(r, 'admitted', lambda v: str(int(v) + 1)), 'shared_capacity_and_exit'),
        ('candidate_shortest_time_corrupted', 8, 'candidates.csv.gz', 'candidate',
         lambda r: mutate_first(r, 'pickup_sec', lambda v: str(float(v) + 1)), 'candidate_shortest_paths'),
        ('candidate_missing', 8, 'candidates.csv.gz', 'candidate',
         lambda r: r.pop(), 'cycle_counts'),
        ('candidate_nan_source_speed', 8, 'candidates.csv.gz', 'candidate',
         lambda r: mutate_first(r, 'source_speed_mps', 'nan'), 'ValueError'),
        ('zero_road_row_missing', 8, 'edge_observations.csv.gz', 'road',
         lambda r: r.pop(next(i for i, row in enumerate(r) if row['count'] == '0')), 'full_road_grid'),
        ('snapshot_raw_speed_corrupted', 14, 'snapshot_actor_observations.csv.gz', 'road',
         lambda r: mutate_first(r, 'speed_mps', lambda v: str(float(v) + .2)), 'snapshot_primary_reaggregation'),
        ('native_road_membership_corrupted', 8, 'snapshot_actor_observations.csv.gz', 'road',
         lambda r: mutate_first(r, 'native_edge_contains_vehicle', lambda v: str(v != 'True'),
                                lambda p: p['native_edge_contains_vehicle'] != ''), 'native_edge_membership'),
        ('actor_step_omitted', 14, 'actor_observations.csv.gz', 'actor',
         lambda r: r.pop(0), 'actor_grid_completeness'),
        ('actor_wrong_phase', 14, 'actor_observations.csv.gz', 'actor',
         lambda r: mutate_first(r, 'phase', 'after_control_before_step'), 'actor_phase_unique_membership'),
        ('actor_route_index_corrupted', 14, 'actor_observations.csv.gz', 'actor',
         lambda r: mutate_first(r, 'route_index', '-1', lambda p: p['observation_kind'] == 'onroad'), 'actor_route_index'),
        ('walking_speed_exceeded', 1, 'actor_observations.csv.gz', 'actor',
         lambda r: mutate_first(r, 'speed_mps', '2'), 'actor_walk_integral_and_speed'),
        ('VKT_backend_corrupted', 14, 'vehicle_results.csv', 'actor',
         lambda r: mutate_first(r, 'distance_m', lambda v: str(float(v) + 1)), 'backend_vkt'),
        ('native_controller_clock_conflated', 14, 'person_results.csv', 'actor',
         lambda r: mutate_first(r, 'arrival_sec', lambda v: str(float(v) - cfg['simulation']['step_sec'])), 'actor_arrival_clock'),
    ]
    for name, index, filename, component, change, expected in cases:
        folder = technical / ('cf26101710_c' + str(index).zfill(2)) / 'execution'
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        cfg = json.loads((ROOT / m['parameter_path']).read_text(encoding='utf-8'))
        events = [json.loads(s) for s in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        target = folder / filename
        altered = deepcopy(list(original_stream(target)))
        change(altered)
        fake_rows = lambda path: deepcopy(altered) if path == target else original_rows(path)
        fake_stream = lambda path: iter(deepcopy(altered)) if path == target else original_stream(path)
        try:
            with patch.object(validator, 'rows', side_effect=fake_rows), patch.object(validator, 'stream_rows', side_effect=fake_stream):
                report = (validator.audit_person_tables(folder, m, cfg, events) if component == 'person' else
                          validator.audit_candidates(folder, m, cfg, events) if component == 'candidate' else
                          validator.audit_actor_stream(folder, m, cfg, events) if component == 'actor' else
                          validator.audit_road_snapshots(folder, m, cfg))
            passed = report['status'] == 'INVALID' and report['checks'].get(expected) is False
            failed = [k for k, v in report['checks'].items() if not v]
        except ValueError as error:
            passed, failed = expected == 'ValueError', [str(error)]
        results.append({'case': name, 'expected': expected, 'pass': passed, 'failed_checks': failed})
    unchanged = all(validator.file_sha(path) == value for path, value in signatures.items())
    report = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'status': 'PASS' if all(r['pass'] for r in results) and unchanged else 'FAIL',
              'scope': 'canonical_validator_partial_tables_historical_fixture_diagnostics_not_READY',
              'core_adoption_permitted': False, 'technical_ready': False,
              'historical_fixture_components': baseline, 'counterexamples': results,
              'current_SHA_gate_rejects_old_suite': current_rejection['status'] == 'INVALID',
              'primary_outputs_unchanged': unchanged, 'primary_files_rechecked': len(signatures),
              'validator_sha256': validator.file_sha(Path(validator.__file__)),
              'test_sha256': validator.file_sha(Path(__file__))}
    history = Path(__file__).parent / 'auditor_history'
    history.mkdir(exist_ok=True)
    for source_file in (Path(validator.__file__), Path(__file__)):
        archived = history / (source_file.stem + '_' + validator.file_sha(source_file) + '.py')
        if not archived.exists():
            archived.write_bytes(source_file.read_bytes())
        assert validator.file_sha(archived) == validator.file_sha(source_file)
    target = Path(__file__).with_name('正式検証器_表会計候補_' + datetime.now().strftime('%Y%m%dT%H%M%S') + '.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'historical_fixture_components'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
