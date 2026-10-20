"""Create a separate dated diagram from the verified READY receipt and G1 evidence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DIAGRAMS = ROOT / '03_研究設計文書/図表・UML'
WS = ROOT / '04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1'
result = json.loads((OUT / 'preflight_20261018b.stdout.log').read_text(encoding='utf-8-sig'))
assert result['status'] == 'READY' and result['checks'] and all(result['checks'].values())
receipt_path = ROOT / result['report']
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'READY' and receipt == json.loads((WS / 'preflight_ready.json').read_text(encoding='utf-8'))
for relative, expected in receipt['implementation_sha256'].items():
    assert sha256((ROOT / relative).read_bytes()).hexdigest() == expected
for relative, expected in receipt['evidence_sha256'].items():
    assert sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
batch = json.loads((OUT / 'cs261018a_smoke_sequence.json').read_text(encoding='utf-8'))
assert batch['status'] == 'COMPLETED' and len(batch['completed']) == 14
unit = json.loads((ROOT / receipt['evidence']['unit']).read_text(encoding='utf-8'))
storage = json.loads((ROOT / receipt['evidence']['storage']).read_text(encoding='utf-8'))
now = datetime.now(timezone(timedelta(hours=9))).isoformat()
source_path = OUT / 'READY・新規資料_図v7根拠_20261018.json'
source = {'at_jst': now, 'receipt': result['report'], 'receipt_sha256': sha256(receipt_path.read_bytes()).hexdigest(),
          'unit_tests_pass': unit['tests_run'], 'common_implementation_sha256': receipt['implementation_sha256'],
          'smokes': batch['completed'], 'independent_receipt_checks': result['checks'],
          'evidence_file_count': len(receipt['evidence_sha256']), 'storage': storage,
          'new_source_classification': '02_情報調査/交通・地域/jdrt_goal_20261017/road_height_20261018/河道特性_取得・用途・目視検証.json',
          'research_core_started_at_creation': False, 'comparison_or_method_changed': False}
source['new_source_classification_sha256'] = sha256((ROOT / source['new_source_classification']).read_bytes()).hexdigest()
with source_path.open('x', encoding='utf-8') as stream:
    json.dump(source, stream, ensure_ascii=False, indent=2)
old = DIAGRAMS / 'JDRT_受付代替行動_READY証跡・逐次記録_v6.html'
text = old.read_text(encoding='utf-8').replace(' v6', ' v7').replace('49 unit PASS', f'{unit["tests_run"]} unit PASS')
text = text.replace('本図作成時：入力・容量を再照合中／研究core 0',
                    f'本図作成時：READY独立{len(result["checks"])}検査PASS／研究core 0')
rows = []
for row in batch['completed']:
    path = ROOT / row['validation_report']
    proof = json.loads(path.read_text(encoding='utf-8'))
    assert proof['status'] == 'PASS' and not proof['core_adoption_permitted']
    href = '../../' + row['validation_report']
    rows.append('<tr><td>' + escape(row['cell']['cell_id']) + '</td><td>PASS</td><td><a href="'
                + escape(href, quote=True) + '">' + escape(row['run_id']) + '</a></td></tr>')
text = re.sub(r'<tbody>.*?</tbody>', '<tbody>' + ''.join(rows) + '</tbody>', text, flags=re.S)
text = text.replace('最終14設定・共通21_技術証跡集計_20261018.json', source_path.name)
text = re.sub(r'作成 2026-10-18T[\d:.+\-]+。', '作成 ' + now + '。', text)
extra = '''<section><h2>新規取得資料の位置づけ</h2><p>市の河川縦断図は橋名・位置調査の参考資料。河床・堤防・地盤のY.P.mを、橋の走行面高へ置き換えない。点群の仕様書と全国メタデータも、常総市の橋面点群そのものではない。</p><p>現行登録入力へ追加せず、未取得の橋面高・測量時点・標高基準の照合を不足として保持する。RMS25cmは最大誤差の保証ではない。</p><p><a href="../../02_情報調査/交通・地域/jdrt_goal_20261017/road_height_20261018/路面高_公開候補・精度・採否監査.md">原本・精度・用途の監査</a> · <a href="../../05_タスク管理/jdrt/JDRT-受付代替行動_事前登録分析・出力対応表.md">全70件後の分析と一次出力</a></p></section>'''
text = text.replace('<section><h2>独立検証した設定', extra + '<section><h2>独立検証した設定')
target = DIAGRAMS / 'JDRT_受付代替行動_READY・資料位置づけ_v7.html'
with target.open('x', encoding='utf-8') as stream:
    stream.write(text)
ET.fromstring(re.search(r'<svg .*?</svg>', text, re.S).group(0))
class Links(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if tag == 'a' and key == 'href' and not value.startswith(('http:', 'https:', '#')):
                assert (target.parent / value).resolve().is_file(), value
Links().feed(text)
proof = {'at_jst': now, 'action': 'independent_diagram_v7_created_from_current_READY',
         'path': target.relative_to(ROOT).as_posix(), 'sha256': sha256(target.read_bytes()).hexdigest(),
         'source_path': source_path.relative_to(ROOT).as_posix(), 'source_sha256': sha256(source_path.read_bytes()).hexdigest(),
         'preserved_v6_sha256': sha256(old.read_bytes()).hexdigest(), 'svg_xml': 'PASS', 'local_links': 'PASS',
         'GUI_render_verified': False, 'core_effect_inference': False}
(OUT / '図v7_根拠・構造検証.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for path in [OUT / 'operations.jsonl', WS / 'driver_logs/operations.jsonl']:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(proof, ensure_ascii=False) + '\n')
print(json.dumps(proof, ensure_ascii=False))
