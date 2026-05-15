# テスト結果 Phase 2 全域拡張

## 1. 対象・棚卸し生成テスト（2026/05/15）

対象スクリプト：

- `04_プログラム/scripts/p2_region_inventory.py`

生成物：

- `04_プログラム/output/sumo/regions/_management/phase2_region_targets.csv`
- `04_プログラム/output/sumo/regions/_management/phase2_region_inventory.csv`
- `04_プログラム/output/sumo/regions/_management/phase2_region_inventory.md`

実行コマンド：

```powershell
python -m py_compile 04_プログラム\scripts\p2_region_inventory.py
python 04_プログラム\scripts\p2_region_inventory.py all
```

結果：

| 確認項目 | 結果 |
|---|---:|
| 構文チェック | 合格 |
| Phase 2全域拡張対象 | 41件 |
| 事前確認OK | 41件 |
| Phase 1対象外として保持 | 3件 |
| `phase2_region_targets.csv` 行数 | 41行 |
| `phase2_region_inventory.csv` 内訳 | `yes, yes` 41件、`no, no` 3件 |

判定：

- 合格。
- Phase 1対象地域全域は、成果物化済み41市区町村として固定できる。
- 鹿嶋市・神栖市・東海村は、初回のPhase 2全域拡張には含めない判断を棚卸しファイルへ記録した。
- 対象41件は、Phase 1市区町村HTML・道路ネットワーク・基本アセットの存在確認がすべて揃っている。

残タスク：

- 市区町村別SUMOネットワーク変換は、代表の常総市で確認済み。全41市区町村の一括生成は未実行。
- 市区町村別edge対応表、閉鎖タイムライン、出発地、避難所、安全性判定の生成は未実行。
- small / 10pct / full の全域実行テストは、地域別SUMO入力生成後に実施する。

## 2. 市区町村別SUMOネットワーク変換テスト（2026/05/15）

対象スクリプト：

- `04_プログラム/scripts/p2_sumo_network.py`

実装内容：

- 従来の常総市単独出力は維持したまま、`--city-code` 指定時に `output/network/cities/{city_code}/` のGraphMLを読み込み、`output/sumo/regions/{city_code}/` へ地域別SUMO成果物を出力できるようにした。
- `list-region-targets` コマンドを追加し、`phase2_region_targets.csv` の対象地域を確認できるようにした。

実行コマンド：

```powershell
04_プログラム\venv\Scripts\python.exe -m py_compile 04_プログラム\scripts\p2_sumo_network.py
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_sumo_network.py inspect --city-code 08211
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_sumo_network.py all --city-code 08211
```

代表確認対象：

| 項目 | 値 |
|---|---|
| 市区町村コード | 08211 |
| 市区町村名 | 常総市 |
| GraphML | `output/network/cities/08211/08211_road_network.graphml` |
| OSM XML | `output/sumo/regions/08211/network/08211.osm.xml` |
| SUMO net.xml | `output/sumo/regions/08211/network/08211.net.xml` |
| 対応CSV | `output/sumo/regions/08211/derived/phase1_edge_osm_way_mapping.csv` |

結果：

| 確認項目 | 結果 |
|---|---:|
| 構文チェック | 合格 |
| GraphMLノード数 | 4,589 |
| GraphMLエッジ数 | 12,860 |
| OSM way / 対応CSV行数 | 12,860 |
| netconvert returncode | 0 |
| SUMO通常edge数 | 49,356 |

判定：

- 合格。
- `p2_sumo_network.py --city-code` により、市区町村別のGraphMLから地域別OSM XML・SUMO net.xml・Phase 1 edge対応CSVを生成できる。
- 次は、市区町村別 `edge_id_mapping.csv` と閉鎖edge未対応検査へ進む。

## 3. P2-REGION-5〜9 代表実行テスト（2026/05/15）

対象スクリプト：

- `04_プログラム/scripts/p2_region_pipeline.py`

実装内容：

- `mapping-city` / `mapping-targets`: 市区町村別edge対応表と未対応検査を生成する。
- `derived-city` / `derived-targets`: 時間軸、避難所安全性、人口メッシュ出発地、閉鎖タイムライン、SUMO edgeスナップを生成する。
- `scenario-city` / `scenario-targets`: small / 10pct / full のroute/configを生成する。
- `run-city` / `run-targets`: TraCI動的閉鎖ありで small / 10pct / full を実行する。
- `full-plan`: 10pct結果とfull車両数から、full試行の実行優先度を出力する。

代表確認対象：

| 項目 | 値 |
|---|---|
| 市区町村コード | 08211 |
| 市区町村名 | 常総市 |
| 地域別出力先 | `output/sumo/regions/08211/` |

実行コマンド：

```powershell
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py mapping-city --city-code 08211
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py derived-city --city-code 08211
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py run-city --city-code 08211 --scenario small
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py run-city --city-code 08211 --scenario 10pct
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py full-plan
```

edge対応結果：

| 確認項目 | 結果 |
|---|---:|
| 市別シナリオ閉鎖edge数 | 1,900 |
| edge対応件数 | 1,900 |
| matched | 1,900 |
| unmatched | 0 |
| 対応SUMO edge segment数 | 8,968 |

派生データ結果：

| 確認項目 | 結果 |
|---|---:|
| 時間軸 | 8行 |
| 避難所 | 9件 |
| 安全目的地 | 9件 |
| 出発地メッシュ | 405点 |
| small車両数 | 405台 |
| 10pct車両数 | 1,151台 |
| full車両数 | 9,569台 |
| 閉鎖未対応時点 | 0 |
| 出発地スナップ未対応 | 0 |
| 安全避難所スナップ未対応 | 0 |

TraCI実行結果：

| シナリオ | 車両数 | 到着 | 未到着 | 逃げ遅れ主指標 | 最終閉鎖SUMO edge |
|---|---:|---:|---:|---:|---:|
| small | 405 | 405 | 0 | 0 | 8,968 |
| 10pct | 1,151 | 1,151 | 0 | 0 | 8,968 |

full実行計画：

| 推奨区分 | 件数 |
|---|---:|
| representative_or_defer | 1 |
| wait_for_10pct | 40 |

判定：

- 代表地域（常総市）では、P2-REGION-5〜9の実行器が一連で動作することを確認した。
- small / 10pct の全41市区町村バッチ実行は未実施であるため、P2-REGION-7、P2-REGION-8、P2-REGION-9は実行器実装済み・全域実行待ちとして扱う。
- 10pct実行中にSUMOのteleport警告が1台で発生したが、最終集計では全車到着、逃げ遅れ主指標0台である。
