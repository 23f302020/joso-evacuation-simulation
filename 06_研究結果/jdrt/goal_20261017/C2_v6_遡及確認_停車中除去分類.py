"""C2 v6 retroactive invariance check (read-only; not part of the common five).

Applies the v5 native-log classifier (git HEAD bytes of the validator) and the
working-tree v6 candidate to every choice-series output on this PC.

* Every output whose sumo_errors.log has no `aborts stop` line is unchanged by
  construction: the v6 edit is confined to the `aborts stop` branch (and adds
  one receipt key). Those are counted by a log scan only.
* Every output with an `aborts stop` or `skips stop` line, and every v5
  technical fixture, is re-audited with both rules (actor stream + native logs).

It never writes into run folders, the record files or any operations log. The
only output is the JSON named by --output (default: next to this script).
"""
import argparse
import hashlib
import json
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / '04_プログラム/scripts/jdrt_realtime_choice_validate.py'
EXPERIMENTS = ROOT / '04_プログラム/output/sumo/regions/08211/experiments'
ABORT, SKIP = 'aborts stop', 'skips stop'


def load_versions():
    sys.path.insert(0, str(ROOT / '04_プログラム'))
    from scripts import jdrt_realtime_choice_validate as new
    blob = subprocess.run(['git', 'show', 'HEAD:04_プログラム/scripts/jdrt_realtime_choice_validate.py'],
                          cwd=ROOT, capture_output=True, check=True).stdout
    old = types.ModuleType('validate_v5_head')
    old.__file__ = str(VALIDATOR)  # ROOT resolution only; bytes come from HEAD.
    exec(compile(blob.decode('utf-8'), 'HEAD:jdrt_realtime_choice_validate.py', 'exec'), old.__dict__)
    crlf = hashlib.sha256(blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest()
    return old, new, crlf, hashlib.sha256(VALIDATOR.read_bytes()).hexdigest()


def native_status(module, folder):
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    cfg = json.loads((ROOT / manifest['parameter_path']).read_text(encoding='utf-8'))
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    actor = module.audit_actor_stream(folder, manifest, cfg, events)
    try:
        movement = module.audit_movement_events(folder, manifest, cfg, events)
    except Exception:  # Older outputs may predate movement receipts; walking warnings absent then.
        movement = None
    report = module.audit_native_logs(folder, manifest, events, actor, movement)
    return {'status': report['status'], 'unknown': report['unknown'],
            'classified': sorted((c['raw'], c.get('classification', 'legacy')) for c in report['classified_warnings'])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).with_name('C2_v6_遡及確認_結果_20261121.json'))
    args = parser.parse_args()
    old, new, v5_sha, v6_sha = load_versions()
    logs = sorted(p for w in EXPERIMENTS.glob('jdrt_realtime_choice_*')
                  for p in w.rglob('sumo_errors.log') if 'implementation' not in p.parts)
    rows, scanned = [], 0
    for log in logs:
        folder = log.parent
        text = log.read_text(encoding='utf-8', errors='replace')
        relevant = ABORT in text or SKIP in text
        v5_fixture = 'stopindex_v5' in folder.as_posix() and '/technical/' in folder.as_posix()
        if not relevant and not v5_fixture:
            scanned += 1
            continue
        row = {'folder': folder.relative_to(ROOT).as_posix(), 'aborts_lines': text.count(ABORT),
               'skips_lines': text.count(SKIP)}
        for name, module in (('v5', old), ('v6', new)):
            try:
                row[name] = native_status(module, folder)
            except Exception as error:
                row[name] = {'status': 'NOT_EVALUABLE', 'error': f'{type(error).__name__}: {error}'[:300]}
        a, b = row['v5'], row['v6']
        row['changed'] = (a['status'] != b['status'] or a.get('unknown') != b.get('unknown')
                          or [c[0] for c in a.get('classified', [])] != [c[0] for c in b.get('classified', [])])
        rows.append(row)
    result = {'at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'v5_validator_sha256_crlf': v5_sha, 'v6_candidate_validator_sha256': v6_sha,
              'log_scan_only_unchanged_by_construction': scanned, 'fully_reaudited': len(rows),
              'changed': [r['folder'] for r in rows if r['changed']],
              'not_evaluable': [r['folder'] for r in rows if 'NOT_EVALUABLE' in (r['v5']['status'], r['v6']['status'])],
              'ss261119a25': 'not on this PC (school PC only): unconfirmed here', 'rows': rows}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))
    for r in rows:
        print(r['folder'].split('experiments/')[-1], r['aborts_lines'], r['skips_lines'],
              r['v5']['status'], r['v6']['status'], 'CHANGED' if r['changed'] else '')


if __name__ == '__main__':
    main()
