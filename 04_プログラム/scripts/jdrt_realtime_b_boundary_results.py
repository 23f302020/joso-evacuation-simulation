"""Read-only audit and independent primary-outcome listing for registered boundary B.

Requires all registered cells formally recorded. Does not launch SUMO or change inputs.
"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import csv
import hashlib
import html
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / '04_プログラム/config/jdrt_realtime_b_boundary_v2.json'
P = json.loads(CONFIG.read_text(encoding='utf-8'))
W = ROOT / P['workspace']
LEDGER = ROOT / '05_タスク管理/jdrt/JDRT-実時間B境界整合_セル検証台帳.jsonl'
OUT = ROOT / '06_研究結果/jdrt/realtime_b_boundary_v2'
NOW = datetime.now().astimezone().isoformat()
SOURCES = {}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def evidence(path):
    digest = sha(path)
    SOURCES[path.relative_to(ROOT).as_posix()] = digest
    return digest

def read_json(path):
    evidence(path)
    return json.loads(path.read_text(encoding='utf-8'))

def read_csv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

ledger = [json.loads(x) for x in LEDGER.read_text(encoding='utf-8').splitlines() if x.strip()]
expected = {(s, seed) for seed in P['seeds'] for s in P['scenarios']}
assert len(ledger) == len(expected) == len({r['run_id'] for r in ledger})
assert {(r['scenario'], r['seed']) for r in ledger} == expected
assert all(r['protocol'] == P['protocol'] for r in ledger)
evidence(LEDGER)
parameter_sha = evidence(CONFIG)
evidence(ROOT / P['pap'])
input_sha = evidence(W / P['input_directory'] / 'manifest.json')
common = None
cohort = None
cells = []
for seed in P['seeds']:
    for scenario in P['scenarios']:
        record = next(r for r in ledger if r['seed'] == seed and r['scenario'] == scenario)
        directory = W / 'runs' / record['run_id']
        manifest = read_json(directory / 'manifest.json')
        validation = read_json(directory / 'validation.json')
        assert manifest['status'] == 'COMPLETED' and manifest['purpose'] == 'core'
        assert manifest['protocol'] == P['protocol'] and validation['status'] == 'PASS'
        assert manifest['parameter_sha256'] == parameter_sha and manifest['input_manifest_sha256'] == input_sha
        assert validation['manifest_sha256'] == sha(directory / 'manifest.json')
        assert all(validation['checks'].values())
        assert common is None or manifest['implementation_sha256'] == common
        common = manifest['implementation_sha256']
        for name, digest in manifest['output_sha256'].items():
            assert evidence(directory / name) == digest, (record['run_id'], name)
        rows = read_csv(directory / 'person_results.csv')
        ids = {r['person_id'] for r in rows}
        assert len(ids) == len(rows) == validation['people']
        assert dict(Counter(r['status'] for r in rows)) == manifest['summary']['states']
        type4 = [r for r in rows if r['person_type'] == 'type4']
        ids4 = {r['person_id'] for r in type4}
        assert cohort is None or cohort == ids4
        cohort = ids4
        admitted = sum(r['status'] == 'admitted' and 0 <= float(r['admitted_sec']) <= P['simulation']['duration_sec'] for r in type4)
        exits = sum(r['status'] == 'boundary_exit' for r in type4)
        assert len(type4) == validation['type4_denominator'] == record['validation']['type4_denominator']
        assert admitted == validation['type4_admitted'] == record['validation']['type4_admitted']
        assert exits == validation['type4_boundary_exit'] == record['validation']['type4_boundary_exit']
        vehicles = read_csv(directory / 'vehicle_results.csv')
        trips = {r.attrib['id']: float(r.attrib['routeLength']) for r in ET.parse(directory / 'tripinfo.xml').getroot().findall('tripinfo')}
        assert all((r['distance_m'] == '' and r['vehicle_id'] not in trips and float(r['observed_distance_m']) == 0)
                   or (r['distance_m'] != '' and trips.get(r['vehicle_id']) == float(r['distance_m'])) for r in vehicles)
        distance = sum(float(r['distance_m']) for r in vehicles if r['distance_m'] != '') / 1000
        assert abs(distance - sum(trips.values()) / 1000) < 1e-6
        assert abs(distance - validation['total_vehicle_km']) < 1e-6
        warnings = [x for x in (directory / 'sumo_errors.log').read_text(encoding='utf-8').splitlines() if 'Warning:' in x]
        cells.append({'seed': seed, 'scenario': scenario, 'run_id': record['run_id'], 'people': len(rows),
                      'type4_denominator': len(type4), 'type4_admitted': admitted,
                      'type4_rate_pct': 100 * admitted / len(type4), 'type4_boundary_exit': exits,
                      'all_admitted': sum(r['status'] == 'admitted' for r in rows),
                      'all_boundary_exit': sum(r['status'] == 'boundary_exit' for r in rows),
                      'final_states': dict(Counter(r['status'] for r in rows)),
                      'road_rows': validation['road_rows'], 'candidate_rows': validation['candidate_rows'],
                      'transition_rows': validation['transitions'], 'closed_entries': validation['closed_entries'],
                      'ambiguous_transitions': validation['ambiguous_transitions'], 'vehicle_km': distance,
                      'sumo_warnings': warnings, 'validation': validation['status'],
                      'primary_csv_recomputed': True, 'recorded_at_jst': record['recorded_at_jst']})
for name, digest in common.items():
    assert evidence(ROOT / name) == digest
evidence(Path(__file__))
pairs = []
for seed in P['seeds']:
    group = {r['scenario']: r for r in cells if r['seed'] == seed}
    pairs.append({'seed': seed, 'R0_admitted': group['R0']['type4_admitted'],
                  'R1_admitted': group['R1']['type4_admitted'], 'R2_admitted': group['R2']['type4_admitted'],
                  'denominator_each': group['R0']['type4_denominator'],
                  'R1_minus_R0_pp': group['R1']['type4_rate_pct'] - group['R0']['type4_rate_pct'],
                  'R2_minus_R1_pp': group['R2']['type4_rate_pct'] - group['R1']['type4_rate_pct']})
intro = ('登録された全15セルの一覧。新系列だけを含み、旧B8記録・旧失敗・smokeを含めない。'
         '人物CSVから主指標を別処理で再計数し、各runの独立検証・台帳と照合。全成果物SHAも再照合した。'
         '道路・候補・遷移の行数は各runの独立validate結果を表示し、この一覧生成時には全行の再検証を反復していない。')
limits = ['主指標は6時間以内の域内登録施設受入。退出を受入へ加算せず、全Type4を分母に保持する。',
          'USACE校正水理計算と参照人口・仮定運用の条件付きモデル。現在実態や現場の安全保証ではない。',
          '橋梁等の未検証edge除外、域内4施設・容量・固定終点と退出境界の影響を含む。',
          'native水位300秒、物理制御は最大0.5秒先行。予定T・呼出し・観測上限を区別する。',
          '5seedの記述比較。p値・母集団の有効性・予測一般の有利不利は推定しない。',
          '副指標（Type3・待ち/所要・Gate・道路混雑）の集計と取得監査は次タスク。全PAP項目の分析完了ではない。',
          '監視設定は15分。実施ログの空白を準備監査へ記録済みで、連続監視を主張しない。']
cell_headers = ['seed', '条件', 'Type4受入/分母', '受入率%', 'Type4退出', '道路観測行', '候補行', '閉鎖後進入', '警告', 'run ID']
cell_rows = [[r['seed'], r['scenario'], f"{r['type4_admitted']}/{r['type4_denominator']}",
              f"{r['type4_rate_pct']:.6f}", r['type4_boundary_exit'], r['road_rows'], r['candidate_rows'],
              r['closed_entries'], len(r['sumo_warnings']), r['run_id']] for r in cells]
pair_headers = ['seed', 'R0受入', 'R1受入', 'R2受入', '各分母', 'R1−R0 %pt', 'R2−R1 %pt']
pair_rows = [[r['seed'], r['R0_admitted'], r['R1_admitted'], r['R2_admitted'], r['denominator_each'],
              f"{r['R1_minus_R0_pp']:.6f}", f"{r['R2_minus_R1_pp']:.6f}"] for r in pairs]
def md_table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(str, headers)) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])
def html_table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + html.escape(str(x)) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(str(x)) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'
title = 'JDRT 実時間B 境界整合：全15セル結果一覧'
report = '# ' + title + '\n\n生成：' + NOW + '\n\n' + intro + '\n\n## 全セル\n\n' + md_table(cell_headers, cell_rows) + '\n\n## 主指標のseed内記述比較\n\n' + md_table(pair_headers, pair_rows) + '\n\n## 適用範囲と残作業\n\n' + '\n'.join('- ' + x for x in limits) + '\n'
page = '<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title + '</title><style>body{font:16px/1.7 system-ui,sans-serif;background:#f2f5f8;color:#172b3a;margin:0}main{max-width:1440px;margin:auto;padding:32px 20px}h1{font-size:clamp(25px,4vw,40px)}.scroll{overflow-x:auto;background:white;border:1px solid #cfd9e1;border-radius:12px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:12px;border-bottom:1px solid #dde4eb;text-align:left;white-space:nowrap}th{background:#123a51;color:white}td:last-child{font-size:12px}li{margin:8px 0}.status{background:#dcefe6;padding:16px;border-radius:12px}</style><main><h1>' + title + '</h1><p class="status">15/15正式記録・共通実装・独立検証PASS。研究runの実行中0・未記録0。</p><p>' + html.escape(intro) + '</p><p>生成：' + NOW + '</p><h2>全セル</h2>' + html_table(cell_headers, cell_rows) + '<h2>主指標のseed内記述比較</h2>' + html_table(pair_headers, pair_rows) + '<h2>適用範囲と残作業</h2><ul>' + ''.join('<li>' + html.escape(x) + '</li>' for x in limits) + '</ul><p><a href="../../../05_タスク管理/jdrt/JDRT-実時間B境界整合_完了後分析タスク.md">完了後分析タスク</a> · <a href="../../../05_タスク管理/jdrt/JDRT-実時間B境界整合_開始準備監査.md">全操作・監視空白・警告監査</a> · <a href="../../../context.md">現在地</a></p></main></html>'
assert not OUT.exists(), 'Preserve an existing result directory; do not overwrite'
OUT.mkdir(parents=True)
(OUT / '全セル結果一覧.md').write_text(report, encoding='utf-8')
(OUT / '全セル結果一覧.html').write_text(page, encoding='utf-8')
(OUT / '全セル結果一覧.json').write_text(json.dumps({'protocol': P['protocol'], 'created_at_jst': NOW, 'cells': cells, 'paired_primary': pairs, 'limitations': limits}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
proof = {'protocol': P['protocol'], 'generated_at_jst': NOW, 'registered_cells': len(expected),
         'recorded_cells': len(ledger), 'implementation_sha256': common, 'source_sha256': SOURCES,
         'checks': {'registered_cell_set': True, 'no_old_protocol': True, 'common_implementation': True,
                    'all_output_sha': True, 'all_primary_csv_recomputed': True, 'all_primary_matches_validation_and_ledger': True,
                    'all_final_states_match_manifest': True, 'all_vehicle_distances_recomputed': True},
         'artifact_sha256': {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}}
(OUT / '生成根拠.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'output': str(OUT), 'cells': len(cells), 'paired_primary': pairs, 'source_files': len(SOURCES), 'checks': proof['checks']}, ensure_ascii=False))
