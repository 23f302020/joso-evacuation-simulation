"""Serial technical prerequisites; no core launch, adoption, recovery or retry."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


SCRIPTS = Path('.agents/skills/joso-jdrt-runner/scripts')
GOAL = Path('06_研究結果/jdrt/goal_20261017')
PARAM = Path('04_プログラム/config/jdrt_realtime_choice_v1.json')
AUDITOR = GOAL / 'G4_正式検証器_表会計候補試験.py'


def stamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path, kind=dict):
    value = json.loads(path.read_text(encoding='utf-8'),
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(value, kind):
        raise ValueError(f'{path}: expected {kind.__name__}, got {type(value).__name__}')
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Revalidation:
    def __init__(self, root, suite, prefix):
        self.root = Path(root).resolve()
        for value in (suite, prefix):
            require(re.fullmatch(r'[A-Za-z0-9_-]{1,54}', value), 'Use fresh simple IDs, at most 54 characters')
        self.suite, self.prefix = suite, prefix
        self.params = read_json(self.root / PARAM)
        self.workspace = self.local(self.params['workspace'])
        self.out = self.root / GOAL
        self.state_path = self.out / (suite + '_revalidate.json')
        self.current = {p: sha(self.local(p)) for p in self.params['execution']['implementation_files']}
        sources = [PARAM, SCRIPTS / 'choice_revalidate.py', SCRIPTS / 'choice_technical.py',
                   SCRIPTS / 'choice_smoke_sequence.py', SCRIPTS / 'realtime_choice_cell.py', AUDITOR,
                   Path('04_プログラム/scripts/jdrt_choice_fixtures.py')]
        self.sources = {p.as_posix(): sha(self.root / p) for p in sources}
        self.state = {'purpose': 'technical_prerequisites_only', 'research_adoption_permitted': False,
                      'status': 'RUNNING', 'pid': os.getpid(), 'started_at_jst': stamp(),
                      'suite': suite, 'smoke_prefix': prefix, 'implementation_sha256': self.current,
                      'source_sha256': self.sources, 'completed': [], 'active': None, 'artifacts': {}}

    def local(self, name):
        path = (self.root / name).resolve()
        require(path.is_relative_to(self.root), 'Artifact must be inside project root')
        return path

    def save(self):
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(self.state_path)

    def bind(self, path):
        path = self.local(path)
        self.state['artifacts'][path.relative_to(self.root).as_posix()] = sha(path)
        return path

    def frozen(self):
        for name, expected in {**self.current, **self.sources, **self.state['artifacts']}.items():
            require(sha(self.local(name)) == expected, 'Bound source/artifact changed: ' + name)

    def command(self, stage, args):
        self.frozen()
        base = self.out / (self.suite + '_revalidate_' + stage)
        stdout, stderr = base.with_suffix('.stdout.log'), base.with_suffix('.stderr.log')
        active = {'stage': stage, 'command': args, 'suite': self.suite, 'smoke_prefix': self.prefix,
                  'started_at_jst': stamp(), 'stdout': stdout.relative_to(self.root).as_posix(),
                  'stderr': stderr.relative_to(self.root).as_posix(), 'pid': None, 'exit_code': None,
                  'monitor_paths': [(self.workspace / 'technical' / self.suite / 'manifest.json').relative_to(self.root).as_posix(),
                                    (self.workspace / 'technical' / self.suite / 'progress.json').relative_to(self.root).as_posix(),
                                    (GOAL / (self.prefix + '_smoke_sequence.json')).as_posix()]}
        self.state['active'] = active
        self.save()
        with stdout.open('xb') as out, stderr.open('xb') as err:
            child = subprocess.Popen(args, cwd=self.root, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            active['pid'] = child.pid
            self.save()
            started = time.monotonic()
            while True:
                try:
                    code = child.wait(timeout=15)
                    break
                except subprocess.TimeoutExpired:
                    active.update(observed_at_jst=stamp(), child_alive=True,
                                  elapsed_sec=round(time.monotonic() - started, 1))
                    self.save()
                    # Observation timeout never kills/restarts the same child.
        active.update(exit_code=code, child_alive=False, finished_at_jst=stamp())
        self.save()
        require(code == 0, stage + ' command failed; preserved exit code ' + str(code))
        self.frozen()
        return stdout

    def finish(self, path):
        self.state['active']['result_path'] = self.bind(path).relative_to(self.root).as_posix()
        self.state['completed'].append(dict(self.state['active']))
        self.state['active'] = None
        self.save()

    def fixture(self, stdout):
        result = read_json(stdout)
        path = self.workspace / 'technical' / self.suite / 'manifest.json'
        manifest = read_json(path)
        require(result == manifest, 'Fixture stdout does not match suite manifest')
        require(manifest['status'] == 'COMPLETED' and manifest['run_id'] == self.suite
                and manifest['research_adoption_permitted'] is False, 'Incomplete or research fixture')
        require(isinstance(manifest['cases'], list) and manifest['cases'], 'Missing fixture cases')
        for case in manifest['cases']:
            require(isinstance(case, dict) and case['status'] == 'PASS', 'Invalid fixture case')
            child_path = self.workspace / 'technical' / case['child_run_id'] / 'execution/manifest.json'
            child = read_json(child_path)
            require(child['status'] == 'COMPLETED' and child['implementation_sha256'] == self.current
                    and sha(child_path) == case['execution_manifest_sha256'], 'Fixture child manifest mismatch')
            self.bind(child_path)
        self.finish(path)

    def audit(self, stdout, before):
        created = set(self.out.glob('正式検証器_表会計候補_*.json')) - before
        require(len(created) == 1, 'Expected exactly one newly created independent audit report')
        path = created.pop()
        report, printed = read_json(path), read_json(stdout)
        require(printed == {k: v for k, v in report.items() if k != 'fixture_components'},
                'Independent audit stdout/report mismatch')
        require(report['suite'] == self.suite and report['status'] == 'PASS'
                and report['historical_diagnostic'] is False and report['primary_outputs_unchanged'] is True
                and report['core_adoption_permitted'] is False and report['technical_ready'] is False,
                'Independent audit not current technical PASS')
        require(isinstance(report['counterexamples'], list) and report['counterexamples']
                and all(isinstance(c, dict) and c['pass'] is True for c in report['counterexamples']),
                'Invalid counterexample list')
        components = report['fixture_components']
        require(isinstance(components, list) and components
                and all(isinstance(c, dict) and c['implementation_sha256'] == self.current for c in components),
                'Independent fixture components do not bind current implementation')
        require(report['test_sha256'] == self.sources[AUDITOR.as_posix()], 'Independent auditor SHA mismatch')
        self.finish(path)
        return path

    def smoke(self):
        path = self.out / (self.prefix + '_smoke_sequence.json')
        result = read_json(path)
        cells = [c for c in self.params['cells'] if c['seed'] == self.params['seeds'][0]]
        completed = result['completed']
        require(result['status'] == 'COMPLETED' and result['active'] is None
                and result['implementation_sha256'] == self.current
                and result['research_adoption_permitted'] is False
                and isinstance(completed, list) and cells
                and [r['cell'] for r in completed] == cells, 'Incomplete registered-setting smoke sequence')
        require(result['audit_sha256'] == sha(self.audit_path)
                and self.local(result['audit_path']) == self.audit_path, 'Smoke independent audit mismatch')
        for index, row in enumerate(completed, 1):
            run_id = self.prefix + '_' + str(index).zfill(2)
            require(row['run_id'] == run_id, 'Smoke run ID mismatch')
            manifest_path = self.workspace / 'smoke' / run_id / 'manifest.json'
            manifest, proof = read_json(manifest_path), read_json(self.local(row['validation_report']))
            require(manifest['status'] == 'COMPLETED' and manifest['implementation_sha256'] == self.current
                    and proof['status'] == 'PASS' and proof['core_adoption_permitted'] is False
                    and proof['manifest_sha256'] == row['manifest_sha256'] == sha(manifest_path),
                    'Smoke primary manifest/independent validation mismatch')
            self.bind(manifest_path)
            self.bind(self.local(row['validation_report']))
        self.finish(path)

    def preflight(self, stdout):
        result = read_json(stdout)
        path = self.local(result['report'])
        receipt = read_json(path)
        require(result['status'] == receipt['status'] == 'READY'
                and receipt['implementation_sha256'] == self.current
                and isinstance(result['checks'], dict) and result['checks']
                and all(v is True for v in result['checks'].values())
                and receipt['independent_receipt_checks'] == result['checks'], 'Preflight did not return verified READY')
        require(self.local(receipt['evidence']['counterexamples']) == self.audit_path
                and self.local(receipt['evidence']['fixture_manifest']) == self.workspace / 'technical' / self.suite / 'manifest.json',
                'Preflight binds different suite/audit')
        for name, expected in receipt['evidence_sha256'].items():
            require(sha(self.local(name)) == expected, 'Preflight evidence SHA mismatch: ' + name)
        self.finish(path)

    def run(self):
        self.out.mkdir(parents=True, exist_ok=True)
        with self.state_path.open('x', encoding='utf-8') as stream:
            json.dump(self.state, stream, ensure_ascii=False, indent=2)
        lock = self.out / 'choice_revalidate.lock'
        owned_lock = False
        try:
            require(not (self.workspace / 'technical' / self.suite).exists(), 'Suite ID already exists')
            require(not (self.out / (self.prefix + '_smoke_sequence.json')).exists(), 'Smoke prefix already exists')
            require(not any((self.workspace / 'smoke').glob(self.prefix + '_*')), 'Smoke run prefix already exists')
            with lock.open('x', encoding='utf-8') as stream:
                json.dump({'pid': os.getpid(), 'state': self.state_path.as_posix()}, stream)
            owned_lock = True
            # Reservation survives failures before smoke starts; IDs are never silently reused.
            with (self.out / (self.prefix + '_revalidate_reservation.json')).open('x', encoding='utf-8') as stream:
                json.dump({'suite': self.suite, 'state': self.state_path.as_posix()}, stream)
            python = [sys.executable, '-X', 'utf8']
            cli = python + [str(self.root / SCRIPTS / 'realtime_choice_cell.py'), '--project-root', str(self.root)]
            self.fixture(self.command('fixture', python + [str(self.root / SCRIPTS / 'choice_technical.py'),
                         '--project-root', str(self.root), 'fixture', '--run-id', self.suite]))
            before = set(self.out.glob('正式検証器_表会計候補_*.json'))
            self.audit_path = self.audit(self.command('independent', python + [str(self.root / AUDITOR), '--suite', self.suite]), before)
            self.command('smoke', python + [str(self.root / SCRIPTS / 'choice_smoke_sequence.py'),
                         '--prefix', self.prefix, '--audit', self.audit_path.relative_to(self.root).as_posix()])
            self.smoke()
            self.preflight(self.command('preflight', cli + ['preflight', '--suite-id', self.suite,
                           '--counterexamples', self.audit_path.relative_to(self.root).as_posix()]))
            self.frozen()
            self.state.update(status='COMPLETED', finished_at_jst=stamp())
        except BaseException as error:
            self.state.update(status='FAILED', finished_at_jst=stamp(), error_type=type(error).__name__, error=str(error))
            raise
        finally:
            self.save()
            # An interrupted wait may leave a live child. Preserve the lock for inspection.
            active = self.state['active']
            if owned_lock and (active is None or active['exit_code'] is not None):
                lock.unlink()
        return self.state_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--suite-id', required=True, help='Fresh complete fixture suite ID')
    parser.add_argument('--smoke-prefix', required=True, help='Fresh prefix reserved for all registered setting smokes')
    args = parser.parse_args()
    path = Revalidation(args.project_root, args.suite_id, args.smoke_prefix).run()
    print(json.dumps({'status': 'COMPLETED', 'state': str(path), 'research_adoption_permitted': False}))


if __name__ == '__main__':
    main()
