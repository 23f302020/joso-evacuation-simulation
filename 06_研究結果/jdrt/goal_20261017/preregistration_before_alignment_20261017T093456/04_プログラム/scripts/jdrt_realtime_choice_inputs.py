"""Exclusive input preparation for the preregistered choice series; never starts SUMO."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import json
import shutil

import networkx as nx

from scripts.jdrt_choice_policy import facility_first_destinations, hash_number, select_intents

ROOT = Path(__file__).resolve().parents[2]
PARAM = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare():
    params = json.loads(PARAM.read_text(encoding='utf-8'))
    parent = ROOT / params['parent_input_manifest']
    prior = json.loads(parent.read_text(encoding='utf-8'))
    for name, expected in prior['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Parent source SHA mismatch: ' + name)
    for name, expected in prior['artifacts'].items():
        if sha(parent.parent / name) != expected:
            raise ValueError('Parent artifact SHA mismatch: ' + name)
    directory = ROOT / params['workspace'] / params['input_directory']
    directory.mkdir(parents=True, exist_ok=False)
    for name in prior['artifacts']:
        shutil.copy2(parent.parent / name, directory / name)
    raw_graphs = json.loads((directory / 'graphs.json').read_text(encoding='utf-8'))
    graphs = {}
    for mode, data in raw_graphs.items():
        g = nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from(data['nodes'].items())
        g.add_edges_from(data['edges'])
        g.remove_nodes_from(row['edge_id'] for row in read_csv(directory / 'hazard.csv')
                            if row['mode'] == mode and row['closure_sec'] == '0')
        graphs[mode] = g
    origins = read_csv(directory / 'origins.csv')
    terminals = read_csv(directory / 'terminals.csv')
    # D0 is copied exactly, not regenerated with changed tie semantics.
    shutil.copy2(directory / 'origins.csv', directory / 'destinations_fixed_reference.csv')
    improved = facility_first_destinations(origins, graphs, terminals)
    for row in improved:
        row['car_route'] = json.dumps(row['car_route'])
        row['walk_route'] = json.dumps(row['walk_route'])
    write_csv(directory / 'destinations_facility_first.csv', improved)
    people = read_csv(directory / 'people.csv')
    for seed in params['seeds']:
        masks = {key: select_intents(people, seed, value['fraction'])
                 for key, value in params['demand_levels'].items()}
        low, high = params['population']['ready_interval_sec']
        rows = []
        for person in sorted(people, key=lambda row: row['person_id']):
            pid = person['person_id']
            key = person['vehicle_id'] or pid
            rows.append({**person, 'ready_sec': low + hash_number(seed, key, 'ready') % (high - low + 1),
                         **{'intent_' + level: pid in mask for level, mask in masks.items()}})
        write_csv(directory / f'common_realization_seed{seed}.csv', rows)
    (directory / 'cells.json').write_text(json.dumps(params['cells'], ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8')
    sources = dict(prior['source_sha256'])
    for path in (PARAM, parent, Path(__file__), ROOT / params['pap'],
                 ROOT / params['registry_document'], ROOT / params['state_contract'],
                 ROOT / '04_プログラム/scripts/jdrt_choice_policy.py'):
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
    artifacts = {path.name: sha(path) for path in directory.iterdir() if path.is_file()}
    if any(artifacts[name] != expected for name, expected in prior['artifacts'].items()):
        raise ValueError('Physical copy differs from parent')
    manifest = {
        'protocol': params['protocol'], 'created_at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'status': 'PREPARED_PENDING_INDEPENDENT_VALIDATION',
        'source_sha256': sources, 'artifacts': artifacts,
        'physical_artifacts_sha256': prior['artifacts'],
        'lineage': {'parent_manifest': params['parent_input_manifest'], 'parent_manifest_sha256': sha(parent)},
        'execution_contract': params['execution'],
        'people': len(people), 'population_counts': dict(Counter(row['person_type'] for row in people)),
        'origins': len(origins), 'depot_edge': prior['depot_edge'],
        'facilities': prior['facilities'], 'boundary_exits': prior['boundary_exits'],
        'registered_cells': len(params['cells']), 'technical_ready': False,
    }
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8')
    return manifest


if __name__ == '__main__':
    report = prepare()
    print(json.dumps({key: report[key] for key in ('protocol', 'status', 'people', 'registered_cells',
                                                  'technical_ready')}, ensure_ascii=False, indent=2))
