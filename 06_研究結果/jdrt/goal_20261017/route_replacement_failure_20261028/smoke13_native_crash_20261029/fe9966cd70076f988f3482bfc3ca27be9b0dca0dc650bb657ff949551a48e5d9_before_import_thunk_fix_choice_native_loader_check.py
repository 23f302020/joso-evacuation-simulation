"""Bind clean system-only loader/--version evidence to an explicit terminal build.

Generalizes the dated native_loader_diagnose_20261020.py recipe without changing
its historical bytes or accidentally snapshotting the old global build state.
Never simulates, packages, switches a selector or establishes READY.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from choice_package_toolchain import OS_DLLS, pe_imports
from choice_native_regression import read_json


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def parse_imports(text):
    imports=[];current=None
    for line in text.splitlines():
        match=re.search(r'DLL Name:\s*(\S+)',line)
        if match:
            current={'name':match[1],'symbols':[]};imports.append(current)
        elif current is not None:
            match=re.fullmatch(r'\s*[0-9a-f]+\s+\d+\s+(\S+)\s*',line)
            if match:current['symbols'].append(match[1])
    names=[x['name'].lower() for x in imports]
    if (not imports or len(names)!=len(set(names)) or set(names)-OS_DLLS
            or any(not x['symbols'] or len(x['symbols'])!=len(set(x['symbols'])) for x in imports)):
        raise ValueError('Complete unambiguous allowed-system imports required')
    return imports


def run(root,state_path,output):
    root,state_path,output=root.resolve(),state_path.resolve(),output.resolve()
    staging=Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019').resolve()
    goal=root/'06_研究結果/jdrt/goal_20261017'
    if not state_path.is_relative_to(staging) or not output.is_relative_to(goal) or output.exists():
        raise ValueError('Explicit isolated build state and unused goal-local output required')
    state=read_json(state_path);state_sha=sha(state_path);build=Path(state['diagnostic_build']).resolve()
    if (state.get('status')!='COMPILED_VERSION_CHECKED_NOT_SIMULATED' or state.get('child_pid') is not None
            or state.get('simulation_allowed') is not False or state.get('research_cli_switch_allowed') is not False
            or state.get('research_adoption_permitted') is not False or not build.is_relative_to(staging)
            or len(state['binaries'])!=2):
        raise ValueError('Terminal nonadoptable two-target build required')
    output.mkdir(parents=True,exist_ok=False)
    (output/'build_state.snapshot.bin').write_bytes(state_path.read_bytes())
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'state':str(state_path),'state_sha256':state_sha,
            'build_directory':str(build),'simulation_executed':False,'global_environment_modified':False,
            'source_sha256':sha(__file__),'binaries':[],'status':'CHECKING_NOT_READY'}
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LoadLibraryExW.argtypes=[wintypes.LPCWSTR,wintypes.HANDLE,wintypes.DWORD]
    kernel.LoadLibraryExW.restype=wintypes.HMODULE
    kernel.GetProcAddress.argtypes=[wintypes.HMODULE,ctypes.c_char_p]
    kernel.GetProcAddress.restype=ctypes.c_void_p
    kernel.GetModuleFileNameW.argtypes=[wintypes.HMODULE,wintypes.LPWSTR,wintypes.DWORD]
    kernel.GetModuleFileNameW.restype=wintypes.DWORD
    kernel.FreeLibrary.argtypes=[wintypes.HMODULE]
    kernel.SetErrorMode(0x0001|0x0002|0x8000)
    try:
        for name in ('sumo','netconvert'):
            binary=build/'src'/(name+'.exe')
            entries=[x for x in state['binaries'] if Path(x['path']).resolve()==binary]
            if len(entries)!=1 or sha(binary)!=entries[0]['sha256'] or binary.stat().st_size!=entries[0]['bytes']:
                raise ValueError('Actual executable does not match terminal build')
            commands=[x for x in state['commands'] if x['phase']==name+'_diagnostic_imports']
            if len(commands)!=1 or commands[0]['exit_code']!=0:raise ValueError('Native import command required')
            command=commands[0];log=Path(command['log'])
            if sha(log)!=command['log_sha256'] or log.stat().st_size!=command['log_bytes']:
                raise ValueError('Original native import log changed')
            shutil.copyfile(log,output/(name+'_objdump.log'))
            imports=parse_imports(log.read_text(encoding='utf-8'))
            if sorted(x['name'].lower() for x in imports)!=pe_imports(binary):
                raise ValueError('Actual PE import set differs from raw symbol log')
            for item in imports:
                handle=kernel.LoadLibraryExW(item['name'],None,0x00000800)
                item['system_only_load_error']=ctypes.get_last_error() if not handle else 0
                if handle:
                    buffer=ctypes.create_unicode_buffer(32768)
                    size=kernel.GetModuleFileNameW(handle,buffer,len(buffer))
                    item['loaded_module_path']=buffer.value if size else None
                    item['missing_symbols']=[x for x in item['symbols'] if not kernel.GetProcAddress(handle,x.encode('ascii'))]
                    kernel.FreeLibrary(handle)
                if (not handle or item.get('missing_symbols') or not item.get('loaded_module_path')
                        or Path(item['loaded_module_path']).parent.resolve()!=(Path(os.environ['SystemRoot'])/'System32').resolve()):
                    raise ValueError('System-only DLL/export resolution failed: '+item['name'])
            env=os.environ.copy();env['PATH']=os.environ['SystemRoot']+'/System32;'+os.environ['SystemRoot']
            version=subprocess.run([str(binary),'--version'],capture_output=True,env=env,cwd=output,timeout=20)
            (output/(name+'_clean_version.stdout')).write_bytes(version.stdout)
            (output/(name+'_clean_version.stderr')).write_bytes(version.stderr)
            result['binaries'].append({'path':str(binary),'sha256':sha(binary),'bytes':binary.stat().st_size,
                'imports':imports,'clean_version_returncode':version.returncode,'clean_version_hex':hex(version.returncode&0xffffffff)})
            if version.returncode or version.stderr or state['custom_version'].encode() not in version.stdout:
                raise ValueError('Clean-path actual version mismatch')
        if sha(state_path)!=state_sha:raise ValueError('Terminal build state changed during loader check')
        result['status']='SYSTEM_ONLY_LOADER_VERIFIED_NOT_READY'
    except BaseException as error:
        result.update(status='FAILED_PRESERVED',error=repr(error))
        raise
    finally:
        result['files_sha256']={p.name:sha(p) for p in output.iterdir() if p.is_file()}
        with (output/'diagnosis.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'report':str(output/'diagnosis.json'),'status':result['status'],'binaries':len(result['binaries'])}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,required=True)
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.project_root,a.state,a.output)
