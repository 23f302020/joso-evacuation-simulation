"""Read back one finished seven-file choice record; never validate or adopt.

Run immediately after the original finish owner exits, before display edits.
This reads terminal metadata, not the underlying physical CSV streams again.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re

from choice_finish_cell import CONFIG, HOLDS, ROOT, digest, local, read, require

COMPONENTS = {'person_tables', 'candidate_tables', 'road_snapshots', 'actor_stream',
              'movement_events', 'native_logs', 'native_fixture_boundaries'}


def audit(root, run_id):
    root = Path(root).resolve()
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,40}', run_id), 'Simple existing run ID required')
    cfg = read(root / CONFIG)
    require(cfg['protocol'] == 'realtime_choice_v1' and cfg.get('registration_id'), 'Registered choice only')
    workspace = local(root, cfg['workspace'])
    operation = workspace / 'driver_logs' / (run_id + '.finish')
    state = read(operation / 'operation.json')
    require(state['run_id'] == run_id and state['status'] == 'RECORDED_VERIFIED'
            and state['record_attempted'] is True and not state['next_start_performed']
            and state['formal_record_result'] in ('RECORDED', 'ALREADY_RECORDED'), 'Finish not terminal/recorded')
    require(state['config_sha256'] == digest(root / CONFIG), 'Configuration changed since finish')
    records = [local(root, name) for name in cfg['record_files']]
    require(len(records) == len(set(records)) == 7, 'Seven distinct record files required')
    hashes = {p.relative_to(root).as_posix(): digest(p) for p in records}
    require(hashes == state['record_files_sha256'], 'Record bytes changed since finish; preserve and inspect')
    marker = '<!-- choice_record:' + run_id + ' -->'
    for path in records[:-1]:
        text = path.read_text(encoding='utf-8-sig')
        if path.name == 'context.md':
            parts = re.split(r'(?m)^<!-- AGENT_CURRENT_END -->[ \t\r]*$', text)
            require(len(parts) == 2, 'One standalone context end marker required')
            text = parts[0]
        require(text.count(marker) == 1, 'One current record marker required: ' + str(path))
    ledger = [json.loads(s) for s in records[-1].read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    require(all(row['protocol'] == cfg['protocol'] and row['registration_id'] == cfg['registration_id']
                for row in ledger), 'Foreign ledger registration')
    require(len({row['run_id'] for row in ledger}) == len(ledger)
            and len({row['cell_id'] for row in ledger}) == len(ledger), 'Duplicate ledger identity')
    require([row['cell_id'] for row in ledger] == [cell['cell_id'] for cell in cfg['cells'][:len(ledger)]],
            'Ledger is not the registered prefix')
    matching = [row for row in ledger if row['run_id'] == run_id]
    require(len(matching) == 1, 'Exactly one matching ledger row required')
    row = matching[0]
    manifest_path = workspace / 'runs' / run_id / 'manifest.json'
    manifest = read(manifest_path)
    require(manifest['run_id'] == run_id and manifest['purpose'] == row['purpose'] == 'core'
            and manifest['protocol'] == cfg['protocol'] and manifest['registration_id'] == cfg['registration_id']
            and manifest['status'] == 'COMPLETED' and manifest['cell_id'] == row['cell_id'], 'Core identity differs')
    require(digest(manifest_path) == row['manifest_sha256'], 'Manifest bytes differ')
    require(manifest['parameter_sha256'] == digest(root / CONFIG), 'Manifest configuration differs')
    implementation = row['implementation_sha256']
    require(implementation == manifest['implementation_sha256'] and len(implementation) == 5
            and all(digest(local(root, p)) == h for p, h in implementation.items()), 'Current common-five differs')
    input_manifest = local(root, manifest['input_directory']) / 'manifest.json'
    require(digest(input_manifest) == manifest['input_manifest_sha256'] == row['input_manifest_sha256'],
            'Input manifest differs')
    original_path = local(root, read(operation / 'validate.stdout.log')['validation_report'])
    formal_path = local(root, row['validation_report'])
    require(digest(original_path) == state['validation_report_sha256']
            and digest(formal_path) == row['validation_report_sha256'], 'Validation report bytes differ')
    original, formal = read(original_path), read(formal_path)
    for report in (original, formal):
        require(report['run_id'] == run_id and report['purpose'] == 'core' and report['status'] == 'PASS'
                and report['core_adoption_permitted'] is True and row['validation_status'] == 'PASS',
                'Adoptable independent/formal PASS required')
        require(report['manifest_sha256'] == row['manifest_sha256']
                and report['parameter_sha256'] == manifest['parameter_sha256']
                and report['input_manifest_sha256'] == manifest['input_manifest_sha256']
                and report['implementation_sha256'] == implementation, 'Report input/source identity differs')
        require(set(report['components']) == COMPONENTS
                and all(v['status'] == 'PASS' for v in report['components'].values()), 'Seven PASS components required')
    require(original['components'] == formal['components'], 'Independent and record components differ')
    recorded = read(operation / 'record.stdout.log')
    require(recorded['run_id'] == run_id and recorded['status'] == state['formal_record_result'],
            'Dedicated record result differs')
    transactions = list((workspace / 'record_transactions').glob(run_id + '_*/journal.json'))
    require(len(transactions) == 1, 'Exactly one record transaction required')
    journal = read(transactions[0])
    require(journal['run_id'] == run_id and journal['status'] == 'COMMITTED'
            and journal['sha256_after'] == hashes, 'Committed seven-file journal differs')
    if 'transaction' in recorded:
        require(local(root, recorded['transaction']) == transactions[0].parent, 'Dedicated transaction differs')
    status = read(operation / 'status.stdout.log')
    require(status['recorded_cells'] == len(ledger) and not any(status[k] for k in HOLDS),
            'Finish status retains a hold')
    return {'at_jst': datetime.now().astimezone().isoformat(), 'status': 'RECORD7_PRIMARY_READBACK_PASS',
            'scope': 'terminal_metadata_only_not_new_physics_validation_or_live_start_permission',
            'run_id': run_id, 'registration_id': cfg['registration_id'], 'recorded_cells': len(ledger),
            'record_files_sha256': hashes, 'six_document_single_markers': True,
            'unique_current_registration_ledger': True, 'formal_row': row,
            'original_independent_report': original_path.relative_to(root).as_posix(),
            'original_independent_report_sha256': digest(original_path),
            'formal_report_sha256': digest(formal_path), 'original_and_record_validation_components_differ': [],
            'transaction': transactions[0].relative_to(root).as_posix(), 'transaction_sha256': digest(transactions[0]),
            'finish_operation': (operation / 'operation.json').relative_to(root).as_posix(),
            'finish_operation_sha256': digest(operation / 'operation.json'), 'source_common5_current': True,
            'all_status_holds_clear_at_finish': True, 'next_cell': status['next_cell'], 'next_start_performed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True, help='Fresh metadata report; existing paths refused')
    args = parser.parse_args()
    result = audit(args.project_root, args.run_id)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'run_id', 'recorded_cells', 'next_cell')}, ensure_ascii=False))
