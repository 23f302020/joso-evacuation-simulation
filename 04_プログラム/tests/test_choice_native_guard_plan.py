"""Synthetic plan contracts do not demonstrate any native branch."""
from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/joso-jdrt-runner/scripts'))
import choice_native_guard_plan as plan


class NativeGuardPlanContracts(unittest.TestCase):
    def net(self, length=100.):
        return (f'<net><edge id="long" from="L0" to="L1"><lane id="long_0" allow="pedestrian" length="{length}"/></edge>'
                '<edge id="e0" from="A" to="B"><lane id="e0_0" allow="pedestrian" length="50"/></edge>'
                '<edge id="e1" from="B" to="C"><lane id="e1_0" allow="pedestrian" length="50"/></edge>'
                '<edge id="e2" from="C" to="F"><lane id="e2_0" allow="pedestrian" length="20"/></edge></net>').encode()

    def test_internal_route_arrival_uses_its_own_final_edge_length(self):
        cases={c['id']:c for c in plan.build(self.net(240.),{'type3':1.,'type4':.6},.5)}
        for walk in ET.fromstring(cases['internal_walk']['routes_xml']).findall('person/walk'):
            self.assertEqual(walk.get('edges'),'e0 e1 e2')
            self.assertEqual(float(walk.get('arrivalPos')),20.)
        self.assertEqual(cases['internal_walk']['replacement_endpoint_m'],20.)

    def test_all_contract_groups_are_present_and_technical_only(self):
        cases=plan.build(self.net(),{'type3':1.,'type4':.6},.5)
        self.assertEqual(len({c['group'] for c in cases}),13)
        self.assertEqual(len({c['id'] for c in cases}),len(cases))
        for c in cases:
            self.assertIs(c['research_adoption_permitted'],False)
            self.assertEqual(c['status'],'PREPARED_NOT_EXECUTED')
            ET.fromstring(c['routes_xml'])
        self.assertEqual({c['operation_order'] for c in cases if c['group']=='multiple_people_order'},
                         {('p3','p4'),('p4','p3')})

    def test_reverse_routes_use_native_endpoints_and_the_original_speeds(self):
        cases={c['id']:c for c in plan.build(self.net(240.),{'type3':1.2,'type4':.4},.25)}
        reverse=ET.fromstring(cases['reverse_forward']['routes_xml'])
        self.assertEqual({w.get('arrivalPos') for w in reverse.findall('person/walk')},{'0.0'})
        types={v.get('id'):float(v.get('maxSpeed')) for v in reverse.findall('vType')}
        self.assertEqual(types,{'type3':1.2,'type4':.4})
        self.assertEqual(cases['forward_reverse']['replacement_endpoint_m'],0.)
        self.assertEqual(cases['reverse_forward']['replacement_endpoint_m'],240.)
        for person in reverse.findall('person'):
            self.assertTrue(0<float(person.get('departPos'))<240)

    def test_explicit_random_legacy_have_real_native_input_paths(self):
        cases={c['id']:c for c in plan.build(self.net(),{'type3':1.,'type4':.6},.5)}
        self.assertEqual(ET.fromstring(cases['random_lateral']['routes_xml']).find('person/walk').get('departPosLat'),'random')
        self.assertIsNotNone(ET.fromstring(cases['explicit_lateral']['routes_xml']).find('person/walk').get('departPosLat'))
        self.assertEqual(cases['legacy']['sumo_options'],['--pedestrian.striping.legacy-departposlat','true'])
        for c in cases.values():
            self.assertNotIn('moveTo',c['routes_xml'])

    def test_natural_stage_variants_preserve_legal_order_and_no_forced_replacement(self):
        cases=plan.build(self.net(),{'type3':1.,'type4':.6},.5)
        kinds={c['id']:[x.tag for x in ET.fromstring(c['routes_xml']).find('person')] for c in cases if c['group'] in ('natural_walk_walk','natural_walk_wait_walk')}
        self.assertEqual(kinds['natural_same_edge'],['walk','walk'])
        self.assertEqual(kinds['natural_different_edge'],['walk','walk'])
        self.assertEqual(kinds['natural_wait'],['walk','stop','walk'])
        self.assertTrue(all(c['operation']=='observe' for c in cases if c['id'] in kinds))

    def test_invalid_geometry_or_clock_is_not_silently_adjusted(self):
        for net,speeds,step in [(self.net(1),{'type3':1.,'type4':.6},.5),
                                (self.net(),{'type3':1.,'type4':1.},.5),
                                (self.net(),{'type3':1.,'type4':.6},0),
                                (self.net(),{'type3':float('nan'),'type4':.6},.5)]:
            with self.subTest(step=step),self.assertRaises(ValueError):plan.build(net,speeds,step)

    def test_native_enum_and_double_sentinels_are_source_derived(self):
        model=b'const double MSPModel::UNSPECIFIED_POS_LAT(std::numeric_limits<double>::max());\nconst double MSPModel::RANDOM_POS_LAT(-std::numeric_limits<double>::max());\n'
        stage=b'enum class MSStageType { WAITING = 1, WALKING = 7, DRIVING = 3 };'
        c=plan.source_constants(model,stage)
        self.assertEqual(c['walking_type'],7)
        self.assertEqual(c['random'],-c['unspecified'])
        for bad in (b'',model+model,model.replace(b'(-std::',b'(std::')):
            with self.assertRaises(ValueError):plan.source_constants(bad,stage)


if __name__=='__main__':unittest.main()
