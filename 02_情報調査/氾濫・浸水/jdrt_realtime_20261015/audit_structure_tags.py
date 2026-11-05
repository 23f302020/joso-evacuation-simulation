"""Inspect existing OSM structure tags. Absence of a tag is not road elevation."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
OSM=ROOT/'04_プログラム/output/sumo/regions/08211/network/08211.osm.xml'
CAND=BASE/'derived/usace_candidate_v3'

def run():
    ways={}
    for _,element in ET.iterparse(OSM,events=('end',)):
        if element.tag=='way':
            ways[element.attrib['id']]={x.attrib['k']:x.attrib['v'] for x in element.findall('tag')}
            element.clear()
    with (CAND/'network_domain_coverage.csv').open(encoding='utf-8',newline='') as handle: roads=list(csv.DictReader(handle))
    rows=[]
    for road in roads:
        base_id=road['edge_id'].lstrip('-').split('#')[0]
        tags=ways.get(base_id,{})
        rows.append({'edge_id':road['edge_id'],'source_way_id':base_id,'way_match':base_id in ways,
                     'coverage':road['status'],'bridge_tag':tags.get('bridge',''),
                     'tunnel_tag':tags.get('tunnel',''),'layer_tag':tags.get('layer',''),
                     'deck_elevation_m':'','interpretation':'tag_only_not_deck_height'})
    target=CAND/'structure_tags_audit.csv'
    if target.exists():raise RuntimeError('Refuse overwrite')
    with target.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'source_osm_sha256':hashlib.sha256(OSM.read_bytes()).hexdigest(),
            'source_ways':len(ways),'road_edges':len(rows),'matched_edges':sum(r['way_match'] for r in rows),
            'bridge_tagged_edges':sum(bool(r['bridge_tag']) for r in rows),
            'tunnel_tagged_edges':sum(bool(r['tunnel_tag']) for r in rows),
            'bridge_coverage':dict(Counter(r['coverage'] for r in rows if r['bridge_tag'])),
            'deck_elevations_available':False,'no_tag_means':'unknown, not proof of at-grade',
            'artifact_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (CAND/'structure_tags_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':run()
