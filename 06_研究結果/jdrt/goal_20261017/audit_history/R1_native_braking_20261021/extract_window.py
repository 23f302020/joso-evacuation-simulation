"""Read-only native-braking evidence extraction; no validation or adoption."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = root / '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1'
    run = workspace / 'runs/ch261021_002'
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    inputs = root / manifest['input_directory']
    actor, lane, at = 'scen_c_origin_0381_0016', '9407#2_1', 6112.5
    edge = lane.rsplit('_', 1)[0]
    net = ET.parse(inputs / 'bounded.net.xml').getroot()
    links = [dict(c.attrib) for c in net.findall('connection') if edge in (c.get('from'), c.get('to'))]
    nearby = {edge} | {c[k] for c in links for k in ('from', 'to')}
    via = {c.get('via', '').rsplit('_', 1)[0] for c in links}
    lanes = [dict(e.attrib, lanes=[dict(l.attrib) for l in e.findall('lane')])
             for e in net.findall('edge') if e.get('id') in nearby | via]
    paths = [run / 'actor_observations.csv.gz', run / 'events.jsonl', run / 'types.rou.xml',
             inputs / 'bounded.net.xml', inputs / 'hazard.csv', run / 'manifest.json']
    before = {str(p.relative_to(root)): digest(p) for p in paths}
    targets, neighbors, prior_time = [], [], -1
    with gzip.open(run / 'actor_observations.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            time = float(row['time_sec'])
            if time < prior_time:
                raise RuntimeError('Actor stream time is not monotone')
            prior_time = time
            if time > at + 4:
                break
            if time >= at - 4:
                if row['actor_id'] == actor:
                    targets.append(row)
                if row['road_id'] in nearby | via:
                    neighbors.append(row)
    events = []
    with (run / 'events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            if actor in line:
                events.append(json.loads(line))
    with (inputs / 'hazard.csv').open(encoding='utf-8', newline='') as stream:
        hazards = [r for r in csv.DictReader(stream) if r['edge_id'] in nearby]
    evidence = {'run_id': manifest['run_id'], 'actor': actor, 'native_warning_sec': at,
                'actor_window': targets, 'nearby_actor_window': neighbors, 'actor_events': events,
                'net_links': links, 'net_edges': lanes, 'hazards': hazards,
                'vehicle_types': [dict(t.attrib) for t in ET.parse(run / 'types.rou.xml').getroot()],
                'read_bytes_before': before, 'research_adoption_permitted': False,
                'limitation': 'Source window only; leader/link state must be independently reconstructed. No causal claim.'}
    after = {str(p.relative_to(root)): digest(p) for p in paths}
    if before != after:
        raise RuntimeError('Primary evidence changed during extraction')
    evidence['primary_bytes_unchanged'] = True
    with (output / 'window.json').open('x', encoding='utf-8') as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'target_frames': len(targets), 'nearby_frames': len(neighbors),
                      'target_events': len(events), 'primary_bytes_unchanged': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.project_root, args.output)
