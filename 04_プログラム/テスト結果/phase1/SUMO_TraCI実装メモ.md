# SUMO + TraCI 実装メモ

> 作成日：2026/04/17  
> 目的：SUMOで鬼怒川氾濫避難シミュレーションを実装するための技術メモ。浸水進行に応じた動的道路閉鎖とバス運行の実装方法を整理する。

---

## 実装の全体像

```
浸水時系列データ（GSI KML・8時点）
        ↓
 各タイムステップで浸水ポリゴンと道路リンクを照合
        ↓
 TraCI API で浸水深0.5m以上の道路リンクを閉鎖
        ↓
 SUMO 上の車両・バスが閉鎖道路を迂回
        ↓
 逃げ遅れ人数・渋滞・避難完了時間を出力・記録
```

---

## 1. TraCI による動的道路閉鎖

### 基本的な仕組み

Python の `traci` ライブラリでシミュレーション実行中にリアルタイムで道路を操作できる。浸水ポリゴンの時系列に合わせて各ステップで閉鎖リンクを更新する。

```python
import traci

# SUMOを起動してTraCIで接続
traci.start(["sumo", "-c", "kinugawa.sumocfg"])

def close_flooded_edges(flooded_edge_ids):
    for edge_id in flooded_edge_ids:
        # 乗用車・バスともに通行不可に設定
        traci.edge.setDisallowed(edge_id, ["passenger", "bus"])

step = 0
while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    flooded = get_flooded_edges_at(step)  # 時系列KMLから判定
    close_flooded_edges(flooded)
    step += 1

traci.close()
```

### 参照URL

- TraCI Python インターフェース（公式）: https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html
- TraCI 日本語 wiki: https://kudzuyu.github.io/SUMO-wiki-ja/TraCI/

---

## 2. 浸水エリアの時系列マッピング手順

1. 国土地理院 KML（D1-No.917・8時点）から各時点の浸水ポリゴンを読み込む
2. osmnxで取得した常総市の道路ネットワークと GeoDataFrame で重ね合わせ
3. 浸水ポリゴンと交差する道路エッジIDのリストを時点別に作成
4. 各シミュレーションステップ（時刻）に対応する閉鎖リストを TraCI に渡す

```python
import osmnx as ox
import geopandas as gpd

# 常総市の道路ネットワーク取得
G = ox.graph_from_place("常総市, 茨城県, Japan", network_type='drive')
edges = ox.graph_to_gdfs(G, nodes=False)

# 浸水ポリゴンと重ね合わせ（各時点）
flood_polygon = gpd.read_file("flood_t1.kml")
flooded_edges = edges[edges.intersects(flood_polygon.geometry.union_all())]
flooded_edge_ids = flooded_edges.index.tolist()
```

---

## 3. バスの運行設定（シナリオB）

### 方針：固定往復ルートとして実装（卒論スコープ）

SUMOでのバスは公共交通（pt）として定義し、固定ルートを往復させる方式が最もシンプル。動的ルート変更はTraCIで可能だが、卒論スコープでは**台数の感度分析（3・5・10台）**に絞る実装が現実的。

```xml
<!-- routes.xml のバス定義例 -->
<vehicle id="bus_0" type="bus" depart="0" line="evacuation">
    <route edges="edge_1 edge_2 edge_3 shelter_edge"/>
</vehicle>
```

### TraCIでの動的ルート変更（発展実装・余裕があれば）

```python
# 浸水で通れなくなった際にバスルートをリアルタイム更新
traci.vehicle.setRoute("bus_0", new_route_edges)
```

---

## 4. 評価指標の取得方法

| 評価指標 | TraCI での取得方法 |
|---------|-----------------|
| 道路の平均速度（渋滞指標） | `traci.edge.getLastStepMeanSpeed(edge_id)` |
| 道路上の車両数（密度） | `traci.edge.getLastStepVehicleNumber(edge_id)` |
| 車両の現在位置 | `traci.vehicle.getPosition(vehicle_id)` |
| 避難完了（避難所到着） | 車両が避難所エッジに到達したことを検出 |
| 逃げ遅れ判定 | 浸水到達時刻に浸水エリア内にいる車両・歩行者をカウント |

---

## 5. 実装ロードマップ

| ステップ | 内容 | 難易度 |
|---------|------|--------|
| **Step 1** | osmnxで常総市道路NW取得 → netconvertでSUMO用ネットワーク変換 | ★★☆ |
| **Step 2** | 車両エージェント（シナリオA・車のみ）を投入して基本走行確認 | ★★☆ |
| **Step 3** | TraCIで浸水時系列に応じた動的道路閉鎖を実装 | ★★★ |
| **Step 4** | バス（固定ルート・5台）を追加してシナリオBを実装 | ★★☆ |
| **Step 5** | バス台数を3・5・10台に変えて感度分析を実施 | ★★☆ |
| **Step 6** | 出力データを集計し、渋滞・逃げ遅れをA/B比較 | ★★☆ |

---

## 6. 参考ツール・リンク

| ツール | 用途 | URL |
|--------|------|-----|
| SUMO 公式ドキュメント | 全般 | https://sumo.dlr.de/docs/ |
| TraCI Python API | 動的制御 | https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html |
| netconvert | OSMネットワーク → SUMO変換 | https://sumo.dlr.de/docs/netconvert.html |
| osmnx | 道路NW取得（Python） | https://github.com/gboeing/osmnx |
| UXsim | Python製軽量マクロ交通流シミュレータ（SUMO代替候補） | https://github.com/toruseo/UXsim |
