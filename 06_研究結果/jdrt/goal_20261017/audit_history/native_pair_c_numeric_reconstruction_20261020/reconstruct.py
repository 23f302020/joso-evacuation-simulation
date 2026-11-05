"""Read-only forensic calculation for the preserved repeated-walk fixture.

No SUMO launch, original-file write, validation, adoption, or runtime change.
Walking-area geometry follows the archived native straight-lane/default-detail
branch; assertions deliberately reject networks outside this diagnostic scope.
"""
import csv
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[5]
CASE = ROOT / ('04_プログラム/output/sumo/regions/08211/experiments/'
               'jdrt_realtime_choice_v1/technical/np261020c_c26')
OUT = Path(__file__).parent
NATIVE = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/'
              'choice_v126_20261019/sources/control126_20261020/src')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def shape(lane):
    return [tuple(map(float, p.split(','))) for p in lane.get('shape').split()]


def unit(a, b):
    length = math.dist(a, b)
    assert length > 0
    return tuple((y - x) / length for x, y in zip(a, b))


def shift(a, direction, amount):
    return tuple(x + d * amount for x, d in zip(a, direction))


def main():
    inputs, execution = CASE / 'fixture_inputs', CASE / 'execution'
    sources = [inputs / 'bounded.net.xml', execution / 'actor_observations.csv.gz',
               execution / 'events.jsonl', execution / 'manifest.json',
               execution / 'implementation/04_プログラム/scripts/jdrt_realtime_choice.py',
               NATIVE / 'microsim/transportables/MSPModel_Striping.cpp',
               NATIVE / 'microsim/transportables/MSPModel_Striping.h',
               NATIVE / 'microsim/transportables/MSStageWalking.cpp',
               NATIVE / 'microsim/MSFrame.cpp']
    before = {str(p): digest(p) for p in sources}
    native = sources[-4].read_text(encoding='utf-8')
    frame = sources[-1].read_text(encoding='utf-8')
    runtime = sources[4].read_text(encoding='utf-8')
    assert 'else if (myWalkingAreaDetail > 4)' in native
    assert 'new Option_Integer(4)' in frame.split('"pedestrian.striping.walkingarea-detail"', 1)[1][:80]
    assert 'pedestrian.striping.walkingarea-detail' not in runtime
    tree = ET.parse(inputs / 'bounded.net.xml')
    edges = {e.get('id'): e for e in tree.findall('edge')}
    lanes = {k: next(l for l in e.findall('lane') if 'pedestrian' in l.get('allow', '').split())
             for k, e in edges.items() if any('pedestrian' in l.get('allow', '').split() for l in e.findall('lane'))}
    links = {(c.get('from'), c.get('to')) for c in tree.findall('connection')
             if c.get('fromLane') == '0' and c.get('toLane') == '0'}
    events = [json.loads(s) for s in (execution / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    with gzip.open(execution / 'actor_observations.csv.gz', 'rt', encoding='utf-8-sig') as stream:
        actors = list(csv.DictReader(stream))
    results = []
    plans = {}
    for event in events:
        if event['event'] != 'walk_plan':
            continue
        person = event['person_id']
        prior = plans.get(person)
        plans[person] = event
        if not prior or event.get('stage') != 'reroute' or not prior.get('replacement_receipts'):
            continue
        route = prior['route']
        assert all(edges[a].get('to') == edges[b].get('from') for a, b in zip(route, route[1:]))
        assert all(len(shape(lanes[e])) == 2 for e in route)
        endpoint_terms = [math.dist(shape(lanes[a])[-1], shape(lanes[b])[0])
                          for a, b in zip(route, route[1:])]
        external = sum(float(lanes[e].get('length')) for e in route)
        base = external - prior['depart_pos'] - (float(lanes[route[-1]].get('length')) - prior['arrival_pos'])
        observations = [r for r in actors if r['actor_id'] == person
                        and prior['time_sec'] <= float(r['time_sec']) <= event['time_sec']]
        visited = []
        for row in observations:
            if not visited or row['road_id'] != visited[-1]:
                visited.append(row['road_id'])
        assert visited[0] == route[0] and visited[-1] == route[1]
        internal = []
        for index, edge in enumerate(visited[1:-1], 1):
            lane = lanes[edge]
            assert edge.startswith(':')
            if edges[edge].get('function') == 'walkingarea':
                previous, following = visited[index - 1], visited[index + 1]
                assert (previous, edge) in links and (edge, following) in links
                from_shape, to_shape = shape(lanes[previous]), shape(lanes[following])
                assert len(from_shape) == len(to_shape) == 2
                a, b = from_shape[-1], to_shape[0]
                amount = min(math.dist(a, b) / 4, float(lane.get('width')) / 2)
                points = [a, shift(a, unit(*from_shape), amount),
                          shift(b, unit(*to_shape), -amount), b]
                length = sum(math.dist(x, y) for x, y in zip(points, points[1:]))
                internal.append({'edge': edge, 'shape_reconstructed': points, 'length_m': length})
            else:
                assert edges[edge].get('function') == 'crossing'
                internal.append({'edge': edge, 'length_m': float(lane.get('length'))})
        internal_sum = sum(x['length_m'] for x in internal)
        installed = base + sum(endpoint_terms)
        live = base + internal_sum
        raw_live = event['replacement_receipts'][0]['before']['stage_length_m']
        assert math.isclose(installed, prior['sumo_plan_length_m'], rel_tol=0, abs_tol=1e-10)
        assert math.isclose(live, raw_live, rel_tol=0, abs_tol=1e-10)
        results.append({'actor': person, 'time_sec': event['time_sec'], 'route': route,
                        'external_base_m': base, 'junction_endpoint_terms_m': endpoint_terms,
                        'junction_endpoint_sum_m': sum(endpoint_terms), 'visited': visited,
                        'completed_internal_paths': internal, 'completed_internal_sum_m': internal_sum,
                        'reconstructed_installed_plan_m': installed, 'raw_installed_plan_m': prior['sumo_plan_length_m'],
                        'reconstructed_live_length_m': live, 'raw_live_length_m': raw_live,
                        'difference_m': internal_sum - sum(endpoint_terms),
                        'remaining_length_was_not_substituted': True})
    assert len(results) == 2
    assert before == {str(p): digest(p) for p in sources}
    result = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'status': 'DIAGNOSTIC_GEOMETRY_RECONSTRUCTED_NOT_ACCEPTANCE', 'results': results,
              'source_sha256': before, 'analysis_source_sha256': digest(Path(__file__)),
              'originals_unchanged': True, 'runtime_or_validator_changed': False,
              'research_adoption_permitted': False, 'technical_ready': False,
              'limitation': 'Only the preserved straight-lane/default-detail fixture branch; no generalized native guard trace or full regression proof.'}
    with (OUT / 'result.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'status': result['status'], 'actors': len(results),
                      'differences_m': [r['difference_m'] for r in results], 'originals_unchanged': True}))


if __name__ == '__main__':
    main()
