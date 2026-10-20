"""Independent input checks. Core validation/preflight are not implemented yet."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
import csv
import hashlib
import json
import math

import h5py
import networkx as nx
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
PARAM = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def validate_choice_tables():
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    parent = ROOT / params['parent_input_manifest']
    prior = json.loads(parent.read_text(encoding='utf-8'))
    checks = {}
    checks['all_sources_current'] = all(file_sha(ROOT / path) == expected
                                       for path, expected in manifest['source_sha256'].items())
    checks['all_artifacts_current'] = all(file_sha(directory / path) == expected
                                         for path, expected in manifest['artifacts'].items())
    checks['physical_copy_exact'] = all(file_sha(directory / path) == expected
                                       for path, expected in prior['artifacts'].items())
    checks['lineage'] = (manifest['lineage']['parent_manifest_sha256'] == file_sha(parent)
                         and manifest['protocol'] == params['protocol'])
    checks['d0_byte_identical'] = file_sha(directory / 'destinations_fixed_reference.csv') == prior['artifacts']['origins.csv']
    raw = json.loads((directory / 'graphs.json').read_text(encoding='utf-8'))
    hazards = rows(directory / 'hazard.csv')
    graphs = {}
    for mode, data in raw.items():
        g = nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from(data['nodes'].items())
        g.add_edges_from(data['edges'])
        g.remove_nodes_from(row['edge_id'] for row in hazards
                            if row['mode'] == mode and row['closure_sec'] == '0')
        graphs[mode] = g
    origins = rows(directory / 'origins.csv')
    terms = {row['terminal_id']: row for row in rows(directory / 'terminals.csv')}
    derived = rows(directory / 'destinations_facility_first.csv')
    checks['d1_origins_exact'] = (len(derived) == len(origins)
                                 and {r['origin_id'] for r in derived} == {r['origin_id'] for r in origins})
    by_origin = {r['origin_id']: r for r in origins}
    mismatches = []
    for row in derived:
        start = by_origin[row['origin_id']]['edge_id']
        # Generator uses reverse Decimal distances. Audit uses forward rational distances.
        distance = {mode: nx.single_source_dijkstra_path_length(
                        graph, start, weight=lambda u, v, data: Fraction(str(data['length'])))
                    if start in graph else {} for mode, graph in graphs.items()}
        expected = None
        for stage, (kind, mode) in enumerate((('facility', 'passenger'), ('facility', 'pedestrian'),
                                              ('boundary_exit', 'passenger'), ('boundary_exit', 'pedestrian')), 1):
            choices = [(distance[mode][t['edge_id']], key)
                       for key, t in terms.items() if t['kind'] == kind and t['edge_id'] in distance[mode]]
            if choices:
                cost, key = min(choices)
                expected = (stage, cost, key)
                break
        if expected is None:
            valid = row['terminal_id'] == '' and row['selection_stage'] == ''
        else:
            stage, cost, key = expected
            valid = (row['terminal_id'] == key and int(row['selection_stage']) == stage
                     and Fraction(row['selection_distance_exact_m']) == cost)
        for mode, field in [('passenger', 'car_route'), ('pedestrian', 'walk_route')]:
            path = json.loads(row[field])
            target = terms[row['terminal_id']]['edge_id'] if row['terminal_id'] else None
            possible = target in distance[mode]
            valid &= bool(path) == possible
            if path and possible:
                valid &= path[0] == start and path[-1] == target and len(path) == len(set(path))
                valid &= all(graphs[mode].has_edge(a, b) for a, b in zip(path, path[1:]))
                if valid:
                    total = sum((Fraction(str(graphs[mode][a][b]['length']))
                                 for a, b in zip(path, path[1:])), Fraction(0))
                    valid &= total == distance[mode][target]
            if mode == 'pedestrian' and path:
                valid &= math.isclose(float(row['walk_length_m']),
                                      sum(graphs[mode].nodes[n]['length'] for n in path), abs_tol=1e-8)
        if not valid:
            mismatches.append(row['origin_id'])
    checks['d1_priority_distance_and_paths'] = not mismatches
    people = rows(directory / 'people.csv')
    base = {p['person_id']: p for p in people}
    checks['population_unique'] = len(base) == len(people) == manifest['people']
    realization_counts = {}
    realization_valid = True
    for seed in params['seeds']:
        common = rows(directory / f'common_realization_seed{seed}.csv')
        valid = len(common) == len(people) and {p['person_id'] for p in common} == set(base)
        expected_masks = {}
        for level, value in params['demand_levels'].items():
            mask = set()
            for typ in ('type3', 'type4'):
                candidates = [p['person_id'] for p in people if p['person_type'] == typ]
                candidates.sort(key=lambda pid: (hashlib.sha256(f'{seed}|uptake|{pid}'.encode()).digest(), pid))
                count = math.floor(len(candidates) * value['fraction'] + .5)
                mask.update(candidates[:count])
            expected_masks[level] = mask
        valid &= expected_masks['u05'] <= expected_masks['u50']
        low, high = params['population']['ready_interval_sec']
        for p in common:
            source = base[p['person_id']]
            valid &= all(p[k] == v for k, v in source.items())
            key = source['vehicle_id'] or p['person_id']
            ready = low + int.from_bytes(hashlib.sha256(f'{seed}|ready|{key}'.encode()).digest(), 'big') % (high - low + 1)
            valid &= int(p['ready_sec']) == ready
            for level, mask in expected_masks.items():
                valid &= p['intent_' + level] == str(p['person_id'] in mask)
        realization_counts[str(seed)] = {key: len(value) for key, value in expected_masks.items()}
        realization_valid &= valid
    checks['common_realization_independent'] = bool(realization_valid)
    cells = json.loads((directory / 'cells.json').read_text(encoding='utf-8'))
    expected_keys = set()
    for seed in params['seeds']:
        for policy in params['destination_policies']:
            expected_keys.add((policy, None, 'R0', seed))
            expected_keys.update((policy, level, scenario, seed)
                                 for level in params['demand_levels'] for scenario in ('R1', 'R2P900', 'R2P0'))
    keys = [(r['destination_policy'], r['demand_level'], r['scenario'], r['seed']) for r in cells]
    checks['cell_set_unique_and_exact'] = (cells == params['cells'] and len(keys) == len(set(keys))
                                          and set(keys) == expected_keys
                                          and len({r['cell_id'] for r in cells}) == len(cells))
    report = {
        'status': 'PASS' if all(checks.values()) else 'FAIL',
        'scope': 'derived_choice_tables_and_physical_byte_lineage_only',
        'technical_ready': False,
        'pending': ['raw_hdf_terrain_physical_recomputation', 'core_executor_and_validator',
                    'actual_sumo_cancellation_timing', 'all_14_setting_smoke', 'skill_cli_and_record'],
        'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'checks': checks, 'd1_mismatched_origins': mismatches,
        'realization_counts': realization_counts, 'registered_cells': len(cells),
        'd1_terminal_counts_origins': dict(Counter(row['terminal_id'] for row in derived)),
        'input_manifest_sha256': file_sha(directory / 'manifest.json'),
        'validator_sha256': file_sha(Path(__file__)),
    }
    target = ROOT / params['workspace'] / 'choice_table_validation.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def validate_physical_inputs():
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    checks = {'current_sources': all(file_sha(ROOT / p) == value
                                    for p, value in manifest['source_sha256'].items())}

    def source(suffix):
        matches = [ROOT / path for path in manifest['source_sha256'] if path.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError('Ambiguous primary source: ' + suffix)
        return matches[0]

    domain_data = json.loads(source('cells_utm54n.geojson').read_text(encoding='utf-8'))
    domain = unary_union([shape(feature['geometry']) for feature in domain_data['features']])
    transform = Transformer.from_crs(4326, 32654, always_xy=True)
    reference_origins = rows(source('scenario_c_agent_types.csv'))
    inside = {row['origin_id'] for row in reference_origins
              if domain.covers(Point(*transform.transform(float(row['lon']), float(row['lat']))))}
    reference_people = rows(source('scenario_c_mode_ledger.csv'))
    expected = {row['person_id']: row for row in reference_people if row['origin_id'] in inside}
    people, excluded = rows(directory / 'people.csv'), rows(directory / 'excluded_people.csv')
    checks['population_from_primary_domain'] = (len(people) == len(expected)
                                               and {p['source_person_id'] for p in people} == set(expected))
    checks['attributes_from_primary'] = all(p['person_type'] == expected[p['source_person_id']]['person_type']
                                            and p['base_mode'] == expected[p['source_person_id']]['assigned_mode']
                                            for p in people)
    checks['source_population_partition'] = (len(people) + len(excluded) == len(reference_people)
                                             and not {p['source_person_id'] for p in people}
                                             & {p['source_person_id'] for p in excluded})
    checks['origins_from_primary_domain'] = {o['origin_id'] for o in rows(directory / 'origins.csv')} == inside
    with np.load(directory / 'road_samples.npz') as archive:
        samples = {key: archive[key] for key in archive.files}
    with h5py.File(source('Calibrated/Calibrated.hdf'), 'r') as hydraulic:
        prefix = 'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
        dates = [datetime.strptime(value.decode(), '%d%b%Y %H:%M:%S')
                 for value in hydraulic[prefix + 'Time Date Stamp'][:]]
        start = datetime.fromisoformat(params['simulation']['start_jst']).replace(tzinfo=None)
        end = start + timedelta(seconds=params['simulation']['duration_sec'])
        indices = [i for i, value in enumerate(dates) if start <= value <= end]
        seconds = np.array([(dates[i] - start).total_seconds() for i in indices], dtype=int)
        surface = hydraulic[prefix + '2D Flow Areas/Joso Area/Water Surface'][indices, :]
    checks['native_times_from_hdf'] = (np.array_equal(seconds, samples['native_sec'])
                                      and seconds[0] == 0 and seconds[-1] == params['simulation']['duration_sec'])
    with rasterio.open(source('Terrain.kinugawa.tif')) as terrain:
        inverse = ~terrain.transform
        x, y = samples['xy'][:, 0], samples['xy'][:, 1]
        cols = np.floor(inverse.a * x + inverse.b * y + inverse.c).astype(int)
        rids = np.floor(inverse.d * x + inverse.e * y + inverse.f).astype(int)
        valid = (rids >= 0) & (rids < terrain.height) & (cols >= 0) & (cols < terrain.width)
        elevations = np.full(len(rids), terrain.nodata, dtype=float)
        grid = terrain.read(1)
        elevations[valid] = grid[rids[valid], cols[valid]]
    checks['elevation_from_primary_tif'] = np.array_equal(elevations, samples['elevation_m'])
    groups = defaultdict(list)
    for index, (edge, mode) in enumerate(zip(samples['edge_id'], samples['mode'])):
        groups[str(edge), str(mode)].append(index)
    hazard = rows(directory / 'hazard.csv')
    bad = []
    for row in hazard:
        indices = np.array(groups[row['edge_id'], row['mode']])
        if not np.all(samples['valid'][indices]):
            bad.append((row['edge_id'], row['mode']))
            continue
        cell_ids = samples['cell_id'][indices]
        depths = (surface[:, cell_ids] - elevations[indices]).clip(min=0).max(axis=1)
        threshold = params['hazard']['vehicle_depth_m' if row['mode'] == 'passenger' else 'pedestrian_depth_m']
        hits = np.nonzero(depths >= threshold)[0]
        hit = int(hits[0]) if len(hits) else None
        closure = str(int(seconds[hit])) if hit is not None else ''
        lower = str(int(seconds[max(0, hit - 1)])) if hit is not None else ''
        correct = (closure == row['closure_sec'] and closure == row['upper_sec']
                   and lower == row['lower_sec'] and float(row['threshold_m']) == threshold
                   and math.isclose(float(max(depths)), float(row['max_depth_m']), abs_tol=1e-6)
                   and math.isclose(float(depths[0]), float(row['initial_depth_m']), abs_tol=1e-6))
        if not correct:
            bad.append((row['edge_id'], row['mode']))
    checks['all_road_depths_threshold_intervals_from_hdf_tif'] = not bad
    tags = {row['edge_id']: row for row in rows(source('structure_tags_audit.csv'))}
    eligible = {row['edge_id'] for row in hazard}
    checks['unverified_structures_excluded'] = all(not tags[key]['bridge_tag'] and not tags[key]['tunnel_tag']
                                                  and tags[key]['way_match'] == 'True' for key in eligible)
    terms = rows(directory / 'terminals.csv')
    capacity = {r['shelter_id']: int(r['published_capacity_people'])
                for r in rows(source('既存9施設_公表容量照合_20261015.csv'))}
    checks['facility_capacity_primary'] = all(int(t['capacity']) == capacity[t['terminal_id']]
                                             for t in terms if t['kind'] == 'facility')
    by_hazard = {(r['edge_id'], r['mode']): r for r in hazard}
    checks['terminal_access_model_dry_window'] = all(by_hazard[t['edge_id'], mode]['closure_sec'] == ''
                                                    for t in terms for mode in ('passenger', 'pedestrian'))
    checks['exit_separate_from_facilities'] = all(t['terminal_id'].startswith('exit_') and t['capacity'] == ''
                                                 for t in terms if t['kind'] == 'boundary_exit')
    report = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'technical_ready': False,
              'scope': 'physical_primary_hdf_terrain_population_capacity_recomputation',
              'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'checks': {k: bool(value) for k, value in checks.items()},
              'hazard_rows_recomputed': len(hazard), 'mismatched_edge_modes': bad,
              'input_manifest_sha256': file_sha(directory / 'manifest.json'),
              'validator_sha256': file_sha(Path(__file__))}
    target = ROOT / params['workspace'] / 'physical_input_validation.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def validate_inputs():
    choice = validate_choice_tables()
    physical = validate_physical_inputs()
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    directory = ROOT / params['workspace'] / params['input_directory']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    still_current = (choice['input_manifest_sha256'] == physical['input_manifest_sha256']
                     == file_sha(directory / 'manifest.json')
                     and all(file_sha(ROOT / path) == expected
                             for path, expected in manifest['source_sha256'].items()))
    report = {
        'status': 'PASS' if choice['status'] == physical['status'] == 'PASS' and still_current else 'FAIL',
        'scope': 'registered_physical_and_choice_inputs', 'technical_ready': False,
        'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'checks': {**{'choice_' + k: v for k, v in choice['checks'].items()},
                   **{'physical_' + k: v for k, v in physical['checks'].items()},
                   'sources_current_after_recomputation': still_current},
        'input_manifest_sha256': file_sha(directory / 'manifest.json'),
        'validator_sha256': file_sha(Path(__file__)),
        'component_reports_sha256': {name: file_sha(ROOT / params['workspace'] / name)
                                     for name in ('choice_table_validation.json', 'physical_input_validation.json')},
        'pending': ['core_executor_and_run_validator', 'actual_sumo_cancellation_timing',
                    'all_14_setting_smoke', 'skill_cli_and_record'],
    }
    (ROOT / params['workspace'] / 'input_validation.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--physical', action='store_true')
    group.add_argument('--all', action='store_true')
    arguments = parser.parse_args()
    result = (validate_inputs() if arguments.all else validate_physical_inputs()
              if arguments.physical else validate_choice_tables())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
