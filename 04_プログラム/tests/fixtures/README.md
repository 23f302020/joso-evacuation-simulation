# tests/fixtures — 小規模固定サンプル

外部データ取得（OSM・GIS・API）を一切呼ばずにテストするための、
小さな固定入力を置く。ネットワークI/Oはテストで絶対に呼ばない（再現性の敵）。

## 作成予定ファイル（テスト設計書 §6）

| ファイル | 内容 | 用途 | 作り方 |
|----------|------|------|--------|
| `mini_hydrograph.json` | 3メッシュ×2時刻、depth 0.499/0.5/0.501 | T1 浸水0.5m境界(float) | 実 `hydrograph_origins_BP030.json` の形式を縮小して手書き |
| `mini_a31a.xml` | A31a GML 最小2ポリゴン（waterDepth 1と2） | T1 浸水閾値(intコード値) | 実GMLから1フィーチャ抜粋しwaterDepthを書換 |
| `mini_vehicle_log.csv` | 5台（到着3/reroute失敗1/blocked1） | T6 summarize_vehicle_log | 手書き |
| `mini_origin_points.csv` | 3メッシュ（pop 0/23/100, elderly 0/5/27） | T5 回帰 | 実 `output/agents/origin_points.csv` から3行抜粋 |

## mini_edges（道路網）はコード生成する

「道路から29m/31m」の距離を正確に作るため、shapely で EPSG:6690（メートル）
座標を指定して構築し `to_crs(6668)` する。外部ファイル化せず conftest.py の
fixture（`flood_cell_factory` と同方式）でコード生成するのが確実。

## 注意

- fixture は「小さく・固定・決定論的」に保つ。実データの丸ごとコピーは置かない。
- shift_jis のメッシュ表を切り出す場合はエンコーディングを保持（エンコーディングバグ回帰用）。
