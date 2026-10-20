"""Independent primary-artifact validation for realtime-B inputs and cells."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timedelta
import argparse
import csv
import gzip
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import h5py
import numpy as np
import rasterio
from shapely.geometry import shape,Point
from shapely.ops import unary_union
from pyproj import Transformer
from scripts.jdrt_realtime_b_inputs import ROOT,PARAM,EVIDENCE,SOURCE,REF,read_csv,sha

def validate_inputs():
    p=json.loads(PARAM.read_text(encoding='utf-8'));directory=ROOT/p['workspace']/p['input_directory'];m=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    checks={}
    checks['source_sha']=all(sha(ROOT/n)==s for n,s in m['source_sha256'].items())
    checks['artifact_sha']=all(sha(directory/n)==s for n,s in m['artifacts'].items())
    geom=json.loads((EVIDENCE/'derived/usace_candidate_v3/cells_utm54n.geojson').read_text())
    domain=unary_union([shape(x['geometry']) for x in geom['features']]);trans=Transformer.from_crs(4326,32654,always_xy=True)
    origin_source=read_csv(REF/'inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_agent_types.csv')
    inside={r['origin_id'] for r in origin_source if domain.covers(Point(*trans.transform(float(r['lon']),float(r['lat']))))}
    old=read_csv(REF/'inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_mode_ledger.csv')
    expected={r['person_id']:r for r in old if r['origin_id'] in inside};people=read_csv(directory/'people.csv');excluded=read_csv(directory/'excluded_people.csv')
    checks['spatial_population_exact']=len(people)==len(expected) and {r['source_person_id'] for r in people}==set(expected)
    checks['attributes_preserved']=all(r['person_type']==expected[r['source_person_id']]['person_type'] and r['base_mode']==expected[r['source_person_id']]['assigned_mode'] for r in people)
    checks['source_population_partition']=len(people)+len(excluded)==len(old) and not ({r['source_person_id'] for r in people}&{r['source_person_id'] for r in excluded})
    origin_rows=read_csv(directory/'origins.csv');checks['all_origins_preserved']={r['origin_id'] for r in origin_rows}==inside
    with np.load(directory/'road_samples.npz') as archive:samples={name:archive[name] for name in archive.files}
    hazard=read_csv(directory/'hazard.csv')
    with h5py.File(SOURCE/'Calibrated/Calibrated.hdf','r') as f:
        key='Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
        dates=[datetime.strptime(x.decode(),'%d%b%Y %H:%M:%S') for x in f[key+'Time Date Stamp'][:]]
        start=datetime.fromisoformat(p['simulation']['start_jst']).replace(tzinfo=None);end=start+timedelta(seconds=p['simulation']['duration_sec'])
        ix=[i for i,d in enumerate(dates) if start<=d<=end];secs=np.array([(dates[i]-start).total_seconds() for i in ix],dtype=int)
        surface=f[key+'2D Flow Areas/Joso Area/Water Surface'][ix,:]
    checks['native_time_exact']=np.array_equal(secs,samples['native_sec']) and secs[0]==0 and secs[-1]==p['simulation']['duration_sec']
    with rasterio.open(SOURCE/'Terrains/Terrain1/Terrain.kinugawa.tif') as r:
        inverse=~r.transform;xx=samples['xy'][:,0];yy=samples['xy'][:,1]
        cc=np.floor(inverse.a*xx+inverse.b*yy+inverse.c).astype(int)
        rr=np.floor(inverse.d*xx+inverse.e*yy+inverse.f).astype(int)
        valid=(rr>=0)&(rr<r.height)&(cc>=0)&(cc<r.width)
        terrain=np.full(len(rr),r.nodata,dtype=float);grid=r.read(1);terrain[valid]=grid[rr[valid],cc[valid]]
    checks['sample_terrain_equal_source']=np.array_equal(terrain,samples['elevation_m'])
    groups=defaultdict(list)
    for i,(edge,mode) in enumerate(zip(samples['edge_id'],samples['mode'])):groups[str(edge),str(mode)].append(i)
    mismatches=[]
    for row in hazard:
        ids=np.array(groups[row['edge_id'],row['mode']]);cell=samples['cell_id'][ids]
        if not np.all(samples['valid'][ids]):mismatches.append(row['edge_id']);continue
        depth=(surface[:,cell]-terrain[ids]).clip(min=0).max(axis=1);hit=np.nonzero(depth>=float(row['threshold_m']))[0]
        at=str(int(secs[hit[0]])) if len(hit) else ''
        if at!=row['closure_sec'] or not math.isclose(float(max(depth)),float(row['max_depth_m']),abs_tol=1e-6):mismatches.append(row['edge_id'])
    checks['all_road_thresholds_from_primary']=not mismatches
    tags={r['edge_id']:r for r in read_csv(EVIDENCE/'derived/usace_candidate_v3/structure_tags_audit.csv')}
    eligible={r['edge_id'] for r in hazard}
    checks['no_unverified_structure_in_graph']=all(not tags[n]['bridge_tag'] and not tags[n]['tunnel_tag'] and tags[n]['way_match']=='True' for n in eligible)
    terms=read_csv(directory/'terminals.csv');capacity={r['shelter_id']:int(r['published_capacity_people']) for r in read_csv(ROOT/'02_情報調査/交通・地域/jdrt_realistic/既存9施設_公表容量照合_20261015.csv')}
    checks['facility_capacities_from_source']=all(int(r['capacity'])==capacity[r['terminal_id']] for r in terms if r['kind']=='facility')
    by_hazard={(r['edge_id'],r['mode']):r for r in hazard}
    checks['terminal_access_dry_all_window']=all(by_hazard[r['edge_id'],mode]['closure_sec']=='' for r in terms for mode in ['passenger','pedestrian'])
    checks['exit_not_internal_quarantine']=all(r['terminal_id'].startswith('exit_') and r['capacity']=='' for r in terms if r['kind']=='boundary_exit')
    graph_data=json.loads((directory/'graphs.json').read_text())
    checks['graph_population_boundaries']=all(set(d['nodes'])<=eligible for d in graph_data.values())
    checks['route_membership']=all(all(n in graph_data[mode]['nodes'] for n in json.loads(r[field])) for r in origin_rows for mode,field in [('passenger','car_route'),('pedestrian','walk_route')])
    checks={k:bool(v) for k,v in checks.items()}
    report={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'input_manifest_sha256':sha(directory/'manifest.json'),
            'people':len(people),'types':dict(Counter(r['person_type'] for r in people)),'hazard_rows_recomputed':len(hazard),'mismatched_edges':mismatches,
            'validator_sha256':sha(Path(__file__))}
    target=ROOT/p['workspace']/'input_validation.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def validate_run(run_dir):
    p=json.loads(PARAM.read_text(encoding='utf-8'));m=json.loads((run_dir/'manifest.json').read_text());directory=ROOT/m['input_directory'];checks={}
    checks['completed']=m['status']=='COMPLETED';checks['parameter_sha']=m['parameter_sha256']==sha(PARAM)
    checks['input_manifest_sha']=m['input_manifest_sha256']==sha(directory/'manifest.json')
    checks['implementation_sha']=all(sha(ROOT/n)==s for n,s in m['implementation_sha256'].items())
    checks['output_sha']=all(sha(run_dir/n)==s for n,s in m.get('output_sha256',{}).items())
    people=read_csv(run_dir/'person_results.csv');realized=read_csv(run_dir/'common_realization.csv');by_id={r['person_id']:r for r in realized}
    base=read_csv(directory/'people.csv');base_ids={r['person_id'] for r in base}
    checks['population_ids']=len(people)==len(realized)==len({r['person_id'] for r in people}) and set(by_id)=={r['person_id'] for r in people}
    if m['purpose']=='core':checks['full_population_exact']=set(by_id)==base_ids
    checks['attributes_unchanged']=all(r['source_person_id']==by_id[r['person_id']]['source_person_id'] and r['person_type']==by_id[r['person_id']]['person_type'] and r['terminal_id']==by_id[r['person_id']]['terminal_id'] for r in people)
    checks['mode_whitelist']=all(r['mode']==('drt' if m['scenario']!='R0' and by_id[r['person_id']]['selected_jdrt']=='True' else r['base_mode']) for r in people)
    final={'admitted','boundary_exit','capacity_rejected','no_origin_connection','no_route','walk_limit','initial_or_current_closed','route_cut','stranded_drt','time_limit'}
    checks['every_person_terminal']=all(r['status'] in final for r in people)
    checks['primary_time_bounds']=all(r['admitted_sec']!='' and 0<=float(r['admitted_sec'])<=m['end_sec'] for r in people if r['status']=='admitted')
    if m['purpose']=='smoke':
        checks['smoke_walk_physically_completed']=any(r['mode']=='walk' and r['status']=='admitted' for r in people)
        if m['scenario']!='R0':checks['smoke_drt_physically_completed']=any(r['mode']=='drt' and r['status']=='admitted' and r['pickup_sec']!='' for r in people)
    requests=read_csv(run_dir/'request_results.csv');checks['request_person_bijection']={r['person_id'] for r in requests}=={r['person_id'] for r in people if r['mode']=='drt'} and len(requests)==sum(r['mode']=='drt' for r in people)
    checks['pickup_arrival_order']=all(r['pickup_sec']=='' or r['arrival_sec']=='' or float(r['pickup_sec'])<=float(r['arrival_sec']) for r in requests)
    facilities=read_csv(run_dir/'facility_results.csv');admissions=Counter(r['terminal_id'] for r in people if r['status']=='admitted')
    checks['capacity_accounting']=all(int(r['admitted'])==admissions[r['terminal_id']]<=int(r['capacity']) for r in facilities) and sum(int(r['admitted']) for r in facilities)==sum(admissions.values())
    vehicles=read_csv(run_dir/'vehicle_results.csv');expected_fleet=p['operation']['fleet_count'] if m['scenario']!='R0' else 0
    checks['fleet_count']=sum(r['kind']=='drt' for r in vehicles)==expected_fleet
    checks['capacity_bound']=all(not r['passenger_capacity'] or int(r['maximum_onboard'])<=int(r['passenger_capacity']) for r in vehicles)
    trips={r.attrib['id']:r.attrib for r in ET.parse(run_dir/'tripinfo.xml').getroot().findall('tripinfo')}
    checks['vehicle_distance_from_tripinfo']=all((r['distance_m']=='' and r['vehicle_id'] not in trips) or (r['vehicle_id'] in trips and float(r['distance_m'])==float(trips[r['vehicle_id']]['routeLength'])) for r in vehicles)
    summary=m['summary'];checks['population_summary']=summary['people']==len(people) and summary['states']==dict(Counter(r['status'] for r in people))
    checks['step_counts']=summary['counts']['steps']==round(m['end_sec']/m['step_sec']) and summary['counts']['controller_ticks']==int(m['end_sec']/p['simulation']['controller_sec'])+1
    checks['zero_technical_anomalies']=all(summary['counts'][name]==0 for name in ['teleports','collisions','missing_vehicle_subscriptions','missing_person_subscriptions'])
    errors=0
    log=run_dir/'sumo_errors.log'
    if log.exists():errors=sum(line.startswith('Error:') for line in log.read_text(encoding='utf-8',errors='replace').splitlines())
    checks['zero_sumo_error_lines']=errors==0 and summary['sumo_errors']['error_count']==errors
    stderr=run_dir.parents[1]/'driver_logs'/(m['run_id']+'.stderr.log')
    driver_errors=[line for line in stderr.read_text(encoding='utf-8',errors='replace').splitlines() if line.startswith('Error:') or line.startswith('Traceback (most recent call last):')] if stderr.exists() else None
    checks['zero_driver_error_lines']=driver_errors is not None and len(driver_errors)==0
    hazard={(r['edge_id'],r['mode']):int(r['closure_sec']) for r in read_csv(directory/'hazard.csv') if r['closure_sec']!=''}
    expected_applied={key for key,sec in hazard.items() if sec<=m['end_sec']};applied=[];boarded=Counter()
    with (run_dir/'events.jsonl').open(encoding='utf-8') as f:
        for line in f:
            e=json.loads(line)
            if e['event']=='closure_applied':applied.append((e['edge_id'],e['mode']))
            if e['event']=='drt_boarded':boarded[e['vehicle_id']]=max(boarded[e['vehicle_id']],int(e['onboard_count']))
    checks['all_closures_once']=set(applied)==expected_applied and len(applied)==len(expected_applied)
    checks['capacity_from_events']=all(int(r['maximum_onboard'])==boarded[r['vehicle_id']] for r in vehicles if r['kind']=='drt')
    graph=json.loads((directory/'graphs.json').read_text());expected_pairs={(n,mode) for mode,physical in [('car','passenger'),('drt','passenger'),('walk','pedestrian')] for n in graph[physical]['nodes']}
    expected_times=list(range(0,int(m['end_sec'])+1,int(m['snapshot_sec'])));seen_times=[];current=None;seen=set();road_ok=True;road_rows=0
    with gzip.open(run_dir/'edge_observations.csv.gz','rt',encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            now=float(r['time_sec'])
            if now!=current:
                if current is not None and seen!=expected_pairs:road_ok=False
                current=now;seen_times.append(now);seen=set()
            pair=(r['edge_id'],r['mode'])
            if pair in seen:road_ok=False
            seen.add(pair);road_rows+=1
            if r['observation_status']!='observed' or (int(r['count'])==0 and r['mean_speed_mps']!=''):road_ok=False
            physical='pedestrian' if r['mode']=='walk' else 'passenger';closed=hazard.get((r['edge_id'],physical),math.inf)<=now
            if (r['closed']=='True')!=closed:road_ok=False
    checks['complete_zero_inclusive_edge_observations']=road_ok and seen==expected_pairs and seen_times==expected_times and road_rows==len(expected_pairs)*len(expected_times)
    transitions=0;entries=0;ambiguous=0
    with gzip.open(run_dir/'transitions.csv.gz','rt',encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            transitions+=1;entries+=int(r['kind']=='closed_entry');ambiguous+=int(r['ambiguous']=='True')
    checks['transition_accounting']=transitions==summary['counts']['transition_rows'] and entries==summary['counts']['closed_entry_rows'] and ambiguous==summary['counts']['ambiguous_transitions']
    checks['unambiguous_closed_road_control']=entries==0 and ambiguous==0
    candidate_count=0;candidate_ok=True
    with gzip.open(run_dir/'candidates.csv.gz','rt',encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            candidate_count+=1
            if m['scenario']=='R1' and (r['forecast_remaining_sec'] or r['gate_applicable']=='True'):candidate_ok=False
            if r['gate_applicable']=='True' and r['required_sec'] and r['forecast_remaining_sec']:
                if (float(r['required_sec'])<float(r['forecast_remaining_sec']))!=(r['gate_pass']=='True'):candidate_ok=False
    checks['candidate_gate_recomputed']=candidate_ok and candidate_count==summary['counts']['candidate_rows']
    type4=[r for r in people if r['person_type']==p['evaluation']['primary_type']];numerator=sum(r['status']=='admitted' for r in type4)
    report={'status':'PASS' if all(checks.values()) else 'FAIL','run_id':m['run_id'],'purpose':m['purpose'],'checks':checks,
            'people':len(people),'type4_denominator':len(type4),'type4_admitted':numerator,
            'type4_rate':numerator/len(type4) if type4 else None,'type4_boundary_exit':sum(r['status']=='boundary_exit' for r in type4),
            'road_rows':road_rows,'candidate_rows':candidate_count,'transitions':transitions,'closed_entries':entries,'ambiguous_transitions':ambiguous,
            'total_vehicle_km':sum(float(r['routeLength']) for r in trips.values())/1000,
            'driver_error_lines':driver_errors,'driver_stderr_sha256':sha(stderr) if stderr.exists() else None,
            'primary_scope':'in-domain facility admissions; boundary exits excluded from numerator',
            'validator_sha256':sha(Path(__file__)),'manifest_sha256':sha(run_dir/'manifest.json')}
    (run_dir/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--run-dir');x=a.parse_args()
    report=validate_run(Path(x.run_dir)) if x.run_dir else validate_inputs();print(json.dumps(report,ensure_ascii=False,indent=2));sys_exit=0 if report['status']=='PASS' else 1
    raise SystemExit(sys_exit)
