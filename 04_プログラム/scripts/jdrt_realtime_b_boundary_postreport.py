"""Report and cross-table verification for the immutable boundary secondary audit."""
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import gzip
import hashlib
import html
import json
import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '06_研究結果/jdrt/realtime_b_boundary_v2/postanalysis_20261017'
P = json.loads((ROOT / '04_プログラム/config/jdrt_realtime_b_boundary_v2.json').read_text(encoding='utf-8'))
W = ROOT / P['workspace']
INPUT = W / P['input_directory']


def now():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def count(cell, dimension='all', group='all'):
    return next(r for r in cell['outcomes'] if r['dimension'] == dimension and r['group'] == group)


def num(x):
    return '—' if x is None else f'{x:.2f}' if isinstance(x, float) else str(x)


def main():
    data = json.loads((OUT / '副指標・観測監査集計.json').read_text(encoding='utf-8'))
    cells = data['cells']
    expected = {(seed, scenario) for seed in P['seeds'] for scenario in P['scenarios']}
    assert {(c['seed'], c['scenario']) for c in cells} == expected and len(cells) == len(expected)
    checks = []
    pairs = []
    matrices = []
    original = {}
    # Independent csv module counts, event assignment joins, selected candidate rows.
    for c in cells:
        directory = W / 'runs' / c['run_id']
        with (directory / 'person_results.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        original[(c['seed'], c['scenario'])] = {r['person_id']: r for r in rows}
        for r in c['outcomes']:
            sub = rows if r['dimension'] == 'all' else [x for x in rows if x.get(r['dimension']) == r['group']] if r['dimension'] != 'terminal_kind' else None
            if sub is not None:
                assert len(sub) == r['denominator'] and dict(Counter(x['status'] for x in sub)) == r['states']
        assignments = set()
        with (directory / 'events.jsonl').open(encoding='utf-8') as f:
            for line in f:
                e = json.loads(line)
                if e['event'] == 'drt_assigned':
                    assignments.add((e['time_sec'], e['vehicle_id'], e['person_id']))
        chosen = set()
        for chunk in pd.read_csv(directory / 'candidates.csv.gz', chunksize=200000, usecols=['time_sec', 'vehicle_id', 'person_id', 'decision']):
            selected = chunk[chunk.decision == 'selected']
            for r in selected.itertuples():
                key = (float(r.time_sec), r.vehicle_id, r.person_id)
                assert key not in chosen
                chosen.add(key)
        assert chosen == assignments
        assert sum(g['rows'] for g in c['candidates']['groups']) == c['candidates']['rows']
        checks.append({'run_id': c['run_id'], 'independent_person_groups': True, 'selected_candidates_equal_assignments': True,
                       'selected': len(chosen), 'candidate_rows_reconcile': True})
    for seed in P['seeds']:
        for a, b in [('R0', 'R1'), ('R1', 'R2')]:
            ca = next(c for c in cells if c['seed'] == seed and c['scenario'] == a)
            cb = next(c for c in cells if c['seed'] == seed and c['scenario'] == b)
            assert set(original[(seed, a)]) == set(original[(seed, b)])
            for dimension, group in [('all', 'all'), ('person_type', 'type3'), ('person_type', 'type4')]:
                x, y = count(ca, dimension, group), count(cb, dimension, group)
                assert x['denominator'] == y['denominator']
                states = {k: y['states'].get(k, 0) - x['states'].get(k, 0) for k in sorted(set(x['states']) | set(y['states']))}
                assert sum(states.values()) == 0
                pairs.append({'seed': seed, 'comparison': b + '−' + a, 'dimension': dimension, 'group': group,
                              'denominator': x['denominator'], 'state_count_differences': states,
                              'admission_pct_point_difference': 100 * (y['admitted'] - x['admitted']) / x['denominator']})
            cross = Counter()
            for pid, x in original[(seed, a)].items():
                y = original[(seed, b)][pid]
                assert (x['person_type'], x['terminal_id'], x['ready_sec'], x['selected_jdrt']) == (y['person_type'], y['terminal_id'], y['ready_sec'], y['selected_jdrt'])
                cross[(x['person_type'], x['selected_jdrt'], x['status'], y['status'])] += 1
            matrices.append({'seed': seed, 'comparison': b + '−' + a,
                             'rows': [{'person_type': k[0], 'selected_jdrt': k[1], 'from_status': k[2], 'to_status': k[3], 'people': n} for k, n in sorted(cross.items())]})
    save('対応seed・人物比較.json', {'paired': pairs, 'individual_state_matrices': matrices, 'checks': checks})
    # Registered graph diagnostic only: no alternate input, no changed routing or simulation.
    raw = json.loads((INPUT / 'graphs.json').read_text(encoding='utf-8'))['passenger']
    graph = nx.DiGraph() if raw['directed'] else nx.Graph()
    graph.add_nodes_from(raw['nodes'])
    graph.add_edges_from((a, b) for a, b, _ in raw['edges'])
    hazard = pd.read_csv(INPUT / 'hazard.csv', dtype={'edge_id': str})
    graph.remove_nodes_from(hazard.loc[(hazard['mode'] == 'passenger') & hazard.closure_sec.eq(0), 'edge_id'])
    manifest = json.loads((INPUT / 'manifest.json').read_text(encoding='utf-8'))
    depot = manifest['depot_edge']
    reachable = (nx.descendants(graph, depot) | {depot}) if depot in graph else set()
    origins = pd.read_csv(INPUT / 'origins.csv', keep_default_na=False, dtype={'edge_id': str}).set_index('origin_id')
    pop = pd.read_csv(INPUT / 'people.csv')
    reachable_origins = set(origins.index[origins.edge_id.isin(reachable)])
    diag = {'definition': 'Initial closure removed passenger graph; directed reachability from registered depot only. Not dispatch outcome or future vehicle position.',
            'depot_edge': depot, 'reachable_graph_nodes': len(reachable), 'initial_graph_nodes': len(graph),
            'origin_count': len(origins), 'reachable_origin_count': len(reachable_origins),
            'population_by_type': [{'person_type': typ, 'people': len(sub), 'initial_depot_reachable': int(sub.origin_id.isin(reachable_origins).sum())}
                                   for typ, sub in pop.groupby('person_type')],
            'no_policy_change': True}
    save('初期拠点接続診断.json', diag)
    # One source for both human-readable formats.
    md, web = [], []
    def heading(title, level=2):
        md.append('#' * level + ' ' + title + '\n')
        web.append(f'<h{level}>{html.escape(title)}</h{level}>')
    def para(text):
        md.append(text + '\n')
        web.append('<p>' + html.escape(text) + '</p>')
    def table(headers, rows):
        md.append('| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join(['---'] * len(headers)) + ' |\n' + '\n'.join('| ' + ' | '.join(num(x) for x in r) + ' |' for r in rows) + '\n')
        web.append('<div class="scroll"><table><thead><tr>' + ''.join('<th>' + html.escape(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(num(x)) + '</td>' for x in r) + '</tr>' for r in rows) + '</tbody></table></div>')
    heading('境界整合B：副指標・時間・候補・道路の完了後監査', 1)
    para('作成：' + now() + '。新15セルのみ。一次人物・要求・施設・イベント・候補・道路・遷移を再読取し、元249ファイルのSHAを集計前後に確認した。追加run・条件変更・旧系列の混在なし。')
    heading('結果から確定する次の方針')
    para('登録条件の比較報告を確定し、次は固定終点・初期拠点接続・候補の到達可能性を優先した根拠整理と、現在の災害時供給／需要資料の不足解消へ進む。単純な増車や予測重みの変更を自動採用しない。追加シミュレーションは開始しない。')
    primary_pairs = [r for r in pairs if r['dimension'] == 'person_type' and r['group'] == P['evaluation']['primary_type']]
    for comparison in ['R1−R0', 'R2−R1']:
        differences = [r['state_count_differences'].get(P['evaluation']['primary_status'], 0) for r in primary_pairs if r['comparison'] == comparison]
        para('Type4施設受入の ' + comparison + ' 人数差（登録seed順）は ' + ', '.join(str(x) for x in differences) + '。')
    para('退出・未完了・配車結果には違いがあり、この主指標だけでJDRTや予測一般の効果なしとは言えない。p値・母集団推論・未完了時間の推定は追加しない。')
    heading('Type4：全員を分母に残した終了状態')
    table(['seed', '条件', '分母', '施設到着', '受入', '退出', '満員', '時間切れ', 'DRT不能', 'その他不能'],
          [[c['seed'], c['scenario'], (r := count(c, 'person_type', 'type4'))['denominator'], r['facility_arrived'], r['admitted'], r['boundary_exit'], r['states'].get('capacity_rejected', 0), r['states'].get('time_limit', 0), r['states'].get('stranded_drt', 0), sum(n for k, n in r['states'].items() if k not in ['admitted', 'boundary_exit', 'capacity_rejected', 'time_limit', 'stranded_drt'])] for c in cells])
    heading('Type3・全人口と対応seed差')
    table(['seed', '条件', 'Type3受入/退出/時限', '全人口受入', '全人口退出', '全人口時限'],
          [[c['seed'], c['scenario'], '/'.join(str((r := count(c, 'person_type', 'type3'))['states'].get(k, 0)) for k in ['admitted', 'boundary_exit', 'time_limit']), count(c)['admitted'], count(c)['boundary_exit'], count(c)['states'].get('time_limit', 0)] for c in cells])
    table(['seed', '比較', '対象', '受入差（%pt）', '退出人数差', '時間切れ人数差'],
          [[r['seed'], r['comparison'], r['group'], r['admission_pct_point_difference'], r['state_count_differences'].get('boundary_exit', 0), r['state_count_differences'].get('time_limit', 0)] for r in pairs])
    para('人物IDで対応させた終了状態の移行表、全Type・mode・固定終点種別・選択有無の分解はJSONおよび人物区分CSVへ保存した。全区分合計が分母と一致。結果に応じた人物の除外はない。')
    heading('固定終点と施設容量の構造')
    fixed = Counter()
    for r in cells[0]['fixed_terminal_population']:
        if r['person_type'] == P['evaluation']['primary_type']:
            fixed[r['terminal_kind']] += r['people']
    for c in cells:
        assert c['fixed_terminal_population'] == cells[0]['fixed_terminal_population']
    table(['Type4固定終点種別', '人数'], list(sorted(fixed.items())))
    table(['seed', '条件', '施設', '容量', '受入', '空き'], [[c['seed'], c['scenario'], f['terminal_id'], f['capacity'], f['admitted'], f['capacity'] - f['admitted']] for c in cells for f in c['facilities']])
    para('固定終点は全条件・seedで共通。空き容量があっても別施設へ再割当する設計ではない。固定退出先の人は受入の分母へ残るが、登録ルールでは施設受入に至らない。この構造と経路・容量の制約を報告し、低い主指標を供給量だけの原因と断定しない。')
    heading('要求・乗降・所要時間：観測範囲付きの記述')
    table(['seed', '条件', 'DRT要求', '乗車開始', '乗車完了', '降車完了', '要求→乗車完了の平均秒（観測者のみ）'],
          [[c['seed'], c['scenario'], (t := next(r for r in c['timing'] if r['dimension'] == 'all' and r['metric'] == 'request_to_pickup_complete'))['eligible'], c['event_counts'].get('boarding_started', 0), t['observed'], c['event_counts'].get('drt_alighted', 0), t['mean_sec']] for c in cells])
    para('request_secは外生ready_secであり予約受理ではない。car/walkのdepart_secはSUMOへの投入要求時刻で、物理的な発進・道路への挿入待ちの実測ではない。ready_to_departが0でも混雑待ち0とは言わない。pickup_secは乗車300秒の処理完了。車両の終点停車はalighting_started、arrival_secは降車300秒の完了後の割当。未乗車・未到達は0に補完せず、全対象者・観測者・欠けた終点・その終了状態を各指標へ併記した。観測者だけの平均差を全要求者の待ち時間改善とは解釈しない。time_limit以外の不能・満員・退出は競合状態であり、一律に同じ打切りとはしない。')
    heading('候補評価とGate：経路拒否を独立に区分')
    table(['seed', '条件', '評価行数', '選択', 'no_pickup_route', 'no_delivery_route', 'forecast_gate', 'Gate適用・pass', 'Gate適用・reject'],
          [[c['seed'], c['scenario'], c['candidates']['rows'], sum(g['rows'] for g in c['candidates']['groups'] if g['decision'] == 'selected'), *[sum(g['rows'] for g in c['candidates']['groups'] if g['reason'] == reason) for reason in ['no_pickup_route', 'no_delivery_route', 'forecast_gate']], *[sum(g['rows'] for g in c['candidates']['groups'] if g['gate_class'] == kind) for kind in ['pass', 'reject']]] for c in cells])
    para('評価行は車両×人物×配車cycle×stageの反復で、拒否人数ではない。優先理由no_pickup_route/no_delivery_routeとforecast_gateは排他的なreason集計。Gate不合格欄には経路なしも含まれるため、それを全て予測情報による追加拒否と呼ばない。適用なし行のgate_pass=Trueも成功へ加えない。選択候補の時刻・車両・人物集合はdrt_assignedイベントと全セル一致した。')
    heading('初期拠点接続の登録入力診断')
    para('初期閉鎖を除いた登録車道graphで、登録拠点 ' + depot + ' から到達可能な起点は ' + str(diag['reachable_origin_count']) + '/' + str(diag['origin_count']) + '。これは初期の有向接続の診断で、移動後の車両位置や将来配車可能性を示す値ではない。道路除外や一拠点の構造を確認する資料として保持する。')
    table(['Type', '人物母数', '初期拠点から到達可能な起点の人物'], [[r['person_type'], r['people'], r['initial_depot_reachable']] for r in diag['population_by_type']])
    heading('道路・遷移・閉鎖時計・警告')
    table(['seed', '条件', '道路行数', 'snapshot', '候補行数', '遷移行数', '閉鎖進入', '曖昧', '警告'],
          [[c['seed'], c['scenario'], c['roads']['rows'], c['roads']['snapshots'], c['candidates']['rows'], c['transitions']['rows'], c['transitions']['closed_entries'], c['transitions']['ambiguous'], sum(c['warnings'].values())] for c in cells])
    table(['seed', '条件', 'mode', '0台行', '観測されたactorの反復数', '停止actorの反復数'], [[c['seed'], c['scenario'], r['mode'], r['zero_rows'], r['count'], r['halting_count']] for c in cells for r in c['roads']['by_mode']])
    para('全道路キーは各snapshotで一度ずつ存在。0台行だけ平均速度が空欄で、欠測を0台へ置換していない。道路別と60秒時刻別の集約CSVを保存。反復actor数は固有車両数でもperson数でもなく、60秒間の連続平均・滞留時間・VKTへ変換しない。重み付き速度も観測時点のactor観測の平均に限定する。')
    para('閉鎖予定T・実呼出しmax(0,T−0.5)・観測上限T・phaseをhazardから全件再計算。初期・最終境界を含み、最大0.5秒先行を隠さない。遷移は閉鎖表と上限時刻から再判定した。閉鎖制御除去、stranded_drt、SUMO警告はJSONに分類と実例を保存。警告0を採用条件へ追加せず、元の正式PASSを維持する。')
    heading('取得できたものと残るもの')
    para('本系列で登録された人物・要求・施設・候補Gate・全道路snapshot・全step遷移・閉鎖3時計は取得・集約・照合できた。現実の災害時利用率・予約分布・車両／運転者・路面高は実測未取得のまま。現在の通常運行、2015年型校正洪水、人口／運用仮定の時点と位置づけを分けた。詳細はデータ取得監査を参照する。')
    heading('次段の詳細タスクと実行境界')
    table(['ID', '役割・順序', '作業', '完了条件・現在状態'], [
        ['NP-01', '同chat・技術診断', '固定終点・施設空き・初期拠点到達性・候補経路拒否の対応を保存', '今回完了。入力診断JSONと全seed比較あり'],
        ['NP-02', '同chat・資料担当', '現在の災害時車両/運転者/出庫・利用意思/予約分布・介助の根拠を取得台帳化', '公開案内を再取得、実測不足を確認済み。未取得項目は不足として保留、問い合わせ送信なし'],
        ['NP-03', '同chat・入力根拠担当', '橋梁/路面高・施設開設/介助/代替行先を現行資料の時点付きで整理', '不足項目と必要条件を取得監査へ登録。未確認edgeを自動復帰しない'],
        ['NP-04', '同chat・研究設計整理', '資料が得られた場合の登録仮定との差、方法変更の代替案と影響を具体化', '現条件は確定報告。追加感度/再割当/対象/主要指標変更は未採用、別判断・事前登録が必要'],
    ])
    para('当面は既存登録条件の監査済み比較を研究結果として保持する。一般化や追加runを先取りせず、外部送信・Drive編集・公開更新を行わない。監視jdrt-b-15はPAUSEDのまま。論文提出用編集の保留条件と既存Phase3の結論も維持する。')
    heading('証跡と再現手順')
    para('生成コード：04_プログラム/scripts/jdrt_realtime_b_boundary_postanalysis.py と postreport.py。project venv Python -X utf8から順に実行。初回分類名の誤指定、2回目の非有限値の扱いによる停止、修正前コードと途中出力は保存済み。元runや正式台帳の変更はない。後処理の失敗を研究runの失敗と混同しない。')
    links = [('副指標・観測監査集計.json', '全集計JSON'), ('対応seed・人物比較.json', '対応seed・人物比較'), ('初期拠点接続診断.json', '初期接続診断'), ('データ取得監査.md', 'データ取得監査'), ('Drive読取証跡.json', 'Drive証跡'), ('分析生成根拠.json', '生成根拠'), ('operations.jsonl', '実行・修正履歴'), ('../全セル結果一覧.html', '主指標の独立全セル一覧')]
    md.append('関連資料：' + '・'.join(f'[{title}]({name})' for name, title in links) + '\n')
    web.append('<nav>' + ' / '.join(f'<a href="{html.escape(name)}">{html.escape(title)}</a>' for name, title in links) + '</nav>')
    (OUT / '副指標・観測監査報告.md').write_text('\n'.join(md), encoding='utf-8')
    style = 'body{font:16px/1.8 system-ui,sans-serif;color:#20303e;background:#f5f7fa;margin:0}main{max-width:1180px;margin:auto;padding:36px 24px 80px}h1{font-size:2rem}h2{margin-top:2.5em;border-bottom:2px solid #aac6ce;padding-bottom:.3em}p{max-width:1000px}table{border-collapse:collapse;width:100%;background:white;font-size:.88rem}th,td{border:1px solid #d0dce2;padding:8px 12px;text-align:left;white-space:nowrap}th{background:#e4f0f1}tr:nth-child(even){background:#f7fafb}.scroll{overflow-x:auto;margin:20px 0}a{color:#005e83}nav{padding:20px;background:#e4f0f1}'
    (OUT / '副指標・観測監査報告.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>境界整合B 完了後監査</title><style>' + style + '</style><main>' + ''.join(web) + '</main></html>', encoding='utf-8')
    save('報告独立照合.json', {'at_jst': now(), 'cells': checks, 'paired_count_accounts': True, 'common_person_realization': True, 'initial_graph_diagnostic': diag})
    with (OUT / 'operations.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'at_jst': now(), 'action': 'report_complete', 'cells': len(cells), 'independent_candidate_assignment_join': True, 'static_diagnostic': True}, ensure_ascii=False) + '\n')
    print(json.dumps({'cells': len(cells), 'roads': sum(c['roads']['rows'] for c in cells), 'candidates': sum(c['candidates']['rows'] for c in cells), 'fixed_type4': dict(fixed), 'depot_diagnostic': diag}, ensure_ascii=False))


if __name__ == '__main__':
    main()
