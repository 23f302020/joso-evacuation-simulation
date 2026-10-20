"""Build isolated, bounded-domain Joso realtime-B inputs from primary data."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import h5py
import networkx as nx
import numpy as np
import rasterio
import shapely
from shapely.geometry import shape, Point, LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
from pyproj import Transformer, CRS

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'04_プログラム'))
from scripts.jdrt.smoke import resolve_sumo_binary, load_traci
PARAM=ROOT/'04_プログラム/config/jdrt_realtime_b_v1.json'
EVIDENCE=ROOT/'02_情報調査/氾濫・浸水/jdrt_realtime_20261015'
SOURCE=EVIDENCE/'derived/usace_original/LifeSim_Validation_Joso/Hydraulic_Data'
REGION=ROOT/'04_プログラム/output/sumo/regions/08211'
REF=REGION/'experiments/scenario_c'

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))

def write_csv(path,rows,fields=None):
    with path.open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=fields or list(rows[0]));writer.writeheader();writer.writerows(rows)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def graph_from_net(net,mode,eligible):
    graph=nx.DiGraph() if mode=='passenger' else nx.Graph()
    edges={e.getID():e for e in net.getEdges() if e.getID() in eligible and e.allows(mode)}
    for name in sorted(edges):
        e=edges[name];graph.add_node(name,length=e.getLength(),free_sec=e.getLength()/max(e.getSpeed(),.1))
    if mode=='passenger':
        for name in sorted(edges):
            for other in sorted(edges[name].getOutgoing(),key=lambda x:x.getID()):
                if other.getID() in edges and any(c.getFromLane().allows(mode) and c.getToLane().allows(mode) for c in edges[name].getOutgoing()[other]):
                    graph.add_edge(name,other.getID(),length=other.getLength(),travel_sec=other.getLength()/max(other.getSpeed(),.1))
    else:
        at_node=defaultdict(list)
        for name,e in edges.items():
            at_node[e.getFromNode().getID()].append(name);at_node[e.getToNode().getID()].append(name)
        for names in at_node.values():
            for a in names:
                for b in names:
                    if a!=b:graph.add_edge(a,b,length=(edges[a].getLength()+edges[b].getLength())/2,travel_sec=(edges[a].getLength()+edges[b].getLength())/2)
    return graph

def build():
    parameters=json.loads(PARAM.read_text(encoding='utf-8'))
    out=ROOT/parameters['workspace']/parameters['input_directory'];out.mkdir(parents=True,exist_ok=False)
    operations=out.parent/'build_operations.jsonl'
    def log(stage,**data):
        record={'at_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),'stage':stage,**data}
        with operations.open('a',encoding='utf-8') as h:h.write(json.dumps(record,ensure_ascii=False)+'\n')
        print(json.dumps(record,ensure_ascii=False),flush=True)
    log('start',output=str(out.relative_to(ROOT)))
    sources=[PARAM,Path(__file__),SOURCE/'Calibrated/Calibrated.hdf',SOURCE/'Terrains/Terrain1/Terrain.kinugawa.tif',
             REF/'network/08211_ped.net.xml',REGION/'network/08211.osm.xml',
             EVIDENCE/'derived/usace_candidate_v3/cells_utm54n.geojson',EVIDENCE/'derived/usace_candidate_v3/network_domain_coverage.csv',
             EVIDENCE/'derived/usace_candidate_v3/structure_tags_audit.csv',
             REF/'inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_agent_types.csv',
             REF/'inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_mode_ledger.csv',
             REF/'preflight_20260810/non_car_15pct/car_occupancy_ledger.csv',REGION/'derived/shelters_sumo.csv',
             ROOT/'02_情報調査/交通・地域/jdrt_realistic/既存9施設_公表容量照合_20261015.csv',
             ROOT/parameters['pap']]
    source_sha={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    features=json.loads(sources[6].read_text(encoding='utf-8'))['features']
    polygons=[shape(f['geometry']) for f in features];cell_ids=np.array([f['properties']['cell_id'] for f in features]);domain=unary_union(polygons);tree=STRtree(polygons)
    cover=read_csv(sources[7]);tags={r['edge_id']:r for r in read_csv(sources[8])}
    reasons={}
    for row in cover:
        name=row['edge_id'];tag=tags[name]
        if row['status']!='inside_2d':reasons[name]='outside_or_partial_domain'
        elif tag['way_match']!='True':reasons[name]='unmapped_source_way'
        elif tag['bridge_tag'] or tag['tunnel_tag']:reasons[name]='unverified_structure_elevation'
    keep=sorted(r['edge_id'] for r in cover if r['edge_id'] not in reasons)
    (out/'keep_edges.txt').write_text('\n'.join(keep)+'\n',encoding='utf-8')
    sumo=resolve_sumo_binary();load_traci(sumo);import sumolib
    command=[str(sumo.with_name('netconvert.exe')),'--sumo-net-file',os.path.relpath(sources[4],out),'--keep-edges.input-file','keep_edges.txt',
             '--output-file','bounded.net.xml','--no-turnarounds','true','--walkingareas','true','--no-warnings','true']
    result=subprocess.run(command,cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (out/'netconvert.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('netconvert failed; inspect new input directory')
    net=sumolib.net.readNet(str(out/'bounded.net.xml'));source_net=sumolib.net.readNet(str(sources[4]))
    location=ET.parse(out/'bounded.net.xml').getroot().find('location').attrib
    offset=np.array([float(x) for x in location['netOffset'].split(',')]);transform=Transformer.from_crs(CRS.from_user_input(location['projParameter']),32654,always_xy=True)
    with h5py.File(sources[2],'r') as f:
        prefix='Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
        dates=[datetime.strptime(x.decode(),'%d%b%Y %H:%M:%S') for x in f[prefix+'Time Date Stamp'][:]]
        start=datetime.fromisoformat(parameters['simulation']['start_jst']).replace(tzinfo=None);end=start+timedelta(seconds=parameters['simulation']['duration_sec'])
        time_ix=[i for i,d in enumerate(dates) if start<=d<=end];seconds=np.array([(dates[i]-start).total_seconds() for i in time_ix],dtype=int)
        assert seconds[0]==0 and seconds[-1]==parameters['simulation']['duration_sec']
        wse=f[prefix+'2D Flow Areas/Joso Area/Water Surface'][time_ix,:]
    samples=[];sample_edge=[];sample_class=[]
    spacing=parameters['hazard']['sample_spacing_m']
    for edge in net.getEdges():
        for lane in edge.getLanes():
            classes=[m for m in ['passenger','pedestrian'] if lane.allows(m)]
            if not classes:continue
            xy=np.array(lane.getShape())-offset;xx,yy=transform.transform(xy[:,0],xy[:,1]);line=LineString(zip(xx,yy))
            points=[line.interpolate(d) for d in np.linspace(0,line.length,max(2,math.ceil(line.length/spacing)+1))]
            for mode in classes:
                samples.extend([(p.x,p.y) for p in points]);sample_edge.extend([edge.getID()]*len(points));sample_class.extend([mode]*len(points))
    log('sample_geometry',edges=len(net.getEdges()),sample_points=len(samples))
    points=shapely.points(np.asarray(samples));hits=tree.query(points,predicate='intersects');order=np.lexsort((cell_ids[hits[1]],hits[0]));hits=hits[:,order]
    unique=np.r_[True,np.diff(hits[0])!=0];point_ids=hits[0,unique];selected_cells=cell_ids[hits[1,unique]]
    ids=np.full(len(samples),-1,dtype=int);ids[point_ids]=selected_cells
    with rasterio.open(sources[3]) as terrain:
        elevations=np.array([float(x[0]) for x in terrain.sample(samples)])
        valid=(ids>=0)&np.isfinite(elevations)&(elevations!=terrain.nodata)
    bad_edges=set(sample_edge[i] for i in np.flatnonzero(~valid))
    for name in bad_edges:reasons[name]='native_cell_or_terrain_missing'
    eligible=set(keep)-bad_edges
    by_group=defaultdict(list)
    for i,(name,mode) in enumerate(zip(sample_edge,sample_class)):
        if name in eligible:by_group[name,mode].append(i)
    hazard=[]
    for (name,mode),indexes in sorted(by_group.items()):
        ix=np.array(indexes);depth=np.maximum(wse[:,ids[ix]]-elevations[ix],0).max(axis=1)
        threshold=parameters['hazard']['vehicle_depth_m' if mode=='passenger' else 'pedestrian_depth_m'];cross=np.flatnonzero(depth>=threshold)
        k=int(cross[0]) if len(cross) else None
        hazard.append({'edge_id':name,'mode':mode,'closure_sec':int(seconds[k]) if k is not None else '',
                       'lower_sec':int(seconds[k-1]) if k is not None and k>0 else 0 if k==0 else '',
                       'upper_sec':int(seconds[k]) if k is not None else '',
                       'initial_depth_m':float(depth[0]),'max_depth_m':float(max(depth)),
                       'sample_count':len(ix),'threshold_m':threshold})
    write_csv(out/'hazard.csv',hazard);write_csv(out/'quarantined_edges.csv',[{'edge_id':n,'reason':r} for n,r in sorted(reasons.items())])
    np.savez_compressed(out/'road_samples.npz',xy=np.asarray(samples),edge_id=np.asarray(sample_edge),mode=np.asarray(sample_class),cell_id=ids,elevation_m=elevations,valid=valid,native_sec=seconds)
    graphs={m:graph_from_net(net,m,eligible) for m in ['passenger','pedestrian']}
    initial_closed={m:{r['edge_id'] for r in hazard if r['mode']==m and r['closure_sec']==0} for m in graphs}
    dry={m:{r['edge_id'] for r in hazard if r['mode']==m and r['closure_sec']==''} for m in graphs}
    terminal_rows=[];ll_to_xy=Transformer.from_crs(4326,32654,always_xy=True)
    shapes={e.getID():LineString([(x-offset[0],y-offset[1]) for x,y in e.getShape()]) for e in net.getEdges() if e.getID() in eligible}
    shared=sorted(set(graphs['passenger'])&set(graphs['pedestrian']))
    def nearest(point,allowed):
        options=sorted((point.distance(shapes[n]),n) for n in allowed if net.getEdge(n).getLength()>=15)
        return options[0] if options else (math.inf,'')
    capacities={r['shelter_id']:r for r in read_csv(sources[13])}
    for facility in read_csv(sources[12]):
        point=Point(*ll_to_xy.transform(float(facility['lon']),float(facility['lat'])))
        if not domain.covers(point):continue
        distance,name=nearest(point,[n for n in shared if n in dry['passenger'] and n in dry['pedestrian']])
        if distance>parameters['population']['snap_limit_m']:continue
        terminal_rows.append({'terminal_id':facility['shelter_id'],'kind':'facility','edge_id':name,'name':facility['name'],
                              'capacity':int(capacities[facility['shelter_id']]['published_capacity_people']),
                              'snap_m':distance,'open_sec':0})
    # Candidate portals are only outer-domain cuts, not bridge/data quarantines inside the domain.
    source_cover={r['edge_id']:r['status'] for r in cover}
    portal_nodes=set()
    for name in shared:
        if name not in dry['passenger'] or name not in dry['pedestrian'] or net.getEdge(name).getLength()<15:continue
        original=source_net.getEdge(name);node=original.getToNode()
        if any(source_cover.get(e.getID()) in ['outside_2d','partial_2d'] for e in node.getOutgoing()):
            node_id=node.getID()
            if node_id in portal_nodes:continue
            portal_nodes.add(node_id)
            terminal_rows.append({'terminal_id':'exit_'+node_id,'kind':'boundary_exit','edge_id':name,'name':'model outflow '+node_id,
                                  'capacity':'','snap_m':0,'open_sec':0})
    assert any(r['kind']=='facility' for r in terminal_rows) and any(r['kind']=='boundary_exit' for r in terminal_rows)
    write_csv(out/'terminals.csv',terminal_rows)
    graphs_initial={m:g.copy() for m,g in graphs.items()}
    for m,g in graphs_initial.items():g.remove_nodes_from(initial_closed[m])
    terminal_by_edge={}
    for r in sorted(terminal_rows,key=lambda x:x['terminal_id'],reverse=True):terminal_by_edge[r['edge_id']]=r['terminal_id']
    nearest_maps={}
    for mode,g in graphs_initial.items():
        reverse=g.reverse(copy=False) if g.is_directed() else g
        dest_edges=sorted(set(terminal_by_edge)&set(g))
        nearest_maps[mode]=nx.multi_source_dijkstra(reverse,dest_edges,weight='length')
    origin_rows=[];inside_ids=set();raw_origins=read_csv(sources[9])
    for origin in raw_origins:
        point=Point(*ll_to_xy.transform(float(origin['lon']),float(origin['lat'])))
        if not domain.covers(point):continue
        inside_ids.add(origin['origin_id']);distance,name=nearest(point,shared)
        if distance>parameters['population']['snap_limit_m']:name=''
        dest='';car_route=[];walk_route=[]
        for mode in ['passenger','pedestrian']:
            paths=nearest_maps[mode][1]
            if name in paths:dest=terminal_by_edge[paths[name][0]];break
        if dest:
            terminal=next(r for r in terminal_rows if r['terminal_id']==dest)
            for mode in graphs_initial:
                graph=graphs_initial[mode]
                try:route=nx.shortest_path(graph,name,terminal['edge_id'],weight='length')
                except (nx.NetworkXNoPath,nx.NodeNotFound):route=[]
                if mode=='passenger':car_route=route
                else:walk_route=route
        origin_rows.append({'origin_id':origin['origin_id'],'edge_id':name,'snap_m':distance,'terminal_id':dest,
                            'car_route':json.dumps(car_route),'walk_route':json.dumps(walk_route),
                            'walk_length_m':sum(net.getEdge(n).getLength() for n in walk_route) if walk_route else ''})
    write_csv(out/'origins.csv',origin_rows)
    occupancy={r['person_id']:r['vehicle_id'] for r in read_csv(sources[11])}
    people=[];excluded=[]
    for person in read_csv(sources[10]):
        row={'person_id':'b_'+person['person_id'],'source_person_id':person['person_id'],'origin_id':person['origin_id'],
             'person_type':person['person_type'],'base_mode':person['assigned_mode'],'vehicle_id':occupancy.get(person['person_id'],'')}
        if person['origin_id'] in inside_ids:people.append(row)
        else:excluded.append({**row,'reason':'origin_outside_hydraulic_domain'})
    write_csv(out/'people.csv',people);write_csv(out/'excluded_people.csv',excluded)
    depot=next((r['edge_id'] for r in terminal_rows if r['terminal_id']==parameters['operation']['reference_depot_shelter']),None)
    if depot is None:depot=sorted(r['edge_id'] for r in terminal_rows if r['kind']=='facility')[0]
    graph_data={mode:{'nodes':{n:dict(a) for n,a in g.nodes(data=True)},'edges':[(a,b,dict(d)) for a,b,d in g.edges(data=True)],'directed':g.is_directed()} for mode,g in graphs.items()}
    (out/'graphs.json').write_text(json.dumps(graph_data),encoding='utf-8')
    manifest={'protocol':parameters['protocol'],'created_at_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'status':'BUILT_PENDING_INDEPENDENT_VALIDATION','source_sha256':source_sha,
              'population_counts':dict(Counter(r['person_type'] for r in people)), 'people':len(people),'origins':len(origin_rows),
              'private_vehicles':len({r['vehicle_id'] for r in people if r['vehicle_id']}),'facilities':sum(r['kind']=='facility' for r in terminal_rows),
              'boundary_exits':sum(r['kind']=='boundary_exit' for r in terminal_rows),'depot_edge':depot,
              'eligible_edges':len(eligible),'quarantines':dict(Counter(reasons.values())),
              'timezone_interpretation':'JST event alignment; source has no timezone tag',
              'artifacts':{p.relative_to(out).as_posix():sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    log('built',people=manifest['people'],counts=manifest['population_counts'],origins=len(origin_rows),facilities=manifest['facilities'],boundary_exits=manifest['boundary_exits'],eligible_edges=len(eligible))
    return manifest

if __name__=='__main__':
    build()
