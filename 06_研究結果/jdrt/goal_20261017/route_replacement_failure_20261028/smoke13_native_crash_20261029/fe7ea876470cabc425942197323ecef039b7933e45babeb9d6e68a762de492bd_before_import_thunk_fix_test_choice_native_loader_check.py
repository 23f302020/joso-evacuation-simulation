import unittest
from choice_native_loader_check import parse_imports


class ImportCoverage(unittest.TestCase):
    def test_keeps_exact_dll_symbol_coverage(self):
        text='DLL Name: KERNEL32.dll\n  1000  1 CreateFileW\n  1010  2 CloseHandle\n'
        self.assertEqual(parse_imports(text),[{'name':'KERNEL32.dll','symbols':['CreateFileW','CloseHandle']}])

    def test_empty_missing_symbols_duplicate_and_non_system_are_refused(self):
        for text in ('','DLL Name: KERNEL32.dll\n',
                     'DLL Name: libunknown.dll\n 1000 1 x\n',
                     'DLL Name: KERNEL32.dll\n 1000 1 x\nDLL Name: kernel32.dll\n 2000 2 y\n',
                     'DLL Name: KERNEL32.dll\n 1000 1 x\n 1010 2 x\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):parse_imports(text)


if __name__=='__main__':unittest.main()
