"""Apply the completed postanalysis state; preserve dated run histories."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
data = json.loads((OUT / '副指標・観測監査集計.json').read_text(encoding='utf-8'))
assert len(data['cells']) == 15 and all(data['checks'].values())
assert (OUT / '報告独立照合.json').exists()
stamp = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
relative = '06_研究結果/jdrt/realtime_b_boundary_v2/postanalysis_20261017'
road_rows = sum(c['roads']['rows'] for c in data['cells'])
candidate_rows = sum(c['candidates']['rows'] for c in data['cells'])
current = f'新境界整合Bは15/15正式記録済み。BA-02〜06の副指標・時間・候補・道路・取得監査と方針整理を完了。道路{road_rows:,}行・候補{candidate_rows:,}行を全読取し、全人物会計・時刻・選択候補/配車event・3時計・遷移を照合。Type4の固定終点・施設空き・拠点接続を診断。次はNP-02/03の災害時供給/需要・路面高/施設条件の不足資料整理。追加run・方法変更は未採用、監視PAUSED。Driveは5文書読取のみ、外部送信なし。'
changes = []


def edit(name, transform):
    p = ROOT / name
    before = p.read_bytes()
    text = p.read_text(encoding='utf-8')
    after = transform(text)
    assert after != text, name
    p.write_text(after, encoding='utf-8')
    changes.append({'path': name, 'before_sha256': hashlib.sha256(before).hexdigest(), 'after_sha256': hashlib.sha256(p.read_bytes()).hexdigest()})


def context(text):
    lines = text.splitlines()
    old = next(x for x in lines if x.startswith('**最優先の現在地：**'))
    text = text.replace(old, '**最優先の現在地：** ' + current, 1)
    text = re.sub(r'\*\*最終更新：\*\*[^\n]+', '**最終更新：** 2026-10-17（BA-02〜06完了・副指標/観測/取得監査を反映）', text, count=1)
    text = text.replace('独立一覧を作成。次は副指標/取得監査。', '独立一覧とBA-02〜06の副指標/観測/取得監査を完了。次は不足資料の整理。', 1)
    text = text.replace('独立一覧/主指標記述表作成、副指標/取得監査は次タスク', '独立一覧と副指標/観測/取得監査・方針整理完了。次は不足資料', 1)
    text = text.replace('次は完了後分析タスクBA-02 |', 'BA-02〜06完了、次はNP-02/03の資料整理 |', 1)
    marker = '\n<!-- AGENT_CURRENT_END -->'
    assert marker in text
    block = '\n\n**完了後分析（' + stamp + '）：** [' + '副指標・観測監査報告](' + relative + '/副指標・観測監査報告.html)・[取得監査](' + relative + '/データ取得監査.md)。未取得実測値は不足のまま保持。追加感度/再割当/対象/主要指標変更は未採用。\n'
    return text.replace(marker, block + marker, 1)


edit('context.md', context)
edit('00_全体整理/現状把握_静的・動的シミュレーション整理.md', lambda s: s.replace('> **最終更新：** 2026-10-16', '> **最終更新：** 2026-10-17', 1).replace('現実条件版は別系列であり、先行R0 1セルは正式採用保留である。', '現実条件版は別系列。新境界整合Bは15セル正式記録・完了後監査済み。先行R0/旧Bは履歴として分離保全する。', 1).replace('\n---\n', '\n\n## 現在地（2026-10-17・完了後監査）\n\n' + current + '\n\n[副指標・観測監査報告](../' + relative + '/副指標・観測監査報告.html)・[取得監査](../' + relative + '/データ取得監査.md)・[独立集計フロー](../' + relative + '/集計・監査フロー.md)。以下の過去日時付き進行記録は当時の履歴として保持する。\n\n---\n', 1))
edit('00_全体整理/現状把握_静的・動的シミュレーション整理.html', lambda s: s.replace('<aside class="callout" id="boundary-current">', '<aside class="callout" id="boundary-current"><h4>2026-10-17：副指標・観測・取得監査完了</h4><p>' + current + '</p><p><a href="../' + relative + '/副指標・観測監査報告.html">副指標・観測監査報告</a>・<a href="../' + relative + '/データ取得監査.md">取得監査</a>・<a href="../' + relative + '/集計・監査フロー.md">独立集計フロー</a></p><p>以下は当時の進行履歴です。</p>', 1))


def task(text):
    lines = []
    for line in text.splitlines():
        if any(line.startswith('| ' + key + ' |') for key in ['BA-02', 'BA-03', 'BA-04', 'BA-05', 'BA-06']):
            line = re.sub(r'\| [^|]+ \|$', '| 完了（2026-10-17、証跡は下記） |', line)
        lines.append(line)
    return '\n'.join(lines) + '\n\n## 完了後監査の実施結果（' + stamp + '）\n\n' + current + '\n\n[副指標報告](../../' + relative + '/副指標・観測監査報告.html)・[全集計JSON](../../' + relative + '/副指標・観測監査集計.json)・[独立照合](../../' + relative + '/報告独立照合.json)・[詳細実行履歴](../../' + relative + '/operations.jsonl)。初回2停止と修正コード/途中出力を保全。元run/台帳/入力/共通実装の変更なし。\n\n### 次段の役割と依存\n\n同chatが順次担当し、別chat/サブエージェントは起動しない。\n\n| ID | 担当・作業 | 完了条件 | 状態 |\n|---|---|---|---|\n| NP-01 | 技術診断：固定終点、施設空き、初期拠点到達、候補拒否を関連付ける | 登録入力の診断JSONと全seedの記述比較 | 完了 |\n| NP-02 | 資料：現在の災害時fleet/運転者/出庫・需要/予約/介助の根拠を整理 | 項目・母数・対象時点・原本・SHA・採否。不足は不足と明記 | 次の1件。公開案内とDrive再確認済み、災害時実測は不足 |\n| NP-03 | 資料：橋梁路面高・施設開設/介助/代替行先 | 空間/時刻/使用条件を照合。未確認edgeは自動復帰しない | 不足一覧登録済み |\n| NP-04 | 研究設計：資料が揃った場合の代替案と影響 | 方法変更はユーザー判断・事前登録後だけ採用 | 未採用。現条件の追加runなし |\n'


edit('05_タスク管理/jdrt/JDRT-実時間B境界整合_完了後分析タスク.md', task)
paired = json.loads((OUT / '対応seed・人物比較.json').read_text(encoding='utf-8'))['paired']
differences = {comparison: [r['state_count_differences'].get('admitted', 0) for r in paired if r['dimension'] == 'person_type' and r['group'] == 'type4' and r['comparison'] == comparison] for comparison in ['R1−R0', 'R2−R1']}
detail = '\n\n### ' + stamp + ' 境界整合B 完了後監査・次段方針\n\n' + current + '\n\nType4施設受入の対応seed人数差：' + json.dumps(differences, ensure_ascii=False) + '。退出・時間切れ・配車結果を別表示し、一般的有効性/無効性へ一般化しない。待ち/所要は観測件数と未完了状態を併記。初期拠点診断は登録入力の技術診断。単純な増車/再割当やGate変更を採用せず、供給/需要・路面高/施設条件の根拠整理を優先する。\n\n新成果物：`' + relative + '/`。道路全キー一意、0台速度空欄、人物/施設/event会計、選択候補と配車集合、3時計・遷移を独立照合。初回分類名の誤指定と非有限値の扱いで後処理が2回停止、ログと当時コード/途中出力を保全して修正。研究run失敗ではない。Drive2フォルダ5本文を読取、市通常運行案内をHTTP200再取得。災害時実測不足は未解消。外部送信/Drive編集/新runなし。詳細コマンド・時刻・チェックポイントはoperations.jsonl、コードとSHAは生成根拠。\n'
for name in ['05_タスク管理/jdrt/JDRT_実装タスク管理.md', '05_タスク管理/jdrt/JDRT-実時間B境界整合_開始準備監査.md', '00_全体整理/決定ログ.md', '01_経過報告/経過報告2026年08月/経過報告20260826.md']:
    edit(name, lambda s: s + detail)
for name in ['00_全体整理/INDEX.md', '06_研究結果/README.md']:
    prefix = '../' if name.startswith('00_') else '../'
    edit(name, lambda s: s + '\n\n### 2026-10-17 境界整合B 完了後監査\n\n[副指標・観測監査報告](' + prefix + relative + '/副指標・観測監査報告.html)・[取得監査](' + prefix + relative + '/データ取得監査.md)・[集計フロー](' + prefix + relative + '/集計・監査フロー.md)。15セルの登録済み分析、元データ不変。\n')
for name in ['README.md', '04_プログラム/README.md']:
    prefix = '' if name == 'README.md' else '../'
    edit(name, lambda s: s.replace('\n', '\n\n**境界整合Bの現在地（2026-10-17）：** BA-02〜06の完了後監査を完了。次は災害時供給/需要と入力根拠の不足整理。新runなし。監視PAUSED。[副指標報告](' + prefix + relative + '/副指標・観測監査報告.html)。下記の過去日時付き状態は履歴。\n', 1))
edit('04_プログラム/output/jdrt.html', lambda s: s.replace('<body>', '<body><aside style="margin:20px;padding:20px;background:#e4f0f1"><strong>2026-10-17：新境界整合Bの副指標・観測・取得監査完了。</strong>追加runなし、監視PAUSED。<a href="../../' + relative + '/副指標・観測監査報告.html">完了後監査報告</a></aside>', 1))
save = {'at_jst': stamp, 'current_state': current, 'changes': changes}
(OUT / '文書更新記録.json').write_text(json.dumps(save, ensure_ascii=False, indent=2), encoding='utf-8')
with (OUT / 'operations.jsonl').open('a', encoding='utf-8') as f:
    f.write(json.dumps({'at_jst': stamp, 'action': 'current_documents_updated', 'files': len(changes), 'detail': '文書更新記録.json'}, ensure_ascii=False) + '\n')
print(json.dumps({'updated': len(changes), 'current': current}, ensure_ascii=False))
