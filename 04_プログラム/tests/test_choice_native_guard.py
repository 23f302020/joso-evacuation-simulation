"""Collection contracts with artificial getters; no native physics claims."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import subprocess
import tempfile
import json
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_guard as guard


class People:
    def __init__(self):
        self.positions={'p3':(4.,1.),'p4':(8.,1.)};self.calls=[]
    def getIDList(self):return tuple(self.positions)
    def getRoadID(self,p):return 'long'
    def getLaneID(self,p):return 'long_0'
    def getLanePosition(self,p):return self.positions[p][0]
    def getPosition(self,p):return self.positions[p]
    def getSpeed(self,p):return .5
    def getRemainingStages(self,p):return 1
    def getStage(self,p,index=0):return SimpleNamespace(type=2,edges=('long',),departPos=0.,arrivalPos=100.,length=96.,departure=0.)
    def replaceStage(self,p,index,stage):self.calls.append(('replace',p,index,deepcopy(stage.__dict__)))
    def setSpeed(self,p,speed):self.calls.append(('speed',p,speed))


class GuardCollectionContracts(unittest.TestCase):
    def setUp(self):
        self.people=People();self.connection=SimpleNamespace(person=self.people)
    def test_snapshot_contains_native_stage_and_position_without_mutation(self):
        before=deepcopy(self.people.positions);row=guard.snapshot(self.connection,'p3')
        self.assertEqual(row['xy'],[4.,1.]);self.assertEqual(row['stage_edges'],['long'])
        self.assertEqual(row['stage_length_m'],96.);self.assertEqual(self.people.positions,before)
    def test_replacement_preserves_raw_before_after_and_non_target(self):
        row=guard.replacement(self.connection,'p3','new_route',['long'],4.,0.,.5)
        self.assertEqual(row['before']['p4'],row['after']['p4'])
        self.assertEqual(row['before']['p3']['xy'],row['after']['p3']['xy'])
        self.assertEqual(self.people.calls[0][0],'replace');self.assertEqual(self.people.calls[1],('speed','p3',.5))
        request=self.people.calls[0][3]
        self.assertEqual(request['departPos'],4.);self.assertEqual(request['arrivalPos'],0.)
    def test_movement_or_api_rejection_is_saved_without_position_correction(self):
        def moving(p,index,stage):self.people.positions[p]=(5.,1.)
        self.people.replaceStage=moving
        row=guard.replacement(self.connection,'p3','new_route',['long'],4.,0.,.5)
        self.assertNotEqual(row['before']['p3']['xy'],row['after']['p3']['xy'])
        def reject(p,index,stage):raise RuntimeError('native rejection')
        self.people.replaceStage=reject
        row=guard.replacement(self.connection,'p3','internal',['long'],5.,0.,.5)
        self.assertEqual(row['api_error']['message'],'native rejection')
        self.assertEqual(row['before']['p3']['xy'],row['after']['p3']['xy'])
    def test_geometry_uses_signed_normal_and_rejects_non_straight_lane(self):
        self.assertEqual(guard.signed_side((2.,3.),[(0.,0.),(10.,0.)]),3.)
        self.assertEqual(guard.signed_side((3.,2.),[(0.,0.),(0.,10.)]),-3.)
        for shape in ([(0.,0.)],[(0.,0.),(0.,0.)],[(0.,0.),(1.,1.),(2.,0.)]):
            with self.assertRaises(ValueError):guard.signed_side((2.,3.),shape)
    def test_command_has_explicit_binary_and_outputs_without_move_or_restart(self):
        args=guard.command('diagnostic.exe','net.xml','routes.xml',Path('out'),.5,30.,12345,42,['--some-native-option','true'])
        self.assertEqual(args[0],'diagnostic.exe')
        self.assertEqual(args[args.index('--remote-port')+1],'12345')
        self.assertEqual(args[args.index('--end')+1],'30.5')
        self.assertIn('--some-native-option',args)
        self.assertIn('--tripinfo-output.write-unfinished',args)

    def test_internal_requests_follow_actual_next_edge_and_keep_final_destination(self):
        self.people.getNextEdge=lambda p:'e1'
        row={'edge_id':':B_w1','stage_edges':['e0','e1','e2'],
             'lane_position_m':.25,'stage_arrival_pos_m':19.}
        requests=guard.replacement_requests(self.connection,'p3',row,
                    {'operation':'internal_replace','replacement_endpoint_m':19.})
        self.assertEqual(requests,[('old_remaining',[':B_w1','e1','e2'],.25,19.),
                                   ('new_route',[':B_w1','e1','e2'],.25,19.)])
        self.people.getNextEdge=lambda p:'missing'
        with self.assertRaises(ValueError):
            guard.replacement_requests(self.connection,'p3',row,{'operation':'internal_replace'})

    def test_reused_output_is_never_written_and_exclusive_writer_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'technical').mkdir();(root/'driver_logs').mkdir()
            old=root/'technical/old';old.mkdir();(old/'manifest.json').write_bytes(b'original')
            with self.assertRaises(ValueError):guard.reserve_output(root,'old')
            self.assertEqual((old/'manifest.json').read_bytes(),b'original')
            self.assertFalse((root/'driver_logs/native_guard.lock').exists())
            output,lock,claim=guard.reserve_output(root,'fresh')
            self.assertTrue(output.is_dir());self.assertEqual(lock.read_bytes(),claim)
            with self.assertRaises(FileExistsError):guard.reserve_output(root,'other')
            self.assertFalse((root/'technical/other').exists());self.assertEqual(lock.read_bytes(),claim)

    def test_endpoint_query_rejects_non_port_values_without_shell_interpolation(self):
        for port in (0,65536,True,'1; something'):
            with self.assertRaises(ValueError):guard.endpoint_owners(port)

    def fake_connection(self):
        simulation=SimpleNamespace(getTime=lambda:.5,getDepartedPersonIDList=lambda:[],
            getArrivedPersonIDList=lambda:[],getStartingTeleportIDList=lambda:[],
            getCollidingVehiclesIDList=lambda:[],getMinExpectedNumber=lambda:0)
        return SimpleNamespace(simulation=simulation,person=SimpleNamespace(getIDList=lambda:()),lane=SimpleNamespace(),
            startTracing=Mock(),simulationStep=Mock(),getVersion=lambda:(22,'artificial'),close=Mock())

    def run_fake(self, folder, traci, state):
        spec={'id':'observe','operation':'observe','sumo_options':[], 'step_sec':.5,'horizon_sec':1.}
        binary=Path(folder)/'artificial.exe';binary.write_bytes(b'artificial')
        return guard.run_case(traci,binary,Path('net.xml'),Path('routes.xml'),Path(folder)/'case',spec,
                              {'type3':1.,'type4':.6},42,state,Mock())

    def test_one_owned_child_is_closed_waited_and_raw_artifacts_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            connection=self.fake_connection();traci=SimpleNamespace(connect=Mock(return_value=connection),constants=SimpleNamespace(TRACI_VERSION=22))
            process=SimpleNamespace(pid=123,wait=Mock(return_value=0),poll=Mock(return_value=None))
            with patch.object(guard.subprocess,'Popen',return_value=process) as launch, \
                    patch.object(guard,'cim_utf8',return_value={'ProcessId':123}),patch.object(guard,'endpoint_owners',return_value=[123]):
                result=self.run_fake(folder,traci,{})
            self.assertEqual(launch.call_count,1);connection.close.assert_called_once_with(wait=False)
            process.wait.assert_called_once_with(timeout=15);self.assertEqual(result['exit_code'],0)
            for name in ('actors.jsonl','native.stdout.log','native.stderr.log','child.json'):
                self.assertTrue((Path(folder)/'case'/name).is_file())

    def test_initial_identity_failure_keeps_exact_spawned_pid_for_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            traci=SimpleNamespace(connect=Mock());state={}
            process=SimpleNamespace(pid=123,wait=Mock(),poll=Mock(return_value=None))
            with patch.object(guard.subprocess,'Popen',return_value=process), \
                    patch.object(guard,'cim_utf8',side_effect=RuntimeError('identity unavailable')):
                with self.assertRaises(RuntimeError):self.run_fake(folder,traci,state)
            self.assertEqual(state['active']['pid'],123)
            traci.connect.assert_not_called();process.wait.assert_not_called()

    def test_wrong_server_endpoint_stops_and_closes_only_its_owned_child(self):
        with tempfile.TemporaryDirectory() as folder:
            connection=self.fake_connection();traci=SimpleNamespace(connect=Mock(return_value=connection))
            process=SimpleNamespace(pid=123,wait=Mock(return_value=0),poll=Mock(return_value=None));state={}
            with patch.object(guard.subprocess,'Popen',return_value=process) as launch, \
                    patch.object(guard,'cim_utf8',return_value={'ProcessId':123}),patch.object(guard,'endpoint_owners',return_value=[999]):
                with self.assertRaises(ValueError):self.run_fake(folder,traci,state)
            self.assertEqual(launch.call_count,1);connection.close.assert_called_once_with(wait=False)
            self.assertEqual(state['active']['exit_code'],0)

    def test_pinned_transport_traces_bound_connection_domains_without_global_switch(self):
        script=r'''
import os,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
root=Path(sys.argv[1]);out=Path(sys.argv[2])
sys.path[:0]=[str(root/'.agents/skills/joso-jdrt-runner/scripts'),str(root/'04_プログラム')]
from scripts.jdrt_choice_toolchain import resolve_choice_toolchain,load_choice_traci,MANIFEST_ENV
os.environ[MANIFEST_ENV]=str(root/'04_プログラム/output/sumo/toolchains/native_lat_20261020a/toolchain.json')
traci=load_choice_traci(resolve_choice_toolchain(require_manifest=True))
import choice_native_guard as guard
with patch('traci.connection.socket.socket'):
    connection=guard.connect_native(traci,12345,SimpleNamespace(poll=lambda:None),out/'calls.py')
    connection.simulation._getUniversal=lambda *args:12.5
    try:
        assert connection.simulation.getTime()==12.5
        connection._traceFile.flush()
        assert 'traci.simulation.getTime()' in (out/'calls.py').read_text()
    finally:
        connection._traceFile.close()
        connection._socket.close()
print('PINNED_TRANSPORT_BOUND_DOMAIN_TRACE_PASS_NO_NATIVE_NO_SOCKET')
'''
        with tempfile.TemporaryDirectory() as folder:
            result=subprocess.run([sys.executable,'-B','-X','utf8','-c',script,str(ROOT),folder],
                                  capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PINNED_TRANSPORT_BOUND_DOMAIN_TRACE_PASS',result.stdout)

    def test_transient_windows_replace_retries_same_bytes_without_restarting_a_child(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'progress.json';target.write_bytes(b'old')
            replace=Path.replace;calls=[]
            def busy_once(source,destination):
                calls.append((source,destination,source.read_bytes()))
                if len(calls)==1:
                    error=PermissionError('sharing');error.winerror=5;raise error
                return replace(source,destination)
            with patch.object(Path,'replace',busy_once):
                guard.write_json(target,{'time_sec':1.})
            self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1])
            self.assertEqual(json.loads(target.read_bytes()),{'time_sec':1.})

    def test_persistent_replace_failure_preserves_original_and_prepared_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'progress.json';target.write_bytes(b'old')
            error=PermissionError('sharing');error.winerror=32
            with patch.object(Path,'replace',side_effect=error) as replace:
                with self.assertRaises(PermissionError):guard.write_json(target,{'time_sec':1.})
            self.assertLessEqual(replace.call_count,4)
            self.assertEqual(target.read_bytes(),b'old')
            self.assertEqual(json.loads(target.with_suffix('.tmp').read_bytes()),{'time_sec':1.})

    def test_display_coalescing_does_not_remove_any_step_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            connection=self.fake_connection()
            connection.simulation.getTime=Mock(side_effect=[.5,1.])
            connection.simulation.getMinExpectedNumber=lambda:1
            traci=SimpleNamespace(connect=Mock(return_value=connection),constants=SimpleNamespace(TRACI_VERSION=22))
            process=SimpleNamespace(pid=123,wait=Mock(return_value=0),poll=Mock(return_value=None))
            with patch.object(guard.subprocess,'Popen',return_value=process), \
                    patch.object(guard,'cim_utf8',return_value={'ProcessId':123}),patch.object(guard,'endpoint_owners',return_value=[123]):
                self.run_fake(folder,traci,{})
            rows=[json.loads(line) for line in (Path(folder)/'case/actors.jsonl').read_text().splitlines()]
            self.assertEqual([row['time_sec'] for row in rows],[.5,1.])


if __name__=='__main__':unittest.main()
