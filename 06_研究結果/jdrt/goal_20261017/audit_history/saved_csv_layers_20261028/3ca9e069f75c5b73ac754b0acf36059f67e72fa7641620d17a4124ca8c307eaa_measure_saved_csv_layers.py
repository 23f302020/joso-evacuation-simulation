"""Time read-only SHA, gzip and CSV layers of an accepted current choice core.

This is a component probe, never a validator, adoption operation or speedup test.
"""
import argparse
import csv
from datetime import datetime
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

CONFIG = '04_プログラム/config/jdrt_realtime_choice_v1.json'
GOAL = '06_研究結果/jdrt/goal_20261017'
VERIFICATION = '07_監視システム/verification'


def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def timed(action):
    wall, cpu = time.perf_counter(), time.process_time()
    value = action()
    return value, time.perf_counter() - wall, time.process_time() - cpu


def expanded_size(path):
    with gzip.open(path, 'rb') as stream:
        return sum(len(block) for block in iter(lambda: stream.read(1024 * 1024), b''))


def csv_rows(path):
    # The first RED deliberately leaves CSV iteration unimplemented.
    return 0


def run(root, run_id, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if not any(output.is_relative_to(root / parent) for parent in (GOAL, VERIFICATION)):
        raise ValueError('Output must be new goal/verification evidence')
    if not run_id or Path(run_id).name != run_id or any(x in run_id for x in ('/', '\\', ':')):
        raise ValueError('Simple run ID required')
    cfg_path = root / CONFIG
    cfg_raw = cfg_path.read_bytes()
    cfg = json.loads(cfg_raw)
    if cfg['protocol'] != 'realtime_choice_v1' or cfg['municipality_code'] != '08211':
        raise ValueError('Current Joso choice registration required')
    workspace = (root / cfg['workspace']).resolve()
    ledger_path = (root / cfg['record_files'][-1]).resolve()
    if not workspace.is_relative_to(root) or not ledger_path.is_relative_to(root):
        raise ValueError('Config path escapes project')
    ledger_raw = ledger_path.read_bytes()
    accepted = [json.loads(line) for line in ledger_raw.decode('utf-8-sig').splitlines() if line.strip()]
    rows = [row for row in accepted if row.get('run_id') == run_id]
    if (len(rows) != 1 or rows[0].get('registration_id') != cfg['registration_id']
            or rows[0].get('validation_status') != 'PASS'):
        raise ValueError('One current accepted ledger row required')
    folder = workspace / 'runs' / run_id
    manifest_path = folder / 'manifest.json'
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if (manifest['status'] != 'COMPLETED' or manifest['purpose'] != 'core'
            or manifest['run_id'] != run_id or manifest['registration_id'] != cfg['registration_id']
            or rows[0]['manifest_sha256'] != sha256(raw).hexdigest()):
        raise ValueError('Completed accepted manifest required')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as receipt:
        report = {'status': 'RUNNING', 'run_id': run_id, 'registration_id': cfg['registration_id'],
                  'scope': 'read_only_component_timing_not_validation_or_adoption',
                  'started_at_jst': datetime.now().astimezone().isoformat(),
                  'helper_sha256': digest(Path(__file__)), 'python_version': sys.version,
                  'manifest_sha256': sha256(raw).hexdigest(),
                  'config_sha256': sha256(cfg_raw).hexdigest(),
                  'ledger_snapshot_sha256': sha256(ledger_raw).hexdigest(), 'files': [],
                  'limits': ['One sequential warm-cache probe; concurrent work may affect time.',
                             'CSV iteration excludes numeric conversion and research accounting.',
                             'These layers do not exactly partition validator time or prove speedup.',
                             'Ledger snapshot binds an accepted row, not live adoption permission.']}
        try:
            for name, expected in manifest['output_sha256'].items():
                path = folder / name
                if not name or Path(name).name != name or not path.resolve().is_relative_to(folder.resolve()):
                    raise ValueError('Artifact path escapes run')
                value, wall, cpu = timed(lambda: digest(path))
                if value != expected:
                    raise ValueError('Artifact SHA mismatch: ' + name)
                row = {'name': name, 'bytes': path.stat().st_size, 'sha256': value,
                       'hash_wall_sec': wall, 'hash_cpu_sec': cpu}
                if name.endswith('.gz'):
                    count, wall, cpu = timed(lambda: expanded_size(path))
                    row.update(gzip_expanded_bytes=count, gzip_wall_sec=wall, gzip_cpu_sec=cpu)
                if name.endswith(('.csv', '.csv.gz')):
                    count, wall, cpu = timed(lambda: csv_rows(path))
                    row.update(csv_rows=count, csv_wall_sec=wall, csv_cpu_sec=cpu)
                if digest(path) != expected:
                    raise ValueError('Artifact changed during component probe: ' + name)
                report['files'].append(row)
            if manifest_path.read_bytes() != raw or cfg_path.read_bytes() != cfg_raw:
                raise ValueError('Manifest/config changed during component probe')
            report['status'] = 'COMPONENT_TIMING_ONLY'
        except BaseException as error:
            report.update(status='FAILED_PRESERVED', error_type=type(error).__name__, error=str(error))
            raise
        finally:
            report['finished_at_jst'] = datetime.now().astimezone().isoformat()
            receipt.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.project_root, args.run_id, args.output)
    print(json.dumps({'status': result['status'], 'files': len(result['files'])}))
