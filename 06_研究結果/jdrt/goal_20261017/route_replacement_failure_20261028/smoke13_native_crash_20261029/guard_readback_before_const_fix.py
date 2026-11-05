"""Independent readback of a complete native guard collection; never grants READY."""
import argparse
import collections
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

import choice_native_guard_audit as audit
import choice_native_guard_plan as planner
import choice_native_trace_check as trace


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_files(folder, hashes):
    require(set(hashes) == {p.name for p in folder.iterdir() if p.is_file()},
            'Primary artifact file set differs')
    for name, expected in hashes.items():
        require(Path(name).name == name and sha(folder / name) == expected,
                'Primary artifact bytes differ: ' + name)
    return len(hashes)


def pair_entries(entries, case_ids):
    require(case_ids and len(case_ids) == len(set(case_ids)), 'Empty or repeated planned cases')
    indexed = {}
    for entry in entries:
        key = (entry['case'], entry['role'])
        require(key not in indexed, 'Repeated native case/role')
        indexed[key] = entry
    expected = {(c, r) for c in case_ids for r in ('control', 'patched', 'trace')}
    require(set(indexed) == expected, 'Incomplete or foreign native case/role product')
    return indexed


def verify_scope(manifest, plan):
    require(manifest['status'] == 'COMPLETED', 'Collection has not completed')
    for key in ('research_adoption_permitted', 'technical_ready', 'native_regression_complete'):
        require(manifest[key] is False, 'Unexpected adoption or readiness flag')
    require(plan['status'] == 'PREPARED_NOT_EXECUTED'
            and plan['research_adoption_permitted'] is False, 'Wrong prepared plan scope')
    require(manifest['cases_requested'] == [c['id'] for c in plan['cases']],
            'Subset is not the complete planned collection')


def audit_run(root, base, manifests):
    manifest, plan = read(base / 'manifest.json'), read(base / 'plan.json')
    verify_scope(manifest, plan)
    entries = pair_entries(manifest['completed'], [c['id'] for c in plan['cases']])
    for name, key in [('plan.json', 'plan_sha256'), ('trace_build.json', 'trace_build_sha256'),
                      ('collection_source.py', 'collection_source_sha256')]:
        require(sha(base / name) == manifest[key], 'Collection receipt differs: ' + name)
    for path, expected in plan['sources'].items():
        require(sha(path) == expected, 'Prepared source changed: ' + path)
    for path, expected in manifest['current_implementation_sha256'].items():
        require(sha(root / path) == expected, 'Current implementation differs: ' + path)
    cfg_path = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
    require(str(cfg_path) in plan['sources'], 'Current configuration is not plan-bound')
    cfg = read(cfg_path)
    speeds = {'p3': cfg['population']['walk_mps']['type3'],
              'p4': cfg['population']['walk_mps']['type4']}
    build = read(base / 'trace_build.json')
    prep_path = Path(build['diagnostic_source']).parent / 'source_preparation.json'
    prep = read(prep_path)
    source = Path(prep['patched_source_root'])
    clock = source / 'src/utils/common/SUMOTime.h'
    units = re.findall(rb'#define STEPS2TIME\(x\) \(static_cast<double>\(x\)/(\d+\.)\)', clock.read_bytes())
    versions = re.findall(rb'^#define TRACI_VERSION\s+(\d+)\s*$',
                          (source / 'src/libsumo/TraCIConstants.h').read_bytes(), re.M)
    require(len(units) == len(versions) == 1, 'Ambiguous native clock or API version')
    constants = planner.source_constants(
        (source / 'src/microsim/transportables/MSPModel.cpp').read_bytes(),
        (source / 'src/microsim/transportables/MSStage.h').read_bytes())
    require(plan['constants'] == constants, 'Plan constants differ from native source')
    binaries = {}
    for role, path in manifests.items():
        require(plan['sources'].get(str(path)) == sha(path), 'Bundle manifest is not plan-bound')
        bundle = read(path)
        for name, expected in bundle['files'].items():
            require(sha(path.parent / name) == expected, 'Bundle bytes differ: ' + name)
        binaries[role] = path.parent / 'bin/sumo.exe'
    binaries['trace'] = Path(build['binaries'][0]['path'])
    binary_hashes = {r: sha(p) for r, p in binaries.items()}
    require(binary_hashes['trace'] == build['binaries'][0]['sha256'], 'Trace EXE differs')
    nets = [Path(p) for p in plan['sources'] if Path(p).name == 'bounded.net.xml']
    require(len(nets) == 1 and sha(base / 'bounded.net.xml') == sha(nets[0]), 'Fixture network differs')
    report = {'at_jst': datetime.now().astimezone().isoformat(), 'run_id': manifest['run_id'],
              'manifest_sha256': sha(base / 'manifest.json'), 'native_runs': len(entries),
              'native_units_per_second': float(units[0]), 'cases': [],
              'primary_artifacts_rehashed': 0, 'research_adoption_permitted': False,
              'technical_ready': False, 'native_regression_complete': False,
              'audit_source_sha256': sha(__file__), 'source_receipts': {str(prep_path): sha(prep_path)},
              'limitations': ['Finite synthetic observation, not research adoption',
                              'Pointer identity flags are native observations, not debugger address reads',
                              'Speed is longitudinal native speed, not Euclidean XY speed']}
    for name in ('src/utils/common/SUMOTime.h', 'src/libsumo/TraCIConstants.h',
                 'src/libsumo/Person.cpp', 'src/microsim/transportables/MSStageWalking.cpp',
                 'src/microsim/transportables/MSPModel.cpp', 'src/microsim/transportables/MSStage.h'):
        report['source_receipts'][str(source / name)] = sha(source / name)
    for module in (audit, planner, trace):
        report['source_receipts'][str(Path(module.__file__).resolve())] = sha(module.__file__)
    for spec in plan['cases']:
        case, data = spec['id'], {}
        require((base / case / 'routes.xml').read_bytes() == spec['routes_xml'].encode('utf-8'),
                'Synthetic routes differ: ' + case)
        for role in ('control', 'patched', 'trace'):
            entry, folder = entries[case, role], base / case / role
            require(Path(entry['output']) == folder and entry['exit_code'] == 0,
                    'Child output or exit differs')
            require(Path(entry['binary']) == binaries[role]
                    and entry['binary_sha256'] == binary_hashes[role], 'Wrong child binary')
            require(set(entry['server_endpoint_owners']) == {entry['pid']}
                    and entry['process_identity']['ProcessId'] == entry['pid']
                    and entry['process_identity']['ParentProcessId'] == manifest['pid'], 'Child owner differs')
            require(entry['api_version'][0] == int(versions[0]), 'Native API version differs')
            command = entry['command']
            expected_options = [('--net-file', str(base / 'bounded.net.xml')),
                                ('--route-files', str(base / case / 'routes.xml')),
                                ('--step-length', str(spec['step_sec'])),
                                ('--seed', str(cfg['seeds'][0])), ('--pedestrian.model', 'striping')]
            expected_options += list(zip(spec['sumo_options'][::2], spec['sumo_options'][1::2]))
            for option, expected in expected_options:
                require(command.count(option) == 1 and command[command.index(option) + 1] == expected,
                        'Native command option differs: ' + option)
            report['primary_artifacts_rehashed'] += verify_files(folder, entry['artifacts'])
            rows = [json.loads(s) for s in (folder / 'actors.jsonl').read_text().splitlines()]
            ops = [json.loads(s) for s in (folder / 'operations.jsonl').read_text().splitlines()]
            accounting = audit.actor_accounting(rows, speeds, spec['step_sec'])
            audit.position_receipts(ops, exact_target=role != 'control' and spec['operation'] != 'internal_replace')
            frames, latest = {r['time_sec']: r['actors'] for r in rows}, {}
            for op in ops:
                require(op['time_sec'] in frames, 'Operation has no same-clock frame')
                require(op['before'] == latest.get(op['time_sec'], frames[op['time_sec']]),
                        'Operation/frame linkage differs')
                latest[op['time_sec']] = op['after']
            warnings = (folder / 'native.stderr.log').read_text().splitlines()
            if case == 'internal_walk':
                require(len(warnings) == len(ops) > 0, 'Internal warning count differs')
                for line in warnings:
                    require(re.fullmatch(r"Warning: Invalid departPos [-0-9.]+ given for person '[^']+' walking from edge ':[^']+'. Using edge end instead\.", line),
                            'Unclassified internal warning')
            else:
                require(not warnings, 'Unexpected native warning: ' + repr(warnings))
            if role == 'trace':
                raw = trace.parse((folder / 'native.stdout.log').read_bytes())
                derived = [trace.derive(row, **constants) for row in raw]
                audit.link_operations(ops, raw, float(units[0]))
            normalized = [{k: v for k, v in op.items() if k not in ('trace_count_before', 'trace_count_after')}
                          for op in ops]
            data[role] = {'rows': rows, 'ops': ops, 'normalized_ops': normalized,
                          'accounting': accounting, 'warnings': warnings}
        for key in ('rows', 'normalized_ops'):
            require(data['patched'][key] == data['trace'][key], 'Trace instrumentation changed ' + key)
        result = {'id': case, 'group': spec['group'], 'raw_trace_rows': raw, 'derived_trace': derived,
                  'branches': dict(collections.Counter(x['branch'] for x in derived)),
                  'patched_trace_all_actor_rows_equal': True, 'patched_trace_all_receipts_equal': True,
                  'accounting': {r: d['accounting'] for r, d in data.items()},
                  'warnings': {r: d['warnings'] for r, d in data.items()}}
        if spec['operation'] == 'observe' or case == 'internal_walk':
            for key in ('rows', 'normalized_ops'):
                require(data['control'][key] == data['patched'][key], 'Negative case baseline differs')
            expected = ('explicit' if case == 'explicit_lateral' else 'random' if case == 'random_lateral'
                        else 'legacy' if case == 'legacy' else 'default')
            require({x['branch'] for x in derived} == {expected}, 'Negative native branch differs')
            result.update(observed_group_contract=True, control_patched_all_actor_rows_equal=True)
        elif case == 'position_mismatch':
            require(not any(r.get('position_same') == '0' or r.get('time_same') == '0' for r in raw),
                    'New mismatch path requires explicit inspection')
            result.update(observed_group_contract=False,
                          classification='UNEXERCISED_FALSE_POSITION_OR_TIME_GUARD')
        else:
            indices = audit.link_operations(data['trace']['ops'], raw, float(units[0]))
            require(indices and all(derived[i]['inherited'] for i in indices), 'Expected inheritance unobserved')
            directions = audit.next_directions(data['patched']['ops'], data['patched']['rows'])
            for op, i in zip(data['trace']['ops'], indices):
                if op['purpose'] == 'new_route':
                    require(derived[i]['new_route_direction'] == directions[op['person']], 'Native direction differs')
            result.update(observed_group_contract=True, next_nonzero_directions=directions)
        report['cases'].append(result)
    groups = {c['group'] for c in report['cases']}
    observed = {c['group'] for c in report['cases'] if c['observed_group_contract']}
    report.update(status='OBSERVED_CONTRACTS_PASS_WITH_DISCLOSED_COVERAGE',
                  groups_requested=sorted(groups), groups_observed=sorted(observed),
                  groups_unexercised=sorted(groups - observed))
    for path, expected in {**plan['sources'], **report['source_receipts']}.items():
        require(sha(path) == expected, 'Source changed during readback: ' + path)
    require(sha(base / 'manifest.json') == report['manifest_sha256'], 'Manifest changed during readback')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--control-manifest', type=Path, required=True)
    parser.add_argument('--patched-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Use a new audit output; never overwrite evidence')
    report = audit_run(args.project_root.resolve(), args.run_dir.resolve(),
                       {'control': args.control_manifest.resolve(), 'patched': args.patched_manifest.resolve()})
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: report[k] for k in ('status', 'run_id', 'native_runs',
                     'primary_artifacts_rehashed', 'groups_unexercised')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
