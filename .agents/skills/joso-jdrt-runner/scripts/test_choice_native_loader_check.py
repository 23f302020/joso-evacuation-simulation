import unittest
from choice_native_loader_check import parse_imports, loader_targets


class ImportCoverage(unittest.TestCase):
    def test_keeps_exact_dll_symbol_coverage(self):
        text='The Import Tables (interpreted .idata section contents)\nDLL Name: KERNEL32.dll\n  1000  1 CreateFileW\n  1010  2 CloseHandle\n'
        self.assertEqual(parse_imports(text),[{'name':'KERNEL32.dll','symbols':['CreateFileW','CloseHandle']}])

    def test_repeated_import_thunks_are_preserved(self):
        text='The Import Tables (interpreted .idata section contents)\nDLL Name: api-ms-win-crt-stdio-l1-1-0.dll\n 1000 1 fflush\n 1010 1 fflush\n'
        self.assertEqual(parse_imports(text)[0]['symbols'],['fflush','fflush'])

    def test_function_table_and_preheader_rows_are_not_imports(self):
        text='DLL Name: fake.dll\n 100 1 hidden\nThe Import Tables (interpreted .idata section contents)\nDLL Name: KERNEL32.dll\n 1000 1 CreateFileW\nThe Function Table (interpreted .pdata section contents)\n 1000 1000 not_a_symbol\n'
        self.assertEqual(parse_imports(text),[{'name':'KERNEL32.dll','symbols':['CreateFileW']}])

    def test_empty_missing_header_missing_symbols_duplicate_dll_and_non_system_are_refused(self):
        for text in ('','DLL Name: KERNEL32.dll\n',
                     'DLL Name: KERNEL32.dll\n 1000 1 x\n',
                     'The Import Tables\nDLL Name: libunknown.dll\n 1000 1 x\n',
                     'The Import Tables\nDLL Name: KERNEL32.dll\n 1000 1 x\nDLL Name: kernel32.dll\n 2000 2 y\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):parse_imports(text)


class LoaderTargets(unittest.TestCase):
    def observation(self):
        return {'role':'OBSERVATION_ONLY_DIAGNOSTIC_NEVER_PRODUCTION',
                'technical_ready':False,'binaries':[{'path':'sumo.exe'}]}

    def test_existing_two_target_build_keeps_per_target_command_phases(self):
        state={'role':'ISOLATED_STOP_INDEX_REPAIR_CANDIDATE_NOT_ADOPTED',
               'binaries':[{'path':'sumo.exe'},{'path':'netconvert.exe'}]}
        self.assertEqual(loader_targets(state),(('sumo','sumo_diagnostic_imports'),
                                                ('netconvert','netconvert_diagnostic_imports')))

    def test_explicit_observation_only_sumo_uses_its_original_raw_phase(self):
        self.assertEqual(loader_targets(self.observation()),(('sumo','diagnostic_imports'),))

    def test_unknown_or_production_role_does_not_gain_single_target_permission(self):
        for role in ('patched','ISOLATED_STOP_INDEX_REPAIR_CANDIDATE_NOT_ADOPTED',None):
            state=self.observation();state['role']=role
            with self.subTest(role=role),self.assertRaises(ValueError):loader_targets(state)

    def test_observation_target_must_be_exactly_one_sumo(self):
        for binaries in ([],[{'path':'netconvert.exe'}],[{'path':'sumo.exe'},{'path':'netconvert.exe'}]):
            state=self.observation();state['binaries']=binaries
            with self.subTest(binaries=binaries),self.assertRaises(ValueError):loader_targets(state)

    def test_observation_ready_or_missing_flag_is_refused(self):
        state=self.observation();state['technical_ready']=True
        with self.assertRaises(ValueError):loader_targets(state)
        state.pop('technical_ready')
        with self.assertRaises(ValueError):loader_targets(state)


if __name__=='__main__':unittest.main()
