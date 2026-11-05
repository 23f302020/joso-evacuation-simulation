"""Read-only expansion of a native-warning window; never validates/adopts a run."""
import argparse
import csv
import gzip
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from extract_window import digest


def main(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    run = root / '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1/runs/ch261021_002'
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    inputs = root / manifest['input_directory']
    warning = re.findall(r"Warning: Vehicle '([^']+)' performs emergency braking on lane '([^']+)'.*time=([\d.]+)\.",
                         (run / 'sumo_errors.log').read_text(encoding='utf-8'))
    if len(warning) != 1:
        raise ValueError('This preserved diagnosis requires exactly one warning')
    actor, lane, at = warning[0]
    at = float(at)
    tree = ET.parse(inputs / 'bounded.net.xml').getroot()
    edges = {e.get('id'): e for e in tree.findall('edge')}
    edge_id = lane.rsplit('_', 1)[0]
    first = edges[edge_id].get('to')
    # Topology, not an assumed route field, selects the second junction.
    outgoing = [c.get('to') for c in tree.findall('connection')
                if c.get('from') == edge_id and c.get('fromLane') == lane.rsplit('_', 1)[1]]
    if len(set(outgoing)) != 1:
        raise ValueError('Ambiguous downstream edge: inspect the original route before expansion')
    second = edges[outgoing[0]].get('to')
    junction_ids = {first, second}
    junctions = [j for j in tree.findall('junction') if j.get('id') in junction_ids]
    if len(junctions) != 2:
        raise ValueError('Missing two-junction topology')
    local_edges = {eid for eid, e in edges.items()
                   if e.get('from') in junction_ids or e.get('to') in junction_ids
                   or any(eid.startswith(':' + jid + '_') for jid in junction_ids)}
    centers = [(float(j.get('x')), float(j.get('y'))) for j in junctions]
    paths = [run / 'actor_observations.csv.gz', run / 'events.jsonl', run / 'types.rou.xml',
             inputs / 'bounded.net.xml', inputs / 'hazard.csv', run / 'manifest.json', run / 'sumo_errors.log']
    before = {str(p.relative_to(root)): digest(p) for p in paths}
    rows, previous = [], -1
    with gzip.open(run / 'actor_observations.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            time = float(row['time_sec'])
            if time < previous:
                raise ValueError('Non-monotonic actor stream')
            previous = time
            if time > at + 8:
                break
            if time < at - 8:
                continue
            spatial = False
            if row['x'] and row['y']:
                x, y = float(row['x']), float(row['y'])
                spatial = any((x-cx)**2 + (y-cy)**2 <= 75**2 for cx, cy in centers)
            if row['actor_id'] == actor or row['road_id'] in local_edges or spatial:
                rows.append(row)
    actor_ids = {row['actor_id'] for row in rows}
    events = []
    with (run / 'events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            if any(a in line for a in actor_ids):
                events.append(json.loads(line))
    with (inputs / 'hazard.csv').open(encoding='utf-8', newline='') as stream:
        hazards = [row for row in csv.DictReader(stream) if row['edge_id'] in local_edges]
    after = {str(p.relative_to(root)): digest(p) for p in paths}
    if before != after:
        raise ValueError('Primary evidence changed')
    evidence = dict(run_id=manifest['run_id'], target=actor, warning_sec=at,
                    window_sec=[at-8, at+8], spatial_supplement_radius_m=75,
                    junction_ids=sorted(junction_ids), local_edges=sorted(local_edges),
                    junction_xml=[ET.tostring(j, encoding='unicode') for j in junctions],
                    edge_xml=[ET.tostring(edges[eid], encoding='unicode') for eid in sorted(local_edges)],
                    connection_xml=[ET.tostring(c, encoding='unicode') for c in tree.findall('connection')
                                    if c.get('from') in local_edges or c.get('to') in local_edges],
                    actor_rows=rows, related_events=events, hazards=hazards,
                    primary_sha256=before, primary_bytes_unchanged=True,
                    research_adoption_permitted=False,
                    limitation='Observed frame/topology context only. Link/leader native decisions are not logged; no unique causal inference.')
    (output / 'window.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(actor_rows=len(rows), actor_ids=sorted(actor_ids),
                          junction_ids=sorted(junction_ids), primary_bytes_unchanged=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.project_root, args.output)
