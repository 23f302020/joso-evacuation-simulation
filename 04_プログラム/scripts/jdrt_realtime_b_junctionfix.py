"""Realtime-B revision: vehicle and pedestrian closures persist across junction traversal."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import networkx as nx

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'04_プログラム'))
from scripts.jdrt.smoke import resolve_sumo_binary,load_traci
from scripts.jdrt.full_run import summarize_sumo_error_log
from scripts.jdrt_realtime_b_inputs import read_csv,write_csv,sha
PARAM=ROOT/'04_プログラム/config/jdrt_realtime_b_v1.json'
FINAL={'admitted','boundary_exit','capacity_rejected','no_origin_connection','no_route','walk_limit',
       'initial_or_current_closed','route_cut','stranded_drt','time_limit'}

def stamp():return datetime.now(timezone(timedelta(hours=9))).isoformat()

def atomic_json(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def load_inputs():
    p=json.loads(PARAM.read_text(encoding='utf-8'));directory=ROOT/p['workspace']/p['input_directory']
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['source_sha256'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Source SHA mismatch: '+name)
    for name,expected in manifest['artifacts'].items():
        if sha(directory/name)!=expected:raise ValueError('Input SHA mismatch: '+name)
    return p,directory,manifest

def hash_number(seed,key,role):
    return int.from_bytes(hashlib.sha256(f'{seed}|{role}|{key}'.encode()).digest(),'big')

def realization(people,origins,seed,parameters):
    selected=set()
    for typ in ['type3','type4']:
        candidates=sorted((p['person_id'] for p in people if p['person_type']==typ),key=lambda pid:(hash_number(seed,pid,'uptake'),pid))
        selected.update(candidates[:math.floor(len(candidates)*parameters['population']['uptake']+.5)])
    low,high=parameters['population']['ready_interval_sec']
    result=[]
    for person in sorted(people,key=lambda r:r['person_id']):
        key=person['vehicle_id'] or person['person_id']
        result.append({**person,'ready_sec':low+hash_number(seed,key,'ready')%(high-low+1),
                       'selected_jdrt':person['person_id'] in selected,
                       'terminal_id':origins[person['origin_id']]['terminal_id']})
    return result

def load_graphs(directory):
    raw=json.loads((directory/'graphs.json').read_text(encoding='utf-8'));graphs={}
    for mode,data in raw.items():
        g=nx.DiGraph() if data['directed'] else nx.Graph()
        g.add_nodes_from((n,a) for n,a in data['nodes'].items());g.add_edges_from((a,b,d) for a,b,d in data['edges']);graphs[mode]=g
    return graphs

def route(graph,start,end,weight='length'):
    try:return nx.shortest_path(graph,start,end,weight=weight)
    except (nx.NodeNotFound,nx.NetworkXNoPath):return []

def allocate_arrivals(arrivals,people,terminals,occupancy,now):
    """One shared capacity account across all modes; deterministic same-tick ties."""
    for pid in sorted(set(arrivals)):
        person=people[pid];terminal=terminals[person['terminal_id']]
        person['arrival_sec']=now
        if terminal['kind']=='boundary_exit':person['status']='boundary_exit'
        elif occupancy[terminal['terminal_id']]<int(terminal['capacity']):
            occupancy[terminal['terminal_id']]+=1;person['status']='admitted';person['admitted_sec']=now
        else:person['status']='capacity_rejected'

def rank_candidates(candidates,forecast_enabled,weights=None):
    weights=weights or {'waiting':1,'vulnerability':1,'pickup':1,'flood':1}
    feasible=[c for c in candidates if c['reason']=='eligible']
    max_wait=max((c['waiting_sec'] for c in feasible),default=0)
    max_pickup=max((c['pickup_sec'] for c in feasible),default=0)
    max_urgency=max((c['urgency'] for c in feasible),default=0)
    for c in feasible:
        c['score']=weights['waiting']*(c['waiting_sec']/max_wait if max_wait else 0)+weights['vulnerability']*c['vulnerability']-weights['pickup']*(c['pickup_sec']/max_pickup if max_pickup else 0)
        if forecast_enabled:c['score']+=weights['flood']*(c['urgency']/max_urgency if max_urgency else 0)
    return min(feasible,key=lambda c:(-c['score'],c['person_id'],c['vehicle_id']),default=None)

def gate(required,remaining):return required<remaining

def remove_sumo_actor(connection,actor,mode):
    domain=connection.person if mode=='pedestrian' else connection.vehicle
    domain.unsubscribe(actor)
    domain.remove(actor)

def apply_remaining_route(connection,actor,path,route_id):
    if not path or connection.vehicle.getRoadID(actor)!=path[0]:
        raise ValueError('Remaining route must begin at the current external edge')
    stopped=connection.vehicle.isStopped(actor)
    connection.route.add(route_id,path)
    connection.vehicle.setRouteID(actor,route_id)
    if stopped:connection.vehicle.resume(actor)

def pedestrian_closure_action(path,current,previous_external,closed):
    if not current:return 'defer',''
    internal=current.startswith(':')
    reference=previous_external or path[0] if internal else current
    index=path.index(reference)
    remaining=path[index+1:] if internal else path[index:]
    if not set(remaining)&closed:return 'clear',''
    if not internal:return ('remove_current' if current in closed else 'reroute'),''
    next_external=remaining[0]
    return ('remove_junction' if next_external in closed else 'defer'),next_external

def vehicle_closure_action(path,current,route_index,closed):
    if not current:return 'defer',''
    if not 0<=route_index<len(path):raise ValueError('Vehicle route index outside controlled path')
    internal=current.startswith(':')
    if not internal and path[route_index]!=current:raise ValueError('Vehicle route index and current edge disagree')
    remaining=path[route_index+1:] if internal else path[route_index:]
    if not set(remaining)&closed:return 'clear',''
    if not internal:return ('remove_current' if current in closed else 'reroute'),''
    next_external=remaining[0]
    return ('remove_junction' if next_external in closed else 'defer'),next_external

def run(scenario,seed,run_id,purpose='core',smoke_people=24,smoke_end=1800):
    parameters,directory,input_manifest=load_inputs()
    if scenario not in parameters['scenarios'] or seed not in parameters['seeds']:raise ValueError('Unregistered cell')
    workspace=ROOT/parameters['workspace'];run_dir=workspace/('runs' if purpose=='core' else 'smoke')/run_id
    run_dir.mkdir(parents=True,exist_ok=False)
    end=parameters['simulation']['duration_sec'] if purpose=='core' else smoke_end
    manifest={'run_id':run_id,'protocol':parameters['protocol'],'scenario':scenario,'seed':seed,'purpose':purpose,
              'status':'RUNNING','pid':os.getpid(),'started_at_jst':stamp(),'parameter_sha256':sha(PARAM),
              'input_manifest_sha256':sha(directory/'manifest.json'),'input_directory':directory.relative_to(ROOT).as_posix(),
              'implementation_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [Path(__file__),ROOT/'04_プログラム/scripts/jdrt_realtime_b_inputs.py']},
              'end_sec':end,'step_sec':parameters['simulation']['step_sec'],'snapshot_sec':parameters['simulation']['snapshot_sec']}
    atomic_json(run_dir/'manifest.json',manifest)
    connection=None;handles=[]
    try:
        origins={r['origin_id']:r for r in read_csv(directory/'origins.csv')}
        terminals={r['terminal_id']:r for r in read_csv(directory/'terminals.csv')}
        raw_people=read_csv(directory/'people.csv');realized=realization(raw_people,origins,seed,parameters)
        if purpose!='core':
            # Technical fixture only; never accepted into the research-cell ledger.
            viable=[r for r in realized if origins[r['origin_id']]['car_route']!='[]' and origins[r['origin_id']]['walk_route']!='[]'
                    and r['terminal_id'] and terminals[r['terminal_id']]['kind']=='facility' and float(origins[r['origin_id']]['walk_length_m'] or 1e9)<1000]
            viable.sort(key=lambda r:(float(origins[r['origin_id']]['walk_length_m']),r['person_id']))
            chosen=[r for r in viable if r['base_mode']=='car'][:smoke_people//2]
            for typ in ['type3','type4']:chosen.extend([r for r in viable if r['person_type']==typ][:smoke_people//4])
            realized=chosen
            for i,r in enumerate(realized):r['ready_sec']=i%10;r['selected_jdrt']=r['base_mode']=='walk' and i%2==0
        write_csv(run_dir/'common_realization.csv',realized)
        people={r['person_id']:{**r,'mode':'drt' if scenario!='R0' and r['selected_jdrt'] else r['base_mode'],
                 'status':'not_ready','depart_sec':'','pickup_sec':'','arrival_sec':'','admitted_sec':''} for r in realized}
        graphs=load_graphs(directory);original_nodes={m:set(g) for m,g in graphs.items()}
        hazard=read_csv(directory/'hazard.csv');true_times={(r['edge_id'],r['mode']):int(r['closure_sec']) for r in hazard if r['closure_sec']!=''}
        closure_events=defaultdict(lambda:defaultdict(set))
        for (edge,mode),sec in true_times.items():closure_events[sec][mode].add(edge)
        forecast={edge:sec+parameters['hazard']['forecast_error_sec'] for (edge,mode),sec in true_times.items() if mode=='passenger'} if scenario=='R2' else None
        private=defaultdict(list)
        for pid,p in people.items():
            if p['mode']=='car':private[p['vehicle_id']].append(pid)
        vehicles={name:{'kind':'car','members':members,'origin_id':people[members[0]]['origin_id'],
                        'terminal_id':people[members[0]]['terminal_id'],'ready_sec':people[members[0]]['ready_sec'],
                        'status':'not_ready','route':[],'distance_m':0,'empty_distance_m':0,'route_version':0} for name,members in private.items()}
        fleet_count=parameters['operation']['fleet_count'] if scenario!='R0' else 0
        for i in range(fleet_count):vehicles[f'b_drt_{i}']={'kind':'drt','members':[],'origin_id':'','terminal_id':'',
            'ready_sec':0,'status':'pending_idle','route':[input_manifest['depot_edge']],'distance_m':0,'empty_distance_m':0,'route_version':0,'active_person':''}
        sumo=resolve_sumo_binary();traci=load_traci(sumo);tc=traci.constants
        root=ET.Element('routes')
        ET.SubElement(root,'vType',id='car',vClass='passenger',length='4.5',minGap='2.5')
        ET.SubElement(root,'vType',id='drt',vClass='passenger',length='4.5',minGap='2.5',personCapacity=str(parameters['operation']['passenger_capacity']))
        for typ,speed in parameters['population']['walk_mps'].items():ET.SubElement(root,'vType',id='walk_'+typ,vClass='pedestrian',maxSpeed=str(speed))
        ET.ElementTree(root).write(run_dir/'types.rou.xml',encoding='utf-8',xml_declaration=True)
        command=[str(sumo),'--net-file',os.path.relpath(directory/'bounded.net.xml',run_dir),'--route-files','types.rou.xml',
                 '--step-length',str(manifest['step_sec']),'--seed',str(seed),'--begin','0','--end',str(end+1),
                 '--time-to-teleport','-1','--collision.action','teleport','--no-step-log','true','--duration-log.disable','true',
                 '--error-log','sumo_errors.log','--log','sumo.log','--tripinfo-output','tripinfo.xml','--tripinfo-output.write-unfinished','true']
        # SUMO's Windows file reader needs ASCII relative arguments.
        old_cwd=Path.cwd();os.chdir(run_dir)
        try:
            traci.start(command,label=run_id,doSwitch=False,verbose=False)
            connection=traci.getConnection(run_id)
        finally:os.chdir(old_cwd)
        t=connection
        net_root=ET.parse(directory/'bounded.net.xml').getroot();lane_info={}
        import sumolib
        pedestrian_net=sumolib.net.readNet(str(directory/'bounded.net.xml'),withInternal=True)
        walk_topology=nx.Graph()
        for edge in pedestrian_net.getEdges(withInternal=True):
            name=edge.getID()
            if (name in original_nodes['pedestrian'] or name.startswith(':')) and edge.allows('pedestrian'):
                walk_topology.add_node(name,length=edge.getLength())
        for edge in pedestrian_net.getEdges(withInternal=True):
            if edge.getID() not in walk_topology:continue
            for other,connections in edge.getAllowedOutgoing('pedestrian').items():
                if other.getID() not in walk_topology:continue
                via,_=pedestrian_net.getInternalPath(connections)
                chain=[edge]+(via or [])+[other]
                if not all(e.getID() in walk_topology for e in chain):continue
                for a,b in zip(chain,chain[1:]):
                    walk_topology.add_edge(a.getID(),b.getID(),length=(a.getLength()+b.getLength())/2)
        for edge in net_root.findall('edge'):
            if edge.attrib['id'].startswith(':'):continue
            for lane in edge.findall('lane'):lane_info[lane.attrib['id']]={'edge':edge.attrib['id'],'length':float(lane.attrib['length'])}
        edge_length={n:float(a['length']) for n,a in graphs['passenger'].nodes(data=True)}
        lanes_by_edge=defaultdict(list)
        for lane,a in lane_info.items():lanes_by_edge[a['edge']].append(lane)
        for edge in lanes_by_edge:
            if edge not in original_nodes['passenger'] and edge not in original_nodes['pedestrian']:
                for lane in lanes_by_edge[edge]:t.lane.setDisallowed(lane,sorted(set(t.lane.getDisallowed(lane))|{'passenger'}))
        observed_vehicle_vars=[tc.VAR_ROAD_ID,tc.VAR_SPEED,tc.VAR_DISTANCE,tc.VAR_ROUTE_INDEX]
        observed_person_vars=[tc.VAR_ROAD_ID,tc.VAR_SPEED]
        for vid,v in vehicles.items():
            if v['kind']!='drt':continue
            depot=input_manifest['depot_edge'];t.route.add('route_'+vid,[depot]);t.vehicle.add(vid,'route_'+vid,typeID='drt',depart='now')
            lane=next(i for i in lanes_by_edge[depot] if 'passenger' in t.lane.getAllowed(i) or not t.lane.getAllowed(i))
            t.vehicle.setStop(vid,depot,pos=max(1,lane_info[lane]['length']-1),laneIndex=int(lane.rsplit('_',1)[1]),duration=end+1,flags=tc.STOP_PARKING)
            t.vehicle.subscribe(vid,observed_vehicle_vars)
        def gz_writer(filename,fields):
            h=gzip.open(run_dir/filename,'wt',encoding='utf-8',newline='',compresslevel=1);handles.append(h)
            w=csv.DictWriter(h,fieldnames=fields);w.writeheader();return w
        road_fields=['time_sec','edge_id','mode','count','mean_speed_mps','halting_count','closed','observation_status']
        road_writer=gz_writer('edge_observations.csv.gz',road_fields)
        transition_writer=gz_writer('transitions.csv.gz',['time_lower_sec','time_upper_sec','actor_id','mode','from_edge','to_edge','kind','closure_sec','ambiguous'])
        candidate_fields=['cycle','stage','time_sec','vehicle_id','person_id','pickup_sec','delivery_sec','waiting_sec','vulnerability',
                          'forecast_remaining_sec','required_sec','gate_applicable','gate_pass','urgency','score','decision','reason']
        candidate_writer=gz_writer('candidates.csv.gz',candidate_fields)
        event_handle=(run_dir/'events.jsonl').open('w',encoding='utf-8');handles.append(event_handle)
        def event(now,kind,**data):event_handle.write(json.dumps({'time_sec':now,'event':kind,**data},ensure_ascii=False)+'\n')
        closed={m:set() for m in graphs};applied=set();occupancy=Counter();last={};walking_routes={};waiting=set();route_cache={};route_counter=0
        counts={'steps':0,'controller_ticks':0,'snapshots':0,'teleports':0,'collisions':0,'transition_rows':0,'closed_entry_rows':0,'ambiguous_transitions':0,'candidate_rows':0,'missing_vehicle_subscriptions':0,'missing_person_subscriptions':0}
        wall_start=time.monotonic();latest_v={};latest_p={};pending_arrivals=[];cycle=0
        def destination(pid):return terminals[people[pid]['terminal_id']]['edge_id']
        def cached_route(mode,start,target):
            key=(mode,start,target,len(closed[mode]))
            if key not in route_cache:route_cache[key]=route(graphs[mode],start,target)
            return route_cache[key]
        def walking_path(start,target,position=0):
            try:
                path=nx.shortest_path(walk_topology,start,target,weight='length')
                names=[n for n in path if not n.startswith(':')]
                return names,max(0,sum(walk_topology.nodes[n]['length'] for n in path)-position)
            except (nx.NetworkXNoPath,nx.NodeNotFound):return [],math.inf
        def remove_actor(actor,mode,status):
            event(float(t.simulation.getTime()),'actor_removed',actor_id=actor,mode=mode,reason=status)
            remove_sumo_actor(t,actor,mode)
            if mode=='pedestrian':
                people[actor]['status']=status;walking_routes.pop(actor,None)
            else:
                v=vehicles[actor]
                for pid in v['members']:people[pid]['status']=status
                if v.get('active_person'):people[v['active_person']]['status']='stranded_drt';waiting.discard(v['active_person'])
                v['status']='stranded';v['members']=[]
            last.pop(actor,None)
        def set_bus_route(vid,path,target,now):
            if not path:return False
            apply_remaining_route(t,vid,path,'remaining_'+vid+'_'+str(vehicles[vid]['route_version']+1))
            lane=next(i for i in lanes_by_edge[target] if 'passenger' in t.lane.getAllowed(i) or not t.lane.getAllowed(i))
            t.vehicle.setStop(vid,target,pos=max(1,lane_info[lane]['length']-1),laneIndex=int(lane.rsplit('_',1)[1]),duration=end+1,flags=tc.STOP_PARKING)
            v=vehicles[vid];v['route']=path;v['route_version']+=1;last.pop(vid,None)
            event(now,'drt_route',vehicle_id=vid,target=target,route=path)
            return True
        def observe_transition(actor,mode,edge,new_time,source_path):
            prior=last.get(actor)
            if prior and prior[0]!=edge:
                try:
                    lo=source_path.index(prior[0]);hi=source_path.index(edge);entered=source_path[lo+1:hi+1] if hi>lo else [edge];ambiguous=hi<=lo
                except ValueError:entered=[edge];ambiguous=True
                for target in entered:
                    sec=true_times.get((target,mode));violation=sec is not None and new_time>=sec
                    transition_writer.writerow({'time_lower_sec':prior[1],'time_upper_sec':new_time,'actor_id':actor,'mode':mode,
                        'from_edge':prior[0],'to_edge':target,'kind':'closed_entry' if violation else 'transition','closure_sec':sec if sec is not None else '', 'ambiguous':ambiguous})
                    counts['transition_rows']+=1;counts['closed_entry_rows']+=int(violation);counts['ambiguous_transitions']+=int(ambiguous)
            last[actor]=(edge,new_time)
        while True:
            now=float(t.simulation.getTime())
            if now%parameters['simulation']['controller_sec']==0:counts['controller_ticks']+=1
            for pid in t.simulation.getArrivedPersonIDList():
                if pid in people and people[pid]['status'] not in FINAL:
                    path=walking_routes.get(pid,[])
                    if path:observe_transition(pid,'pedestrian',path[-1],now,path)
                    pending_arrivals.append(pid);walking_routes.pop(pid,None);last.pop(pid,None)
            for vid in t.simulation.getArrivedIDList():
                if vid in vehicles:
                    v=vehicles[vid]
                    if v['kind']=='drt' and v['status']!='stranded':raise RuntimeError('DRT vehicle left without controlled alighting: '+vid)
                    if v['kind']=='car' and v['status'] not in ['stranded','arrived']:
                        if v['route']:observe_transition(vid,'passenger',v['route'][-1],now,v['route'])
                        pending_arrivals.extend(v['members']);v['status']='arrived';last.pop(vid,None)
            due=[sec for sec in sorted(closure_events) if sec<=now and sec not in applied]
            if due:
                for sec in due:
                    for mode,names in closure_events[sec].items():
                        closed[mode].update(names);graphs[mode].remove_nodes_from(names)
                        for name in sorted(names):
                            if mode=='passenger':
                                for lane in lanes_by_edge[name]:t.lane.setDisallowed(lane,sorted(set(t.lane.getDisallowed(lane))|{mode}))
                            else:
                                if name in walk_topology:walk_topology.remove_node(name)
                            event(now,'closure_applied',edge_id=name,mode=mode,scheduled_sec=sec,method='lane_permission' if mode=='passenger' else 'controller_route_and_removal')
                    applied.add(sec)
                route_cache.clear()
            for vid,v in vehicles.items():
                if v['status'] in ['not_ready','arrived','stranded']:continue
                observed=latest_v.get(vid,{})
                current=observed.get(tc.VAR_ROAD_ID,'')
                action,next_external=vehicle_closure_action(v['route'],current,int(observed.get(tc.VAR_ROUTE_INDEX,-1)),closed['passenger'])
                if action in ['clear','defer']:continue
                if action in ['remove_current','remove_junction']:
                    event(now,'vehicle_closure_control',vehicle_id=vid,current_edge=current,next_external=next_external,action=action)
                    remove_actor(vid,'passenger','initial_or_current_closed' if action=='remove_current' else 'route_cut');continue
                target=v['route'][-1]
                replacement=cached_route('passenger',current,target)
                if not replacement:remove_actor(vid,'passenger','route_cut')
                elif v['kind']=='drt':set_bus_route(vid,replacement,target,now)
                else:apply_remaining_route(t,vid,replacement,'remaining_'+vid+'_'+str(v['route_version']+1));v['route']=replacement;v['route_version']+=1;last.pop(vid,None)
            for pid,path in list(walking_routes.items()):
                current=latest_p.get(pid,{}).get(tc.VAR_ROAD_ID,'')
                action,next_external=pedestrian_closure_action(path,current,last.get(pid,('',0))[0],closed['pedestrian'])
                if action=='clear' or action=='defer':continue
                if action in ['remove_current','remove_junction']:
                    event(now,'walk_closure_control',person_id=pid,current_edge=current,next_external=next_external,action=action)
                    remove_actor(pid,'pedestrian','initial_or_current_closed' if action=='remove_current' else 'route_cut');continue
                replacement,distance=walking_path(current,destination(pid),t.person.getLanePosition(pid))
                if not replacement:remove_actor(pid,'pedestrian','route_cut')
                else:
                    stage=t.person.getStage(pid);stage.edges=replacement
                    position=t.person.getLanePosition(pid)
                    stage.departPos=max(0,min(position,pedestrian_net.getEdge(current).getLength()))
                    t.person.replaceStage(pid,0,stage);walking_routes[pid]=replacement;last.pop(pid,None)
                    event(now,'walk_reroute',person_id=pid,edge_id=current,position_before=position,depart_pos=stage.departPos,route=replacement)
            # Release each exogenous unit once. Selected people remain in the common denominator.
            for vid,v in vehicles.items():
                if v['kind']!='car' or v['status']!='not_ready' or v['ready_sec']>now:continue
                origin=origins[v['origin_id']];start=origin['edge_id']
                path=cached_route('passenger',start,terminals[v['terminal_id']]['edge_id']) if start and v['terminal_id'] else []
                if not path:
                    reason='no_origin_connection' if not start else 'initial_or_current_closed' if start in closed['passenger'] else 'no_route'
                    for pid in v['members']:people[pid]['status']=reason
                    v['status']='stranded';continue
                route_counter+=1;rid='private_'+str(route_counter);t.route.add(rid,path);t.vehicle.add(vid,rid,typeID='car',depart='now',departLane='best')
                t.vehicle.subscribe(vid,observed_vehicle_vars);v['route']=path;v['status']='pending'
                event(now,'private_departure_requested',vehicle_id=vid,members=v['members'],route=path)
                for pid in v['members']:people[pid]['status']='travelling';people[pid]['depart_sec']=now
            for pid,p in people.items():
                if p['mode']=='car' or p['status']!='not_ready' or p['ready_sec']>now:continue
                origin=origins[p['origin_id']];start=origin['edge_id']
                if not start or not p['terminal_id']:p['status']='no_origin_connection' if not start else 'no_route';continue
                mode='passenger' if p['mode']=='drt' else 'pedestrian'
                path=cached_route(mode,start,destination(pid))
                if not path:p['status']='initial_or_current_closed' if start in closed[mode] else 'no_route';continue
                if p['mode']=='drt':p['status']='waiting';waiting.add(pid);continue
                walk,distance=walking_path(start,destination(pid))
                if not walk:p['status']='no_route';continue
                if distance>parameters['population']['walk_limit_m']:p['status']='walk_limit';continue
                t.person.add(pid,start,pos=0,typeID='walk_'+p['person_type'])
                t.person.appendWalkingStage(pid,walk,arrivalPos=-1,speed=parameters['population']['walk_mps'][p['person_type']]);t.person.subscribe(pid,observed_person_vars)
                walking_routes[pid]=walk;p['status']='travelling';p['depart_sec']=now
                event(now,'walk_departure',person_id=pid,route=walking_routes[pid])
            active_ids=set(t.vehicle.getIDList())
            for vid,v in vehicles.items():
                if v['kind']!='drt' or vid not in active_ids or v['status']=='stranded':continue
                if now%parameters['simulation']['controller_sec']!=0:continue
                current=t.vehicle.getRoadID(vid)
                stopped=t.vehicle.isStopped(vid)
                if v['status']=='pending_idle' and stopped:v['status']='idle'
                elif v['status'] in ['pickup','delivery'] and stopped and current==v['route'][-1]:
                    v['status']='boarding' if v['status']=='pickup' else 'alighting';v['until_sec']=now+parameters['operation']['boarding_sec' if v['status']=='boarding' else 'alighting_sec']
                    event(now,v['status']+'_started',vehicle_id=vid,person_id=v['active_person'])
                elif v['status']=='boarding' and now>=v['until_sec']:
                    pid=v['active_person'];p=people[pid];path=cached_route('passenger',current,destination(pid))
                    if not path:remove_actor(vid,'passenger','stranded_drt');continue
                    p['status']='onboard';p['pickup_sec']=now;v['members']=[pid]
                    v['maximum_onboard']=max(v.get('maximum_onboard',0),len(v['members']))
                    event(now,'drt_boarded',vehicle_id=vid,person_id=pid,onboard_count=len(v['members']))
                    set_bus_route(vid,path,destination(pid),now);v['status']='delivery'
                elif v['status']=='alighting' and now>=v['until_sec']:
                    event(now,'drt_alighted',vehicle_id=vid,person_id=v['active_person'],onboard_count=0)
                    pending_arrivals.append(v['active_person']);v['members']=[];v['active_person']='';v['status']='idle'
            if pending_arrivals:
                allocate_arrivals(pending_arrivals,people,terminals,occupancy,now)
                for pid in sorted(set(pending_arrivals)):event(now,'person_terminal',person_id=pid,status=people[pid]['status'],terminal_id=people[pid]['terminal_id'])
                pending_arrivals=[]
            if scenario!='R0' and now%parameters['simulation']['dispatch_sec']==0:
                cycle+=1;free=sorted(v for v in vehicles if vehicles[v]['kind']=='drt' and vehicles[v]['status']=='idle');stage=0
                while free and waiting:
                    stage+=1;candidates=[]
                    for vid in free:
                        current=t.vehicle.getRoadID(vid)
                        if current not in graphs['passenger']:continue
                        # Current travel estimates use observed speeds, never future closures.
                        distances,paths=nx.single_source_dijkstra(graphs['passenger'],current,weight='travel_sec')
                        for pid in sorted(waiting):
                            p=people[pid];origin=origins[p['origin_id']]['edge_id'];pickup_path=paths.get(origin,[])
                            delivery=cached_route('passenger',origin,destination(pid))
                            pickup=distances.get(origin,math.inf);delivery_eta=sum(graphs['passenger'].nodes[n]['free_sec'] for n in delivery) if delivery else math.inf
                            remaining=min((forecast.get(n,math.inf)-now for n in pickup_path+delivery),default=math.inf) if forecast is not None else math.inf
                            required=pickup+parameters['operation']['boarding_sec']+delivery_eta+parameters['operation']['margin_sec']
                            reason='no_pickup_route' if not pickup_path else 'no_delivery_route' if not delivery else 'forecast_gate' if forecast is not None and not gate(required,remaining) else 'eligible'
                            c={'cycle':cycle,'stage':stage,'time_sec':now,'vehicle_id':vid,'person_id':pid,
                               'pickup_sec':pickup,'delivery_sec':delivery_eta,'waiting_sec':now-p['ready_sec'],'vulnerability':int(p['person_type']=='type4'),
                               'forecast_remaining_sec':remaining,'required_sec':required,'gate_applicable':forecast is not None and math.isfinite(remaining),
                               'gate_pass':gate(required,remaining) if forecast is not None else '',
                               'urgency':1/max(remaining,1) if math.isfinite(remaining) else 0,'score':'','decision':'not_selected','reason':reason,
                               '_pickup_path':pickup_path}
                            candidates.append(c)
                    chosen=rank_candidates(candidates,scenario=='R2',parameters['dispatch_weights'])
                    if chosen:chosen['decision']='selected'
                    for c in candidates:
                        candidate_writer.writerow({k:('' if isinstance(v,float) and not math.isfinite(v) else v) for k,v in c.items() if not k.startswith('_')});counts['candidate_rows']+=1
                    if chosen is None:break
                    vid=chosen['vehicle_id'];pid=chosen['person_id'];p=people[pid]
                    set_bus_route(vid,chosen['_pickup_path'],origins[p['origin_id']]['edge_id'],now)
                    vehicles[vid]['status']='pickup';vehicles[vid]['active_person']=pid;people[pid]['status']='assigned';waiting.remove(pid);free.remove(vid)
                    event(now,'drt_assigned',vehicle_id=vid,person_id=pid)
            if now%manifest['snapshot_sec']==0:
                by_group=defaultdict(list)
                for vid,data in latest_v.items():
                    if vid not in vehicles or vehicles[vid]['status'] in ['stranded','arrived']:continue
                    edge=data.get(tc.VAR_ROAD_ID,'')
                    if edge in original_nodes['passenger']:by_group[edge,vehicles[vid]['kind']].append(float(data[tc.VAR_SPEED]))
                for pid,data in latest_p.items():
                    edge=data.get(tc.VAR_ROAD_ID,'')
                    if pid in walking_routes and edge in original_nodes['pedestrian']:by_group[edge,'walk'].append(float(data[tc.VAR_SPEED]))
                for mode,physical in [('car','passenger'),('drt','passenger'),('walk','pedestrian')]:
                    for edge in sorted(original_nodes[physical]):
                        speeds=by_group.get((edge,mode),[])
                        road_writer.writerow({'time_sec':now,'edge_id':edge,'mode':mode,'count':len(speeds),
                            'mean_speed_mps':sum(speeds)/len(speeds) if speeds else '',
                            'halting_count':sum(s<parameters['simulation']['stop_speed_mps'] for s in speeds),
                            'closed':edge in closed[physical],'observation_status':'observed'})
                counts['snapshots']+=1
                progress={'at_jst':stamp(),'run_id':run_id,'time_sec':now,'end_sec':end,'wall_sec':time.monotonic()-wall_start,
                          'people_states':dict(Counter(p['status'] for p in people.values())), 'active_vehicles':len(active_ids),'counts':counts.copy()}
                atomic_json(run_dir/'progress.json',progress);event_handle.flush()
                # Congestion weights refreshed from the observed snapshot.
                for a,b,d in graphs['passenger'].edges(data=True):
                    speeds=by_group.get((b,'car'),[])+by_group.get((b,'drt'),[])
                    d['travel_sec']=graphs['passenger'].nodes[b]['length']/max(sum(speeds)/len(speeds),.1) if speeds else graphs['passenger'].nodes[b]['free_sec']
            if now>=end:break
            t.simulationStep();new_time=float(t.simulation.getTime());counts['steps']+=1
            counts['teleports']+=len(t.simulation.getStartingTeleportIDList());counts['collisions']+=len(t.simulation.getCollidingVehiclesIDList())
            latest_v=t.vehicle.getAllSubscriptionResults();latest_p=t.person.getAllSubscriptionResults()
            counts['missing_vehicle_subscriptions']+=len(set(t.vehicle.getIDList())-set(latest_v))
            counts['missing_person_subscriptions']+=len(set(t.person.getIDList())-set(latest_p))
            for mode,observed in [('passenger',latest_v),('pedestrian',latest_p)]:
                for actor,data in observed.items():
                    edge=data.get(tc.VAR_ROAD_ID,'')
                    if mode=='passenger' and actor in vehicles:
                        v=vehicles[actor];distance=float(data.get(tc.VAR_DISTANCE,0));increment=max(0,distance-v['distance_m'])
                        if not v['members']:v['empty_distance_m']+=increment
                        v['distance_m']=max(v['distance_m'],distance)
                        if v['status']=='pending':v['status']='travelling'
                    if not edge or edge.startswith(':'):continue
                    source_path=vehicles[actor]['route'] if mode=='passenger' else walking_routes.get(actor,[])
                    observe_transition(actor,mode,edge,new_time,source_path)
        for p in people.values():
            if p['status'] not in FINAL:p['status']='time_limit'
        for h in handles:h.close()
        handles=[];t.close();connection=None
        for trip in ET.parse(run_dir/'tripinfo.xml').getroot().findall('tripinfo'):
            if trip.attrib['id'] in vehicles:vehicles[trip.attrib['id']]['tripinfo_distance_m']=float(trip.attrib['routeLength'])
        fields=list(next(iter(people.values())))
        write_csv(run_dir/'person_results.csv',list(people.values()),fields)
        write_csv(run_dir/'vehicle_results.csv',[{'vehicle_id':vid,'kind':v['kind'],'status':v['status'],'distance_m':v.get('tripinfo_distance_m',''),
                  'observed_distance_m':v['distance_m'],'observed_empty_distance_m':v['empty_distance_m'],
                  'passenger_capacity':parameters['operation']['passenger_capacity'] if v['kind']=='drt' else '',
                  'maximum_onboard':v.get('maximum_onboard',0)} for vid,v in sorted(vehicles.items())])
        request_rows=[{'person_id':p['person_id'],'status':p['status'],'request_sec':p['ready_sec'],'pickup_sec':p['pickup_sec'],'terminal_id':p['terminal_id'],'arrival_sec':p['arrival_sec']} for p in people.values() if p['mode']=='drt']
        write_csv(run_dir/'request_results.csv',request_rows,['person_id','status','request_sec','pickup_sec','terminal_id','arrival_sec'])
        write_csv(run_dir/'facility_results.csv',[{'terminal_id':r['terminal_id'],'capacity':r['capacity'],'admitted':occupancy[r['terminal_id']]} for r in terminals.values() if r['kind']=='facility'])
        errors=summarize_sumo_error_log(run_dir/'sumo_errors.log')
        counts['closures_applied']=sum(len(names) for sec in applied for names in closure_events[sec].values())
        summary={'people':len(people),'states':dict(Counter(p['status'] for p in people.values())),
                 'type_counts':dict(Counter(p['person_type'] for p in people.values())), 'counts':counts,'sumo_errors':errors,'fleet_count':fleet_count}
        manifest.update(status='COMPLETED',finished_at_jst=stamp(),summary=summary,
                        output_sha256={p.name:sha(p) for p in run_dir.iterdir() if p.is_file() and p.name not in ['manifest.json']})
        atomic_json(run_dir/'manifest.json',manifest)
        return manifest
    except BaseException as error:
        if connection is not None:
            try:connection.close()
            except Exception:pass
        for handle in handles:
            try:handle.close()
            except Exception:pass
        (run_dir/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
        manifest.update(status='FAILED',finished_at_jst=stamp(),error_type=type(error).__name__,error=str(error))
        atomic_json(run_dir/'manifest.json',manifest)
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',required=True);parser.add_argument('--seed',type=int,required=True);parser.add_argument('--run-id',required=True)
    parser.add_argument('--purpose',choices=['core','smoke'],default='core');parser.add_argument('--smoke-end',type=int,default=1800)
    args=parser.parse_args();print(json.dumps(run(args.scenario,args.seed,args.run_id,args.purpose,smoke_end=args.smoke_end),ensure_ascii=False,indent=2))
