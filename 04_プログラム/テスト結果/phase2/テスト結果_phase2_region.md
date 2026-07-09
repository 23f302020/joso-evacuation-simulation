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

## 4. バッチ状態管理・失敗隔離テスト（2026/05/17）

対象スクリプト：

- `04_プログラム/scripts/p2_region_pipeline.py`

追加実装：

- `status`: 41市区町村の進捗と次アクションを `region_batch_status.csv/md` に出力する。
- `--codes`: targets系コマンドで処理対象コードを限定する。
- `--skip-completed`: 完了済み工程をスキップする。
- `--continue-on-error`: 失敗を `region_batch_failures.csv` に記録し、次の市区町村へ進む。
- `--max-process`: 完了済みスキップ後、未完了を最大N件だけ処理する。

実行コマンド：

```powershell
04_プログラム\venv\Scripts\python.exe -m py_compile 04_プログラム\scripts\p2_region_pipeline.py
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py status
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py mapping-targets --codes 08211 --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py mapping-targets --codes 08201 --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py mapping-targets --skip-completed --continue-on-error --max-process 2
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py mapping-targets --skip-completed --continue-on-error --max-process 1
```

状態表生成結果：

| 次アクション | 件数 |
|---|---:|
| full_plan_or_eval | 1 |
| mapping | 40 |

完了済みスキップ結果：

| 対象 | 結果 |
|---|---|
| 08211 常総市 | `mapping` 完了済みのためskip |
| processed / skipped / failed | 0 / 1 / 0 |

水戸市mapping実行結果：

| 確認項目 | 結果 |
|---|---:|
| OSM way数 | 29,821 |
| SUMO通常edge数 | 103,816 |
| 市別シナリオ閉鎖edge数 | 3,639 |
| edge対応件数 | 3,639 |
| matched | 3,639 |
| unmatched | 0 |
| 対応SUMO edge segment数 | 16,389 |

水戸市実行後の状態：

| 次アクション | 件数 |
|---|---:|
| derived | 1 |
| full_plan_or_eval | 1 |
| mapping | 39 |

判定：

- 合格。
- 全域実行前に、完了済みスキップ、対象コード限定、状態表生成、失敗隔離の基盤が成立した。
- 次は未処理39市区町村の `mapping-targets` を進め、その後 `derived-targets` へ進む。

追加mapping実行結果：

| コード | 市区町村 | 閉鎖edge | matched | unmatched | 判定 |
|---|---|---:|---:|---:|---|
| 08202 | 日立市 | 715 | 713 | 2 | `inspect_mapping` |
| 08203 | 土浦市 | 807 | 807 | 0 | `derived` |
| 08204 | 古河市 | 1,068 | 1,068 | 0 | `derived` |
| 08205 | 石岡市 | 777 | 777 | 0 | `derived` |

最終状態：

| 次アクション | 件数 |
|---|---:|
| derived | 4 |
| full_plan_or_eval | 1 |
| inspect_mapping | 1 |
| mapping | 35 |

補足：

- `--max-process 2` の実行中に15分タイムアウトしたが、古河市の中間成果物は有効だった。
- その後、古河市を単独で再実行し、検証JSONと管理summaryを確定した。
- 実装ミスとして `closure_timeline` 参照位置の誤りを修正し、`py_compile` 合格を確認した。

## 5. 日立市未対応edge調査・除外ポリシーテスト（2026/05/17）

対象スクリプト：

- `04_プログラム/scripts/p2_region_pipeline.py`

追加実装：

- `inspect-mapping-city`: `edge_id_mapping.csv` の `unmatched` を調査し、近接通常SUMO edgeと推奨処理を `edge_mapping_unmatched_inspection.csv/md` に出力する。
- `resolve-unmatched-city --policy exclude`: SUMO通常edgeが生成されなかった閉鎖edgeを `excluded_unmapped` として明示除外し、`edge_mapping_validation.json` を再生成する。
- `closure_timeline_sumo.json`: `excluded_unmapped_phase1_edge_ids` と件数を時刻別に記録する。
- `region_batch_status.csv`: `mapping_excluded_unmapped_count` を追加する。

実行コマンド：

```powershell
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py inspect-mapping-city --city-code 08202
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py resolve-unmatched-city --city-code 08202 --policy exclude
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py derived-city --city-code 08202
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py status
```

判断：

- 日立市の未対応2件は、OSM XML上のsynthetic way IDは存在するが、netconvert後の通常SUMO edgeとしては生成されていなかった。
- 近接junctionには通常edgeが存在するが、それらを代替閉鎖すると本来の短い接続部以外の流入・流出edgeまで止める可能性がある。
- そのため、代替閉鎖ではなく `excluded_unmapped` として明示除外する方針を採用した。欠落は2/715件であり、過剰閉鎖による歪みを避けるほうが適切と判断した。

日立市の結果：

| 確認項目 | 結果 |
|---|---:|
| phase1閉鎖edge数 | 715 |
| matched | 713 |
| unmatched | 0 |
| excluded_unmapped | 2 |
| can_proceed_to_region_closure | true |
| 出発地メッシュ | 107 |
| small車両数 | 107 |
| 10pct車両数 | 488 |
| full車両数 | 4,336 |
| 閉鎖未対応時点 | 0 |
| 除外edgeを含む閉鎖時点 | 5 |
| 出発地スナップ未対応 | 0 |
| 安全避難所スナップ未対応 | 0 |
| can_proceed_to_small | true |

除外edge：

| phase1_edge_id | 初回時点 | 閉鎖時点数 |
|---|---|---:|
| `5987717376_5987717380_0` | t3 | 5 |
| `5987717380_5987717376_0` | t3 | 5 |

最終状態：

| 次アクション | 件数 |
|---|---:|
| derived | 4 |
| full_plan_or_eval | 1 |
| mapping | 35 |
| run_small | 1 |

判定：

- 合格。
- 日立市は `inspect_mapping` から復帰し、次工程 `run_small` に進める状態になった。
- 今後同種の未対応edgeが出た場合は、調査レポートを生成したうえで、近隣edgeへの自動代替ではなく `excluded_unmapped` として記録除外する。ただし除外件数・割合が大きい場合は市区町村単位で手動確認へ回す。

## 6. Phase 2全域拡張の最終実行・統合テスト（2026/05/18）

対象スクリプト：

- `04_プログラム/scripts/p2_region_pipeline.py`
- `04_プログラム/scripts/gen_index.py`

実装・実行内容：

- 未処理35市区町村の `mapping-targets` を実行し、全41市区町村のedge対応表生成を完了した。
- 全41市区町村の `derived-targets` を完了した。
- 龍ケ崎市 `08208` と境町 `08546` で、スナップ距離に数値と空文字が混在したため集計処理を修正した。
- 出発地・安全避難所の一部がSUMO edgeへスナップできない場合でも、到達可能な出発地・安全避難所が残る場合は、未対応点を記録除外して後続処理へ進める方針を実装した。
- 全41市区町村で `small` と `10pct` を実行した。
- `10pct` 結果に基づき、`full` は代表・軽量対象6市区町村に限定して実行した。
- 市区町村別評価CSV、Phase 1/2比較CSV、全域SUMO結果HTML、トップページ導線を生成した。

主な実行コマンド：

```powershell
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py mapping-targets --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py derived-targets --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py run-targets --scenario small --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py run-targets --scenario 10pct --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py full-plan
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py run-targets --scenario full --codes 08224 08226 08233 08309 08442 08542 --skip-completed --continue-on-error
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\p2_region_pipeline.py region-finalize
04_プログラム\venv\Scripts\python.exe 04_プログラム\scripts\gen_index.py
```

実行結果：

| 確認項目 | 結果 |
|---|---:|
| Phase 2対象市区町村 | 41 |
| edge対応完了 | 41 |
| 派生データ生成完了 | 41 |
| small実行完了 | 41 |
| 10pct実行完了 | 41 |
| full実行完了 | 6 |
| fullを代表・後続課題扱いにした市区町村 | 35 |
| `10pct` 逃げ遅れ合計 | 0 |
| `full` 逃げ遅れ合計 | 0 |
| 市区町村別評価CSV行数 | 41 |
| Phase 1/2比較CSV行数 | 164 |
| `region_batch_status.csv` の `next_action=full_plan_or_eval` | 41 |

`full` 実行対象：

| city_code | 市区町村 | full車両数 | 到着 | 逃げ遅れ |
|---|---|---:|---:|---:|
| 08224 | 守谷市 | 333 | 333 | 0 |
| 08226 | 那珂市 | 498 | 498 | 0 |
| 08233 | 行方市 | 61 | 61 | 0 |
| 08309 | 大洗町 | 40 | 40 | 0 |
| 08442 | 美浦村 | 982 | 982 | 0 |
| 08542 | 五霞町 | 128 | 128 | 0 |

生成成果物：

| 成果物 | パス |
|---|---|
| 市区町村別評価CSV | `04_プログラム/output/sumo/evaluation/evacuation_summary_by_municipality.csv` |
| Phase 1/2比較CSV | `04_プログラム/output/sumo/evaluation/phase1_phase2_region_comparison.csv` |
| 全域SUMO結果HTML | `04_プログラム/output/sumo/regions/index.html` |
| トップページ | `04_プログラム/output/index.html` |

検証：

| テスト | 結果 |
|---|---|
| `py_compile` | `p2_region_pipeline.py`、`gen_index.py` とも合格 |
| 出力件数検証 | small 41、10pct 41、full 6を確認 |
| 評価CSV検証 | 41行、比較CSV 164行を確認 |
| HTMLリンク検証 | `sumo/regions/index.html` は92リンク中欠損0 |
| トップページ静的リンク検証 | `output/index.html` は3リンク中欠損0 |
| `phase1-pages.js` 動的リンク検証 | 63リンク中欠損0 |
| 実行プロセス残留確認 | `python`、`sumo`、`netconvert` の残留なし |

注意点：

- SUMO実行中に `No route`、teleport等の警告は複数出たが、全市区町村で実行終了コード0、summary出力あり、主評価指標では `10pct` 逃げ遅れ合計0であった。
- `msedge` と `playwright` コマンドがPATH上で検出できなかったため、ヘッドレスブラウザによるスクリーンショット検証は未実施である。HTMLリンクと生成ファイルの整合性はスクリプトで確認済みである。

判定：

- 合格。
- Phase 2全域拡張の残実装は完了し、全41市区町村で `small` / `10pct` のSUMO/TraCI結果を比較可能な形で整理した。

## 7. Phase 1/2考察利用前の追加確認（2026/05/18）

確認内容：

- Phase 1は静的ネットワーク分析、Phase 2はSUMO/TraCIによる動的車両シミュレーションとして分離されているか確認した。
- `phase1_phase2_region_comparison.csv` では、Phase 1行を `closed_edges_and_origin_meshes`、Phase 2行を `vehicle` または `vehicle_plan` として区別していることを確認した。
- `evacuation_summary_by_municipality.csv` の `origin_routable_count` と `safe_shelter_routable_count` に空欄が残っていたため、旧形式summaryを読む場合も `origin_count` / `safe_shelter_count` で補完するよう修正し、評価CSVを再生成した。

再検証結果：

| 確認項目 | 結果 |
|---|---:|
| 評価CSV行数 | 41 |
| 比較CSV行数 | 164 |
| `origin_routable_count` 空欄 | 0 |
| `safe_shelter_routable_count` 空欄 | 0 |
| small結果 | 41 |
| 10pct結果 | 41 |
| full実行結果 | 6 |
| 10pct逃げ遅れ合計 | 0 |
| full逃げ遅れ合計 | 0 |

考察利用上の判定：

- 利用可能。
- ただし、Phase 1の到達不可・閉鎖道路数とPhase 2の逃げ遅れ台数は同一指標ではないため、本文では「静的な道路ネットワーク制約」と「動的な車両流シミュレーション結果」として分けて説明する。
- `full` は全41市区町村ではなく6市区町村のみであり、全域比較の主指標は `10pct` とする。
