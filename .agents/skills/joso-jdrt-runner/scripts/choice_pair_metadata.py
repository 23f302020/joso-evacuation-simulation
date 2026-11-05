"""Compare paired native build metadata; this does not verify native behavior."""
import re
from pathlib import Path, PureWindowsPath

FILES = ('CMakeCache.txt', 'src/config.h', *(f'src/CMakeFiles/{target}.dir/{name}'
          for target in ('sumo', 'netconvert')
          for name in ('flags.make', 'includes_CXX.rsp', 'link.txt', 'linkLibs.rsp')))


COMPILERS = {'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER'}
PYTHON_REASON = '_Python_Interpreter_REASON_FAILURE'


def normalizer(roots):
    if len(roots) != 2 or any(not PureWindowsPath(root).is_absolute() for root in roots):
        raise ValueError('Two absolute Windows source/build roots required')
    replacements = {}
    for root, token in zip(roots, ('<SOURCE>', '<BUILD>')):
        for value in {str(root), str(Path(root).resolve())}:
            for spelling in {value.replace('\\', '/'), value.replace('/', '\\')}:
                replacements[spelling] = token

    def normalized(text):
        for spelling in sorted(replacements, key=len, reverse=True):
            pattern = re.escape(spelling) + r'''(?=$|[/\\\s"';)])'''
            text = re.sub(pattern, lambda match: replacements[spelling], text, flags=re.I)
        return text.replace('\r\n', '\n')
    return normalized


def cache_entries(text):
    values = {}
    for line in text.splitlines():
        if not line or line.startswith(('#', '//')):
            continue
        match = re.fullmatch(r'([^:=]+):([^=]+)=(.*)', line)
        if not match or match[1] in values:
            raise ValueError('Malformed or duplicate CMake cache entry')
        values[match[1]] = (match[2], match[3])
    if not COMPILERS <= set(values):
        raise ValueError('Both compiler cache entries are required')
    return values


def compare_metadata(patched, control, patched_roots, control_roots):
    """Require every metadata file; preserve non-path flags, values and types."""
    if (set(patched) != set(FILES) or set(control) != set(FILES)
            or any(not isinstance(text, str) for table in (patched, control) for text in table.values())):
        raise ValueError('Complete paired native metadata required')
    normalize = {'patched': normalizer(patched_roots), 'control': normalizer(control_roots)}
    tables = {'patched': patched, 'control': control}
    raw_cache = {role: cache_entries(table['CMakeCache.txt']) for role, table in tables.items()}
    native_only = all(table.get('ENABLE_PYTHON_BINDINGS') == ('BOOL', 'OFF') for table in raw_cache.values())
    effective = {}
    for role, entries in raw_cache.items():
        effective[role] = {}
        for name, (cache_type, value) in entries.items():
            if name in COMPILERS:
                path = PureWindowsPath(value)
                if cache_type not in ('STRING', 'FILEPATH', 'UNINITIALIZED') or not path.is_absolute():
                    raise ValueError('Compiler cache entry must be an absolute path with a path-compatible type')
                effective[role][name] = ('COMPILER_PATH', path.as_posix().casefold())
            elif name == PYTHON_REASON and value == '' and native_only:
                continue
            else:
                effective[role][name] = (cache_type, normalize[role](value))
    cache_differences = sorted(name for name in set(effective['patched']) | set(effective['control'])
                               if effective['patched'].get(name) != effective['control'].get(name))
    different = ['CMakeCache.txt'] if cache_differences else []
    for name in FILES[1:]:
        if normalize['patched'](patched[name]) != normalize['control'](control[name]):
            different.append(name)
    representations = sorted(name for name in set(raw_cache['patched']) | set(raw_cache['control'])
                             if raw_cache['patched'].get(name) != raw_cache['control'].get(name)
                             and effective['patched'].get(name) == effective['control'].get(name))
    return {'equal': not different, 'different_files': different,
            'effective_cache_difference_keys': cache_differences,
            'equivalent_cache_representation_keys': representations,
            'compiler_files_and_executables_verified': False, 'native_behavior_verified': False}
