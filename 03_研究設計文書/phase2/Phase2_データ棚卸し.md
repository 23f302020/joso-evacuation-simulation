# Phase 2 データ棚卸し

> 作成日：2026/05/14  
> 目的：Phase 2（SUMO/TraCIによる自家用車避難シミュレーション）に使う入力データ、既存列、派生作成が必要なデータを整理する。  
> 位置づけ：判断不要の下準備文書。追加の外部データ取得は現時点で不要。

---

## 1. 結論

Phase 2の開始に必要な主要データは、既にローカルに存在する。

追加で必要なのは外部データ取得ではなく、既存データからSUMO用に派生作成するデータである。

---

## 2. Phase 2で直接使う既存データ

| 用途 | ファイル | 主な列・内容 | 状態 |
|---|---|---|---:|
| 常総市道路ネットワーク | `04_プログラム/output/network/joso_road_network.graphml` | osmnx GraphML | 既存 |
| 道路エッジ確認 | `04_プログラム/output/network/joso_edges.gpkg` | 道路リンク、ジオメトリ、Phase 1 edge ID | 既存 |
| 閉鎖タイムラインJSON | `04_プログラム/output/closure/road_closure_timeline.json` | 時刻別閉鎖エッジ | 既存 |
| 閉鎖タイムラインCSV | `04_プログラム/output/closure/road_closure_timeline.csv` | `timestamp`, `edge_id` | 既存 |
| 出発地メッシュ | `04_プログラム/output/agents/origin_points.csv` | `KEY_CODE`, `lon`, `lat`, `total_pop`, `elderly_pop` | 既存 |
| 避難所 | `04_プログラム/output/agents/shelters.csv` | `name`, `capacity`, `lon`, `lat` | 既存 |
| 到達不可結果 | `04_プログラム/output/routes/unreachable_agents.csv` | Phase 1到達不可エージェント | 既存 |

---

## 3. 補助的に使う既存データ

| 用途 | ファイル・フォルダ | 使い道 |
|---|---|---|
| 浸水想定区域 | `04_プログラム/data/flood_hazard_a31/` | 避難所の浸水リスク判定、道路閉鎖根拠 |
| 国土地理院KML | `04_プログラム/data/flood_kml/` | 実時系列の浸水範囲確認 |
| 浸水ナビ | `04_プログラム/data/suiboumap/hydrograph_origins_BP030.json` | 破堤点・時系列説明の補助 |
| 人口メッシュ | `04_プログラム/data/population_mesh/` | 1/10試行、車両台数換算の根拠 |
| 避難所原データ | `04_プログラム/data/shelters/` | 避難所属性の再確認 |
| 車両統計 | `04_プログラム/data/vehicle_stats/` | 車両保有率・車両台数換算の根拠 |
| 行政区域 | `04_プログラム/data/admin_boundary/` | 常総市範囲・市境確認 |

---

## 4. 既存データから派生作成するデータ

| 派生データ | 入力 | 目的 | 判断要否 |
|---|---|---|---:|
| `shelters_safety.csv` | `shelters.csv`、A31a浸水想定区域 | 避難所が浸水想定区域に入るか判定 | 要 |
| `agent_origins_10pct.csv` | `origin_points.csv` | 1/10試行用の出発地・車両数 | 要 |
| `time_mapping_sumo.csv` | `road_closure_timeline.csv`、破堤時刻 | t0〜t7をSUMO秒へ対応 | 要 |
| `edge_id_mapping.csv` | `joso_edges.gpkg`、SUMOネットワーク | Phase 1 edge IDとSUMO edge ID対応 | 技術設計 |
| `closure_timeline_sumo.json` | `road_closure_timeline.json`、`edge_id_mapping.csv` | TraCIで閉鎖するSUMO edge ID一覧 | 技術設計 |
| `agent_origins_sumo.csv` | `origin_points.csv`、SUMOネットワーク | 出発地をSUMO edgeへスナップ | 技術設計 |
| `shelters_sumo.csv` | `shelters.csv`、SUMOネットワーク | 避難所をSUMO edgeへスナップ | 技術設計 |

---

## 5. 実装前に確認する列

### `origin_points.csv`

| 列 | 内容 |
|---|---|
| `KEY_CODE` | 250mメッシュコード |
| `lon` | 出発地経度 |
| `lat` | 出発地緯度 |
| `total_pop` | メッシュ総人口 |
| `elderly_pop` | メッシュ高齢者人口 |

### `shelters.csv`

| 列 | 内容 |
|---|---|
| `name` | 避難所名 |
| `capacity` | 収容人数 |
| `lon` | 避難所経度 |
| `lat` | 避難所緯度 |

### `road_closure_timeline.csv`

| 列 | 内容 |
|---|---|
| `timestamp` | 閉鎖時刻 |
| `edge_id` | Phase 1の道路エッジID |

---

## 6. データ面の残課題

| 課題 | 内容 |
|---|---|
| 避難所安全性 | 浸水想定区域内の避難所を除外するか判断が必要 |
| 1/10試行 | 全メッシュを残して車両数だけ減らすか、メッシュを抽出するか判断が必要 |
| 車両台数換算 | 1メッシュ1台、人口換算、世帯・車両保有率換算のどれを採用するか判断が必要 |
| 時間軸 | 実時間か6時間圧縮か判断が必要 |
| edge ID対応 | Phase 1 edge ID と SUMO edge ID の対応が最重要 |

