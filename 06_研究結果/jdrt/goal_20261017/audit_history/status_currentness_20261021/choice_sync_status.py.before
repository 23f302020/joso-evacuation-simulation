"""Synchronize current displays from accepted records and observed manifests.

Ordinary documentation only: never validate/adopt/start/recover a cell or create
choice_record markers. Shared writer lock prevents conflict with formal record.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re

from realtime_choice_cell import ChoiceController, file_sha, pid_alive, single_writer

ROOT = Path(__file__).resolve().parents[4]
DISPLAY_FILES = ['context.md', '00_全体整理/現状把握_静的・動的シミュレーション整理.md',
                 '00_全体整理/現状把握_静的・動的シミュレーション整理.html']


def read_json(path):
    return json.loads(path.read_bytes().decode('utf-8-sig'))


def local_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Display evidence must be local to the project')
    return path


def build_observation(root, path):
    """Verify an archived point observation, without querying present processes."""
    from choice_native_build_monitor import identity
    path = local_path(root, path)
    value = read_json(path)
    if value.get('action') != 'isolated_native_build_monitor':
        raise ValueError('Expected canonical isolated native-build observation')
    for key in ('formal_validation_or_adoption', 'core_ready', 'native_regression_verified',
                'downstream_start_permitted', 'simulation_allowed', 'research_cli_switch_allowed'):
        if value.get(key) is not False:
            raise ValueError('Build observation must keep adoption/READY/downstream gates false')
    if value.get('report') != path.relative_to(root).as_posix():
        raise ValueError('Build observation report identity differs from its path')
    snapshot = local_path(root, value['state_snapshot_file'])
    raw = snapshot.read_bytes()
    state = json.loads(raw.decode('utf-8-sig'))
    if (sha256(raw).hexdigest() != value['state_snapshot_sha256'] or len(raw) != value['state_snapshot_bytes']
            or state != value['state_snapshot'] or state.get('schema') != 'isolated_native_build_v1'
            or any(state.get(key) != value.get(key) for key in ('status', 'phase', 'attempt_id'))
            or state.get('simulation_allowed') is not False or state.get('research_cli_switch_allowed') is not False):
        raise ValueError('Build state snapshot does not match observation')
    at = datetime.fromisoformat(value['at_jst'])
    if at.tzinfo is None:
        raise ValueError('Build observation timestamp must include timezone')
    if value['status'] not in ('RUNNING', 'FAILED', 'FAILED_PRESERVED', 'COMPLETED', 'COMPILED_VERSION_CHECKED_NOT_SIMULATED'):
        raise ValueError('Unsupported build observation status')
    for role in ('owner', 'child'):
        entry = value.get(role)
        if entry is None and role == 'child' and value['status'] != 'RUNNING':
            continue
        if not isinstance(entry, dict) or entry.get('pid') != state.get(role + '_pid'):
            raise ValueError('Build PID does not match snapshot')
        if role == 'owner':
            expected = state.get('owner_process_identity')
        else:
            commands = [item for item in state['commands'] if item.get('pid') == entry['pid'] and item.get('phase') == state['phase']]
            if len(commands) != 1:
                raise ValueError('Build child command evidence is ambiguous')
            expected = commands[0].get('process_identity')
        if entry.get('expected') != expected:
            raise ValueError('Build PID expected identity differs from snapshot')
        actual = identity(entry['pid'], expected, lambda pid: entry.get('observed_cim'))
        if actual['identity'] != entry.get('identity'):
            raise ValueError('Build observed PID identity is inconsistent')
    return value, {path: file_sha(path), snapshot: file_sha(snapshot)}


def newline(raw):
    return b'\r\r\n' if b'\r\r\n' in raw else b'\r\n' if b'\r\n' in raw else b'\n'


def bounded(raw, label, content, migration):
    """Replace one exact region; prefix/suffix stay as original bytes."""
    begin = ('<!-- CHOICE_CURRENT_' + label + '_BEGIN -->').encode()
    end = ('<!-- CHOICE_CURRENT_' + label + '_END -->').encode()
    if raw.count(begin) or raw.count(end):
        if raw.count(begin) != 1 or raw.count(end) != 1 or raw.index(begin) >= raw.index(end):
            raise ValueError('Ambiguous current display markers: ' + label)
        start, stop = raw.index(begin), raw.index(end) + len(end)
    else:
        match = migration(raw)
        if match is None:
            raise ValueError('Cannot identify existing current display: ' + label)
        start, stop = match.span()
    replacement = begin + newline(raw) + content + newline(raw) + end
    return raw[:start] + replacement + raw[stop:]


def replace_date(raw, pattern, day):
    matches = list(re.finditer(pattern, raw))
    if len(matches) != 1:
        raise ValueError('Current date location is missing or ambiguous')
    start, stop = matches[0].span(1)
    return raw[:start] + day.encode() + raw[stop:]


def display_plans(root, summary, at, task_summary):
    """Use document-specific encoding; never serialize whole text documents."""
    day = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=9))).date().isoformat()
    plain = summary.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').encode('utf-8')
    html = escape(summary, quote=True).encode('utf-8')
    plans = {}
    for name, label in zip(DISPLAY_FILES[:2], ('CONTEXT', 'MARKDOWN')):
        path = root / name
        raw = path.read_bytes()
        result = bounded(raw, label, (b'> ' if label == 'MARKDOWN' else b'') + plain,
                         lambda data: re.search(rb'(?m)^[ \t>]*(?:\*\*)?(?:' + '最新HOLD|最終goal'.encode() + rb')[^\r\n]*', data[:15000]))
        result = replace_date(result, rb'\*\*' + '最終更新：'.encode() + rb'\*\* (\d{4}-\d{2}-\d{2})', day)
        plans[path] = result
    path = root / DISPLAY_FILES[2]
    raw = path.read_bytes()
    top = b'<aside data-choice-current="top" role="status"><p>' + html + b'</p></aside>'
    detail = ('<aside class="callout" id="choice-current-hold" role="status"><h2>'
              + day + '：受付・代替行動系列の観測時点の状況</h2><p>').encode() + html + b'</p></aside>'
    result = bounded(raw, 'HTML_TOP', top, lambda data: re.search(rb'<aside\b[^>]*data-choice-technical-hold="[^"]*"[^>]*>.*?</aside>', data, re.S))
    result = bounded(result, 'HTML_DETAIL', detail, lambda data: re.search(rb'<aside\b[^>]*id="choice-current-hold"[^>]*>.*?</aside>', data, re.S))
    result = replace_date(result, rb'<p class="snapshot">(\d{4}-\d{2}-\d{2})', day)
    result = replace_date(result, rb'(?s)<footer\b[^>]*>.*?(\d{4}-\d{2}-\d{2})(?=' + '更新'.encode() + rb')', day)
    plans[path] = result
    task = root / '05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md'
    raw = task.read_bytes()
    matches = list(re.finditer(rb'(?m)^\| CH-M1 \|[^\r\n]*', raw))
    if len(matches) != 1:
        raise ValueError('CH-M1 latest display row is missing or ambiguous')
    match = matches[0]
    fields = match.group().split(b'|')
    fields[-2] = (' ' + task_summary.replace('|', '／').replace('\n', ' ').replace('\r', ' ') + ' ').encode()
    plans[task] = raw[:match.start()] + b'|'.join(fields) + raw[match.end():]
    for path, content in plans.items():
        original = path.read_bytes()
        markers = rb'<!--\s*choice_record\b.*?-->'
        if b'\0' in original or b'\0' in content or re.findall(markers, original, re.S) != re.findall(markers, content, re.S):
            raise ValueError('NUL or altered formal acceptance markers in display plan')
    return plans


def atomic_bytes(path, raw):
    temporary = path.with_name(path.name + '.choice_sync.tmp')
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if created and temporary.exists():
            temporary.unlink()


def synchronize(root=ROOT, apply=False, build_report=None, controller=None):
    root = root.resolve()
    out = root / '06_研究結果/jdrt/goal_20261017'
    controller = controller or ChoiceController(root)
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
        checkpoint_path = out / 'G4実装・実SUMO_継続チェックポイント.json'
        checkpoint_raw = checkpoint_path.read_bytes()
        checkpoint = json.loads(checkpoint_raw.decode('utf-8-sig'))
        parameters = read_json(root / '04_プログラム/config/jdrt_realtime_choice_v1.json')
        implementation = {name: file_sha(root / name) for name in parameters['execution']['implementation_files']}
        build, dependencies = build_observation(root, build_report) if build_report else (None, {})
        if build and (active or state['unrecorded']):
            raise RuntimeError('Build display cannot hide an active or unrecorded research core')
        next_cell = state['next_cell']['cell_id'] if state['next_cell'] else '登録集合完了'
        summary = (f'最終goal {checkpoint["goal_status"]}。受付・代替行動系列realtime_choice_v1：'
                   f'正式記録{state["recorded_cells"]}/{state["registered_cells"]}セル。{activity}。'
                   f'登録上の次セルは{next_cell}（開始許可ではない。専用CLIの現行READY/開始gateに従う）。'
                   '状態は専用CLI status/check、正式採用は独立validate PASSと6ファイルrecordを正本とする。'
                   '定型監視/記録はLuna lowを第一候補、判断・異常解析・複雑実装・数式考察は6.1 Sol high指定。'
                   '反復処理はスキルへ集約し、必要な更新の理由/検証/履歴を保存する。'
                   '全登録セル採用前の方向解釈なし。旧系列/失敗/旧図保全。Drive読取のみ・外部送信なし。')
        implementation_changed = checkpoint.get('current_implementation_sha256') != implementation
        hold = (checkpoint.get('technical_ready') is False or bool(checkpoint.get('current_hold')) or implementation_changed
                or 'HOLD' in checkpoint['summary'])
        at = checkpoint['at_jst']
        if build:
            at = build['at_jst']
            identities = '、'.join(f'{role} PID {build[role]["pid"]} identity={build[role]["identity"]}'
                                  for role in ('owner', 'child') if build.get(role))
            summary = (f'最新HOLD（観測時点 {at}）：goal {checkpoint["goal_status"]}。'
                       f'realtime_choice_v1正式記録{state["recorded_cells"]}/{state["registered_cells"]}、'
                       f'研究core稼働{len(active)}、技術READY=false。隔離native build '
                       f'{build["attempt_id"]} は当該観測時点で{build["status"]}、phase {build["phase"]}。'
                       f'{identities}。これは過去のポイント観測で、現在のPID生存や連続監視は主張しない。'
                       'compile完成はnative回帰の合格やREADYを意味しない。旧FAILED/INVALID・attempt履歴を保全。'
                       f'登録上の次セルは{next_cell}（開始許可ではない）。後続開始は禁止。'
                       'native回帰・現行全fixture suite・独立audit・全設定smoke・新preflight・G6再監査が必要。'
                       '研究入力/PAP/受入条件不変。Drive読取のみ・外部送信/公開更新なし。'
                       f'観測証拠：{build["report"]}。')
            if build.get('anomaly_flags'):
                summary += '観測anomaly：' + ', '.join(build['anomaly_flags']) + '。'
        elif hold:
            prior_summary = checkpoint['summary'].split('。専用CLIの今回core観測：', 1)[0]
            summary = re.sub(r'正式記録\d+/\d+', f'正式記録{state["recorded_cells"]}/{state["registered_cells"]}', prior_summary)
            summary = re.sub(r'研究core稼働\d+', f'研究core稼働{len(active)}', summary)
            if 'READY=false' not in summary:
                summary = (f'最新HOLD（表示根拠 {at}）：正式記録{state["recorded_cells"]}/{state["registered_cells"]}。'
                           '技術READY=false。旧READY/技術PASSはSTALE/historical。後続開始禁止。'
                           '元summaryと旧証拠はcheckpoint履歴に保全。')
            if chosen:
                summary += '。専用CLIの今回core観測：' + activity + '。後続開始は禁止。'
        task_summary = (f'正式記録{state["recorded_cells"]}/{state["registered_cells"]}。'
                        + (summary if build else '技術HOLD保全・後続開始禁止。' if hold else activity + '。最新は専用CLI status/check。'))
        plans = display_plans(root, summary, at, task_summary)
        report = {'at_jst': at, 'action': 'skill_current_display_sync',
                  'summary': summary, 'state': state, 'observation': observed,
                  'formal_adoption_created': False, 'skill_source_sha256': file_sha(Path(__file__))}
        if build:
            report['build_observation'] = {key: build.get(key) for key in
                ('report', 'at_jst', 'status', 'phase', 'attempt_id', 'owner', 'child', 'state_snapshot_sha256', 'anomaly_flags')}
            report['build_evidence_sha256'] = {p.relative_to(root).as_posix(): expected for p, expected in dependencies.items()}
        updated = dict(checkpoint)
        stale = build is not None or hold or checkpoint.get('current_implementation_sha256') != implementation
        if stale:
            for key in ('preflight_state', 'independent_audit_status', 'smoke_sequence_status', 'integrated_suite_current_status'):
                if key in updated and not str(updated[key]).lower().startswith(('stale', 'historical')):
                    updated[key] = 'STALE historical: ' + str(updated[key])
            updated.update(technical_ready=False, technical_evidence_classification=
                           'STALE/historical: legacy PASS fields do not establish current READY')
        updated.update(at_jst=at, summary=summary, core_runs=len(records),
                       running=[observed] if observed and observed['status'] == 'RUNNING' else [],
                       unrecorded_runs=state['unrecorded'], observed_formally_recorded=state['recorded_cells'],
                       current_implementation_sha256=implementation, latest_status_sync=report)
        if build:
            updated.update(current_build_observation=report['build_observation'],
                           progress_classification='isolated_native_build_point_observation',
                           next='HOLD: finish native regression, current suite/audit/all-setting smokes/new preflight/G6 before any core')
        if updated != checkpoint:
            previous = {'sha256': sha256(checkpoint_raw).hexdigest(),
                        'file': (out / 'document_history' / (sha256(checkpoint_raw).hexdigest() + checkpoint_path.suffix)).relative_to(root).as_posix()}
            updated['historical_display_checkpoints'] = [*checkpoint.get('historical_display_checkpoints', []), previous]
        bom = b'\xef\xbb\xbf' if checkpoint_raw.startswith(b'\xef\xbb\xbf') else b''
        plans[checkpoint_path] = bom + (json.dumps(updated, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode().replace(b'\n', newline(checkpoint_raw))
        originals = {path: path.read_bytes() for path in plans}
        changed_plans = {path: content for path, content in plans.items() if content != originals[path]}
        if apply and changed_plans:
            if controller.status(inspect_processes=False) != state:
                raise RuntimeError('Formal status changed after display preview')
            if any(file_sha(path) != expected for path, expected in dependencies.items()):
                raise RuntimeError('Build observation evidence changed after preview')
            if any(path.read_bytes() != raw for path, raw in originals.items()):
                raise RuntimeError('Current document bytes changed after preview')
            if any(file_sha(root / name) != expected for name, expected in implementation.items()):
                raise RuntimeError('Implementation changed after display preview')
            if file_sha(Path(__file__)) != report['skill_source_sha256']:
                raise RuntimeError('Display helper changed after preview')
            history = out / 'document_history'
            history.mkdir(exist_ok=True)
            for path, raw in originals.items():
                backup = history / (sha256(raw).hexdigest() + path.suffix)
                if not backup.exists():
                    backup.write_bytes(raw)
                if backup.read_bytes() != raw:
                    raise RuntimeError('Display history archive bytes differ from original')
            changed = []
            try:
                for path, content in changed_plans.items():
                    changed.append(path)
                    atomic_bytes(path, content)
                if any(path.read_bytes() != content for path, content in plans.items()):
                    raise RuntimeError('Display readback mismatch')
            except BaseException:
                for path in changed:
                    atomic_bytes(path, originals[path])
                raise
            event = {**report, 'applied': True, 'files': {path.relative_to(root).as_posix(): file_sha(path) for path in plans}}
            for path in [out / 'operations.jsonl', controller.logs / 'operations.jsonl']:
                with path.open('a+b') as stream:
                    stream.seek(0, 2)
                    prefix = b''
                    if stream.tell():
                        stream.seek(-1, 2)
                        prefix = b'' if stream.read(1) == b'\n' else b'\n'
                    stream.write(prefix + json.dumps(event, ensure_ascii=False).encode() + b'\n')
        return {'applied': apply, 'changed_files': [path.relative_to(root).as_posix() for path in changed_plans],
                'summary': summary, 'recorded_cells': state['recorded_cells'], 'observed_run': chosen,
                'build_observation': report.get('build_observation'), 'formal_adoption_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write the verified current display; default is preview')
    parser.add_argument('--build-observation', type=Path, help='Canonical native-build monitor report; remains a point observation')
    args = parser.parse_args()
    print(json.dumps(synchronize(apply=args.apply, build_report=args.build_observation), ensure_ascii=False))


if __name__ == '__main__':
    main()
