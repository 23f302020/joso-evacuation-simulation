"""Input-only registered theoretical quantities. Never opens experiment runs."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).parent


def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    helper = BASE / 'G6_副指標・理論上限_集計.py'
    spec = importlib.util.spec_from_file_location('choice_input_theory', helper)
    secondary = importlib.util.module_from_spec(spec); spec.loader.exec_module(secondary)
    config = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'
    cfg = json.loads(config.read_text(encoding='utf-8'))
    inputs = ROOT / cfg['workspace'] / cfg['input_directory']
    manifest_path = inputs / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    proof_path = BASE / 'G6_副指標・理論上限_実装証跡.json'
    proof = json.loads(proof_path.read_text(encoding='utf-8-sig'))
    names = ['people.csv', 'terminals.csv'] + ['destinations_' + d + '.csv' for d in cfg['destination_policies']]
    names += ['common_realization_seed' + str(seed) + '.csv' for seed in cfg['seeds']]
    bound = {inputs / name: manifest['artifacts'][name] for name in names}
    bound.update({ROOT / name: value for name, value in proof['implementation_sha256'].items()})
    bound.update({manifest_path: digest(manifest_path), config: digest(config), helper: digest(helper), proof_path: digest(proof_path)})
    secondary.require(all(digest(path) == expected for path, expected in bound.items()), 'Input/source proof SHA mismatch')
    people = list(secondary.rows(inputs / 'people.csv'))
    terminals = {r['terminal_id']: r for r in secondary.rows(inputs / 'terminals.csv')}
    bounds = {d: secondary.structural_bounds(people, list(secondary.rows(inputs / ('destinations_' + d + '.csv'))),
        terminals, cfg['population']['walk_limit_m']) for d in cfg['destination_policies']}
    offered = []
    for seed in cfg['seeds']:
        realization = list(secondary.rows(inputs / ('common_realization_seed' + str(seed) + '.csv')))
        secondary.require({p['person_id'] for p in realization} == {p['person_id'] for p in people}, 'Realization population mismatch')
        offered.extend({'seed': seed, **secondary.workload(realization, demand, cfg)} for demand in cfg['demand_levels'])
    op = cfg['operation']
    conditions = proof['conditions']
    secondary.require(not op['pooling'] and all(conditions.values()), 'Frozen service assumptions unestablished')
    upper = secondary.service_bound(cfg['simulation']['duration_sec'], [0] * op['fleet_count'],
        op['boarding_sec'], op['alighting_sec'], initially_empty=conditions['initially_empty'],
        serial_one_person=conditions['serial_one_person'])
    secondary.require(all(digest(path) == expected for path, expected in bound.items()), 'Input/source proof changed during calculation')
    now = datetime.now(timezone(timedelta(hours=9)))
    output = {'status': 'INPUT_ONLY_THEORY_NOT_RESEARCH_RESULT', 'observed_at': now.isoformat(),
        'scope': 'PAP section 7 fixed assignment capacity, offered service workload and conditional serial DRT upper bound',
        'people': len(people), 'type4_denominator': sum(p['person_type'] == 'type4' for p in people),
        'facility_bounds': bounds, 'offered_request_workloads': offered,
        'serial_drt_completion_upper': upper, 'service_contract_conditions': conditions,
        'limitations': ['Capacity bound counts all assigned Type4, keeps disconnected people and shares facility capacity with other modes; no attainment guarantee',
            'rho uses offered intent including rejected connections; not utilization or feasibility',
            'Direct DRT admitted <= served <= service upper; not a Type4 or population improvement bound',
            'No accepted core results, method comparisons, direction interpretation or simulation execution'],
        'sha256': {path.relative_to(ROOT).as_posix(): expected for path, expected in bound.items()}}
    target = BASE / ('G6_登録入力_理論値確認_' + now.strftime('%Y%m%dT%H%M%S%f') + '.json')
    with target.open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({'path': target.name, 'status': output['status'], 'type4_denominator': output['type4_denominator'],
        'serial_drt_completion_upper': upper, 'offered': [{'seed': r['seed'], 'u': r['demand_level'],
            'N': r['intended_requests'], 'rho': r['rho_service_only']} for r in offered]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
