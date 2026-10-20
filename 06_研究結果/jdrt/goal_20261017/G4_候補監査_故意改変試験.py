"""In-memory counterexamples; never modify run artifacts or invoke SUMO."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import importlib.util
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
SOURCE = HERE / 'G4_候補選択独立監査.py'
spec = importlib.util.spec_from_file_location('choice_independent_candidate_audit', SOURCE)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
RUN = 'choice_smoke_u05r2p900_seed23423_20261017_02'
cfg = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
folder = ROOT / cfg['workspace'] / 'smoke' / RUN
original_rows = auditor.rows
base = list(original_rows(folder / 'candidates.csv.gz'))
# Candidate audit needs traffic values and every snapshot time, not zero road rows.
# The complete road table is independently checked by the alignment/accounting auditors.
sparse, seen = [], set()
for row in original_rows(folder / 'edge_observations.csv.gz'):
    if row['time_sec'] not in seen or (row['mode'] in ('car', 'drt') and int(row['traffic_count']) > 0):
        sparse.append(row)
    seen.add(row['time_sec'])
mutated = base


def fixture_rows(path):
    if path.name == 'candidates.csv.gz':
        return iter(mutated)
    if path.name == 'edge_observations.csv.gz':
        return iter(sparse)
    return original_rows(path)


def set_value(rows, index, name, value):
    rows[index][name] = value


eligible = next(i for i, row in enumerate(base) if row['score'] != '')
finite = next(i for i, row in enumerate(base) if row['forecast_remaining_kind'] == 'finite')
selected = next(i for i, row in enumerate(base) if row['decision'] == 'selected')
path_index = next(i for i, row in enumerate(base) if json.loads(row['pickup_path']))
cases = [
    ('source_position_shift', lambda r: set_value(r, 0, 'source_pos_m', str(float(r[0]['source_pos_m']) + 1)), 'candidate_source_observation'),
    ('pickup_time_shift', lambda r: set_value(r, eligible, 'pickup_sec', str(float(r[eligible]['pickup_sec']) + 1)), 'candidate_shortest_time'),
    ('forecast_time_shift', lambda r: set_value(r, finite, 'forecast_remaining_sec', str(float(r[finite]['forecast_remaining_sec']) + 60)), 'candidate_forecast_required'),
    ('score_shift', lambda r: set_value(r, eligible, 'score', str(float(r[eligible]['score']) + .125)), 'candidate_score'),
    ('selection_omitted', lambda r: set_value(r, selected, 'decision', 'not_selected'), 'candidate_choice_and_acceptance'),
    ('candidate_omitted', lambda r: r.pop(), 'cycle_primary_counts'),
    ('gate_boolean_flipped', lambda r: set_value(r, finite, 'gate_pass', 'False' if r[finite]['gate_pass'] == 'True' else 'True'), 'candidate_gate_components'),
    ('path_origin_corrupted', lambda r: set_value(r, path_index, 'pickup_path', json.dumps(['__not_a_road__'] + json.loads(r[path_index]['pickup_path'])[1:])), 'candidate_open_path'),
    ('urgency_shift', lambda r: set_value(r, finite, 'urgency', str(float(r[finite]['urgency']) + .1)), 'candidate_score_components'),
    ('nan_disguised_finite', lambda r: set_value(r, eligible, 'pickup_sec', 'nan'), 'exception'),
]
results = []
with patch.object(auditor, 'rows', side_effect=fixture_rows):
    baseline = auditor.audit(RUN)
    assert baseline['status'] == 'PASS', baseline['errors']
    for name, change, expected in cases:
        mutated = deepcopy(base)
        change(mutated)
        try:
            result = auditor.audit(RUN)
            passed = result['status'] == 'FAIL' and result['checks'].get(expected) is False
            results.append({'case': name, 'expected_rejection': expected, 'pass': passed,
                            'failed_checks': [k for k, v in result['checks'].items() if not v]})
        except ValueError as error:
            results.append({'case': name, 'expected_rejection': expected, 'pass': expected == 'exception',
                            'exception': type(error).__name__, 'message': str(error)})
report = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
          'status': 'PASS' if all(r['pass'] for r in results) else 'FAIL', 'run_id': RUN,
          'scope': 'candidate_auditor_counterexamples_only_not_core_readiness',
          'baseline': baseline['status'], 'cases': results, 'primary_artifacts_modified': False,
          'auditor_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'sparse_traffic_rows': len(sparse), 'snapshot_times_preserved': len(seen)}
target = HERE / '候補監査_故意改変試験.json'
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report['status'] == 'PASS' else 1)
