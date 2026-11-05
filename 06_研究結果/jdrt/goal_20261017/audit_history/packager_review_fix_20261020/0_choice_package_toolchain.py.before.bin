"""Create a new pinned choice bundle; never build or start a simulation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
# This packager supports static non-OS dependencies only. No PATH/DLL search.
OS_DLLS = {'advapi32.dll', 'bcrypt.dll', 'crypt32.dll', 'dnsapi.dll', 'gdi32.dll',
           'iphlpapi.dll', 'kernel32.dll', 'msvcrt.dll', 'ntdll.dll', 'ole32.dll',
           'oleaut32.dll', 'psapi.dll', 'secur32.dll', 'shell32.dll', 'shlwapi.dll',
           'ucrtbase.dll', 'user32.dll', 'userenv.dll', 'version.dll', 'winmm.dll',
           'winspool.drv', 'ws2_32.dll', 'wsock32.dll'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def regular(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError(f'Symlinks/junctions are forbidden: {path}')
    if not path.is_file() or path.suffix.lower() in ('.pyc', '.pyo'):
        raise ValueError(f'Missing regular source or forbidden bytecode: {path}')
    return path.resolve()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(regular(path).read_bytes(), object_pairs_hook=unique)


def checked(item):
    path = regular(item['path'])
    if (not re.fullmatch('[0-9a-f]{64}', item['sha256']) or sha(path) != item['sha256']
            or ('bytes' in item and path.stat().st_size != item['bytes'])):
        raise ValueError(f'Source SHA/size mismatch: {path}')
    return path


def pe_imports(path):
    """Read PE32/PE32+ import names directly; delay imports are unsupported."""
    data = regular(path).read_bytes()
    try:
        pe = struct.unpack_from('<I', data, 60)[0]
        if data[:2] != b'MZ' or data[pe:pe + 4] != b'PE\0\0':
            raise ValueError('Executable is not PE')
        count = struct.unpack_from('<H', data, pe + 6)[0]
        optional_size = struct.unpack_from('<H', data, pe + 20)[0]
        optional = pe + 24
        magic = struct.unpack_from('<H', data, optional)[0]
        if magic not in (0x10b, 0x20b):
            raise ValueError('Unsupported PE optional header')
        directory = optional + (112 if magic == 0x20b else 96)
        if optional_size < directory - optional + 14 * 8:
            raise ValueError('Truncated PE data directories')
        if any(struct.unpack_from('<II', data, directory + 13 * 8)):
            raise ValueError('Delay-import DLLs are unsupported')
        sections = [struct.unpack_from('<IIII', data, optional + optional_size + i * 40 + 8)
                    for i in range(count)]
        def offset(rva):
            for size, address, raw_size, raw in sections:
                if address <= rva < address + min(size, raw_size):
                    return raw + rva - address
            raise ValueError('PE import RVA outside raw sections')
        rva, size = struct.unpack_from('<II', data, directory + 8)
        if not rva or size < 20:
            raise ValueError('PE import table is missing')
        names = []
        for index in range(size // 20):
            entry = struct.unpack_from('<IIIII', data, offset(rva + index * 20))
            if not any(entry):
                return sorted(names)
            start = offset(entry[3])
            end = data.index(b'\0', start, min(len(data), start + 256))
            name = data[start:end].decode('ascii').lower()
            if name not in OS_DLLS:
                raise ValueError(f'Non-OS DLL dependency is unsupported: {name}')
            names.append(name)
        raise ValueError('PE import table lacks a terminator')
    except (IndexError, struct.error, UnicodeDecodeError) as error:
        raise ValueError('Malformed PE import table') from error


def package(source_tools, sumo, netconvert, provenance, tools_inventory, destination, project_root=ROOT,
            evidence=()):
    destination = Path(destination).absolute()
    allowed = Path(project_root).resolve() / '04_プログラム/output/sumo/toolchains'
    if destination.exists():
        raise ValueError('Destination already exists; preserve it and choose a new destination')
    if (not destination.resolve().is_relative_to(allowed) or destination.resolve() == allowed
            or any(p.is_symlink() or p.is_junction() for p in (destination, *destination.parents))):
        raise ValueError('Destination must be a new bundle under 04_プログラム/output/sumo/toolchains')
    raw_tools = Path(source_tools).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (raw_tools, *raw_tools.parents)):
        raise ValueError('Source tools symlinks/junctions forbidden')
    tools = raw_tools.resolve(strict=True)
    validated = {regular(path): sha(regular(path)) for path in (provenance, tools_inventory)}
    def track(item):
        path = checked(item)
        if path in validated and validated[path] != item['sha256']:
            raise ValueError('Conflicting source SHA evidence')
        validated[path] = item['sha256']
        return path
    proof = read_json(provenance)
    inventory = read_json(tools_inventory)
    if (proof.get('schema') != 'isolated_native_provenance_v1' or proof.get('role') not in ('control', 'patched')
            or proof.get('simulation_executed') is not False or proof.get('research_cli_switched') is not False
            or not proof.get('source_scope') or not proof.get('custom_version')):
        raise ValueError('Incomplete native provenance schema')
    state = proof.get('state', {})
    if (state.get('schema') != 'isolated_native_build_v1'
            or state.get('status') != 'COMPILED_VERSION_CHECKED_NOT_SIMULATED'):
        raise ValueError('Native build must be terminal and version checked')
    build_commands = [c for c in state.get('commands', []) if '--build' in c.get('command', [])
                      and '--target' in c['command'] and {'sumo', 'netconvert'} <= set(c['command'])]
    if not build_commands or build_commands[-1].get('exit_code') != 0:
        raise ValueError('Successful sumo/netconvert target build evidence required')
    if proof['role'] == 'patched' and not re.fullmatch('[0-9a-f]{64}', state.get('patch_applied_sha256', '')):
        raise ValueError('Patched build requires patch SHA')
    if proof['role'] == 'control':
        comparison = proof.get('patched_control_comparison', {})
        if (not proof.get('source_comparison') or comparison.get('configure_equal_except_source_build_paths') is not True
                or comparison.get('zlib_dependency_identical') is not True
                or set(comparison.get('flags', {})) != {'sumo', 'netconvert'}
                or not all(check.get('compiler_defines_and_flags_equal') is True
                           and check.get('link_command_equal') is True for check in comparison['flags'].values())):
            raise ValueError('Control source/flags/dependency comparison required')
    if (inventory.get('schema') != 'official_python_tools_inventory_v1'
            or inventory.get('all_official_bytes_match') is not True
            or not re.fullmatch('[0-9a-f]{40}', inventory.get('source_commit', ''))
            or Path(inventory.get('source_root', '')).resolve() != tools.parent
            or any(inventory.get(k) != [] for k in ('missing', 'mismatched', 'extra_package_files'))):
        raise ValueError('Complete official Python tools inventory required')
    if proof.get('source_commit') != inventory['source_commit']:
        raise ValueError('Native source commit differs from official tools inventory')
    sources = {}
    expected = set()
    for item in inventory['files']:
        name = item['relative_path']
        if (name not in ('AUTHORS', 'LICENSE', 'NOTICE.md') and not name.startswith(('tools/traci/', 'tools/sumolib/'))
                or '\\' in name or ':' in name or any(p in ('', '.', '..') for p in name.split('/'))):
            raise ValueError('Invalid official tools inventory path')
        path = track({'path': tools.parent / name, 'sha256': item['archive_sha256'], 'bytes': item['bytes']})
        if item['source_sha256'] != item['archive_sha256'] or name in expected:
            raise ValueError('Official source inventory mismatch/duplicate')
        expected.add(name)
        sources[name if name.startswith('tools/') else 'licenses/' + name] = path
    actual = set()
    for package_name in ('traci', 'sumolib'):
        for path in (tools / package_name).rglob('*'):
            if path.is_symlink() or path.is_junction():
                raise ValueError('Source symlinks/junctions forbidden')
            if path.is_file():
                regular(path)
                actual.add(path.relative_to(tools.parent).as_posix())
    if actual != {p for p in expected if p.startswith('tools/')} or not {
            'AUTHORS', 'LICENSE', 'NOTICE.md', 'tools/traci/__init__.py', 'tools/traci/_vehicle.py',
            'tools/sumolib/__init__.py'} <= expected:
        raise ValueError('Missing or extra source files')
    required_proof = {'cmake.exe', 'gcc.exe', 'g++.exe', 'libxerces-c.a', 'CMakeCache.txt',
                      'config.h', 'version.h', 'sumo-' + inventory['source_commit'] + '.zip'}
    if (not required_proof <= {Path(item['path']).name for item in proof.get('files', [])}
            or regular(tools_inventory) not in {Path(item['path']).resolve() for item in proof.get('files', [])}):
        raise ValueError('Compiler/config/source archive/official tools evidence required')
    archive_items = [item for item in proof['files'] if Path(item['path']).name == 'sumo-' + inventory['source_commit'] + '.zip']
    if len(archive_items) != 1:
        raise ValueError('Exactly one official source ZIP reference required')
    archive_path = track(archive_items[0])
    prefix = 'sumo-' + inventory['source_commit'] + '/'
    with zipfile.ZipFile(archive_path) as archive:
        selected = [item for item in archive.infolist() if not item.is_dir() and (
            item.filename in {prefix + p for p in ('AUTHORS', 'LICENSE', 'NOTICE.md')}
            or item.filename.startswith((prefix + 'tools/traci/', prefix + 'tools/sumolib/')))]
        if len(selected) != len(expected) or {item.filename for item in selected} != {prefix + name for name in expected}:
            raise ValueError('Official ZIP has missing/duplicate/extra Python/license members')
        for item in selected:
            relative = item.filename[len(prefix):]
            name = relative if relative.startswith('tools/') else 'licenses/' + relative
            if ((item.external_attr >> 16) & 0o170000) == 0o120000 or hashlib.sha256(archive.read(item)).hexdigest() != sha(sources[name]):
                raise ValueError('Official ZIP member differs from source bytes')
    # These are independently checked references, not proof merely because JSON exists.
    for item in proof.get('files', []) + state.get('zlib_dependency', {}).get('files', []):
        track(item)
    if not proof.get('files') or not state.get('zlib_dependency', {}).get('files'):
        raise ValueError('Compiler/source/dependency file evidence required')
    binaries = proof.get('binaries', [])
    if len(binaries) != 2:
        raise ValueError('Both native binaries must have proof')
    for name, supplied in (('sumo', sumo), ('netconvert', netconvert)):
        supplied = regular(supplied)
        matches = [item for item in binaries if Path(item['path']).resolve() == supplied]
        if len(matches) != 1:
            raise ValueError('Binary path differs from supplied provenance')
        item = matches[0]
        track(item)
        if item.get('clean_path_version_exit_code') != 0:
            raise ValueError('Clean-PATH version proof failed')
        version = track({'path': item['version_log'], 'sha256': item['version_log_sha256']})
        if proof['custom_version'] not in version.read_text(errors='strict'):
            raise ValueError('Version log does not identify the custom build')
        if pe_imports(supplied) != sorted(x.lower() for x in item.get('pe_imports', [])):
            raise ValueError('PE import proof differs from actual executable')
        sources['bin/' + name + '.exe'] = supplied
        sources['evidence/' + name + '_version.log'] = version
    sources['evidence/native_provenance.json'] = regular(provenance)
    sources['evidence/official_python_tools_inventory.json'] = regular(tools_inventory)
    # Keep metadata/configuration/log evidence verbatim; do not duplicate the
    # compiler executables, static archives or full official source ZIP.
    for index, item in enumerate(proof['files']):
        path = Path(item['path']).resolve()
        if path.suffix.lower() in ('.json', '.log', '.txt', '.h', '.py', '.patch', '.diff', '.md') and path not in sources.values():
            sources[f'evidence/build_metadata/{index:03d}_{path.name}'] = path
    for index, path in enumerate(evidence):
        path = regular(path)
        sources[f'evidence/attachments/{index:03d}_{path.name}'] = path
    for index, command in enumerate(state['commands']):
        log = regular(command['log'])
        if log.stat().st_size != command['log_bytes']:
            raise ValueError('Build log changed after observation')
        if log not in sources.values():
            sources[f'evidence/build_logs/{index:03d}_{log.name}'] = log
    hashes = {name: sha(path) for name, path in sources.items()}
    if any(sha(path) != expected for path, expected in validated.items()):
        raise ValueError('Validated source/proof changed before packaging')
    # Validation precedes creation. Any subsequent failure leaves a non-adoptable FAILED bundle.
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, source in sources.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if sha(target) != hashes[name] or sha(source) != hashes[name]:
                raise ValueError('Source or copied bytes changed during packaging')
        actual = {p.relative_to(destination).as_posix(): sha(regular(p))
                  for p in destination.rglob('*') if p.is_file()}
        if actual != hashes:
            raise ValueError('Bundle has missing or unlisted files')
        if any(sha(path) != expected for path, expected in validated.items()):
            raise ValueError('Validated source/proof changed during packaging')
        manifest = {'schema_version': 1, 'files': hashes,
                    'roles': {'sumo': 'bin/sumo.exe', 'netconvert': 'bin/netconvert.exe',
                              'traci_init': 'tools/traci/__init__.py', 'sumolib_init': 'tools/sumolib/__init__.py'},
                    'provenance': {'native_provenance': 'evidence/native_provenance.json', 'role': proof['role'],
                                   'source_commit': inventory['source_commit'], 'non_os_runtime_dlls': 0,
                                   'official_python_tools_inventory': 'evidence/official_python_tools_inventory.json'}}
        manifest_path = destination / 'toolchain.json'
        with manifest_path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        return manifest_path
    except BaseException as error:
        with (destination / 'FAILED.json').open('x', encoding='utf-8') as stream:
            json.dump({'status': 'FAILED_PRESERVED', 'error': repr(error), 'adoption_permitted': False}, stream)
        raise


def verify(manifest_path, project_root=ROOT):
    """Use actual pinned Python imports twice in this fresh process; never run SUMO."""
    sys.path.insert(0, str(Path(project_root).resolve() / '04_プログラム'))
    from scripts import jdrt_choice_toolchain as runtime
    os.environ[runtime.MANIFEST_ENV] = str(Path(manifest_path).resolve(strict=True))
    first = runtime.resolve_choice_toolchain(require_manifest=True)
    traci = runtime.load_choice_traci(first)
    before = runtime.choice_runtime_fingerprint(first, traci)
    second = runtime.resolve_choice_toolchain(require_manifest=True)
    after = runtime.choice_runtime_fingerprint(second, runtime.load_choice_traci(second))
    if first != second or before != after:
        raise ValueError('Repeated runtime resolution/import/fingerprint differs')
    return {'status': 'IMPORTS_VERIFIED_NOT_SIMULATED', 'fingerprint': after,
            'modules': {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                        if name.split('.')[0] in ('traci', 'sumolib')}, 'simulation_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('source-tools', 'sumo', 'netconvert', 'provenance', 'tools-inventory', 'destination'):
        parser.add_argument('--' + flag, type=Path)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--evidence', type=Path, action='append', default=[])
    parser.add_argument('--verify-manifest', type=Path,
                        help='Fresh process: resolve/import/fingerprint twice without simulation or bundle writes')
    args = vars(parser.parse_args())
    manifest = args.pop('verify_manifest')
    if manifest:
        if any(args[key] for key in ('source_tools', 'sumo', 'netconvert', 'provenance',
                                      'tools_inventory', 'destination', 'evidence')):
            parser.error('--verify-manifest cannot be combined with packaging inputs')
        print(json.dumps(verify(manifest, args['project_root']), ensure_ascii=False, indent=2))
        return
    if not all(args[key] for key in ('source_tools', 'sumo', 'netconvert', 'provenance', 'tools_inventory', 'destination')):
        parser.error('Packaging requires --source-tools --sumo --netconvert --provenance --tools-inventory --destination')
    print(package(**args))


if __name__ == '__main__':
    main()
