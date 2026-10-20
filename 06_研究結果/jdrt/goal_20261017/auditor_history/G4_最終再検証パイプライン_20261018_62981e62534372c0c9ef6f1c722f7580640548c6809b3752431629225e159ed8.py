"""Sequential registered skill prerequisites; deliberately stops before core start."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SKILL = ROOT / '.agents/skills/joso-jdrt-runner/scripts'


def stamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def main():
    suite, smoke = 'cf26101801', 'cs261018a'
    state_path = OUT / 'G4pipeline_20261018a.json'
    state = {'purpose': 'technical_prerequisites_only', 'status': 'RUNNING', 'pid': os.getpid(),
             'started_at_jst': stamp(), 'suite': suite, 'smoke_prefix': smoke, 'completed': [], 'active': None}
    with state_path.open('x', encoding='utf-8') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
    def save():
        sys.path.insert(0, str(SKILL))
        from realtime_choice_cell import save_json
        save_json(state_path, state)
    def command(stage, script, arguments):
        args = [sys.executable, '-X', 'utf8', str(script), *arguments]
        with (OUT / ('G4pipeline_20261018a_' + stage + '.stdout.log')).open('xb') as stdout, (
                OUT / ('G4pipeline_20261018a_' + stage + '.stderr.log')).open('xb') as stderr:
            child = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
            state['active'] = {'stage': stage, 'pid': child.pid, 'started_at_jst': stamp(), 'command': args}
            save()
            code = child.wait()
        result = {**state['active'], 'finished_at_jst': stamp(), 'exit_code': code}
        with (OUT / 'operations.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'action': 'technical_pipeline_stage', **result}, ensure_ascii=False) + '\n')
        if code:
            raise RuntimeError('Stage failed and preserved: ' + stage)
        state['completed'].append(result)
        state['active'] = None
        save()
    try:
        command('fixture', SKILL / 'choice_technical.py', ['--project-root', str(ROOT), 'fixture', '--run-id', suite])
        command('independent', OUT / 'G4_正式検証器_表会計候補試験.py', ['--suite', suite])
        matches = []
        for path in OUT.glob('正式検証器_表会計候補_*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            if value.get('suite') == suite and value['status'] == 'PASS' and not value['historical_diagnostic']:
                matches.append(path)
        if len(matches) != 1:
            raise RuntimeError('Expected exactly one current independent suite proof')
        audit = matches[0].relative_to(ROOT).as_posix()
        command('smoke14', OUT / 'G4_最終14設定smoke逐次実行.py', ['--prefix', smoke, '--audit', audit])
        command('preflight', SKILL / 'realtime_choice_cell.py', ['--project-root', str(ROOT), 'preflight',
            '--suite-id', suite, '--counterexamples', audit])
        state.update(status='COMPLETED_READY_REVIEW_REQUIRED', finished_at_jst=stamp(), audit=audit)
    except BaseException as error:
        state.update(status='FAILED', finished_at_jst=stamp(), error_type=type(error).__name__, error=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
