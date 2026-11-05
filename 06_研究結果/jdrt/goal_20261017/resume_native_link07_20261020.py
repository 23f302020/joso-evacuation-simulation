"""Preserve a06; remove system import library from whole-archive, no simulation."""
import copy
import difflib
import json
import os
from pathlib import Path
import shutil
import sys

VISIBLE = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
sys.path.insert(0, str(VISIBLE))
import native_build_support as support

ST, CM, GCC = support.ST, support.CM, support.GCC
A = ST / 'attempt07_20261020'
LATEST = ST / 'build_state.json'
SS = VISIBLE / 'sources/sumo-fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3'
SB = VISIBLE / 'b05'
previous_raw = LATEST.read_bytes()
previous = json.loads(previous_raw)
if A.exists() or previous['status'] != 'FAILED_PRESERVED' or previous['attempt_id'] != 'attempt06_20261020':
    raise SystemExit('Expected preserved a06 and unused a07')
if support.identity(previous['owner_pid']):
    raise SystemExit('Previous owner exists; do not start')
physical = SS / 'src/microsim/transportables/MSPModel_Striping.cpp'
if support.sha(physical) != previous['patch_applied_sha256']:
    raise SystemExit('Physical source changed')
cmake = SS / 'src/CMakeLists.txt'
raw = cmake.read_bytes()
eol = b'\r\n' if b'\r\n' in raw else b'\n'
anchor = b'if ((GNU_COMPILER OR CLANG_COMPILER) AND NOT APPLE)' + eol
if raw.count(anchor) != 1:
    raise SystemExit('Ambiguous CMake insertion point')
close = b'    set(sumoguilibs -Wl,--whole-archive ${sumoguilibs} -Wl,--no-whole-archive)' + eol + b'endif()'
if raw.count(close) != 1:
    raise SystemExit('Ambiguous CMake whole-archive boundary')
prefix = eol.join([b'if (MINGW)', b'    list(REMOVE_ITEM sumolibs ws2_32)', b'endif ()', b''])
suffix = eol.join([b'', b'if (MINGW)', b'    list(APPEND sumolibs ws2_32)', b'endif ()'])
new = raw.replace(anchor, prefix + anchor).replace(close, close + suffix)
A.mkdir()
(A / 'previous_build_state.json').write_bytes(previous_raw)
(A / 'CMakeLists.before.bin').write_bytes(raw)
shutil.copyfile(__file__, A / 'build_helper_snapshot.py')
for name in ('sumo', 'netconvert'):
    shutil.copy2(SB / 'src' / (name + '.exe'), A / (name + '.before.exe'))
    for item in ('link.txt', 'linkLibs.rsp'):
        source = SB / 'src/CMakeFiles' / (name + '.dir') / item
        shutil.copy2(source, A / (name + '.' + item + '.before'))
cmake.write_bytes(new)
(A / 'cmake_link.patch').write_text(''.join(difflib.unified_diff(
    raw.decode().splitlines(True), new.decode().splitlines(True), 'src/CMakeLists.txt.before',
    'src/CMakeLists.txt.after')), encoding='utf-8')
state = copy.deepcopy(previous)
state.update(attempt_id=A.name, role='PATCHED_MINGW_IMPORT_LINK_REPAIR', started_at_jst=support.now(),
             owner_pid=os.getpid(), owner_process_identity=support.identity(os.getpid()),
             child_pid=None, status='RUNNING', phase='cmake_link_repair', commands=[], binaries=[],
             previous_state={'path': str(A / 'previous_build_state.json'),
                             'sha256': support.sha(A / 'previous_build_state.json')},
             cmake_link_repair={'path': str(cmake), 'before_sha256': support.sha(A / 'CMakeLists.before.bin'),
                                'after_sha256': support.sha(cmake), 'patch_sha256': support.sha(A / 'cmake_link.patch')},
             simulation_allowed=False, research_cli_switch_allowed=False)
state.pop('error', None)


def run(phase, args):
    try:
        support.run(state, A, LATEST, phase, args)
    finally:
        entry = state['commands'][-1]
        log = Path(entry['log'])
        if log.is_file():
            entry.update(log_bytes=log.stat().st_size, log_sha256=support.sha(log))
        support.save(state, A, LATEST)


try:
    support.save(state, A, LATEST)
    run('sumo_netconvert_build_system_import_boundary', [CM, '--build', SB.as_posix(),
        '--target', 'sumo', 'netconvert', '--parallel', '2'])
    response = (SB / 'src/CMakeFiles/sumo.dir/linkLibs.rsp').read_text()
    tokens = response.split()
    if tokens.count('-lws2_32') != 1 or tokens.index('-lws2_32') < tokens.index('-Wl,--no-whole-archive'):
        raise RuntimeError('System import library remains inside whole-archive')
    state['link_boundary_verified'] = True
    for name in ('sumo', 'netconvert'):
        binary = SB / 'src' / (name + '.exe')
        run(name + '_imports', [GCC / 'objdump.exe', '-p', binary])
        saved_path = support.ENV['PATH']
        try:
            support.ENV['PATH'] = r'C:\Windows\System32;C:\Windows'
            run(name + '_version', [binary, '--version'])
        finally:
            support.ENV['PATH'] = saved_path
        version_log = A / (name + '_version.log')
        if state['custom_version'] not in version_log.read_text():
            raise RuntimeError('Custom version mismatch')
        state['binaries'].append({'path': str(binary), 'sha256': support.sha(binary),
            'bytes': binary.stat().st_size, 'clean_path_version_exit_code': 0,
            'version_log': str(version_log), 'version_log_sha256': support.sha(version_log)})
    if support.sha(physical) != state['patch_applied_sha256'] or support.sha(cmake) != state['cmake_link_repair']['after_sha256']:
        raise RuntimeError('Physical or build source changed')
    state.update(status='COMPILED_VERSION_CHECKED_NOT_SIMULATED', phase='completed', child_pid=None)
    support.save(state, A, LATEST)
    print(state['status'], flush=True)
except BaseException as error:
    state.update(status='FAILED_PRESERVED', error=repr(error), child_pid=None)
    support.save(state, A, LATEST)
    raise
