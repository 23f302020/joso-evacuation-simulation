"""Artificial CMake metadata contracts; no compiler, native process or research data."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / '.agents/skills/joso-jdrt-runner/scripts/choice_pair_metadata.py'
spec = importlib.util.spec_from_file_location('choice_pair_metadata_test', SOURCE)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


class MetadataContracts(unittest.TestCase):
    def setUp(self):
        self.patched = {name: 'same actual content\n' for name in target.FILES}
        self.control = dict(self.patched)
        self.patched['CMakeCache.txt'] = ('CMAKE_C_COMPILER:UNINITIALIZED=C:\\tools\\gcc.exe\n'
            'CMAKE_CXX_COMPILER:UNINITIALIZED=C:\\tools\\g++.exe\n'
            'CMAKE_BUILD_TYPE:STRING=Release\nENABLE_PYTHON_BINDINGS:BOOL=OFF\n'
            '_Python_Interpreter_REASON_FAILURE:INTERNAL=\nSOURCE_DIR:PATH=C:/p/src\n')
        self.control['CMakeCache.txt'] = ('CMAKE_C_COMPILER:STRING=c:/tools/gcc.exe\n'
            'CMAKE_CXX_COMPILER:STRING=c:/tools/g++.exe\n'
            'CMAKE_BUILD_TYPE:STRING=Release\nENABLE_PYTHON_BINDINGS:BOOL=OFF\nSOURCE_DIR:PATH=C:/c/src\n')

    def compare(self):
        return target.compare_metadata(self.patched, self.control, ('C:/p', 'C:/bp'), ('C:/c', 'C:/bc'))

    def test_equivalent_compiler_paths_and_documented_empty_diagnostic(self):
        self.assertTrue(self.compare()['equal'])

    def test_effective_cache_change_is_not_hidden(self):
        self.control['CMakeCache.txt'] = self.control['CMakeCache.txt'].replace('Release', 'Debug')
        self.assertFalse(self.compare()['equal'])

    def test_compiler_path_change_is_not_hidden(self):
        self.control['CMakeCache.txt'] = self.control['CMakeCache.txt'].replace('c:/tools/gcc.exe', 'c:/other/gcc.exe')
        self.assertFalse(self.compare()['equal'])

    def test_nonempty_python_reason_and_enabled_bindings_are_not_ignored(self):
        for mode in ('reason', 'bindings'):
            with self.subTest(mode=mode):
                self.setUp()
                if mode == 'reason':
                    self.control['CMakeCache.txt'] += '_Python_Interpreter_REASON_FAILURE:INTERNAL=missing library\n'
                else:
                    self.patched['CMakeCache.txt'] = self.patched['CMakeCache.txt'].replace('BOOL=OFF', 'BOOL=ON')
                    self.control['CMakeCache.txt'] = self.control['CMakeCache.txt'].replace('BOOL=OFF', 'BOOL=ON')
                self.assertFalse(self.compare()['equal'])

    def test_other_cache_type_change_is_not_ignored(self):
        self.control['CMakeCache.txt'] = self.control['CMakeCache.txt'].replace('CMAKE_BUILD_TYPE:STRING', 'CMAKE_BUILD_TYPE:INTERNAL')
        self.assertFalse(self.compare()['equal'])

    def test_flags_includes_links_and_macro_case_are_compared(self):
        for name in target.FILES[1:]:
            with self.subTest(name=name):
                self.setUp()
                self.control[name] = 'different actual content\n'
                self.assertIn(name, self.compare()['different_files'])

    def test_matching_roots_and_line_endings_are_normalized(self):
        self.patched['src/config.h'] = 'C:/p/include C:/bp/file\n#define ENABLE 1\n'
        self.control['src/config.h'] = 'C:/c/include C:/bc/file\r\n#define ENABLE 1\r\n'
        self.assertTrue(self.compare()['equal'])
        self.control['src/config.h'] = self.control['src/config.h'].replace('ENABLE', 'enable')
        self.assertFalse(self.compare()['equal'])

    def test_sibling_path_prefix_is_not_a_declared_root(self):
        self.patched['src/config.h'] = 'C:/p_extra/include\n'
        self.control['src/config.h'] = 'C:/c_extra/include\n'
        self.assertIn('src/config.h', self.compare()['different_files'])

    def test_incomplete_metadata_rejected_even_if_both_missing(self):
        self.patched.pop('src/config.h')
        self.control.pop('src/config.h')
        with self.assertRaises(ValueError):
            self.compare()

    def test_duplicate_cache_entry_is_rejected(self):
        self.control['CMakeCache.txt'] += 'CMAKE_BUILD_TYPE:STRING=Release\n'
        with self.assertRaises(ValueError):
            self.compare()

    def test_bad_compiler_types_and_relative_paths_are_rejected(self):
        for bad in ('CMAKE_C_COMPILER:BOOL=c:/tools/gcc.exe', 'CMAKE_C_COMPILER:STRING=tools/gcc.exe'):
            with self.subTest(bad=bad):
                self.setUp()
                self.control['CMakeCache.txt'] = self.control['CMakeCache.txt'].replace('CMAKE_C_COMPILER:STRING=c:/tools/gcc.exe', bad)
                with self.assertRaises(ValueError):
                    self.compare()


if __name__ == '__main__':
    unittest.main()
