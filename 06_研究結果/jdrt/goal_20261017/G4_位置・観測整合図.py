"""Create an independent offline diagram from registered02; preserve v1."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parents[3]
config = ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json'
params = json.loads(config.read_text(encoding='utf-8'))
workspace = ROOT / params['workspace']
directory = workspace / params['input_directory']
manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
validation = json.loads((workspace / 'position_input_validation.json').read_text(encoding='utf-8'))
with (directory / 'place_positions.csv').open(encoding='utf-8-sig', newline='') as stream:
    positions = list(csv.DictReader(stream))
mapped = [p for p in positions if p['status'] == 'mapped']
stamp = datetime.now(timezone(timedelta(hours=9))).isoformat()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
proof = {p.relative_to(ROOT).as_posix(): sha(p) for p in
         (config, directory / 'manifest.json', directory / 'place_positions.csv',
          workspace / 'position_input_validation.json', ROOT / params['alignment_addendum'], Path(__file__))}
facts = {'places': len(positions), 'mapped': len(mapped), 'unconnected': len(positions) - len(mapped),
         'clamped': sum(abs(float(p['clamp_shift_m'])) > 1e-8 for p in mapped),
         'gap': max(float(p['lane_point_gap_m']) for p in mapped),
         'access': max(float(p['reference_to_car_point_m']) for p in mapped),
         'people': manifest['people'], 'cells': manifest['registered_cells']}
target = ROOT / '03_研究設計文書/図表・UML/JDRT_受付代替行動_位置・観測・距離_v2.html'
body = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>受付・代替行動：位置・観測・距離の整合</title><style>
body{{margin:0;background:#f3f6f8;color:#19333f;font:16px/1.8 system-ui,sans-serif}}main{{max-width:1160px;margin:auto;padding:28px 22px}}article{{padding:22px;background:white;border:1px solid #c8d5dd;border-radius:9px;margin:20px 0}}svg{{display:block;width:100%;height:auto}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #cedbe0}}a{{color:#006283}}.flag{{background:#fff1d9;padding:12px}}code{{overflow-wrap:anywhere}}small{{color:#425d69}}</style></head>
<body><main><h1>同じ起点を、同じ位置へ対応させる</h1><p>realtime_choice_v1 / registered02 / {stamp}</p>
<p class="flag">開始前の共通条件を登録済み。位置入力の独立検査は{html.escape(validation['status'])}。実行器の統合検証を継続中で、研究coreは未開始。効果を示す結果図ではありません。</p>
<article><h2>追加データと移動の対応</h2><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 510" role="img" aria-label="原座標を車道と歩道へ投影して、全modeの出発と乗降に結合する。駐車と再出庫待ちは配車用速度から分ける。">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#547583"/></marker></defs>
<g fill="none" stroke="#547583" stroke-width="2" marker-end="url(#arrow)"><path d="M225 75H285"/><path d="M535 75H595"/><path d="M835 75H895"/><path d="M410 120V175"/><path d="M715 120V175"/><path d="M410 255V310H255V345"/><path d="M715 255V310H850V345"/></g>
<g stroke="#91aab6"><rect x="10" y="30" width="215" height="90" rx="8" fill="#e9f0f4"/><rect x="285" y="30" width="250" height="90" rx="8" fill="#e9f0f4"/><rect x="595" y="30" width="240" height="90" rx="8" fill="#e9f0f4"/><rect x="895" y="30" width="195" height="90" rx="8" fill="#e9f0f4"/>
<rect x="285" y="175" width="250" height="80" rx="8" fill="#e2f1e9"/><rect x="595" y="175" width="240" height="80" rx="8" fill="#e2f1e9"/>
<rect x="30" y="345" width="450" height="115" rx="8" fill="#e8f2f8"/><rect x="610" y="345" width="480" height="115" rx="8" fill="#fff1d9"/></g>
<g font-family="system-ui,sans-serif" font-size="17" text-anchor="middle" fill="#19333f">
<text x="118" y="65">既存の参照座標</text><text x="118" y="93">起点中心・施設点</text>
<text x="410" y="65">車道への投影・配置制約</text><text x="410" y="93">前端7m以上／末端1m前</text>
<text x="715" y="65">歩道の対応位置</text><text x="715" y="93">車道点から最近接投影</text>
<text x="993" y="65">位置表＋SHA</text><text x="993" y="93">独立XML/PROJ照合</text>
<text x="410" y="207">私有車出発・DRT迎車</text><text x="410" y="235">施設到着・降車stop</text>
<text x="715" y="207">通常／代替徒歩の出発</text><text x="715" y="235">同じ施設・退出対応点</text>
<text x="255" y="378">現在位置を含む所要推定</text><text x="255" y="407">同じ道路の後方 → 前進閉路／経路なし</text><text x="255" y="436">徒歩は端点graph＋SUMO stage距離</text>
<text x="850" y="378">raw観測を残して交通速度を分離</text><text x="850" y="407">路上／駐車／再出庫待ち／初回出発待ち</text><text x="850" y="436">配車用速度は路上車両のみ。0件はfree-flow</text>
<text x="550" y="498" font-size="15">全modeの仮想アクセス省略は共通。参照点は実入口や個人住所の測量ではない。</text></g></svg></article>
<article><h2>位置表から計算した範囲</h2><table><tr><th>追加・維持データ</th><th>位置づけ</th></tr>
<tr><td>{facts['places']}地点：対応{facts['mapped']}／未接続{facts['unconnected']}</td><td>元IDと接続edgeを維持。未接続起点の人物も分母へ残す。</td></tr>
<tr><td>配置制約を適用した地点 {facts['clamped']}</td><td>車体・gap・道路末端制約による移動量を全件保存。</td></tr>
<tr><td>車道／歩道対応点の最大差 {facts['gap']:.3f}m</td><td>横断方向の分離も記録。完全同一XYとは呼ばない。</td></tr>
<tr><td>参照点→車道点の最大距離 {facts['access']:.3f}m</td><td>この仮想アクセス時間は全mode共通に初期配置へ集約。建物からの実避難時間ではない。</td></tr>
<tr><td>人口{facts['people']:,}人／登録{facts['cells']}セル</td><td>需要マスク・準備時刻・D0/D1終点選択はregistered01と同一バイト。</td></tr></table></article>
<article><h2>徒歩距離の数式と観測</h2><p>累積通過予定距離 P、毎stepの速度積分 I＝ΣvΔt、新しい残経路予定長 L を区別し、再経路は max(P,I)＋L ≤ 3000m を検査します。現在位置を保持して旧経路の残り長を求め、Pへ通過部分だけを加えます。次stepの最大増分を残予算が下回るときは移動前に停止し、その先行量を保存します。</p><p>stage置換後のpersoninfo過去length合算は実通過距離と一致しないことを実測しました。予定長と速度積分を別に残し、単純合算による二重計上を避けます。</p></article>
<article><h2>根拠と残る検証</h2><p><a href="../jdrt/常総市JDRT_受付代替行動_位置・観測整合_事前登録追補_v1.md">事前登録追補</a> / <a href="../../05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md">詳細タスク</a> / <a href="JDRT_受付代替行動_データ・状態遷移_v1.html">旧版図解（保全）</a></p><p>現場の需要・供給、入口・路面高・介助条件は不足資料として維持します。正式run検証、故意改変拒否、統合境界試験、全14設定smoke、記録処理のREADY後に本実験を開始します。Drive読取のみ、外部送信・公開更新なし。</p><details><summary>生成根拠SHA-256</summary><pre><code>{html.escape(json.dumps(proof, ensure_ascii=False, indent=2))}</code></pre></details></article></main></body></html>'''
with target.open('x', encoding='utf-8') as stream:
    stream.write(body)
record = {'at_jst': stamp, 'artifact': target.relative_to(ROOT).as_posix(), 'artifact_sha256': sha(target),
          'source_sha256': proof, 'facts': facts, 'core_adoption': False}
with (Path(__file__).parent / 'operations.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps({'operation': 'create_independent_alignment_diagram_v2', **record}, ensure_ascii=False) + '\n')
print(json.dumps({k: v for k, v in record.items() if k != 'source_sha256'}, ensure_ascii=False, indent=2))
