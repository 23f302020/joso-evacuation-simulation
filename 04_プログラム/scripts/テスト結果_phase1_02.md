# テスト結果 Phase 1 — 第4回

## サマリー

全5スクリプト（c3/e1/i1/i2/i3）の構文確認・実行テストをすべて完了しました。
実害のある不具合（OneDrive ファイルロック・KML バッファ CRS・列名解釈・座標式・型差異・最近傍ノード）を修正し、通しで正常動作を確認しました。

| スクリプト | 構文チェック | 実行テスト | 備考 |
|---|---|---|---|
| `c3_get_road_network.py` | ✅ | ✅ | 道路エッジ 12,860 件・CRS EPSG:6668 |
| `e1_load_flood_data.py` | ✅ | ✅ | 浸水ポリゴン 8 時点・CRS EPSG:6668 |
| `i1_spatial_join.py` | ✅ | ✅ | 閉鎖エッジ数 33/31/31/33/20/15/33/33 |
| `i2_generate_closure.py` | ✅ | ✅ | JSON・CSV 出力完了 |
| `i3_route_search.py` | ✅ | ✅ | 出発地 11 メッシュ・到達不可 各時点 3 メッシュ |

---

## テスト詳細

### 構文チェック（AST parse）

```bash
cd 04_プログラム/scripts
python -c "import ast, sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" \
  c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py i3_route_search.py
```

**結果：** ✅ 5ファイルすべて成功

---

### 実行テスト

```bash
cd 04_プログラム/scripts
python c3_get_road_network.py
python e1_load_flood_data.py
python i1_spatial_join.py
python i2_generate_closure.py
python i3_route_search.py
```

**各スクリプトの確認結果：**

| スクリプト | 確認項目 | 結果 |
|---|---|---|
| `c3_get_road_network.py` | 道路エッジ数・CRS | 12,860 件・EPSG:6668 |
| `e1_load_flood_data.py` | 浸水ポリゴン時点数・CRS | 8 時点・EPSG:6668 |
| `i1_spatial_join.py` | タイムスタンプ別閉鎖エッジ数 | 33, 31, 31, 33, 20, 15, 33, 33 |
| `i2_generate_closure.py` | JSON・CSV 出力 | 正常生成 |
| `i3_route_search.py` | 出発地メッシュ数・総人口・高齢者数 | 11 メッシュ・人口 723・高齢者 146 |
| `i3_route_search.py` | 避難所件数 | 19 件 |
| `i3_route_search.py` | ルート HTML | 8 ファイル生成 |
| `i3_route_search.py` | 到達不可（各時点） | 3 メッシュ・人口 87 |

---

## 今回修正した不具合

| 修正内容 | 対象スクリプト |
|---|---|
| Windows/OneDrive 既存ファイルロック時の `PermissionError` 対策 | c3・e1・i1・i2・i3 |
| KML バッファを地理座標系（度）から投影 CRS（EPSG:6690・メートル）で実施 | e1 |
| T001178 CSV の総人口列（`T001178001`）・65歳以上列（`T001178043`〜`T001178055`）を明示指定 | i3 |
| 250m メッシュ座標式をセル南西隅からセル中心点（`+3.75秒`/`+5.625秒`）に修正 | i3 |
| 避難所フラグ `P20_007` の整数/文字列型差異に対し `.astype(str)` を追加 | i3 |
| `ox.distance.nearest_nodes()`（scikit-learn 依存）を純 Python `min()` で代替 | i3 |

---

## 生成された出力ファイル一覧

| 出力ファイル | 生成スクリプト | 確認状態 |
|---|---|---|
| `output/network/joso_road_network.graphml` | c3 | ✅ |
| `output/network/joso_edges.gpkg` | c3 | ✅ |
| `output/network/joso_network_map.html` | c3 | ✅ |
| `output/flood/flood_polygons.pkl` | e1 | ✅ |
| `output/flood/flood_timeline_map.html` | e1 | ✅ |
| `output/closure/closure_dict.pkl` | i1 | ✅ |
| `output/closure/road_closure_timeline.json` | i2 | ✅ |
| `output/closure/road_closure_timeline.csv` | i2 | ✅ |
| `output/agents/origins.csv` | i3 | ✅ |
| `output/agents/shelters.csv` | i3 | ✅ |
| `output/routes/evacuation_routes_t0.html` 〜 `t7.html` | i3 | ✅（8ファイル） |
| `output/routes/unreachable.csv` | i3 | ✅ |

---

## 残っている課題

### 到達不可メッシュ数が全タイムスタンプで一定

封鎖なし（`closure=[]`）では到達不可 0 になるため封鎖の影響自体は出ているが、時系列変化が見られない。

原因と対応方針の選択肢：

| 選択肢 | 内容 | 影響 |
|---|---|---|
| A（累積封鎖） | 浸水ポリゴンを時点ごとに累積扱いにする | 時間が進むほど封鎖が増え到達不可が増加する |
| B（浸水範囲拡張） | 出発地の対象メッシュを浸水エリア外まで広げる | より多くの出発地を扱い変化が出やすくなる |

どちらを採用するかは研究のモデル設定（実際の洪水進行をどう扱うか）に関わるため、**指導教員への確認が必要**。

---

## 次のステップ（優先順）

| 優先度 | タスク | 内容 |
|---|---|---|
| 1 | I-3 モデル判断 | 到達不可が時系列変化しない問題を選択肢A・Bどちらで解消するか指導教員に確認 |
| 2 | 進捗文書の更新 | `実装タスク一覧.md`・`AGENTS.md` の c3〜i3 完了状態を更新 |
| 3 | I-4 SUMO 変換 | `i4_convert_sumo.py` 実装：OSMnx 道路 NW を SUMO `.net.xml` に変換 |
| 4 | I-5 シナリオA | `origins.csv` から車両エージェントを生成・SUMO `.rou.xml` 作成・走行テスト |
| 5 | I-6 TraCI 動的封鎖 | `road_closure_timeline.json` を使って時刻別に道路閉鎖・逃げ遅れ車両ログ取得 |

---

## 各ステップの詳細

### 優先度1：I-3 モデル判断（指導教員確認）

#### 問題の本質

`i3_route_search.py` は全8タイムスタンプで「到達不可 3メッシュ・人口87人」が変わらない。封鎖なしだと到達不可ゼロになるので封鎖の効果自体は出ているが、**時系列変化がない**。

#### 選択肢A：累積封鎖

```python
# 現在のコード（各時点独立）
closed = closure_timeline.get(ts, [])

# 案A（累積）
all_closed = []
for ts in config.KML_TIMESTAMPS[:idx+1]:
    all_closed += closure_timeline.get(ts, [])
closed = list(set(all_closed))
```

| 項目 | 内容 |
|------|------|
| 研究上の意味 | 「一度浸水した道路は最後まで通れない」という仮定 |
| 期待される結果 | t=0(15本) → t=1(33本) → … と単調増加し、到達不可が時系列で増える |
| 妥当性の根拠 | 実際の鬼怒川氾濫では浸水は数日間継続。引き波は緩やか |

#### 選択肢B：出発地拡張

```python
# 現在のコード（t=0浸水エリア内メッシュのみ）
first_flood = flood_dict[config.KML_TIMESTAMPS[0]]
origins = load_mesh_origins(config.MESH_FILE, first_flood)

# 案B（浸水エリア外も含める）
# 常総市全域メッシュ、または全タイムスタンプの浸水エリア合算を対象にする
origins = load_mesh_origins(config.MESH_FILE, flood_union_all)
```

| 項目 | 内容 |
|------|------|
| 研究上の意味 | 「浸水していない住民も事前避難する」という仮定 |
| 期待される結果 | 出発地が増えるため、封鎖パターンの違いが到達不可数に反映されやすい |
| 妥当性の根拠 | 避難勧告は浸水前から発令される |

#### 指導教員への確認フレーム

> 「時刻別道路封鎖を用いた迂回ルート検索を実装しましたが、現状では全タイムスタンプで到達不可数が変わりません。浸水ポリゴンを累積扱いにする案（A）と、出発地を浸水エリア外まで広げる案（B）のどちらが研究の前提として適切でしょうか。」

---

### 優先度3：I-4 SUMO 道路ネットワーク変換

Phase 2 の入口。osmnx で取得済みの道路NWをSUMOが読める形式に変換する。

#### 必要なツール確認

```bash
sumo --version
netconvert --version
```

インストール先の例（Windows）：`C:\Program Files (x86)\Eclipse\Sumo\bin\netconvert.exe`

#### 変換の流れ

```
joso_road_network.graphml
        ↓  osmnx で .osm 形式にエクスポート
joso.osm
        ↓  netconvert で変換
joso.net.xml  ←  SUMO が読む形式
```

#### 実装スクリプト概要（`i4_convert_sumo.py`）

```python
import osmnx as ox
import subprocess

G = ox.load_graphml("output/network/joso_road_network.graphml")
ox.save_graph_xml(G, filepath="output/sumo/joso.osm")

subprocess.run([
    "netconvert",
    "--osm-files",    "output/sumo/joso.osm",
    "--output-file",  "output/sumo/joso.net.xml",
    "--geometry.remove",    # 不要ジオメトリ除去
    "--roundabouts.guess",  # ロータリー自動検出
    "--ramps.guess",        # ランプ自動検出
    "--junctions.join",     # 近接交差点統合
])
```

#### 注意点

- osmnx 2.x では `save_graph_xml()` の API が変わっている可能性あり（実行時に確認）
- netconvert は SUMO インストール時に同梱される

---

### 優先度4：I-5 シナリオA 車両エージェント投入

i3 で生成済みの `origins.csv`（11メッシュ・人口723）を SUMO の車両ファイルに変換する。

#### 入力データ

| ファイル | 内容 |
|---------|------|
| `output/agents/origins.csv` | メッシュ重心 lon/lat・人口 |
| `output/agents/shelters.csv` | 避難所 lon/lat 19件 |
| `output/sumo/joso.net.xml` | 変換済み道路NW |

#### 実装の流れ（`i5_generate_agents.py`）

```python
# 1. origins.csv を読み込み SUMO ノードIDに変換
#    （lon/lat → net.xml 内の junction ID）

# 2. 車両台数を算出
#    世帯あたり 1.25台 × 人口から世帯数を推定

# 3. scenario_a.rou.xml を生成
# <vehicle id="v0" depart="0.0">
#   <route edges="edge1 edge2 edge3"/>
# </vehicle>

# 4. joso_sim.sumocfg を生成
# <configuration>
#   <net-file   value="joso.net.xml"/>
#   <route-files value="scenario_a.rou.xml"/>
#   <begin value="0"/> <end value="86400"/>
# </configuration>
```

#### 課題

- osmnx の node ID と SUMO の junction ID の対応付けが必要
- 出発時刻の設定（避難開始をいつにするか）

---

### 優先度5：I-6 TraCI 動的道路閉鎖

`road_closure_timeline.json` を使って、シミュレーション実行中にリアルタイムで道路を封鎖する。

#### 仕組み

```
SUMO シミュレーション実行中
        ↓  Python（TraCI）がステップごとに介入
        ↓  現在の simulation time が浸水時点を超えたら
        ↓  traci.edge.setAllowed(edge_id, []) で封鎖
```

#### タイムスタンプ → シミュレーション秒数の変換

破堤時刻（12:50）を基準 0秒として換算する。

| タイムスタンプ | 破堤からの経過時間 | シミュレーション秒 |
|---|---|---|
| 2015-09-10T18:00 | +5h10m | 18,600秒 |
| 2015-09-11T06:00 | +17h10m | 61,800秒 |
| 2015-09-11T18:00 | +29h10m | 105,000秒 |
| 2015-09-12T06:00 | +41h10m | 148,200秒 |
| 2015-09-12T18:00 | +53h10m | 191,400秒 |
| 2015-09-13T06:00 | +65h10m | 234,600秒 |
| 2015-09-13T18:00 | +77h10m | 277,800秒 |
| 2015-09-16T10:20 | +141h30m | 509,400秒 |

#### 実装概要（`i6_traci_control.py`）

```python
import traci, json

with open("output/closure/road_closure_timeline.json") as f:
    closure_timeline = json.load(f)

TIMESTAMP_TO_SIM_SEC = {
    "2015-09-10T18:00:00": 18600,
    "2015-09-11T06:00:00": 61800,
    # ...
}

traci.start(["sumo", "-c", "output/sumo/joso_sim.sumocfg"])
step = 0
while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    for ts, sim_sec in TIMESTAMP_TO_SIM_SEC.items():
        if step == sim_sec:
            for edge_id in closure_timeline.get(ts, []):
                traci.edge.setAllowed(edge_id, [])  # 全車両通行禁止
    step += 1
traci.close()
```

#### 主要出力

| ファイル | 内容 |
|---------|------|
| `stranded_vehicles.csv` | 浸水タイミングで封鎖エリア内にいた車両数 |
| `congestion_log.csv` | 各エッジの平均速度・密度の時系列 |

---

## 全体の依存関係

```
【完了】Phase 1 全スクリプト（c3/e1/i1/i2/i3）
       ↓
【最優先】指導教員確認 → i3 モデル修正（選択肢A or B）
       ↓
i4 SUMO変換 → i5 車両エージェント投入 → i6 TraCI動的封鎖
       ↓
Phase 2 完了 → Phase 3（バス追加・A/B比較・集計）
```

> **I-3 のモデル判断が研究の方向性を決める最重要ステップ。** 指導教員への確認を最初に済ませること。
