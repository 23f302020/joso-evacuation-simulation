"""Build one observation-only native object and relink to a fresh diagnostic exe.

The original source, object libraries, bundle and runtime selector are read-only.
This executable is never a research toolchain or READY prerequisite.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def instrument(raw):
    marker = b'    if (hasDeparted() && stop.edge > myRoute->begin()) {'
    if raw.count(marker) != 1 or b'JDRT_STOP_INDEX' in raw:
        raise ValueError('Expected exactly one setSkips entry')
    trace = b'''    std::cerr << "JDRT_STOP_INDEX time=" << SIMTIME << " veh=" << getID()
        << " route_size=" << myRoute->getEdges().size()
        << " current_index=" << (myCurrEdge - myRoute->begin())
        << " stop_index=" << (stop.edge - myRoute->begin())
        << " active_prior=" << prevActiveStops
        << " past_count=" << myPastStops.size();
    if (!myPastStops.empty()) {
        std::cerr << " past_index=" << myPastStops.back().routeIndex
            << " past_edge=" << myPastStops.back().edge;
    }
    std::cerr << std::endl;
'''.replace(b'\n', b'\r\n' if b'\r\n' in raw else b'\n')
    return raw.replace(marker, trace + marker)


def build(root, output, remap_past_stops=False):
    root, output = root.resolve(), output.resolve()
    bundle = root / '04_プログラム/output/sumo/toolchains/native_lat_20261020a'
    provenance = json.loads((bundle / 'evidence/native_provenance.json').read_bytes())
    original = Path(next(x['path'] for x in provenance['binaries'] if Path(x['path']).name == 'sumo.exe'))
    if digest(original) != digest(bundle / 'bin/sumo.exe'):
        raise ValueError('Original build does not match selected bundle')
    original_build = original.parent.parent
    source = Path(provenance['state']['visible_staging']) / 'sources' / ('sumo-' + provenance['source_commit']) / 'src/microsim/MSBaseVehicle.cpp'
    if output.exists() or output.is_relative_to(original_build) or output.is_relative_to(bundle):
        raise ValueError('Need unused isolated output outside original build and bundle')
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'purpose': ('ISOLATED_STOP_INDEX_REPAIR_CANDIDATE_NOT_ADOPTION' if remap_past_stops
                           else 'OBSERVATION_ONLY_NOT_ADOPTION'), 'status': 'BUILDING',
               'started_at_jst': datetime.now().astimezone().isoformat(),
               'pid': __import__('os').getpid(), 'core_adoption_permitted': False,
               'technical_ready': False, 'original_exe_sha256': digest(original),
               'original_source': str(source), 'original_source_sha256': digest(source),
               'helper_sha256': digest(__file__), 'commands': []}
    # Match the existing native build's process-local compiler environment.
    env = os.environ.copy()
    env['PATH'] = 'C:/Ruby31-x64/msys64/ucrt64/bin;C:/Windows/System32;C:/Windows'
    for key in ('SUMO_HOME', 'SUMO_LIBRARIES', 'CMAKE_PREFIX_PATH', 'CC', 'CXX',
                'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'INCLUDE', 'LIB'):
        env.pop(key, None)
    def save():
        (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    def run(label, args, cwd):
        with (output / (label+'.stdout.log')).open('xb') as out, (output / (label+'.stderr.log')).open('xb') as err:
            item = {'label': label, 'args': [str(x) for x in args], 'cwd': str(cwd)}
            child = subprocess.Popen(item['args'], cwd=cwd, env=env, stdout=out, stderr=err)
            item['pid'] = child.pid
            receipt['commands'].append(item)
            save()
            item['exit_code'] = child.wait()
            save()
        if item['exit_code']:
            raise RuntimeError(label+' failed; original logs preserved')
    try:
        target = output / 'MSBaseVehicle.cpp'
        candidate = source.read_bytes()
        if remap_past_stops:
            from choice_native_stop_index_remap import remap_source
            patch_helper = Path(__file__).with_name('choice_native_stop_index_remap.py')
            receipt['candidate_helper_sha256'] = digest(patch_helper)
            candidate = remap_source(candidate)
        target.write_bytes(instrument(candidate))
        (output / 'MSBaseVehicle.original.cpp').write_bytes(source.read_bytes())
        receipt['diagnostic_source_sha256'] = digest(target)
        old = original_build / 'src'
        micro = old / 'microsim'
        flags_path = micro / 'CMakeFiles/microsim.dir/flags.make'
        flags = dict(line.split(' = ',1) for line in flags_path.read_text().splitlines() if ' = ' in line)
        includes = micro / 'CMakeFiles/microsim.dir/includes_CXX.rsp'
        compiler = Path('C:/Ruby31-x64/msys64/ucrt64/bin/g++.exe')
        ar = compiler.with_name('ar.exe')
        original_lib = micro / 'libmicrosim.a'
        libs_rsp = old / 'CMakeFiles/sumo.dir/linkLibs.rsp'
        objects = old / 'CMakeFiles/sumo.dir/objects.a'
        lib_args = shlex.split(libs_rsp.read_text())
        paths = [source, original, flags_path, includes, objects, compiler, ar, libs_rsp]
        paths += [(old / x).resolve() for x in lib_args if x.endswith('.a')]
        receipt['original_inputs_sha256'] = {str(p): digest(p) for p in paths}
        save()
        obj = output / 'MSBaseVehicle.cpp.obj'
        run('compile', [compiler, *shlex.split(flags['CXX_DEFINES']), '@'+str(includes),
                        '-I'+str(source.parent), *shlex.split(flags['CXX_FLAGS']), '-c', target, '-o', obj], micro)
        lib = output / 'libmicrosim.a'
        shutil.copyfile(original_lib, lib)
        run('archive', [ar, 'r', lib, obj], output)
        if lib_args.count('microsim/libmicrosim.a') != 1:
            raise ValueError('Expected unique original microsim library')
        lib_args[lib_args.index('microsim/libmicrosim.a')] = str(lib)
        exe = output / 'sumo-stop-index-diagnostic.exe'
        run('link', [compiler, *[x for x in shlex.split(flags['CXX_FLAGS']) if not x.startswith('-std=')],
                     '-static','-static-libgcc','-static-libstdc++','-Wl,--whole-archive',objects,
                     '-Wl,--no-whole-archive','-o',exe,'-Wl,--out-implib,'+str(output/'libsumo.dll.a'),
                     '-Wl,--major-image-version,0,--minor-image-version,0', *lib_args], old)
        for name, expected in receipt['original_inputs_sha256'].items():
            if digest(name) != expected:
                raise ValueError('Original input changed: '+name)
        receipt.update(status='COMPILED_NOT_SIMULATED_NOT_READY', binary=str(exe), binary_sha256=digest(exe),
                       original_inputs_unchanged=True, finished_at_jst=datetime.now().astimezone().isoformat())
        save()
        print(json.dumps({'status':receipt['status'], 'receipt':str(output/'receipt.json')}))
    except BaseException as error:
        receipt.update(status='FAILED_PRESERVED', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--remap-past-stops', action='store_true', help='Isolated repair candidate only; never READY')
    args = parser.parse_args()
    build(args.project_root, args.output, args.remap_past_stops)
