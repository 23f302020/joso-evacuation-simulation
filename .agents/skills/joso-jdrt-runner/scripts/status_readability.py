"""Presentation only: no research state, adoption, or execution is changed."""
from datetime import datetime, timedelta, timezone
import re


def reader_summary(state, observed, hold, at):
    point = observed.get('progress') if observed else None
    stamp = point.get('at_jst', at) if point else at
    when = datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=9)))
    text = (f'{when:%Y年%m月%d日 %H:%M}（日本時間）の確認内容です。'
            f'予定した{state["registered_cells"]}回のうち{state["recorded_cells"]}回は、'
            '結果の確認と正式な記録が終わっています。')
    blocked = hold or bool(state['unresolved_failures'] or state['unresolved_launches'])
    if observed and observed['status'] == 'RUNNING':
        if observed['pid_alive']:
            text += '実験を1回実行中です。'
            if not point:
                text += '計算の進み具合は未確認です。'
        else:
            text += '実行記録と動作状況が一致せず、状態の確認が必要です。'
            blocked = True
    elif state['unrecorded']:
        text += '計算が終わり、結果の確認・記録を待っている実験があります。'
        blocked = True
    else:
        text += '実行中や確認・記録待ちの実験はありません。'
    if blocked:
        text += '必要な確認が終わるまで、次の実験は開始できません。'
    else:
        text += '次の実験を始める際は、その時点の開始条件を確認します。'
    if state['recorded_cells'] < state['registered_cells']:
        text += 'すべての実験がそろうまでは、方法の優劣を判断しません。'
    return text


def normalize_progress(markdown):
    """Translate only the frozen recorder's exact one-line presentation format."""
    begin, end = '<!-- PROGRESS_LOG_BEGIN -->', '<!-- PROGRESS_LOG_END -->'
    if begin not in markdown or end not in markdown:
        return markdown
    prefix, body = markdown.split(begin, 1)
    body, suffix = body.split(end, 1)
    pattern = r'(?m)^- ([^\r\n]+) / seed=([^\r\n]+)：独立検証PASS・正式記録（([a-zA-Z0-9_-]+)）。(?=\r?$)'
    body = re.sub(pattern, r'- 実験1回分の確認と正式な記録が終わりました。照合用：条件=\1、設定番号=\2、実行番号=\3。', body)
    return prefix + begin + body + end + suffix
