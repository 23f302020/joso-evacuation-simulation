"""Enable the generated version header in a fresh preserved build attempt."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys

VISIBLE = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
sys.path.insert(0, str(VISIBLE))
import native_build_support as support

ST, CM, GCC = support.ST, support.CM, support.GCC
A = ST / 'attempt08_20261020'
LATEST = ST / 'build_state.json'
SB = VISIBLE / 'b05'
previous_raw = LATEST.read_bytes()
previous = json.loads(previous_raw)
if A.exists() or previous['attempt_id'] != 'attempt07_20261020' or previous['status'] != 'FAILED_PRESERVED':
    raise SystemExit('Expected preserved a07 and new a08')
if support.identity(previous['owner_pid']):
    raise SystemExit('Previous owner remains; stop')
older = json.loads((ST / 'attempt07_20261020/previous_build_state.json').read_bytes())
configure = [item['command'] for item in older['commands'] if item['phase'] == 'sumo_configure_short_path']
if len(configure) != 1:
    raise SystemExit('Missing exact successful configure command')
args = configure[0]
old_define = '-DCOMPILE_DEFINITIONS=XERCES_STATIC_LIBRARY'
if args.count(old_define) != 1:
    raise SystemExit('Unexpected previous compiler definitions')
args = [('-DCOMPILE_DEFINITIONS=XERCES_STATIC_LIBRARY;HAVE_VERSION_H' if arg == old_define else arg) for arg in args]
physical = Path(previous['visible_staging']) / 'sources/sumo-fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3/src/microsim/transportables/MSPModel_Striping.cpp'
if support.sha(physical) != previous['patch_applied_sha256']:
    raise SystemExit('Physical source mismatch')
A.mkdir()
(A / 'previous_build_state.json').write_bytes(previous_raw)
shutil.copyfile(__file__, A / 'build_helper_snapshot.py')
for name in ('sumo', 'netconvert'):
    shutil.copy2(SB / 'src' / (name + '.exe'), A / (name + '.before.exe'))
for name in ('CMakeCache.txt', 'src/config.h', 'src/version.h'):
    shutil.copy2(SB / name, A / (Path(name).name + '.before'))
state = copy.deepcopy(previous)
state.update(attempt_id=A.name, role='PATCHED_GENERATED_VERSION_DEFINE', started_at_jst=support.now(),
             owner_pid=os.getpid(), owner_process_identity=support.identity(os.getpid()),
             child_pid=None, status='RUNNING', phase='version_header_configure', commands=[], binaries=[],
             previous_state={'path': str(A / 'previous_build_state.json'),
                             'sha256': support.sha(A / 'previous_build_state.json')},
             custom_version='1.26.0-jdrt-choice-latpreserve-93d3ca0c-ucrt12-static-zlib1213-a08',
             version_define_repair={'before': 'XERCES_STATIC_LIBRARY',
                                    'after': 'XERCES_STATIC_LIBRARY;HAVE_VERSION_H'},
             simulation_allowed=False, research_cli_switch_allowed=False)
state.pop('error', None)


def run(phase, command):
    try:
        support.run(state, A, LATEST, phase, command)
    finally:
        entry = state['commands'][-1]
        log = Path(entry['log'])
        if log.is_file():
            entry.update(log_bytes=log.stat().st_size, log_sha256=support.sha(log))
        support.save(state, A, LATEST)


try:
    support.save(state, A, LATEST)
    run('version_header_configure', args)
    flags = (SB / 'src/CMakeFiles/sumo.dir/flags.make').read_text()
    if '-DHAVE_VERSION_H' not in flags or '-DXERCES_STATIC_LIBRARY' not in flags:
        raise RuntimeError('Required compiler definitions absent')
    header = SB / 'src/version.h'
    header.write_text('#define VERSION_STRING "' + state['custom_version'] + '"\n', encoding='ascii')
    state['custom_version_header'] = {'path': str(header), 'sha256': support.sha(header)}
    run('sumo_netconvert_build_generated_version', [CM, '--build', SB.as_posix(), '--target', 'sumo', 'netconvert', '--parallel', '2'])
    response = (SB / 'src/CMakeFiles/sumo.dir/linkLibs.rsp').read_text().split()
    if response.count('-lws2_32') != 1 or response.index('-lws2_32') < response.index('-Wl,--no-whole-archive'):
        raise RuntimeError('System import boundary regressed')
    for name in ('sumo', 'netconvert'):
        binary = SB / 'src' / (name + '.exe')
        run(name + '_imports', [GCC / 'objdump.exe', '-p', binary])
        old_path = support.ENV['PATH']
        try:
            support.ENV['PATH'] = r'C:\Windows\System32;C:\Windows'
            run(name + '_version', [binary, '--version'])
        finally:
            support.ENV['PATH'] = old_path
        log = A / (name + '_version.log')
        if state['custom_version'] not in log.read_text():
            raise RuntimeError('Actual custom version mismatch')
        state['binaries'].append({'path': str(binary), 'sha256': support.sha(binary), 'bytes': binary.stat().st_size,
            'clean_path_version_exit_code': 0, 'version_log': str(log), 'version_log_sha256': support.sha(log)})
    if support.sha(physical) != state['patch_applied_sha256']:
        raise RuntimeError('Physical source changed')
    state.update(status='COMPILED_VERSION_CHECKED_NOT_SIMULATED', phase='completed', child_pid=None)
    support.save(state, A, LATEST)
    print(state['status'], flush=True)
except BaseException as error:
    state.update(status='FAILED_PRESERVED', error=repr(error), child_pid=None)
    support.save(state, A, LATEST)
    raise
