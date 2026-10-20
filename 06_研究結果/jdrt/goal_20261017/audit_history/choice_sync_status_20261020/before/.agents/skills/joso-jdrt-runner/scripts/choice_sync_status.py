"""Synchronize current displays from accepted records and observed manifests.

Ordinary documentation only: never validate/adopt/start/recover a cell or create
choice_record markers. Shared writer lock prevents conflict with formal record.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from realtime_choice_cell import ChoiceController, file_sha, pid_alive, save_json, single_writer

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / '06_研究結果/jdrt/goal_20261017'
DISPLAY_FILES = ['context.md', '00_全体整理/現状把握_静的・動的シミュレーション整理.md',
                 '00_全体整理/現状把握_静的・動的シミュレーション整理.html']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write the verified current display; default is preview')
    args = parser.parse_args()
    controller = ChoiceController(ROOT)
    with single_writer(controller.workspace):
        state = controller.status(inspect_processes=False)
        if state['partial_records'] or state['record_identity_mismatch'] or state['pending_record_journals']:
            raise RuntimeError('Partial or inconsistent formal records require diagnosis before display sync')
        records = {m['run_id']: (p, m) for p, m in controller.records() if m['purpose'] == 'core'}
        active = state['running']
        if len(active) > 1:
            raise RuntimeError('Multiple active manifests require diagnosis')
        chosen = active[0] if active else (state['unrecorded'][0] if state['unrecorded'] else None)
        if chosen and chosen not in records:
            raise RuntimeError('Technical run active; do not mislabel it as a core')
        point, observed = None, None
        if chosen:
            path, m = records[chosen]
            progress_path = path.parent / 'progress.json'
            point = json.loads(progress_path.read_text(encoding='utf-8')) if progress_path.is_file() else None
            observed = {'run_id': chosen, 'cell_id': m['cell_id'], 'pid': m['pid'],
                        'pid_alive': pid_alive(m['pid']), 'status': m['status'], 'progress': point}
            activity = (f'{chosen}（{m["cell_id"]}）{m["status"]}・PID生存{observed["pid_alive"]}'
                        + (f'・sim {point["time_sec"]}/{m["end_sec"]}秒（{point["at_jst"]}）' if point else '・進捗未観測'))
        else:
            activity = '実行中/完了未記録coreなし'
        if state['unresolved_failures'] or state['unresolved_launches']:
            activity += '。未診断の失敗/起動あり・後続停止'
        checkpoint_path = OUT / 'G4実装・実SUMO_継続チェックポイント.json'
        checkpoint = json.loads(checkpoint_path.read_text(encoding='utf-8'))
        old = checkpoint['summary']
        next_cell = state['next_cell']['cell_id'] if state['next_cell'] else '登録集合完了'
        summary = (f'最終goal {checkpoint["goal_status"]}。受付・代替行動系列realtime_choice_v1：'
                   f'正式記録{state["recorded_cells"]}/{state["registered_cells"]}セル。{activity}。'
                   f'次の登録セルは{next_cell}（実行中/未記録がある間は開始しない）。'
                   '状態は専用CLI status/check、正式採用は独立validate PASSと6ファイルrecordを正本とする。'
                   '定型監視/記録はLuna lowを第一候補、判断・異常解析・複雑実装・数式考察は6.1 Sol high指定。'
                   '反復処理はスキルへ集約し、必要な更新の理由/検証/履歴を保存する。'
                   '全登録セル採用前の方向解釈なし。旧系列/失敗/旧図保全。Drive読取のみ・外部送信なし。')
        plans = {}
        for name in DISPLAY_FILES:
            path = ROOT / name
            text = path.read_text(encoding='utf-8')
            if old not in text:
                raise RuntimeError('Current display does not match checkpoint: ' + name)
            plans[path] = text.replace(old, summary)
        task_path = ROOT / '05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md'
        task = task_path.read_text(encoding='utf-8')
        lines = []
        for line in task.splitlines():
            if line.startswith('| CH-M1 |'):
                parts = line.split('|')
                parts[-2] = f' 正式記録{state["recorded_cells"]}/{state["registered_cells"]}。{activity}。最新は専用CLI status/check。 '
                line = '|'.join(parts)
            lines.append(line)
        plans[task_path] = '\n'.join(lines) + '\n'
        now = datetime.now(timezone(timedelta(hours=9))).isoformat()
        report = {'at_jst': now, 'action': 'skill_current_display_sync', 'applied': args.apply,
                  'summary': summary, 'state': state, 'observation': observed,
                  'formal_adoption_created': False, 'skill_source_sha256': file_sha(Path(__file__))}
        if args.apply:
            history = OUT / 'document_history'
            history.mkdir(exist_ok=True)
            originals = {path: path.read_bytes() for path in [*plans, checkpoint_path]}
            for path, raw in originals.items():
                backup = history / (sha256(raw).hexdigest() + path.suffix)
                if not backup.exists():
                    backup.write_bytes(raw)
            changed = []
            try:
                for path, content in plans.items():
                    changed.append(path)
                    path.write_text(content, encoding='utf-8', newline='\n')
                checkpoint.update(at_jst=now, summary=summary, core_runs=len(records),
                                  running=[observed] if observed and observed['status'] == 'RUNNING' else [],
                                  unrecorded_runs=state['unrecorded'],
                                  observed_formally_recorded=state['recorded_cells'], latest_status_sync=report)
                changed.append(checkpoint_path)
                save_json(checkpoint_path, checkpoint)
                if any(path.read_text(encoding='utf-8') != content for path, content in plans.items()):
                    raise RuntimeError('Display readback mismatch')
            except BaseException:
                for path in changed:
                    path.write_bytes(originals[path])
                raise
            report['files'] = {path.relative_to(ROOT).as_posix(): file_sha(path) for path in [*plans, checkpoint_path]}
            for path in [OUT / 'operations.jsonl', controller.logs / 'operations.jsonl']:
                with path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(report, ensure_ascii=False) + '\n')
        print(json.dumps({'applied': args.apply, 'summary': summary, 'recorded_cells': state['recorded_cells'],
                          'observed_run': chosen}, ensure_ascii=False))


if __name__ == '__main__':
    main()
