"""Historical primary-artifact integration and in-memory counterexamples only."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import json
import argparse
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '04_プログラム'))
from scripts import jdrt_realtime_choice_validate as validator


def main(suite_id, historical=False):
    cfg = json.loads(validator.PARAM.read_text(encoding='utf-8'))
    technical = ROOT / cfg['workspace'] / 'technical'
    suite = json.loads((technical / suite_id / 'manifest.json').read_text(encoding='utf-8'))
    baseline, signatures = [], {}
    for case in suite['cases']:
        report = validator.audit_run_tables(case['child_run_id'], 'fixture', require_current=not historical)
        baseline.append(report)
        folder = technical / case['child_run_id'] / 'execution'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        for filename in manifest['output_sha256']:
            signatures[folder / filename] = validator.file_sha(folder / filename)
    assert all(r['status'] == 'INCOMPLETE' and not r['core_adoption_permitted']
               and all(c['status'] == 'PASS' for c in r['components'].values()) for r in baseline), [
                   {'run': r['run_id'], 'error': r.get('error'), 'failures': {
                       k: v.get('examples', v.get('checks')) for k, v in r['components'].items() if v['status'] != 'PASS'}}
                   for r in baseline if r['status'] != 'INCOMPLETE']
    current_rejection = validator.audit_run_tables('cf26101710_c01', 'fixture')
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
        ('native_braking_bound_corrupted', 8, 'candidates.csv.gz', 'candidate',
         lambda r: mutate_first(r, 'minimum_advance_m', lambda v: str(float(v) + 1)), 'candidate_source'),
        ('native_deceleration_corrupted', 8, 'candidates.csv.gz', 'candidate',
         lambda r: mutate_first(r, 'source_decel_mps2', lambda v: str(float(v) * 2)), 'candidate_source'),
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
        ('external_entry_omitted', 14, 'transitions.csv.gz', 'movement',
         lambda r: r.pop(), 'all_entries_primary_multiset'),
        ('external_entry_duplicate', 14, 'transitions.csv.gz', 'movement',
         lambda r: r.append(deepcopy(r[-1])), 'all_entries_primary_multiset'),
        ('walk_native_remaining_corrupted', 1, 'events.jsonl', 'movement',
         lambda r: mutate_first(r, 'old_remaining_m', lambda v: v - 1,
             lambda p: p['event'] == 'walk_plan' and p.get('stage') == 'reroute'), 'walk_stage_budget_recurrence'),
        ('walk_budget_stop_event_omitted', 3, 'events.jsonl', 'movement',
         lambda r: r.__setitem__(slice(None), [e for e in r if e['event'] != 'walk_budget_pre_step_stop']), 'walk_pre_step_budget_stop'),
        ('person_invalid_state_transition', 15, 'events.jsonl', 'person',
         lambda r: mutate_first(r, 'after', 'boarding', lambda p: p['event'] == 'person_state'), 'person_fsm'),
    ]
    if len(suite['cases']) >= 21:
        cases.extend([
            ('before_deadline_boarding_moved_to_equality', 18, 'request_results.csv', 'boundary',
             lambda r: mutate_first(r, 'boarding_started_sec', r[0]['deadline_sec']), 'boarding_strictly_before_then_continues'),
            ('internal_cancel_time_corrupted', 20, 'request_results.csv', 'boundary',
             lambda r: mutate_first(r, 'cancel_sec', lambda v: str(float(v) + cfg['simulation']['step_sec'])), 'accepted_timeout_before_boarding_once_fallback'),
            ('next_closed_edge_removal_time_corrupted', 21, 'events.jsonl', 'boundary',
             lambda r: mutate_first(r, 'time_sec', lambda v: v + cfg['simulation']['step_sec'],
                                    lambda e: e['event'] == 'actor_removed'), 'next_external_closure_and_removal'),
        ])
    for name, index, filename, component, change, expected in cases:
        folder = technical / suite['cases'][index - 1]['child_run_id'] / 'execution'
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        cfg = json.loads((ROOT / m['parameter_path']).read_text(encoding='utf-8'))
        events = [json.loads(s) for s in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        target = folder / filename
        altered = deepcopy(events if filename == 'events.jsonl' else list(original_stream(target)))
        change(altered)
        if filename == 'events.jsonl':
            events = altered
        fake_rows = lambda path: deepcopy(altered) if path == target else original_rows(path)
        fake_stream = lambda path: iter(deepcopy(altered)) if path == target else original_stream(path)
        try:
            with patch.object(validator, 'rows', side_effect=fake_rows), patch.object(validator, 'stream_rows', side_effect=fake_stream):
                report = (validator.audit_person_tables(folder, m, cfg, events) if component == 'person' else
                          validator.audit_candidates(folder, m, cfg, events) if component == 'candidate' else
                          validator.audit_actor_stream(folder, m, cfg, events) if component == 'actor' else
                          validator.audit_movement_events(folder, m, cfg, events) if component == 'movement' else
                          validator.audit_fixture_timing(folder, m, cfg, events) if component == 'boundary' else
                          validator.audit_road_snapshots(folder, m, cfg))
            passed = report['status'] == 'INVALID' and report['checks'].get(expected) is False
            failed = [k for k, v in report['checks'].items() if not v]
        except ValueError as error:
            passed, failed = expected == 'ValueError', [str(error)]
        results.append({'case': name, 'expected': expected, 'pass': passed, 'failed_checks': failed})
    if len(suite['cases']) >= 21:
        for name, index, mutate, expected in [
            ('derived_deadline_metadata_corrupted', 17,
             lambda s: s['native_timing_reference'].__setitem__('derived_deadline_sec', s['native_timing_reference']['derived_deadline_sec'] + 1),
             'derived_deadline_registered_only_in_fixture'),
            ('artificial_time_scale_hidden', 20,
             lambda s: s['native_timing_reference'].__setitem__('technical_free_time_scale', 1),
             'explicit_artificial_underprediction_same_geometry'),
            ('internal_reference_edge_corrupted', 20,
             lambda s: s['native_timing_reference']['selected_internal_window'].__setitem__('internal_edge', ':unobserved_test'),
             'native_internal_reference'),
        ]:
            folder = technical / suite['cases'][index - 1]['child_run_id'] / 'execution'
            m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
            cfg = json.loads((ROOT / m['parameter_path']).read_text(encoding='utf-8'))
            events = [json.loads(s) for s in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
            target = ROOT / m['input_directory'] / 'manifest.json'
            original_read = Path.read_text
            changed = json.loads(original_read(target, encoding='utf-8'))
            mutate(changed)
            def fake_read(path, *args, **kwargs):
                return json.dumps(changed) if path == target else original_read(path, *args, **kwargs)
            with patch.object(Path, 'read_text', fake_read):
                result = validator.audit_fixture_timing(folder, m, cfg, events)
            results.append({'case': name, 'expected': expected,
                            'pass': result['status'] == 'INVALID' and result['checks'][expected] is False,
                            'failed_checks': [k for k, v in result['checks'].items() if not v]})
    original_sha = validator.file_sha
    archive = technical / 'cf26101711/factory.py'
    with patch.object(validator, 'file_sha', side_effect=lambda p: '0' * 64 if p == archive else original_sha(p)):
        rejected_archive = validator.audit_run_tables('cf26101711_c01', 'fixture', require_current=False)
    results.append({'case': 'historical_factory_archive_hash_corrupted', 'expected': 'all_bound_bytes_before',
                    'pass': rejected_archive['status'] == 'INVALID' and rejected_archive['checks']['all_bound_bytes_before'] is False,
                    'failed_checks': [k for k, v in rejected_archive['checks'].items() if not v]})
    folder = technical / suite['cases'][4]['child_run_id'] / 'execution'
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    events = [json.loads(s) for s in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    actor = baseline[4]['components']['actor_stream']
    original_read = Path.read_text
    target = folder / 'sumo_errors.log'
    raw = original_read(target, encoding='utf-8')
    native_cases = [
        ('unknown_native_warning', raw + 'Warning: unclassified test diagnostic\n', events, actor, 'all_warnings_evidence_classified'),
        ('native_error', raw + 'Error: test diagnostic\n', events, actor, 'no_native_errors'),
        ('known_warning_without_raw_removal_observation', raw, events,
         {**actor, 'removal_observations': {}}, 'all_warnings_evidence_classified'),
    ]
    for name, text, changed_events, changed_actor, expected in native_cases:
        def fake_read(path, *args, **kwargs):
            return text if path == target else original_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', fake_read):
            result = validator.audit_native_logs(folder, m, changed_events, changed_actor)
        results.append({'case': name, 'expected': expected,
                        'pass': result['status'] == 'INVALID' and result['checks'][expected] is False,
                        'failed_checks': [k for k, v in result['checks'].items() if not v]})
    unchanged = all(validator.file_sha(path) == value for path, value in signatures.items())
    report = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'status': 'PASS' if all(r['pass'] for r in results) and unchanged else 'FAIL',
              'scope': 'canonical_validator_fixture_components_not_READY', 'suite': suite_id,
              'historical_diagnostic': historical,
              'core_adoption_permitted': False, 'technical_ready': False,
              'fixture_components': baseline, 'counterexamples': results,
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
    print(json.dumps({k: v for k, v in report.items() if k != 'fixture_components'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', required=True)
    parser.add_argument('--historical', action='store_true')
    args = parser.parse_args()
    main(args.suite, args.historical)
