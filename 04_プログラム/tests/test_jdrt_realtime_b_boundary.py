"""Boundary, conservation and recording tests for the new realtime-B protocol."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock,call
import networkx as nx
from scripts.jdrt_realtime_b_boundary import realization,allocate_arrivals,rank_candidates,gate,route,remove_sumo_actor,apply_remaining_route,pedestrian_closure_action,vehicle_closure_action,closure_timing
from scripts.jdrt_realtime_b_boundary_inputs import ROOT
from scripts.jdrt_realtime_b_boundary_validate import closure_event_valid


class ProtocolTests(unittest.TestCase):
    def test_initial_positive_and_window_end_closure_clocks(self):
        for at in [0,300,21600]:
            event=closure_timing(at,.5);event['time_sec']=event['control_call_sec']
            self.assertTrue(closure_event_valid(event,at,.5))
            self.assertEqual(event['control_call_sec'],max(0,at-.5))
            self.assertEqual(event['observation_upper_sec'],at)
            self.assertLessEqual(event['control_lead_sec'],.5)

    def test_independent_timing_check_rejects_late_early_and_disguised_call(self):
        e=closure_timing(300,.5);e['time_sec']=e['control_call_sec']
        for field,value in [('time_sec',300),('control_call_sec',299),('observation_upper_sec',299.5),('phase','after_step')]:
            with self.subTest(field=field):
                altered={**e,field:value};self.assertFalse(closure_event_valid(altered,300,.5))
        with self.assertRaises(ValueError):closure_timing(1.25,.5)
        with self.assertRaises(ValueError):closure_timing(-1,.5)

    def test_positive_native_calls_do_not_coincide_with_dispatch_or_readiness(self):
        for scheduled in range(300,21601,300):
            call_sec=closure_timing(scheduled,.5)['control_call_sec']
            self.assertNotEqual(call_sec%1,0);self.assertNotEqual(call_sec%60,0)

    def test_vehicle_junction_closed_next_removed_using_actual_route_index(self):
        self.assertEqual(vehicle_closure_action(['a','b','c'],':j',0,{'b'}),('remove_junction','b'))
        self.assertEqual(vehicle_closure_action(['a','b','c'],':j',1,{'c'}),('remove_junction','c'))

    def test_vehicle_safe_next_defers_then_external_reroutes_and_past_is_ignored(self):
        self.assertEqual(vehicle_closure_action(['a','b','c'],':j',0,{'c'}),('defer','b'))
        self.assertEqual(vehicle_closure_action(['a','b','c'],'b',1,{'c'}),('reroute',''))
        self.assertEqual(vehicle_closure_action(['a','b','c'],'b',1,{'a'}),('clear',''))
        self.assertEqual(vehicle_closure_action(['a','b','c'],'c',2,{'c'}),('remove_current',''))

    def test_vehicle_missing_route_reference_is_not_clear(self):
        self.assertEqual(vehicle_closure_action(['a'],'',-1,{'a'}),('defer',''))
        with self.assertRaises(ValueError):vehicle_closure_action(['a','b'],':j',-1,{'b'})
        with self.assertRaises(ValueError):vehicle_closure_action(['a','b'],'b',0,{'b'})

    def test_junction_next_closed_is_removed_before_external_entry(self):
        self.assertEqual(pedestrian_closure_action(['a','b','c'],':junction','a',{'b'}),('remove_junction','b'))

    def test_junction_safe_next_defers_then_external_reroutes(self):
        self.assertEqual(pedestrian_closure_action(['a','b','c'],':junction','a',{'c'}),('defer','b'))
        self.assertEqual(pedestrian_closure_action(['a','b','c'],'b','a',{'c'}),('reroute',''))
        self.assertEqual(pedestrian_closure_action(['a','b','c'],'c','b',{'c'}),('remove_current',''))

    def test_past_closure_and_missing_route_reference_not_misreported_clear(self):
        self.assertEqual(pedestrian_closure_action(['a','b','c'],':junction','a',{'a'}),('clear',''))
        with self.assertRaises(ValueError):pedestrian_closure_action(['a','b','c'],':junction','unrecorded',{'c'})

    def test_remaining_route_id_preserves_vehicle_and_uses_no_history_prefix(self):
        connection=Mock();connection.vehicle.getRoadID.return_value='current';connection.vehicle.isStopped.return_value=False
        apply_remaining_route(connection,'v',['current','next'],'unique_id')
        self.assertEqual(connection.mock_calls,[call.vehicle.getRoadID('v'),call.vehicle.isStopped('v'),call.route.add('unique_id',['current','next']),call.vehicle.setRouteID('v','unique_id')])
        connection.vehicle.setRoute.assert_not_called()

    def test_parked_route_is_replaced_before_resume_hides_current_edge(self):
        connection=Mock();connection.vehicle.getRoadID.return_value='current';connection.vehicle.isStopped.return_value=True
        apply_remaining_route(connection,'v',['current','next'],'id')
        self.assertEqual(connection.mock_calls,[call.vehicle.getRoadID('v'),call.vehicle.isStopped('v'),call.route.add('id',['current','next']),call.vehicle.setRouteID('v','id'),call.vehicle.resume('v')])

    def test_remaining_route_rejects_wrong_origin_before_any_mutation(self):
        connection=Mock();connection.vehicle.getRoadID.return_value='current'
        with self.assertRaises(ValueError):apply_remaining_route(connection,'v',['elsewhere','next'],'id')
        connection.route.add.assert_not_called();connection.vehicle.setRouteID.assert_not_called()

    def test_removed_actor_subscription_is_cancelled_before_removal(self):
        for mode,domain in [('passenger','vehicle'),('pedestrian','person')]:
            connection=Mock();remove_sumo_actor(connection,'actor',mode)
            self.assertEqual(connection.mock_calls,[call.__getattr__(domain).unsubscribe('actor'),call.__getattr__(domain).remove('actor')])

    def test_strict_gate_boundary(self):
        self.assertFalse(gate(900,900));self.assertTrue(gate(899.5,900));self.assertFalse(gate(901,900))

    def test_shared_capacity_tie_and_exit_separate(self):
        terminals={'s':{'terminal_id':'s','kind':'facility','capacity':1},'x':{'terminal_id':'x','kind':'boundary_exit','capacity':''}}
        people={'b':{'terminal_id':'s','mode':'drt'},'a':{'terminal_id':'s','mode':'walk'},'c':{'terminal_id':'x','mode':'car'}}
        occupancy={'s':0};allocate_arrivals(['b','a','c'],people,terminals,occupancy,12)
        self.assertEqual(people['a']['status'],'admitted');self.assertEqual(people['b']['status'],'capacity_rejected')
        self.assertEqual(people['c']['status'],'boundary_exit');self.assertNotIn('admitted_sec',people['c']);self.assertEqual(occupancy['s'],1)

    def test_common_realization_group_time_and_nested_selection(self):
        people=[{'person_id':str(i),'person_type':'type4','vehicle_id':'','origin_id':'o','base_mode':'walk'} for i in range(5)]
        people.extend([{'person_id':'car_a','person_type':'type1','vehicle_id':'v','origin_id':'o','base_mode':'car'},
                       {'person_id':'car_b','person_type':'type2','vehicle_id':'v','origin_id':'o','base_mode':'car'}])
        params={'population':{'uptake':.5,'ready_interval_sec':[0,7200]}};origins={'o':{'terminal_id':'s'}}
        a=realization(people,origins,42,params);b=realization(list(reversed(people)),origins,42,params)
        self.assertEqual(a,b);self.assertEqual(sum(r['selected_jdrt'] for r in a),3)
        car=[r for r in a if r['vehicle_id']];self.assertEqual(car[0]['ready_sec'],car[1]['ready_sec'])
        params['population']['uptake']=1;all_selected=realization(people,origins,42,params)
        self.assertTrue({r['person_id'] for r in a if r['selected_jdrt']}<={r['person_id'] for r in all_selected if r['selected_jdrt']})

    def test_forecast_does_not_change_nonforecast_score(self):
        def choices():return [{'person_id':'a','vehicle_id':'v','waiting_sec':10,'pickup_sec':10,'vulnerability':0,'urgency':1,'reason':'eligible'},
                              {'person_id':'b','vehicle_id':'v','waiting_sec':10,'pickup_sec':10,'vulnerability':0,'urgency':0,'reason':'eligible'}]
        a=choices();a[0]['urgency']=0;a[1]['urgency']=100
        self.assertEqual(rank_candidates(a,False)['person_id'],'a');self.assertEqual(rank_candidates(a,True)['person_id'],'b')

    def test_closure_removes_path_without_removing_people(self):
        g=nx.DiGraph();g.add_edge('o','mid',length=1);g.add_edge('mid','s',length=1)
        self.assertEqual(route(g,'o','s'),['o','mid','s']);g.remove_node('mid');self.assertEqual(route(g,'o','s'),[])
        self.assertEqual(route(g,'missing','s'),[])


class RecordingTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'.agents/skills/joso-jdrt-runner/scripts/realtime_b_boundary_cell.py'
        spec=importlib.util.spec_from_file_location('rtb_cli_test',path);self.cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.cli)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir()
        self.paths=[self.root/'05_タスク管理/jdrt/record.md',self.root/'05_タスク管理/jdrt/JDRT-v2_完了後方針・タスク.md',self.root/'context.md',
                    self.root/'00_全体整理/決定ログ.md',self.root/'01_経過報告/経過報告2026年08月/経過報告20260826.md',self.root/'05_タスク管理/jdrt/ledger.jsonl']
        for p in self.paths[:-1]:p.parent.mkdir(parents=True,exist_ok=True);p.write_text('before\n<!-- AGENT_CURRENT_END -->\n',encoding='utf-8')
        self.validation={'status':'PASS','people':2,'type4_denominator':1,'type4_admitted':0,'type4_boundary_exit':1,'road_rows':2,'candidate_rows':0,'closed_entries':0,'ambiguous_transitions':0}
        self.manifest={'purpose':'core','scenario':'R0','seed':42,'_directory':str(self.run)}
        self.patches=[patch.object(self.cli,'ROOT',self.root),patch.object(self.cli,'LEDGER',self.paths[-1]),patch.object(self.cli,'RECORD',self.paths[0]),
                      patch.object(self.cli,'find',return_value=self.manifest),patch.object(self.cli,'validate_run',return_value=self.validation),patch.object(self.cli,'status',return_value={})]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_recorded_code_mismatch_blocks_new_comparison(self):
        current={'executor':'current_sha'}
        with patch.object(self.cli,'implementation',return_value=current),patch.object(self.cli,'ledger_ids',return_value={'fixture'}),patch.object(self.cli,'items',return_value=[{'run_id':'fixture','protocol':self.cli.P['protocol'],'implementation_sha256':current}]):
            self.cli.assert_common_implementation()
        with patch.object(self.cli,'implementation',return_value=current),patch.object(self.cli,'ledger_ids',return_value={'fixture'}),patch.object(self.cli,'items',return_value=[{'run_id':'fixture','protocol':self.cli.P['protocol'],'implementation_sha256':{'executor':'old_sha'}}]):
            with self.assertRaises(RuntimeError):self.cli.assert_common_implementation()
        with patch.object(self.cli,'implementation',return_value=current),patch.object(self.cli,'ledger_ids',return_value={'missing'}),patch.object(self.cli,'items',return_value=[]):
            with self.assertRaises(RuntimeError):self.cli.assert_common_implementation()

    def test_duplicate_and_foreign_protocol_ledgers_are_rejected(self):
        self.paths[-1].parent.mkdir(parents=True,exist_ok=True)
        for rows in [[{'run_id':'same','protocol':self.cli.P['protocol']}]*2,[{'run_id':'foreign','protocol':'realtime_b_v1'}]]:
            self.paths[-1].write_text('\n'.join(json.dumps(row) for row in rows)+'\n',encoding='utf-8')
            with self.assertRaises(RuntimeError):self.cli.ledger_ids()

    def test_record_idempotence_and_six_file_sync(self):
        self.assertEqual(self.cli.record('fixture')['status'],'RECORDED')
        before={p:p.read_bytes() for p in self.paths}
        self.assertEqual(self.cli.record('fixture')['status'],'ALREADY_RECORDED');self.assertEqual(before,{p:p.read_bytes() for p in self.paths})
        self.assertEqual(len(self.paths[-1].read_text().splitlines()),1)

    def test_partial_write_rolls_back_all_files(self):
        before={p:p.read_bytes() if p.exists() else None for p in self.paths};original=Path.write_text
        def injected(path,*args,**kwargs):
            if path==self.root/'context.md':raise OSError('fixture write failure')
            return original(path,*args,**kwargs)
        with patch.object(Path,'write_text',injected):
            with self.assertRaises(OSError):self.cli.record('fixture')
        self.assertEqual(before,{p:p.read_bytes() if p.exists() else None for p in self.paths})

    def test_validation_failure_never_records(self):
        with patch.object(self.cli,'validate_run',return_value={'status':'FAIL'}):
            with self.assertRaises(RuntimeError):self.cli.record('fixture')
        self.assertFalse(self.paths[-1].exists())


if __name__=='__main__':unittest.main()
