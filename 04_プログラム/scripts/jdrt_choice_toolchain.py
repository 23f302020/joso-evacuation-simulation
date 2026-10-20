"""Process-local, fail-closed runtime selection for choice technical/core runs."""
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

from scripts.jdrt.smoke import load_traci, resolve_sumo_binary

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_ENV = 'JDRT_CHOICE_TOOLCHAIN_MANIFEST'
ROLES = {'sumo', 'netconvert', 'traci_init', 'sumolib_init'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _relative_file(root, name):
    relative = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or relative.is_absolute()
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('Toolchain paths must be canonical bundle-relative POSIX paths')
    path = root.joinpath(*relative.parts)
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
        raise ValueError('Toolchain symlinks are forbidden')
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('Toolchain file is missing or outside its bundle')
    return path.resolve()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate toolchain manifest key')
        result[key] = value
    return result


def resolve_choice_toolchain(*, require_manifest=False):
    """Only absence of the selector permits legacy installed-toolchain discovery."""
    if MANIFEST_ENV not in os.environ:
        if require_manifest:
            raise ValueError('Choice core/READY requires an explicit pinned toolchain manifest')
        binary = resolve_sumo_binary()
        return {'sumo': binary, 'netconvert': binary.parent / 'netconvert.exe'}
    selected = os.environ[MANIFEST_ENV]
    if not selected.strip():
        raise ValueError('Explicit choice toolchain manifest is empty')
    if Path(selected).is_symlink():
        raise ValueError('Toolchain manifest symlinks are forbidden')
    manifest_path = Path(selected).resolve(strict=True)
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'files', 'roles', 'provenance'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or not isinstance(manifest['files'], dict)
            or not manifest['files'] or not isinstance(manifest['roles'], dict)
            or set(manifest['roles']) != ROLES or not isinstance(manifest['provenance'], dict)
            or not manifest['provenance']):
        raise ValueError('Invalid choice toolchain manifest schema')
    root = manifest_path.parent
    paths = {}
    for name, expected in manifest['files'].items():
        if not isinstance(name, str) or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('Invalid toolchain file hash')
        path = _relative_file(root, name)
        if path == manifest_path or path.suffix.lower() in ('.pyc', '.pyo'):
            raise ValueError('Manifest and Python bytecode cannot be controlled runtime files')
        if sha(path) != expected:
            raise ValueError(f'Toolchain SHA mismatch: {name}')
        paths[name] = path
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Toolchain symlinks are forbidden')
        if path.is_file() and path != manifest_path:
            actual.add(path.relative_to(root).as_posix())
    if actual != set(paths):
        raise ValueError('Toolchain bundle contains missing or unlisted files')
    if not all(isinstance(name, str) and name in paths for name in manifest['roles'].values()):
        raise ValueError('Toolchain role is not bound to a controlled file')
    roles = {role: paths[name] for role, name in manifest['roles'].items()}
    for package in ('traci', 'sumolib'):
        if roles[package + '_init'].name != '__init__.py' or roles[package + '_init'].parent.name != package:
            raise ValueError('Toolchain Python roles must name package __init__.py files')
    if roles['traci_init'].parent.parent != roles['sumolib_init'].parent.parent:
        raise ValueError('Toolchain Python packages must share one tools directory')
    return {**roles, 'manifest_path': manifest_path, 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'files': manifest['files'], 'roles': manifest['roles'], 'provenance': manifest['provenance'], 'root': root}


def _check_loaded_modules(selection):
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('traci', 'sumolib'):
            path = Path(getattr(module, '__file__', '')).resolve()
            if (not path.is_relative_to(selection['root'])
                    or path.relative_to(selection['root']).as_posix() not in selection['files']
                    or sha(path) != selection['files'][path.relative_to(selection['root']).as_posix()]):
                raise ValueError(f'Loaded Python module is outside pinned toolchain: {name}')
    for package in ('traci', 'sumolib'):
        if package in sys.modules and Path(sys.modules[package].__file__).resolve() != selection[package + '_init']:
            raise ValueError(f'Loaded Python package differs from selected role: {package}')


def load_choice_traci(selection):
    if 'manifest_path' not in selection:
        return load_traci(selection['sumo'])
    _check_loaded_modules(selection)
    tools = str(selection['traci_init'].parent.parent)
    sys.path.insert(0, tools)
    try:
        # Later lazy imports must also leave the immutable bundle byte-for-byte intact.
        sys.dont_write_bytecode = True
        traci = importlib.import_module('traci')
        importlib.import_module('sumolib')
    finally:
        sys.path.remove(tools)
    _check_loaded_modules(selection)
    return traci


def choice_runtime_fingerprint(selection=None, traci=None):
    selection = resolve_choice_toolchain() if selection is None else selection
    traci = load_choice_traci(selection) if traci is None else traci
    result = {'sumo_binary': sha(selection['sumo']), 'traci_init': sha(Path(traci.__file__)),
              'traci_vehicle': sha(Path(traci.__file__).parent / '_vehicle.py'),
              'shared_smoke': sha(ROOT / '04_プログラム/scripts/jdrt/smoke.py'),
              'shared_log_parser': sha(ROOT / '04_プログラム/scripts/jdrt/full_run.py'),
              'choice_toolchain_helper': sha(Path(__file__))}
    if 'manifest_path' in selection:
        current = resolve_choice_toolchain()
        if current != selection:
            raise ValueError('Choice toolchain selection changed after resolution')
        _check_loaded_modules(selection)
        result.update(toolchain_manifest_sha256=selection['manifest_sha256'],
                      toolchain_manifest_path=str(selection['manifest_path']),
                      toolchain_files_sha256=dict(selection['files']), toolchain_roles=dict(selection['roles']),
                      toolchain_provenance=dict(selection['provenance']),
                      sumo_binary_path=str(selection['sumo']), netconvert_binary_path=str(selection['netconvert']))
    return result
