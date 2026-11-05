"""Capture only this packager revision's source, preserved baselines and checks."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[4]
PATHS = [ROOT / '.agents/skills/joso-jdrt-runner/scripts/choice_package_toolchain.py',
         ROOT / '04_プログラム/tests/test_choice_package_toolchain.py',
         ROOT / '.agents/skills/joso-jdrt-runner/references/realtime_choice.md',
         ROOT / '06_研究結果/jdrt/goal_20261017/choice_toolchain_binding_20261020.md']
BEFORE = {PATHS[2]: AUDIT / 'previous_realtime_choice.md',
          PATHS[3]: AUDIT / 'previous_binding_report.md'}
rows, diffs, checks = [], [], []
for path in PATHS:
    raw = path.read_bytes()
    source = raw.decode('utf-8')
    if path.suffix == '.py':
        ast.parse(source)
    rows.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest(),
                 'bytes': len(raw), 'trailing_whitespace_lines': [i for i, line in enumerate(source.splitlines(), 1)
                                                                if line.rstrip() != line]})
    arguments = ['git', 'diff', '--no-index', str(BEFORE.get(path, '/dev/null')), str(path)]
    diff = subprocess.run(arguments, capture_output=True, text=True, encoding='utf-8')
    check = subprocess.run(arguments[:3] + ['--check'] + arguments[3:], capture_output=True,
                           text=True, encoding='utf-8')
    if diff.returncode not in (0, 1) or check.returncode not in (0, 1):
        raise RuntimeError((diff.stderr, check.stderr))
    diffs.append(diff.stdout)
    checks.append({'path': path.relative_to(ROOT).as_posix(), 'returncode': check.returncode,
                   'stdout': check.stdout, 'stderr': check.stderr})
result = {'files': rows, 'ast_parse': 'PASS', 'diff_check': checks,
          'requested_model': 'gpt-6.1-sol/high', 'actual_backend': 'unconfirmed',
          'research_ready': False, 'real_bundle_generated': False, 'simulation_executed': False}
(AUDIT / 'after_sha256_and_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(AUDIT / 'changes.patch').write_text(''.join(diffs), encoding='utf-8', newline='\n')
(AUDIT / 'unit_result.json').write_text(json.dumps({
    'command': '.\\venv\\Scripts\\python.exe -m pytest tests/test_choice_package_toolchain.py tests/test_jdrt_choice_toolchain.py -q',
    'cwd': str(ROOT / '04_プログラム'), 'exit_code': 0, 'passed': 25, 'subtests_passed': 27,
    'pytest_elapsed_seconds': 27.25, 'evidence': 'Observed exec cell 61cb74 and session 93751 final output 063f76',
    'fixtures': 'Artificial PE, mock native proof and temporary Python packages; no native simulation'
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert all(not row['trailing_whitespace_lines'] for row in rows)
assert all(not check['stdout'] for check in checks)
print(json.dumps({'ast_parse': 'PASS', 'whitespace': 'PASS', 'files': len(rows), 'tests': 25}))
