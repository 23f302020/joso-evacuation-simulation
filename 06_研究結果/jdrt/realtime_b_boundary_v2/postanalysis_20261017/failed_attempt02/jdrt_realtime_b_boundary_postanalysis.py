"""Read-only, registered boundary-series secondary summaries. Never starts SUMO.

Durations describe observed endpoints only, with denominators and incomplete states.
Roads are instantaneous 60-second snapshots, not continuous traffic exposure.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import re
import sys
import traceback
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '06_研究結果/jdrt/realtime_b_boundary_v2/postanalysis_20261017'
CONFIG = ROOT / '04_プログラム/config/jdrt_realtime_b_boundary_v2.json'
P = json.loads(CONFIG.read_text(encoding='utf-8'))
W = ROOT / P['workspace']
INPUT = W / P['input_directory']
LEDGER = ROOT / '05_タスク管理/jdrt/JDRT-実時間B境界整合_セル検証台帳.jsonl'


def stamp():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def log(action, **fields):
    row = {'at_jst': stamp(), 'action': action, **fields}
    with (OUT / 'operations.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)


def read(name, directory):
    return pd.read_csv(directory / name, keep_default_na=False)


def records(df):
    return json.loads(df.to_json(orient='records', force_ascii=False))


def groups(df):
    yield 'all', 'all', df
    for col in ['person_type', 'mode', 'terminal_kind', 'selected_jdrt']:
        for key, part in df.groupby(col, dropna=False):
            yield col, str(key), part


def people_analysis(directory, manifest):
    people = read('person_results.csv', directory)
    common = read('common_realization.csv', directory)
    requests = read('request_results.csv', directory)
    facilities = read('facility_results.csv', directory)
    terminals = read('terminals.csv', INPUT).set_index('terminal_id')
    assert people.person_id.is_unique and common.person_id.is_unique
    people = people.set_index('person_id', drop=False)
    common = common.set_index('person_id', drop=False).loc[people.index]
    assert (people[common.columns] == common).all().all()
    people['terminal_kind'] = people.terminal_id.map(terminals.kind).fillna('unassigned')
    assert not people.loc[people.terminal_kind == 'unassigned', 'terminal_id'].ne('').any()
    assert dict(Counter(people.status)) == manifest['summary']['states']
    for col in ['ready_sec', 'depart_sec', 'pickup_sec', 'arrival_sec', 'admitted_sec']:
        people[col] = pd.to_numeric(people[col], errors='coerce')
    assert set(requests.person_id) == set(people.loc[people['mode'] == 'drt', 'person_id'])
    assert requests.person_id.is_unique
    for r in requests.to_dict('records'):
        p = people.loc[r['person_id']]
        assert r['status'] == p.status and r['terminal_id'] == p.terminal_id
        assert float(r['request_sec']) == p.ready_sec
        for col in ['pickup_sec', 'arrival_sec']:
            assert (r[col] == '' and pd.isna(p[col])) or float(r[col]) == p[col]
    event_counts = Counter()
    event_reasons = Counter()
    terminal_events = {}
    timing_events = defaultdict(dict)
    closures = []
    examples = {}
    with (directory / 'events.jsonl').open(encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            kind = e['event']
            event_counts[kind] += 1
            if kind == 'closure_applied':
                closures.append(e)
            if kind == 'person_terminal':
                assert e['person_id'] not in terminal_events
                terminal_events[e['person_id']] = e
            if kind in ['drt_assigned', 'boarding_started', 'drt_boarded', 'alighting_started', 'drt_alighted']:
                pid = e['person_id']
                assert kind not in timing_events[pid]
                timing_events[pid][kind] = e['time_sec']
            if kind in ['actor_removed', 'vehicle_closure_control']:
                key = kind + ':' + e.get('reason', e.get('action', ''))
                event_reasons[key] += 1
                examples.setdefault(key, e)
    arrived = people[people.arrival_sec.notna()]
    assert set(terminal_events) == set(arrived.index)
    for pid, e in terminal_events.items():
        p = people.loc[pid]
        assert e['time_sec'] == p.arrival_sec and e['status'] == p.status and e['terminal_id'] == p.terminal_id
    for r in facilities.to_dict('records'):
        p = people[people.terminal_id == r['terminal_id']]
        assert r['admitted'] == sum(p.status == 'admitted') <= r['capacity']
    assert set(people.loc[people.admitted_sec.notna()].index) == set(people.loc[people.status == 'admitted'].index)
    assert people.loc[people.status == 'admitted', 'terminal_kind'].eq('facility').all()
    assert people.loc[people.status == 'boundary_exit', 'terminal_kind'].eq('boundary_exit').all()
    assert people.loc[people.status == 'admitted', 'admitted_sec'].eq(people.loc[people.status == 'admitted', 'arrival_sec']).all()
    outcomes = []
    times = []
    for kind in ['drt_assigned', 'boarding_started', 'drt_boarded', 'alighting_started', 'drt_alighted']:
        people[kind] = people.index.map(lambda pid: timing_events.get(pid, {}).get(kind, np.nan))
    drt = people[people['mode'] == 'drt']
    assert drt.drt_boarded.equals(drt.pickup_sec.rename('drt_boarded'))
    assert drt.drt_alighted.equals(drt.arrival_sec.rename('drt_alighted'))
    timing_definitions = [
        ('ready_to_depart', 'ready_sec', 'depart_sec', 'non_drt'),
        ('request_to_boarding_start', 'ready_sec', 'boarding_started', 'drt'),
        ('request_to_pickup_complete', 'ready_sec', 'pickup_sec', 'drt'),
        ('boarding_processing', 'boarding_started', 'pickup_sec', 'drt'),
        ('pickup_to_alighting_start', 'pickup_sec', 'alighting_started', 'drt'),
        ('alighting_processing', 'alighting_started', 'drt_alighted', 'drt'),
        ('ready_to_terminal', 'ready_sec', 'arrival_sec', 'all'),
        ('depart_to_terminal', 'depart_sec', 'arrival_sec', 'non_drt'),
        ('ready_to_admission', 'ready_sec', 'admitted_sec', 'all'),
    ]
    for dimension, group, part in groups(people):
        states = dict(Counter(part.status))
        assert sum(states.values()) == len(part)
        outcomes.append({'dimension': dimension, 'group': group, 'denominator': len(part), 'states': states,
                         'terminal_arrived': int(part.arrival_sec.notna().sum()),
                         'facility_arrived': int(((part.terminal_kind == 'facility') & part.arrival_sec.notna()).sum()),
                         'admitted': int((part.status == 'admitted').sum()), 'boundary_exit': int((part.status == 'boundary_exit').sum())})
        for name, start, end, scope in timing_definitions:
            eligible = part if scope == 'all' else part[part['mode'] == 'drt'] if scope == 'drt' else part[part['mode'] != 'drt']
            duration = (eligible[end] - eligible[start]).dropna()
            assert duration.ge(0).all(), (name, dimension, group)
            incomplete = eligible[eligible[start].isna() | eligible[end].isna()]
            times.append({'dimension': dimension, 'group': group, 'metric': name, 'scope': scope,
                          'eligible': len(eligible), 'observed': len(duration), 'missing_endpoint': len(incomplete),
                          'incomplete_states': dict(Counter(incomplete.status)),
                          'mean_sec': float(duration.mean()) if len(duration) else None,
                          'median_sec': float(duration.median()) if len(duration) else None,
                          'min_sec': float(duration.min()) if len(duration) else None,
                          'max_sec': float(duration.max()) if len(duration) else None})
    joint = people.groupby(['person_type', 'mode', 'terminal_kind', 'status'], dropna=False).size().rename('people').reset_index()
    assert joint.people.sum() == len(people)
    joint.to_csv(OUT / (directory.name + '_人物区分.csv'), index=False, encoding='utf-8')
    timecols = ['person_id', 'person_type', 'mode', 'terminal_kind', 'status', 'ready_sec', 'depart_sec', 'drt_assigned',
                'boarding_started', 'pickup_sec', 'alighting_started', 'drt_alighted', 'arrival_sec', 'admitted_sec']
    people[timecols].to_csv(OUT / (directory.name + '_時刻対応.csv'), index=False, encoding='utf-8')
    # Direct counts by fixed terminal. These are denominator constraints, not a causal decomposition.
    fixed = people.groupby(['terminal_id', 'terminal_kind', 'person_type'], dropna=False).size().rename('people').reset_index()
    closure_frame = pd.DataFrame(closures)
    hazard = read('hazard.csv', INPUT)
    hazard.closure_sec = pd.to_numeric(hazard.closure_sec, errors='coerce')
    due = hazard[hazard.closure_sec.le(P['simulation']['duration_sec'])]
    assert len(due) == len(closure_frame)
    merged = closure_frame.merge(due[['edge_id', 'mode', 'closure_sec']], on=['edge_id', 'mode'], validate='one_to_one')
    assert len(merged) == len(due)
    expected_call = np.maximum(0, merged.closure_sec - P['simulation']['step_sec'])
    assert merged.scheduled_sec.eq(merged.closure_sec).all()
    assert merged.control_call_sec.eq(expected_call).all() and merged.time_sec.eq(expected_call).all()
    assert merged.observation_upper_sec.eq(merged.closure_sec).all()
    assert merged.control_lead_sec.eq(merged.closure_sec - expected_call).all()
    assert merged.phase.eq(np.where(merged.closure_sec.eq(0), 'initial_before_observation', 'before_step_ending_at_closure')).all()
    clock = records(merged.groupby(['scheduled_sec', 'control_call_sec', 'observation_upper_sec', 'control_lead_sec', 'phase']).size().rename('closures').reset_index())
    warnings = Counter()
    for line in (directory / 'sumo_errors.log').read_text(encoding='utf-8').splitlines():
        if 'Warning:' in line:
            key = 'emergency_braking' if 'emergency braking' in line else 'other'
            warnings[key] += 1
    return {'outcomes': outcomes, 'timing': times, 'fixed_terminal_population': records(fixed),
            'facilities': records(facilities), 'event_counts': dict(event_counts), 'control_reasons': dict(event_reasons),
            'control_examples': examples, 'closure_clock': clock, 'warnings': dict(warnings),
            'checks': {'population_and_common': True, 'request_bijection': True, 'terminal_events_and_times': True,
                       'facility_accounts': True, 'drt_event_endpoints': True, 'duration_nonnegative': True, 'closure_three_clocks': True}}


def candidate_analysis(directory, validation):
    counts = Counter()
    rows = 0
    for df in pd.read_csv(directory / 'candidates.csv.gz', chunksize=200000, keep_default_na=False):
        rows += len(df)
        applicable = df.gate_applicable.eq(True) | df.gate_applicable.eq('True')
        passed = df.gate_pass.eq(True) | df.gate_pass.eq('True')
        required = pd.to_numeric(df.required_sec, errors='coerce')
        remaining = pd.to_numeric(df.forecast_remaining_sec, errors='coerce')
        assert required.notna().all()
        assert (required[applicable].lt(remaining[applicable]) == passed[applicable]).all()
        assert required.ge(0).all()
        terms = pd.to_numeric(df.pickup_sec, errors='coerce') + pd.to_numeric(df.delivery_sec, errors='coerce') + P['operation']['boarding_sec'] + P['operation']['margin_sec']
        assert np.isclose(required, terms, equal_nan=False).all()
        df['gate_class'] = np.where(~applicable, 'not_applicable', np.where(passed, 'pass', 'reject'))
        for key, n in df.groupby(['decision', 'reason', 'gate_class']).size().items():
            counts[tuple(str(x) for x in key)] += int(n)
    assert rows == validation['candidate_rows']
    return {'rows': rows, 'groups': [{'decision': k[0], 'reason': k[1], 'gate_class': k[2], 'rows': n} for k, n in sorted(counts.items())],
            'checks': {'row_count': True, 'strict_gate_recomputed': True, 'required_terms_recomputed': True}}


def road_analysis(directory, validation):
    graphs = json.loads((INPUT / 'graphs.json').read_text(encoding='utf-8'))
    pairs = [(edge, mode) for mode, physical in [('car', 'passenger'), ('drt', 'passenger'), ('walk', 'pedestrian')]
             for edge in sorted(graphs[physical]['nodes'])]
    pair_index = pd.MultiIndex.from_tuples(pairs, names=['edge_id', 'mode'])
    steps = np.arange(0, P['simulation']['duration_sec'] + 1, P['simulation']['snapshot_sec'])
    seen = np.zeros((len(steps), len(pairs)), dtype=np.uint8)
    per_edge = np.zeros((len(pairs), 7), dtype=float)
    time_rows = []
    rows = 0
    for df in pd.read_csv(directory / 'edge_observations.csv.gz', chunksize=500000, dtype={'edge_id': str, 'mode': str}):
        rows += len(df)
        ix = pair_index.get_indexer(pd.MultiIndex.from_frame(df[['edge_id', 'mode']]))
        tx = df.time_sec.to_numpy() / P['simulation']['snapshot_sec']
        assert (ix >= 0).all() and np.equal(tx, np.floor(tx)).all()
        tx = tx.astype(int)
        assert ((tx >= 0) & (tx < len(steps))).all()
        flat = tx * len(pairs) + ix
        # This independently verifies each snapshot/edge/mode key, including zero rows.
        assert len(np.unique(flat)) == len(flat) and not seen.ravel()[flat].any()
        seen.ravel()[flat] = 1
        assert df.observation_status.eq('observed').all()
        n = df['count'].to_numpy()
        speed = df.mean_speed_mps.to_numpy()
        halt = df.halting_count.to_numpy()
        assert ((n >= 0) & (halt >= 0) & (halt <= n)).all()
        assert np.array_equal(np.isnan(speed), n == 0)
        assert np.isfinite(speed[n > 0]).all() and (speed[n > 0] >= 0).all()
        weighted = np.nan_to_num(speed) * n
        df['zero_rows'] = n == 0
        df['occupied_rows'] = n > 0
        df['weighted_speed'] = weighted
        df['rows'] = 1
        cols = ['rows', 'zero_rows', 'occupied_rows', 'count', 'halting_count', 'weighted_speed', 'closed']
        for j, col in enumerate(cols):
            per_edge[:, j] += np.bincount(ix, weights=df[col].to_numpy(dtype=float), minlength=len(pairs))
        time_rows.append(df.groupby(['time_sec', 'mode'])[cols].sum())
        if rows % 5000000 == 0:
            log('road_checkpoint', run_id=directory.name, rows=rows)
    assert rows == validation['road_rows'] and seen.all()
    edge = pair_index.to_frame(index=False)
    columns = ['snapshot_rows', 'zero_rows', 'occupied_rows', 'actor_snapshot_count', 'halting_actor_snapshots', 'speed_actor_sum', 'closed_snapshots']
    edge[columns] = per_edge
    edge['observed_actor_weighted_speed_mps'] = np.divide(per_edge[:, 5], per_edge[:, 3], out=np.full(len(pairs), np.nan), where=per_edge[:, 3] > 0)
    edge.to_csv(OUT / (directory.name + '_道路別snapshot集約.csv.gz'), index=False, encoding='utf-8', compression={'method': 'gzip', 'mtime': 0})
    times = pd.concat(time_rows).groupby(level=[0, 1]).sum().reset_index()
    times['observed_actor_weighted_speed_mps'] = times.weighted_speed / times['count'].replace(0, np.nan)
    times.to_csv(OUT / (directory.name + '_60秒道路集約.csv'), index=False, encoding='utf-8')
    summary = times.groupby('mode').sum(numeric_only=True).drop(columns=['time_sec', 'observed_actor_weighted_speed_mps']).reset_index()
    return {'rows': rows, 'snapshots': len(steps), 'edge_mode_pairs': len(pairs), 'by_mode': records(summary),
            'checks': {'all_keys_once': True, 'observed_status': True, 'zero_speed_null_semantics': True, 'count_and_halting_bounds': True}}


def transitions_analysis(directory, validation):
    hazard = read('hazard.csv', INPUT)
    h = {(r.edge_id, r.mode): float(r.closure_sec) for r in hazard.itertuples() if r.closure_sec != ''}
    count = 0
    kinds = Counter()
    closed = ambiguous = 0
    with gzip.open(directory / 'transitions.csv.gz', 'rt', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            count += 1
            kinds[(r['mode'], r['kind'])] += 1
            t = h.get((r['to_edge'], r['mode']), float('inf'))
            is_closed = float(r['time_upper_sec']) >= t
            closed += is_closed
            ambiguous += r['ambiguous'] == 'True'
            assert (r['kind'] == 'closed_entry') == is_closed
    assert count == validation['transitions'] and closed == validation['closed_entries'] and ambiguous == validation['ambiguous_transitions']
    return {'rows': count, 'closed_entries': closed, 'ambiguous': ambiguous,
            'groups': [{'mode': k[0], 'kind': k[1], 'rows': n} for k, n in kinds.items()], 'checks': {'hazard_time_recomputed': True}}


def main():
    OUT.mkdir(exist_ok=True)
    log('preflight_start', python=sys.version, pandas=pd.__version__, command='project venv Python -X utf8 scripts/jdrt_realtime_b_boundary_postanalysis.py')
    previous = json.loads((OUT.parent / '生成根拠.json').read_text(encoding='utf-8'))
    for path, digest in previous['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    ledger = [json.loads(x) for x in LEDGER.read_text(encoding='utf-8').splitlines() if x.strip()]
    expected = {(seed, scenario) for seed in P['seeds'] for scenario in P['scenarios']}
    assert {(r['seed'], r['scenario']) for r in ledger} == expected
    assert len(ledger) == len(expected) == len({r['run_id'] for r in ledger})
    for path, digest in previous['implementation_sha256'].items():
        assert sha(ROOT / path) == digest
    log('preflight_pass', sources=len(previous['source_sha256']), cells=len(ledger), simulation_started=False)
    result = []
    for seed in P['seeds']:
        for scenario in P['scenarios']:
            r = next(r for r in ledger if r['seed'] == seed and r['scenario'] == scenario)
            directory = W / 'runs' / r['run_id']
            checkpoint = OUT / (directory.name + '_集計.json')
            if checkpoint.exists():
                cell = json.loads(checkpoint.read_text(encoding='utf-8'))
                assert cell['analysis_script_sha256'] == sha(Path(__file__)), 'Changed analysis script: preserve checkpoints and choose a new output directory'
                result.append(cell)
                log('checkpoint_reused', run_id=directory.name)
                continue
            log('cell_start', run_id=directory.name, seed=seed, scenario=scenario)
            manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
            validation = json.loads((directory / 'validation.json').read_text(encoding='utf-8'))
            assert manifest['status'] == 'COMPLETED' and validation['status'] == 'PASS'
            cell = {'run_id': directory.name, 'seed': seed, 'scenario': scenario, 'analysis_script_sha256': sha(Path(__file__))}
            cell.update(people_analysis(directory, manifest))
            log('people_and_time_pass', run_id=directory.name)
            cell['candidates'] = candidate_analysis(directory, validation)
            log('candidate_pass', run_id=directory.name, rows=cell['candidates']['rows'])
            cell['roads'] = road_analysis(directory, validation)
            cell['transitions'] = transitions_analysis(directory, validation)
            save(checkpoint, cell)
            result.append(cell)
            log('cell_complete', run_id=directory.name, roads=cell['roads']['rows'], transitions=cell['transitions']['rows'])
    # Check source immutability again after the complete read, without re-running SUMO.
    for path, digest in previous['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    save(OUT / '副指標・観測監査集計.json', {'protocol': P['protocol'], 'created_at_jst': stamp(), 'cells': result,
         'definitions': {'duration':'observed endpoint differences only; incomplete and competing outcomes retained; no survival estimator',
                         'request_sec':'exogenous ready_sec for each DRT-mode person, not confirmed acceptance timestamp',
                         'arrival_sec':'terminal allocation time; DRT after alighting completion, not vehicle physical arrival',
                         'road':'instantaneous snapshots; actor_snapshot_count is a repeated count, not unique actors or time integral',
                         'gate':'only gate_applicable True rows counted as pass/reject; all others not_applicable'},
         'checks': {'registered_cell_set': True, 'source_sha_before_after': True, 'all_cells_complete': len(result) == len(expected)}})
    artifacts = {p.name: sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['operations.jsonl', '分析生成根拠.json']}
    save(OUT / '分析生成根拠.json', {'at_jst': stamp(), 'script_sha256': sha(Path(__file__)), 'source_sha256': previous['source_sha256'],
                                'implementation_sha256': previous['implementation_sha256'], 'artifact_sha256': artifacts})
    log('analysis_complete', cells=len(result), source_files=len(previous['source_sha256']), output_artifacts=len(artifacts))


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        detail = traceback.format_exc()
        log('analysis_failure', traceback=detail)
        raise
