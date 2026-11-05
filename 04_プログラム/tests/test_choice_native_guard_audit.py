"""Artificial audit counterexamples; no native execution proof."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/joso-jdrt-runner/scripts'))
try:
    import choice_native_guard_audit as audit
except ImportError:
    audit=None

class AuditContracts(unittest.TestCase):
    def actor(self, x=0., speed=.4):
        return {'edge_id':'long','lane_id':'long_0','lane_position_m':x,'xy':[x,1.], 'speed_mps':speed}
    def frames(self):
        return [{'time_sec':.5,'actors':{'p3':self.actor()},'departed':['p3'],'arrived':[], 'teleports':[],'collisions':[]},
                {'time_sec':1.,'actors':{'p3':self.actor(.2)},'departed':[],'arrived':[], 'teleports':[],'collisions':[]}]
    def test_clock_mass_speed_and_nonfinite_fail_closed(self):
        self.assertIsNotNone(audit,'audit helper is unimplemented')
        self.assertEqual(audit.actor_accounting(self.frames(),{'p3':1.},.5)['steps'],2)
        for name,value in [('clock',2.),('mass',[]),('speed',1.01),('nan',float('nan'))]:
            rows=self.frames()
            if name=='clock':rows[1]['time_sec']=value
            elif name=='mass':rows[0]['departed']=value
            else:rows[1]['actors']['p3']['speed_mps']=value
            with self.subTest(name=name),self.assertRaises(ValueError):audit.actor_accounting(rows,{'p3':1.},.5)
    def test_one_ulp_same_call_jump_and_non_target_change_are_rejected(self):
        self.assertIsNotNone(audit,'audit helper is unimplemented')
        op={'person':'p3','time_sec':.5,'before':{'p3':self.actor(),'p4':self.actor(2.)},'after':{'p3':self.actor(),'p4':self.actor(2.)}}
        audit.position_receipts([op],exact_target=True)
        for person in ('p3','p4'):
            bad=deepcopy(op);bad['after'][person]['xy'][1]=math.nextafter(1.,math.inf)
            with self.subTest(person=person),self.assertRaises(ValueError):audit.position_receipts([bad],exact_target=True)
        internal=deepcopy(op);internal['after']['p3']['xy'][1]=2.
        audit.position_receipts([internal],exact_target=False)
    def test_first_nonzero_step_uses_requested_new_direction(self):
        self.assertIsNotNone(audit,'audit helper is unimplemented')
        op={'person':'p3','purpose':'new_route','time_sec':.5,'before':{'p3':self.actor()},'after':{'p3':self.actor()},'requested_arrival_pos_m':10.}
        self.assertEqual(audit.next_directions([op],self.frames()),{'p3':1})
        op['requested_arrival_pos_m']=-10.
        with self.assertRaises(ValueError):audit.next_directions([op],self.frames())
        with self.assertRaises(ValueError):audit.next_directions([op],self.frames()[:1])
    def test_operation_trace_link_requires_actual_time_person_and_single_new_row(self):
        self.assertIsNotNone(audit,'audit helper is unimplemented')
        op={'person':'p3','time_sec':.5,'trace_count_before':0,'trace_count_after':1}
        rows=[{'person':'p3','sim_step':'500'}]
        self.assertEqual(audit.link_operations([op],rows,1000.),[0])
        for key,value in [('person','p4'),('time_sec',1.),('trace_count_after',2)]:
            bad=deepcopy(op);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):audit.link_operations([bad],rows,1000.)

if __name__=='__main__':unittest.main()
