"""Build a separate observation or explicit repair candidate; never simulate/adopt."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from choice_pair_sources import source_tree
import choice_native_trace_source as trace

NATIVE = 'src/microsim/transportables/MSPModel_Striping.cpp'
STOP_INDEX_NATIVE = 'src/microsim/MSBaseVehicle.cpp'


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extended(path):
    value = str(Path(path).resolve())
    return Path('\\\\?\\' + value) if os.name == 'nt' and not value.startswith('\\\\?\\') else Path(value)


def configure_command(previous, source, build):
    command = list(previous)
    for flag, replacement in (('-S', source), ('-B', build)):
        if command.count(flag) != 1 or command.index(flag) + 1 >= len(command):
            raise ValueError('Source/build CMake operands are missing or ambiguous')
        command[command.index(flag) + 1] = Path(replacement).as_posix()
    return command


def select_base_source(base, prepared, role):
    if role not in ('control', 'patched'):
        raise ValueError('Explicit native role required')
    commands = [c['command'] for c in base['commands']
                if '-S' in c['command'] and '-B' in c['command']]
    if len(commands) != 1:
        raise ValueError('Need exactly one completed base configure command')
    source = Path(prepared[role + '_source_root'])
    command = commands[0]
    if (command.count('-S') != 1 or command.index('-S') + 1 >= len(command)
            or Path(command[command.index('-S') + 1]).resolve() != source.resolve()):
        raise ValueError('Base configured source differs from requested native role')
    return source, prepared['source_sha256'][role], command


def validate_preparation(prepared, base_path, role, stop_index_repair):
    """A terminal shared-source snapshot can seed observation, never another repair."""
    if prepared.get('status') == 'PREPARED_NOT_BUILT':
        return
    if (prepared.get('status') != 'TERMINAL_SHARED_REPAIR_SOURCE_SNAPSHOT_NOT_READY'
            or stop_index_repair or role != 'patched'
            or any(prepared.get(key) is not False for key in
                   ('compiler_started', 'simulation_executed', 'core_ready'))):
        raise ValueError('Nonadoptable source preparation for this mode required')
    ref = prepared.get('terminal_builds', {}).get(role, {}).get('state', {})
    if (not isinstance(ref.get('path'), str)
            or Path(ref['path']).resolve() != Path(base_path).resolve()
            or ref.get('sha256') != file_sha(base_path)
            or type(ref.get('bytes')) is not int
            or ref['bytes'] != Path(base_path).stat().st_size):
        raise ValueError('Terminal source snapshot must bind this exact base build')


def prepare_source(source, destination, expected, stop_index_repair=False):
    if Path(destination).exists() or source_tree(source) != expected:
        raise ValueError('Need an unused destination and unchanged original inventory')
    shutil.copytree(extended(source), extended(destination))
    native = extended(destination) / (STOP_INDEX_NATIVE if stop_index_repair else NATIVE)
    if stop_index_repair:
        from choice_native_stop_index_remap import remap_source
        native.write_bytes(remap_source(native.read_bytes()))
    else:
        native.write_bytes(trace.instrument(native.read_bytes()))
    return verify_source(source, destination, expected, stop_index_repair)


def verify_source(source, destination, expected, stop_index_repair=False):
    if source_tree(source) != expected:
        raise ValueError('Original source changed')
    actual = source_tree(destination)
    target = STOP_INDEX_NATIVE if stop_index_repair else NATIVE
    if set(actual) != set(expected) or [n for n in actual if actual[n] != expected[n]] != [target]:
        raise ValueError('Diagnostic source differs outside its single observed constructor')
    if stop_index_repair:
        from choice_native_stop_index_remap import remap_source
        if remap_source((extended(source) / target).read_bytes()) != (extended(destination) / target).read_bytes():
            raise ValueError('Repair source differs from exact reviewed transform')
    else:
        trace.verify((extended(source) / target).read_bytes(), (extended(destination) / target).read_bytes())
    return {'original_files': len(expected), 'diagnostic_files': actual,
            'native_original_sha256': expected[target], 'native_trace_sha256': actual[target],
            'target': target, 'scope': 'ISOLATED_REPAIR_CANDIDATE' if stop_index_repair else 'OBSERVATION_ONLY'}


def cim_utf8(pid):
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError('Positive PID required')
    command = ('[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); '
               f'Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" | '
               'Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,'
               '@{n="CreationDate";e={([DateTimeOffset]$_.CreationDate.ToUniversalTime()).ToUnixTimeMilliseconds()}} | '
               'ConvertTo-Json -Compress')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt-id', required=True)
    parser.add_argument('--base-state', type=Path, required=True)
    parser.add_argument('--source-preparation', type=Path, required=True)
    parser.add_argument('--pair-state', type=Path, required=True)
    parser.add_argument('--pair-proof', type=Path, required=True)
    parser.add_argument('--stop-index-repair', action='store_true', help='Separate full-source repair candidate, never adoption')
    parser.add_argument('--build-role', choices=('control','patched'), default='patched')
    options = parser.parse_args()
    pattern = r'repair\d{2}_\d{8}' if options.stop_index_repair else r'diag\d{2}_\d{8}'
    if not re.fullmatch(pattern, options.attempt_id):
        raise ValueError('Fresh short diagnostic attempt ID required')
    if options.build_role != 'patched' and not options.stop_index_repair:
        raise ValueError('Control-source mode requires explicit stop-index repair')
    visible_root = options.base_state.absolute().parent.parent
    native_root = visible_root.resolve()
    sys.path.insert(0, str(native_root))
    import native_build_support as support
    # Only this process uses UTF-8 CIM; the preserved support source is unchanged.
    support.identity = cim_utf8
    base = json.loads(options.base_state.read_bytes())
    prepared = json.loads(options.source_preparation.read_bytes())
    pair = json.loads(options.pair_state.read_bytes())
    proof = json.loads(options.pair_proof.read_bytes())
    if (base['status'] != 'COMPILED_VERSION_CHECKED_NOT_SIMULATED'
            or base['simulation_allowed'] is not False or base['research_cli_switch_allowed'] is not False
            or pair['status'] != 'SELECTED_PAIR_VERIFIED_PENDING_NATIVE_GUARDS'
            or pair['research_adoption_permitted'] is not False or pair['technical_ready'] is not False
            or pair['active'] is not None or proof['bound_mismatches']
            or proof['state_sha256'] != file_sha(options.pair_state)):
        raise ValueError('Need completed, bound, nonadoptable native evidence')
    bindings = pair['source_and_artifact_sha256']
    if proof['bound_files_checked'] != len(bindings):
        raise ValueError('Incomplete pair binding proof')
    for path, expected_sha in bindings.items():
        if file_sha(path) != expected_sha:
            raise ValueError('Pair prerequisite changed: ' + path)
    for path in (options.base_state, options.source_preparation):
        if file_sha(path) not in bindings.values():
            raise ValueError('Build prerequisite not bound by the verified pair')
    validate_preparation(prepared, options.base_state, options.build_role, options.stop_index_repair)
    source, expected, original_configure = select_base_source(base, prepared, options.build_role)
    # CMake/MinGW need the same short visible path convention as the base build.
    # The observer discovers the corresponding physical package path separately.
    attempt = visible_root / options.attempt_id
    if attempt.exists():
        raise ValueError('Attempt already exists; never reuse or overwrite it')
    attempt.mkdir()
    diagnostic_source, diagnostic_build = attempt / 'source', attempt / 'build'
    for name, path in (('base_state', options.base_state), ('source_preparation', options.source_preparation),
                       ('pair_state', options.pair_state), ('pair_proof', options.pair_proof)):
        shutil.copyfile(path, attempt / (name + '.json'))
    for path in (Path(__file__), Path(trace.__file__), Path(support.__file__)):
        shutil.copyfile(path, attempt / path.name)
    if options.stop_index_repair:
        shutil.copyfile(Path(__file__).with_name('choice_native_stop_index_remap.py'), attempt / 'choice_native_stop_index_remap.py')
    state = {'schema': 'isolated_native_build_v1', 'attempt_id': attempt.name,
             'role': ('ISOLATED_STOP_INDEX_REPAIR_CANDIDATE_NOT_ADOPTED' if options.stop_index_repair
                      else 'OBSERVATION_ONLY_DIAGNOSTIC_NEVER_PRODUCTION'),
             'base_role': options.build_role,
             'started_at_jst': support.now(), 'owner_pid': os.getpid(),
             'owner_process_identity': cim_utf8(os.getpid()), 'child_pid': None,
             'staging': str(native_root), 'commands': [], 'binaries': [],
             'max_compile_jobs': 2, 'simulation_allowed': False, 'research_cli_switch_allowed': False,
             'technical_ready': False, 'research_adoption_permitted': False,
             'status': 'RUNNING', 'phase': 'diagnostic_source_preparation',
             'custom_version': ('1.26.0-jdrt-choice-stopindex-' + options.build_role + '-' if options.stop_index_repair
                                else '1.26.0-jdrt-choice-trace-') + options.attempt_id,
             'disk_free_before': shutil.disk_usage(native_root).free,
             'diagnostic_source': str(diagnostic_source), 'diagnostic_build': str(diagnostic_build),
             'snapshot_sha256': {p.name: file_sha(p) for p in attempt.iterdir() if p.is_file()}}
    latest = attempt / 'diagnostic_latest.json'  # Never replace the old global build_state.json.

    def run(phase, command):
        support.run(state, attempt, latest, phase, command)
        item = state['commands'][-1]
        item.update(log_bytes=Path(item['log']).stat().st_size, log_sha256=file_sha(item['log']))
        support.save(state, attempt, latest)

    try:
        if not state['owner_process_identity']:
            raise ValueError('Build owner identity unavailable')
        support.save(state, attempt, latest)
        receipt = prepare_source(source, diagnostic_source, expected, options.stop_index_repair)
        receipt_path = attempt / 'diagnostic_source_receipt.json'
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        state['source_receipt'] = {'path': str(receipt_path), 'sha256': file_sha(receipt_path)}
        if options.stop_index_repair:
            claim = 'control_native_source_sha256' if options.build_role == 'control' else 'patch_applied_sha256'
            state[claim] = receipt['diagnostic_files'][NATIVE]
            state['source_commit'] = prepared['source_commit']
            state['source_scope'] = 'Reviewed shared stop-history repair only, relative to selected original role; no trace output'
        command = configure_command(original_configure, diagnostic_source, diagnostic_build)
        run('diagnostic_configure', command)
        flags = (diagnostic_build / 'src/CMakeFiles/sumo.dir/flags.make').read_text()
        if '-DHAVE_VERSION_H' not in flags or '-DXERCES_STATIC_LIBRARY' not in flags:
            raise ValueError('Diagnostic compile definitions differ')
        header = diagnostic_build / 'src/version.h'
        header.write_text('#define VERSION_STRING "' + state['custom_version'] + '"\n', encoding='ascii')
        state['custom_version_header'] = {'path': str(header), 'sha256': file_sha(header)}
        targets = ['sumo', 'netconvert'] if options.stop_index_repair else ['sumo']
        run('diagnostic_sumo_build', [support.CM, '--build', diagnostic_build, '--target', *targets, '--parallel', '2'])
        response = (diagnostic_build / 'src/CMakeFiles/sumo.dir/linkLibs.rsp').read_text().split()
        if response.count('-lws2_32') != 1 or response.index('-lws2_32') < response.index('-Wl,--no-whole-archive'):
            raise ValueError('Diagnostic Winsock import boundary differs')
        binaries = []
        for name in targets:
            binary = diagnostic_build / 'src' / (name + '.exe')
            prefix = name + '_' if options.stop_index_repair else ''
            run(prefix + 'diagnostic_imports', [support.GCC / 'objdump.exe', '-p', binary])
            old_path = support.ENV['PATH']
            try:
                support.ENV['PATH'] = r'C:\Windows\System32;C:\Windows'
                run(prefix + 'diagnostic_version', [binary, '--version'])
            finally:
                support.ENV['PATH'] = old_path
            if state['custom_version'] not in (attempt / (prefix + 'diagnostic_version.log')).read_text():
                raise ValueError('Diagnostic actual version differs')
            binaries.append({'path': str(binary), 'sha256': file_sha(binary), 'bytes': binary.stat().st_size})
        if verify_source(source, diagnostic_source, expected, options.stop_index_repair) != receipt:
            raise ValueError('Diagnostic source inventory changed during build')
        for path, expected_sha in bindings.items():
            if file_sha(path) != expected_sha:
                raise ValueError('Original pair evidence changed during build: ' + path)
        state['binaries'] = binaries
        state.update(status='COMPILED_VERSION_CHECKED_NOT_SIMULATED', phase='completed')
        support.save(state, attempt, latest)
        print(json.dumps({'status': state['status'], 'state': str(attempt / 'build_state.json')}), flush=True)
    except Exception as error:
        # An interrupted parent leaves its last owned child intact for inspection.
        state.update(status='FAILED_PRESERVED', error=repr(error))
        support.save(state, attempt, latest)
        raise


if __name__ == '__main__':
    main()
