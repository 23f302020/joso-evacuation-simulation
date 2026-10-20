"""In-memory corruptions of fixture logs; keep every primary artifact unchanged."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import importlib.util
import hashlib
import json

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
source = HERE / 'G4_統合fixture独立監査.py'
spec = importlib.util.spec_from_file_location('independent_fixture_audit_for_tamper', source)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
cfg = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
technical = ROOT / cfg['workspace'] / 'technical'
original_rows, original_read = auditor.rows, Path.read_text


def change_field(records, key, value, predicate=lambda row: True):
    row = next(row for row in records if predicate(row))
    row[key] = value(row[key]) if callable(value) else value


cases = [
    ('route_index_invalid', 14, 'actor_observations.csv.gz',
     lambda records: change_field(records, 'route_index', '-1', lambda p: p['observation_kind'] == 'onroad'),
     'actual_route_index_and_version'),
    ('phase_mislabeled', 14, 'actor_observations.csv.gz',
     lambda records: change_field(records, 'phase', 'after_control_before_step'), 'observed_vehicle_empty_distances'),
    ('walking_speed_exceeds_bound', 1, 'actor_observations.csv.gz',
     lambda records: change_field(records, 'speed_mps', '2'), 'walking_speed_and_independent_integral'),
    ('walking_integral_corrupted', 3, 'person_results.csv',
     lambda records: change_field(records, 'walk_speed_integral_m', lambda v: str(float(v) + 1)), 'walking_speed_and_independent_integral'),
    ('backend_distance_corrupted', 14, 'vehicle_results.csv',
     lambda records: change_field(records, 'distance_m', lambda v: str(float(v) + 1)), 'backend_vkt_with_arrival_tail_and_rounding'),
    ('boarding_duration_corrupted', 8, 'request_results.csv',
     lambda records: change_field(records, 'boarded_sec', lambda v: str(float(v) - 1)), 'strict_deadline_and_service_durations'),
    ('snapshot_speed_corrupted', 14, 'snapshot_actor_observations.csv.gz',
     lambda records: change_field(records, 'speed_mps', lambda v: str(float(v) + .2)), 'post_control_snapshot_full_zero_inclusive_reaggregation'),
    ('native_parking_membership_flipped', 8, 'snapshot_actor_observations.csv.gz',
     lambda records: change_field(records, 'native_edge_contains_vehicle', lambda v: str(v != 'True'),
                                  lambda p: p['native_edge_contains_vehicle'] != ''), 'parking_traffic_filter_matches_native_edge_vehicle_ids'),
    ('reroute_events_omitted', 1, 'events.jsonl',
     lambda records: records.__setitem__(slice(None), [p for p in records if p['event'] != 'walk_reroute'
         and not (p['event'] == 'walk_plan' and p.get('stage') == 'reroute')]), 'named_branch_exercised'),
]
results = []
for name, index, filename, change, expected in cases:
    folder = technical / ('cf26101710_c' + str(index).zfill(2)) / 'execution'
    baseline = auditor.audit_case(folder)
    if baseline['status'] != 'PASS':
        raise ValueError('Unmodified baseline must pass: ' + name)
    target = folder / filename
    if filename == 'events.jsonl':
        records = [json.loads(line) for line in original_read(target, encoding='utf-8').splitlines()]
    else:
        records = list(original_rows(target))
    altered = deepcopy(records)
    change(altered)

    def fake_rows(path):
        return iter(altered) if path == target else original_rows(path)

    def fake_read(path, *args, **kwargs):
        return '\n'.join(json.dumps(p) for p in altered) if path == target else original_read(path, *args, **kwargs)

    with patch.object(auditor, 'rows', side_effect=fake_rows), patch.object(Path, 'read_text', fake_read):
        report = auditor.audit_case(folder)
    results.append({'case': name, 'expected_rejection': expected,
                    'pass': report['status'] == 'FAIL' and report['checks'][expected] is False,
                    'failed_checks': [k for k, v in report['checks'].items() if not v]})
report = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
          'status': 'PASS' if all(r['pass'] for r in results) else 'FAIL',
          'scope': 'independent_fixture_auditor_counterexamples_not_core_readiness',
          'primary_artifacts_modified': False, 'suite': 'cf26101710', 'cases': results,
          'auditor_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(HERE / '統合監査_故意改変試験.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report['status'] == 'PASS' else 1)
