"""Build one unpatched control only after the patched build has really ended."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import re

VISIBLE = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
sys.path.insert(0, str(VISIBLE))
import native_build_support as support

ST, CM, GCC = support.ST, support.CM, support.GCC
LATEST = ST / 'build_state.json'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--attempt-id', required=True)
parser.add_argument('--previous-attempt', required=True)
parser.add_argument('--patched-state', type=Path, required=True)
options = parser.parse_args()
if not re.fullmatch(r'control\d{2}_20261020', options.attempt_id):
    raise SystemExit('Use a new short local control attempt ID')
A = ST / options.attempt_id
SOURCE = VISIBLE / 'sources/control126_20261020'
BUILD = VISIBLE / 'bc01'
prepared_path = ST / 'control_source_preparation_20261020.json'
prepared = json.loads(prepared_path.read_bytes())
predecessor_raw = LATEST.read_bytes()
predecessor = json.loads(predecessor_raw)
previous_raw = options.patched_state.read_bytes()
previous = json.loads(previous_raw)
if (A.exists() or BUILD.exists() or prepared['status'] != 'PREPARED_NOT_BUILT'
        or predecessor['attempt_id'] != options.previous_attempt
        or predecessor['status'] not in ('FAILED_PRESERVED', 'COMPILED_VERSION_CHECKED_NOT_SIMULATED')
        or previous['attempt_id'] != 'attempt08_20261020'
        or previous['status'] != 'COMPILED_VERSION_CHECKED_NOT_SIMULATED'):
    raise SystemExit('Need a new control build, completed source preparation and successful a08')
if support.identity(previous['owner_pid']) or support.identity(predecessor['owner_pid']):
    raise SystemExit('Previous build owner still exists; inspect the same handle')
if len(previous['binaries']) != 2 or any(support.sha(item['path']) != item['sha256'] for item in previous['binaries']):
    raise SystemExit('Patched binaries changed')
native = prepared['differences']
if native != ['src/microsim/transportables/MSPModel_Striping.cpp']:
    raise SystemExit('Unexpected source differences')
for name in (native[0], 'src/CMakeLists.txt'):
    if support.sha(SOURCE / name) != prepared['source_sha256']['control'][name]:
        raise SystemExit('Control native/build source changed: ' + name)
configure = [entry['command'] for entry in previous['commands'] if entry['phase'] == 'version_header_configure']
if len(configure) != 1:
    raise SystemExit('Need exact patched configure command')
args = list(configure[0])
args[args.index('-S') + 1] = SOURCE.as_posix()
args[args.index('-B') + 1] = BUILD.as_posix()
A.mkdir()
(A / 'patched_build_state.json').write_bytes(previous_raw)
(A / 'previous_build_state.json').write_bytes(predecessor_raw)
shutil.copyfile(prepared_path, A / 'source_preparation.json')
shutil.copyfile(__file__, A / 'build_helper_snapshot.py')
state = copy.deepcopy(previous)
state.update(attempt_id=A.name, role='UNPATCHED_CONTROL_SAME_BUILD_SETTINGS',
             started_at_jst=support.now(), owner_pid=os.getpid(), owner_process_identity=support.identity(os.getpid()),
             child_pid=None, status='RUNNING', phase='control_configure', commands=[], binaries=[],
             patch_applied_sha256=None,
             control_native_source_sha256=prepared['source_sha256']['control'][native[0]],
             paired_patched_state={'path': str(A / 'patched_build_state.json'),
                                   'sha256': support.sha(A / 'patched_build_state.json')},
             previous_state={'path': str(A / 'previous_build_state.json'),
                             'sha256': support.sha(A / 'previous_build_state.json')},
             source_preparation={'path': str(A / 'source_preparation.json'),
                                 'sha256': support.sha(A / 'source_preparation.json')},
             custom_version='1.26.0-jdrt-choice-unpatched-control-ucrt12-static-zlib1213-c01',
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
    source_check = [sys.executable, '-X', 'utf8', Path(__file__).with_name('verify_native_control_sources_20261020.py'),
                    '--snapshot', A / 'source_preparation.json', '--source-root', SOURCE]
    run('control_source_before_build', source_check)
    run('control_configure', args)
    flags = (BUILD / 'src/CMakeFiles/sumo.dir/flags.make').read_text()
    if '-DHAVE_VERSION_H' not in flags or '-DXERCES_STATIC_LIBRARY' not in flags:
        raise RuntimeError('Control compiler definitions mismatch')
    header = BUILD / 'src/version.h'
    header.write_text('#define VERSION_STRING "' + state['custom_version'] + '"\n', encoding='ascii')
    state['custom_version_header'] = {'path': str(header), 'sha256': support.sha(header)}
    run('control_sumo_netconvert_build', [CM, '--build', BUILD.as_posix(), '--target', 'sumo', 'netconvert', '--parallel', '2'])
    response = (BUILD / 'src/CMakeFiles/sumo.dir/linkLibs.rsp').read_text().split()
    if response.count('-lws2_32') != 1 or response.index('-lws2_32') < response.index('-Wl,--no-whole-archive'):
        raise RuntimeError('Control system import boundary mismatch')
    for name in ('sumo', 'netconvert'):
        binary = BUILD / 'src' / (name + '.exe')
        run(name + '_imports', [GCC / 'objdump.exe', '-p', binary])
        old_path = support.ENV['PATH']
        try:
            support.ENV['PATH'] = r'C:\Windows\System32;C:\Windows'
            run(name + '_version', [binary, '--version'])
        finally:
            support.ENV['PATH'] = old_path
        log = A / (name + '_version.log')
        if state['custom_version'] not in log.read_text():
            raise RuntimeError('Control actual version mismatch')
        state['binaries'].append({'path': str(binary), 'sha256': support.sha(binary), 'bytes': binary.stat().st_size,
            'clean_path_version_exit_code': 0, 'version_log': str(log), 'version_log_sha256': support.sha(log)})
    run('control_source_after_build', source_check)
    state.update(status='COMPILED_VERSION_CHECKED_NOT_SIMULATED', phase='completed', child_pid=None)
    support.save(state, A, LATEST)
    print(state['status'], flush=True)
except BaseException as error:
    state.update(status='FAILED_PRESERVED', error=repr(error), child_pid=None)
    support.save(state, A, LATEST)
    raise
