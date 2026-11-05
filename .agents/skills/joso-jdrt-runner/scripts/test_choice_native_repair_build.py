"""Source-copy boundaries only; actual native compilation is a separate proof."""
import json
from pathlib import Path
import tempfile
import unittest
import choice_native_trace_build as build
from choice_pair_sources import source_tree

ROOT = Path(__file__).resolve().parents[4]
PROV = ROOT / '04_プログラム/output/sumo/toolchains/native_lat_20261020a/evidence/native_provenance.json'


class RepairSourceBoundary(unittest.TestCase):
    def setUp(self):
        provenance = json.loads(PROV.read_bytes())
        self.native = Path(provenance['state']['visible_staging']) / 'sources' / ('sumo-' + provenance['source_commit']) / build.STOP_INDEX_NATIVE

    def fixture(self, temp):
        source = Path(temp)/'original'
        path = source/build.STOP_INDEX_NATIVE
        path.parent.mkdir(parents=True)
        path.write_bytes(self.native.read_bytes())
        (source/'other.txt').write_bytes(b'unchanged dependency\n')
        return source, source_tree(source)

    def test_only_reviewed_target_changes_and_original_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            source, expected = self.fixture(temp)
            destination = Path(temp)/'candidate'
            receipt = build.prepare_source(source,destination,expected,stop_index_repair=True)
            self.assertEqual(source_tree(source),expected)
            self.assertEqual(receipt['scope'],'ISOLATED_REPAIR_CANDIDATE')
            self.assertEqual(receipt['target'],build.STOP_INDEX_NATIVE)
            self.assertEqual((destination/'other.txt').read_bytes(),b'unchanged dependency\n')
            self.assertNotIn(b'JDRT_STOP_INDEX',(destination/build.STOP_INDEX_NATIVE).read_bytes())
            self.assertIn(b'previousCurrentIndex',(destination/build.STOP_INDEX_NATIVE).read_bytes())

    def test_extra_change_and_changed_original_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            source, expected = self.fixture(temp)
            destination = Path(temp)/'candidate'
            build.prepare_source(source,destination,expected,stop_index_repair=True)
            (destination/'other.txt').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                build.verify_source(source,destination,expected,stop_index_repair=True)
            (source/'other.txt').write_bytes(b'changed original')
            with self.assertRaises(ValueError):
                build.prepare_source(source,Path(temp)/'second',expected,stop_index_repair=True)

    def test_existing_destination_is_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            source, expected = self.fixture(temp)
            destination = Path(temp)/'candidate'
            destination.mkdir()
            with self.assertRaises(ValueError):
                build.prepare_source(source,destination,expected,stop_index_repair=True)
            self.assertEqual(list(destination.iterdir()),[])


class PairedRoleSelection(unittest.TestCase):
    def test_each_role_uses_its_own_configured_source_and_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            prepared = {role+'_source_root':str(Path(temp)/role) for role in ('control','patched')}
            prepared['source_sha256']={'control':{'x':'c'},'patched':{'x':'p'}}
            for role in ('control','patched'):
                command=['cmake','-S',prepared[role+'_source_root'],'-B',str(Path(temp)/('build_'+role))]
                base={'commands':[{'command':command}]}
                source,expected,actual=build.select_base_source(base,prepared,role)
                self.assertEqual(source,Path(prepared[role+'_source_root']))
                self.assertEqual(expected,prepared['source_sha256'][role])
                self.assertEqual(actual,command)
                other='patched' if role=='control' else 'control'
                with self.assertRaises(ValueError):
                    build.select_base_source(base,prepared,other)

    def test_missing_ambiguous_or_invalid_role_is_refused(self):
        prepared={'patched_source_root':'source','source_sha256':{'patched':{}}}
        command={'command':['cmake','-S','source','-B','build']}
        for base in ({'commands':[]},{'commands':[command,command]}):
            with self.assertRaises(ValueError):
                build.select_base_source(base,prepared,'patched')
        with self.assertRaises(ValueError):
            build.select_base_source({'commands':[command]},prepared,'guessed')


if __name__=='__main__':
    unittest.main()
