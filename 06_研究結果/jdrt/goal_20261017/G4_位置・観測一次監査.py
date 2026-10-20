"""Independent alignment smoke audit. No producer imports or core acceptance."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import argparse
import csv
import gzip
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else Path.open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def audit(run_id):
    cfg_path = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    folder = ROOT / cfg['workspace'] / 'smoke' / run_id
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    inputs = ROOT / m['input_directory']
    people = {p['person_id']: p for p in rows(folder / 'person_results.csv')}
    vehicles = {v['vehicle_id']: v for v in rows(folder / 'vehicle_results.csv')}
    raw_graph = json.loads((inputs / 'graphs.json').read_text(encoding='utf-8'))['passenger']
    nodes = raw_graph['nodes']
    arcs = {(a, b) for a, b, attrs in raw_graph['edges']}
    sources = {str(folder / name): h for name, h in m['output_sha256'].items()}
    sources[str(folder / 'manifest.json')] = sha(folder / 'manifest.json')
    checks = {'completed_smoke': m['status'] == 'COMPLETED' and m['purpose'] == 'smoke',
              'all_outputs_sha': all(sha(Path(p)) == h for p, h in sources.items()),
              'input_manifest_sha': sha(inputs / 'manifest.json') == m['input_manifest_sha256']}
    errors = defaultdict(list)
    walk_integral, distance, empty = defaultdict(float), defaultdict(float), defaultdict(float)
    kinds, active, frames, actor_rows = Counter(), set(), None, 0
    for row in rows(folder / 'actor_observations.csv.gz'):
        actor_rows += 1
        time = float(row['time_sec'])
        if frames != time:
            active, frames = set(), time
        kind = row['observation_kind']
        kinds[kind] += 1
        members = json.loads(row['members'])
        duplicate = active.intersection(members)
        if duplicate:
            errors['duplicate_active_person'].append((time, sorted(duplicate)))
        active.update(members)
        if row['kind'] == 'walk':
            speed = float(row['speed_mps'])
            maximum = cfg['population']['walk_mps'][people[row['actor_id']]['person_type']]
            if kind != 'onroad' or not 0 <= speed <= maximum + 1e-6:
                errors['walk_observation'].append((time, row['actor_id']))
            walk_integral[row['actor_id']] += speed * m['step_sec']
        elif kind in ('onroad', 'parked', 'reentry_pending'):
            value = float(row['distance_m'])
            if value >= 0:
                increment = value - distance[row['actor_id']]
                if increment < -1e-8:
                    errors['odometer_decrease'].append((time, row['actor_id']))
                distance[row['actor_id']] = max(value, distance[row['actor_id']])
                if not members:
                    empty[row['actor_id']] += max(0, increment)
            if kind == 'parked' and not int(row['stop_state']) & 2:
                errors['parking_bit'].append((time, row['actor_id']))
        elif kind != 'departure_pending':
            errors['unexplained_missing'].append((time, row['actor_id']))
    checks['no_duplicate_active_people_per_step'] = not errors['duplicate_active_person']
    checks['walking_speed_integral_independent'] = all(
        math.isclose(float(p['walk_speed_integral_m']), walk_integral[pid], abs_tol=1e-7)
        and float(p['walk_speed_integral_m']) <= cfg['population']['walk_limit_m'] + 1e-7
        for pid, p in people.items()) and not errors['walk_observation']
    checks['observed_vehicle_and_empty_distance_independent'] = all(
        math.isclose(float(v['observed_distance_m']), distance[vid], abs_tol=1e-7)
        and math.isclose(float(v['observed_empty_distance_m']), empty[vid], abs_tol=1e-7)
        for vid, v in vehicles.items()) and not errors['odometer_decrease']
    checks['raw_observations_explained'] = not errors['unexplained_missing'] and not errors['parking_bit']
    snapshot_speeds = defaultdict(lambda: defaultdict(lambda: [0., 0]))
    road_rows, park_rows = 0, 0
    for row in rows(folder / 'edge_observations.csv.gz'):
        road_rows += 1
        snapshot_speeds[float(row['time_sec'])]
        count, traffic, parked, pending = (int(row[k]) for k in
            ('count', 'traffic_count', 'parked_count', 'reentry_pending_count'))
        if count != traffic + parked + pending or min(count, traffic, parked, pending) < 0:
            errors['road_count_partition'].append((row['time_sec'], row['edge_id'], row['mode']))
        if (traffic == 0) != (row['traffic_mean_speed_mps'] == ''):
            errors['traffic_missingness'].append((row['time_sec'], row['edge_id']))
        if traffic and row['mode'] != 'walk':
            total, n = snapshot_speeds[float(row['time_sec'])][row['edge_id']]
            snapshot_speeds[float(row['time_sec'])][row['edge_id']] = [
                total + traffic * float(row['traffic_mean_speed_mps']), n + traffic]
        park_rows += int(parked > 0)
    checks['all_road_raw_traffic_partitions'] = not errors['road_count_partition'] and not errors['traffic_missingness']
    candidate_rows = 0
    for row in rows(folder / 'candidates.csv.gz'):
        candidate_rows += 1
        now = float(row['time_sec'])
        previous = [time for time in snapshot_speeds if time < now]
        speed_map = snapshot_speeds[max(previous)] if previous else {}
        for prefix, source_pos, target_pos in [('pickup', float(row['source_pos_m']), float(row['pickup_pos_m'])),
                                               ('delivery', float(row['pickup_pos_m']), float(row['terminal_pos_m']))]:
            path = json.loads(row[prefix + '_path'])
            if not path:
                if row[prefix + '_kind'] != 'infinite':
                    errors['candidate_position_time'].append((candidate_rows, prefix, 'empty_finite'))
                continue
            if not all((a, b) in arcs for a, b in zip(path, path[1:])):
                errors['candidate_path'].append((candidate_rows, prefix))
            times = []
            for edge in path:
                total, n = speed_map.get(edge, [0, 0]) if prefix == 'pickup' else [0, 0]
                times.append(nodes[edge]['length'] / max(total / n, .1) if n else nodes[edge]['free_sec'])
            expected = (times[0] * (target_pos - source_pos) / nodes[path[0]]['length'] if len(path) == 1
                        else times[0] * (1 - source_pos / nodes[path[0]]['length'])
                        + sum(times[1:-1]) + times[-1] * target_pos / nodes[path[-1]]['length'])
            if row[prefix + '_kind'] != 'finite' or not math.isclose(float(row[prefix + '_sec']), expected, abs_tol=1e-7):
                errors['candidate_position_time'].append((candidate_rows, prefix, expected, row[prefix + '_sec']))
    checks['candidate_position_time_from_prior_traffic_snapshot'] = not errors['candidate_position_time']
    checks['candidate_vehicle_arc_paths'] = not errors['candidate_path']
    checks['source_unchanged_after_read'] = all(sha(Path(p)) == h for p, h in sources.items())
    return {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(), 'run_id': run_id,
            'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'scope': 'partial_alignment_smoke_audit_not_formal_core_acceptance', 'core_adoption_permitted': False,
            'actor_rows_read': actor_rows, 'actor_observation_kinds': dict(kinds),
            'road_rows_read': road_rows, 'parked_road_rows': park_rows, 'candidate_rows_read': candidate_rows,
            'errors': {k: v[:20] for k, v in errors.items() if v},
            'pending': ['shortest_path_optimality', 'candidate_gate_and_score', 'per_step_closure_routes',
                        'stage_reroute_distance_countercases', 'backend_tripinfo_vkt_tail', 'tamper_rejection',
                        'full_core_common_realization', 'combined_runtime_fixtures', 'all14_smokes', 'record_preflight'],
            'current_implementation_match': all(sha(ROOT / p) == h for p, h in m['implementation_sha256'].items()),
            'auditor_sha256': sha(Path(__file__)), 'source_sha256': sources}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    report = audit(args.run_id)
    target = Path(__file__).parent / (args.run_id + '_位置観測一次監査.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'source_sha256'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
