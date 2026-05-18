# Phase 2 実装タスク管理

> 作成日：2026/05/14  
> 目的：Phase 2（SUMO/TraCIによる自家用車避難シミュレーション）の実装作業を、実行可能な粒度まで分割して管理する。  
> 関連：`Phase2_詳細タスク管理.md`、`Phase2_判断事項一覧.md`、`03_研究設計文書/phase2/Phase2_実装前仕様.md`  
> 進捗記録先：`01_経過報告/経過報告20260520.md`

---

## 1. 実装対象

Phase 2では、まず常総市実データ版を対象に、シナリオA（自家用車のみ）の交通流ベースラインを作る。

2026/05/15時点で、常総市ケースの実装・テスト・可視化は完了済みである。
Phase 1対象地域全域へ広げる作業は、`P2-IMPL-REGION` として別マイルストーン化し、既存の常総市成果物を壊さずに市区町村別バッチ処理へ拡張する。

ここでいう「Phase 1対象地域全域」は、Phase 1で成果物化済みの茨城県内41市区町村を指す。Phase 1対象外として整理済みの鹿嶋市・神栖市・東海村を含めるかどうかは、全域拡張とは別の判断事項として扱う。

Phase 3で扱うバス・デマンド交通は、この実装タスク管理には含めない。

---

## 2. 凡例

| マーク | 意味 |
|---|---|
| ✅ | 完了 |
| 🔄 | 作業中 |
| ❌ | 未着手 |
| ⏸ | 依存タスク待ち |
| 🔴 | 停止条件・要確認 |

---

## 3. 実装マイルストーン

| マイルストーン | 内容 | 状態 | 主な成果物 |
|---|---|---:|---|
| P2-IMPL-0 | 実装環境・作業ディレクトリ準備 | ✅ | SUMO 1.26.0、`output/sumo/` |
| P2-IMPL-1 | SUMO道路ネットワーク変換 | ✅ | `joso.osm.xml`, `joso.net.xml` |
| P2-IMPL-2 | Phase 1 edge ID と SUMO edge ID の対応 | ✅ | `edge_id_mapping.csv` |
| P2-IMPL-3 | 派生データ生成 | ✅ | `shelters_safety.csv`, `agent_origins_10pct.csv`, `time_mapping_sumo.csv` |
| P2-IMPL-4 | SUMO出発地・避難所スナップ | ✅ | `agent_origins_sumo.csv`, `shelters_sumo.csv` |
| P2-IMPL-5 | 小規模シナリオA route/config生成 | ✅ | `scenario_a_small.rou.xml`, `scenario_a_small.sumocfg` |
| P2-IMPL-6 | TraCI動的道路閉鎖 | ✅ | `p2_traci_closure.py`, `scenario_a_small_closure_log.csv` |
| P2-IMPL-7 | 1/10試行・全量試行 | ✅ | `scenario_a_10pct.*`, `scenario_a.*` |
| P2-IMPL-8 | 評価CSV・比較表生成 | ✅ | `evacuation_summary.csv`, `phase1_phase2_comparison.csv` |
| P2-IMPL-9 | 成果物トップページ更新 | ✅ | Phase 1/2/3別 `index.html` |
| P2-TEST | 実装内容テスト・修正 | ✅ | `テスト結果_phase2.md`, `p2_sumo_env.py` |
| P2-IMPL-VIZ | SUMO結果のHTML可視化 | ✅ | `vehicles_small.js`, `vehicles_10pct.js`, `closures.js`, `sumo_viz.html` |
| P2-IMPL-REGION | Phase 1対象地域全域へのSUMO拡張 | 🔄 | 対象リスト・入力棚卸し生成済み、市区町村別SUMO入力・評価統合・全域可視化 |

---

## 4. P2-IMPL-0：環境・作業ディレクトリ

| ID | タスク | 状態 | 成果物・確認 |
|---|---|---:|---|
| P2-IMPL-0-1 | SUMO 1.26.0を導入する | ✅ | 公式MSIをユーザー領域へ管理展開 |
| P2-IMPL-0-2 | `SUMO_HOME` を設定する | ✅ | `C:\Users\Ko_rr\AppData\Local\Programs\sumo-1.26.0-msi-extract\PFiles\Eclipse\Sumo` |
| P2-IMPL-0-3 | `sumo`, `sumo-gui`, `netconvert`, `netedit` を確認する | ✅ | 各 `--version` で 1.26.0 |
| P2-IMPL-0-4 | `traci` / `sumolib` importを確認する | ✅ | `SUMO_HOME/tools` 経由で成功 |
| P2-IMPL-0-5 | SUMO用出力ディレクトリを作成する | ✅ | `network`, `derived`, `scenarios`, `results` |

---

## 5. P2-IMPL-1：SUMO道路ネットワーク変換

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-1-1 | `joso_road_network.graphml` のノード・エッジ属性を確認する | ✅ | P2-IMPL-0 | `graphml_attribute_summary.md` | `u`, `v`, `key`, `osmid`, `geometry`, `length` を確認 |
| P2-IMPL-1-2 | GraphMLからOSM XMLへ変換する方針を実装に落とす | ✅ | 1-1 | `p2_sumo_network.py` | Phase 1 edge ID と synthetic way ID を保持 |
| P2-IMPL-1-3 | `joso.osm.xml` を生成する | ✅ | 1-2 | `output/sumo/network/joso.osm.xml`, `output/sumo/derived/phase1_edge_osm_way_mapping.csv` | 12,860 waysを出力、Phase 1 edge ID → way ID 対応CSVを同時生成 |
| P2-IMPL-1-4 | `netconvert` で `joso.net.xml` を生成する | ✅ | 1-3 | `output/sumo/network/joso.net.xml` | edge 49,356件、returncode 0 |
| P2-IMPL-1-5 | SUMOでネットワークを読み込み確認する | ✅ | 1-4 | `sumo_network_summary.md` | edge 49,356件、SUMO読込OK |

停止条件：

- `joso.net.xml` が生成できない場合は、route生成へ進まない。
- 変換時に元IDを追跡できない場合は、edge ID対応表の方針を修正する。

---

## 6. P2-IMPL-2：edge ID対応

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-2-1 | SUMO edge一覧を抽出する | ✅ | P2-IMPL-1 | `sumo_edges.csv` | 通常edge 49,356件 |
| P2-IMPL-2-2 | Phase 1閉鎖edge一覧を抽出する | ✅ | Phase 1出力 | `phase1_closed_edges.csv` | 閉鎖edge 764件 |
| P2-IMPL-2-3 | `edge_id_mapping.csv` を生成する | ✅ | 2-1,2-2 | `output/sumo/derived/edge_id_mapping.csv` | 764件に `mapping_status` を付与 |
| P2-IMPL-2-4 | 未対応・曖昧対応edgeを検査する | ✅ | 2-3 | `edge_mapping_validation.json` | 764件すべてmatched |
| P2-IMPL-2-5 | 必要なら手動確認結果を追記する | ✅ | 2-4 | 不要 | `unmatched` 0件のため手動追記なし |

停止条件：

- 閉鎖対象edgeに `unmatched` が残る場合、TraCI閉鎖実装へ進まない。

---

## 7. P2-IMPL-3：派生データ生成

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-3-1 | `time_mapping_sumo.csv` を生成する | ✅ | 実装前仕様 | `output/sumo/derived/time_mapping_sumo.csv` | t0=789、t7=21600 |
| P2-IMPL-3-2 | 避難所浸水リスクを判定する | ✅ | A31a, shelters | `shelters_safety.csv` | 19件すべて安全目的地 |
| P2-IMPL-3-3 | 人口メッシュから車両台数を算出する | ✅ | origin_points | `agent_origins_10pct.csv` | 40メッシュ、小規模40台、1/10試行120台、全量1,001台 |
| P2-IMPL-3-4 | 派生データの列・件数を仕様書と照合する | ✅ | 3-1〜3-3 | `derived_data_validation.json` | `can_proceed_to_sumo_snap=true` |

---

## 8. P2-IMPL-4：SUMO edgeへのスナップ

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-4-1 | 出発地メッシュをSUMO edgeへスナップする | ✅ | P2-IMPL-1,3 | `agent_origins_sumo.csv` | 40件すべてmatched |
| P2-IMPL-4-2 | 安全避難所をSUMO edgeへスナップする | ✅ | P2-IMPL-1,3 | `shelters_sumo.csv` | 19件すべてmatched |
| P2-IMPL-4-3 | スナップ距離の外れ値を確認する | ✅ | 4-1,4-2 | `snap_validation.json` | 出発地最大468.839m、避難所最大103.35m、未対応0件 |

---

## 9. P2-IMPL-5：小規模シナリオA route/config生成

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-5-1 | 小規模テスト用の車両ID規則を決める | ✅ | P2-IMPL-4 | `p2_sumo_scenario.py` | `veh_small_{origin_id}_{連番}` |
| P2-IMPL-5-2 | `scenario_a_small.rou.xml` を生成する | ✅ | 5-1 | `scenario_a_small.rou.xml` | 40台のtripを生成 |
| P2-IMPL-5-3 | `scenario_a_small.sumocfg` を生成する | ✅ | 5-2 | `scenario_a_small.sumocfg` | network/route/tripinfo出力を指定 |
| P2-IMPL-5-4 | 小規模シナリオを閉鎖なしで実行する | ✅ | 5-3 | `scenario_a_small_tripinfo.xml` | 40台すべて到着、平均326.95秒 |

---

## 10. P2-IMPL-6：TraCI動的道路閉鎖

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-6-1 | `closure_timeline_sumo.json` を生成する | ✅ | P2-IMPL-2,3 | `closure_timeline_sumo.json` | 8時点すべて未対応0件 |
| P2-IMPL-6-2 | TraCI実行スクリプトを作成する | ✅ | 6-1,5 | `p2_traci_closure.py` | SUMO起動・終了を確認 |
| P2-IMPL-6-3 | 指定時刻でedge閉鎖を実行する | ✅ | 6-2 | `scenario_a_small_closure_log.csv` | t0〜t7の閉鎖件数を記録 |
| P2-IMPL-6-4 | 閉鎖後の再経路探索を実装する | ✅ | 6-3 | `scenario_a_small_closure_log.csv` | reroute成功・失敗列を出力 |
| P2-IMPL-6-5 | 到達不能・600秒停止を記録する | ✅ | 6-4 | `scenario_a_small_vehicle_log.csv` | 主指標列 `stranded_main` を出力 |

---

## 11. P2-IMPL-7：1/10試行・全量試行

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-7-1 | 1/10試行 route/config を生成する | ✅ | P2-IMPL-6 | `scenario_a_10pct.*` | 120台 |
| P2-IMPL-7-2 | 1/10試行を実行する | ✅ | 7-1 | `scenario_a_10pct_traci_summary.json` | 120台すべて到着、逃げ遅れ0台 |
| P2-IMPL-7-3 | 全量試行 route/config を生成する | ✅ | 7-2 | `scenario_a.*` | 1,001台 |
| P2-IMPL-7-4 | 全量試行を実行する | ✅ | 7-3 | `scenario_a_traci_summary.json` | 1,001台中987台到着、出発閉鎖14台 |

---

## 12. P2-IMPL-8：評価CSV・比較表

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-8-1 | `evacuation_summary.csv` を生成する | ✅ | P2-IMPL-6 | `evacuation_summary.csv` | 3ケースの到着・未到着・逃げ遅れ台数 |
| P2-IMPL-8-2 | `congestion_log.csv` を生成する | ✅ | P2-IMPL-6 | `congestion_log.csv` | 3ケース合算1,080行 |
| P2-IMPL-8-3 | `phase1_phase2_comparison.csv` を生成する | ✅ | 8-1 | `phase1_phase2_comparison.csv` | Phase 1静的到達不可とPhase 2動的逃げ遅れを分離 |
| P2-IMPL-8-4 | 卒論用表テンプレートへ反映する | ✅ | 8-1〜8-3 | `Phase2_評価表テンプレート.md` | 主要数値と注記を記載 |

---

## 13. P2-IMPL-9：成果物トップページ更新

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-9-1 | Phase 2成果物リンク構成を決める | ✅ | P2-IMPL-8 | Phase 2評価CSV・summary・network概要 | Phase 1/2/3を別セクション化 |
| P2-IMPL-9-2 | `gen_index.py` を更新する | ✅ | 9-1 | `gen_index.py` | index再生成可能 |
| P2-IMPL-9-3 | `output/index.html` を更新する | ✅ | 9-2 | `output/index.html` | Phase別に確認できる |
| P2-IMPL-9-4 | ブラウザで導線確認する | ✅ | 9-3 | Edge headless確認 | Phase別ナビ表示・Phase 2リンク先5件の存在を確認 |

---

## 14. 実装順序

1. P2-IMPL-1：SUMO道路ネットワーク変換
2. P2-IMPL-2：edge ID対応
3. P2-IMPL-3：派生データ生成
4. P2-IMPL-4：出発地・避難所スナップ
5. P2-IMPL-5：小規模route/config生成
6. P2-IMPL-6：TraCI動的閉鎖
7. P2-IMPL-7：1/10試行・全量試行
8. P2-IMPL-8：評価CSV・比較表
9. P2-IMPL-9：成果物トップページ更新
10. P2-TEST：実装内容テスト・修正
11. P2-IMPL-VIZ：SUMO結果のHTML可視化
12. P2-IMPL-REGION：Phase 1対象地域全域へのSUMO拡張

---

## 15. P2-TEST：実装内容テスト・修正

| ID | タスク | 状態 | 対象 | 結果 |
|---|---|---:|---|---|
| P2-TEST-1 | 構文・ヘルプ・SUMO環境検出を確認する | ✅ | `p2_*.py`, `p2_sumo_env.py` | `sumolib` / `traci` import成功 |
| P2-TEST-2 | パイプライン再生成テストを行う | ✅ | network, mapping, derived, snap, scenario | すべて終了コード0 |
| P2-TEST-3 | 小規模・1/10・全量TraCIを再実行する | ✅ | `p2_traci_closure.py` | small 40/40、1/10 120/120、full 987/1001到着 |
| P2-TEST-4 | 評価CSVとトップページを再生成・確認する | ✅ | `p2_evaluate_results.py`, `gen_index.py` | CSV3件・Phase別トップページを確認 |
| P2-TEST-5 | テスト中に見つかった改善点を修正する | ✅ | SUMO環境検出 | `p2_sumo_env.py` を追加 |
| P2-TEST-6 | テスト結果を記録する | ✅ | `04_プログラム/テスト結果_phase2.md` | 合格判定・注意点を記録 |

---

## 16. P2-IMPL-VIZ：SUMO結果のHTML可視化

設計文書：`03_研究設計文書/phase2/Phase2_可視化設計.md`

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-VIZ-1 | `sumocfg` に FCD 出力設定を追加する | ✅ | P2-IMPL-5 | `p2_sumo_scenario.py` 更新（`fcd-output.geo=true`, `device.fcd.period=30`） | SUMO 1.26.0では `fcd-output.period` ではなく `device.fcd.period` を採用 |
| P2-IMPL-VIZ-2 | small シナリオを FCD 出力付きで再実行する | ✅ | VIZ-1 | `output/sumo/results/scenario_a_small_fcd.xml` | `run-small` 再実行済み、実FCD XML 103,919 bytes、`vehicles_small.js` 40台へ変換済み |
| P2-IMPL-VIZ-3 | `p2_fcd_to_json.py` を作成する | ✅ | VIZ-1 | `p2_fcd_to_json.py`（`vehicles-small`, `vehicles-10pct`, `closures`, `meta`, `html`, `sample`, `all`） | `py_compile` 合格・`sample` コマンド実行確認 |
| P2-IMPL-VIZ-4 | `sumo_viz.html` を作成する（地図 + 車両アニメーション） | ✅ | VIZ-3 | `output/sumo/viz/sumo_viz.html` | Leaflet.js + 車両CircleMarker + サンプルデータで動作確認 |
| P2-IMPL-VIZ-5 | タイムラインスライダー・速度倍率・台数表示を実装する | ✅ | VIZ-4 | 同上（HTML内に含む） | ×1/×5/×10/×60、スライダー、走行中/到着/逃げ遅れ台数表示 |
| P2-IMPL-VIZ-6 | 道路閉鎖ポリラインのアニメーションを実装する | ✅ | VIZ-5 | 同上（HTML内に含む） | sim_time_sec 到達時に赤ポリラインを追加する処理 |
| P2-IMPL-VIZ-7 | `gen_index.py` に Phase 2 可視化リンクを追加する | ✅ | VIZ-4 | `output/index.html` 更新 | `phase2` 配列に `SUMO走行アニメーション / sumo/viz/sumo_viz.html` を追加 |
| P2-IMPL-VIZ-8 | 10pct シナリオへ拡張する | ✅ | VIZ-2 | `output/sumo/results/scenario_a_10pct_fcd.xml`, `output/sumo/viz/vehicles_10pct.js` | 120台のFCDをJS化、HTMLのシナリオ選択で small / 10pct を切替可能 |
| P2-IMPL-VIZ-9 | 可視化テスト結果を記録する | ✅ | VIZ-8 | `04_プログラム/テスト結果_phase2.md` | アプリ内ブラウザで `small (40台)` / `10pct (120台)` と切替後の台数表示を確認 |

停止条件：

- `vehicles_*.js` が 10MB を超える場合は period を 60 秒に変更するかデルタ形式に変更する。
- TraCI 実行中に FCD が出力されない場合は `traci.start()` オプションを確認する。

---

## 17. P2-IMPL-REGION：Phase 1対象地域全域へのSUMO拡張

目的：常総市単独のPhase 2 SUMO/TraCIパイプラインを、Phase 1で成果物化済みの茨城県内41市区町村へ拡張する。
方針：いきなり全市区町村の全量試行へ進まず、対象リスト固定 → 市区町村別入力棚卸し → small全域確認 → 10pct全域確認 → full実行方針判断、の順で進める。

2026/05/15に `p2_region_inventory.py` を追加し、Phase 2全域拡張対象41市区町村の正式リストと、44管理単位（対象41件・対象外3件）の入力棚卸しを生成した。対象41件はすべて事前確認OKである。
同日、`p2_sumo_network.py` を市区町村コード指定に対応させ、代表確認として常総市の地域別SUMOネットワーク `output/sumo/regions/08211/network/08211.net.xml` を生成した。
同日、`p2_region_pipeline.py` を追加し、P2-REGION-5〜9の市区町村別実行器を実装した。代表確認として常総市 `08211` でedge対応、派生データ、small試行、10pct試行、full実行計画生成まで完了した。全41市区町村のsmall/10pctバッチ実行は次タスクとして残す。
2026/05/17時点の次工程は、全41市区町村を一気に実行する前に、バッチ状態管理・失敗隔離・再開機能を追加し、対象ごとの未完了工程を見える化することである。
同日、`p2_region_pipeline.py status`、`--codes`、`--skip-completed`、`--continue-on-error` を追加し、`region_batch_status.csv/md` と `region_batch_failures.csv` の出力に対応した。水戸市 `08201` のmappingを実行し、未対応0件で完了した。
同日、`--max-process` を追加し、完了済みスキップ後に未完了を指定件数だけ処理できるようにした。追加確認として日立市、土浦市、古河市、石岡市のmappingを実行し、日立市のみ未対応edge 2件で `inspect_mapping` に隔離した。
その後、日立市向けに `inspect-mapping-city` と `resolve-unmatched-city --policy exclude` を追加した。未対応2件はnetconvert後に通常SUMO edgeとして生成されない短い接続部であり、近隣edgeへの自動代替は過剰閉鎖になり得るため、`excluded_unmapped` として明示除外する判断を採用した。日立市はmatched 713件、excluded_unmapped 2件、unmatched 0件となり、derived生成も完了して `run_small` へ進める状態になった。
2026/05/18に、未処理35市区町村のmapping、全41市区町村のderived、small、10pctを完了した。`10pct` 結果に基づき、fullは守谷市・那珂市・行方市・大洗町・美浦村・五霞町の6市区町村に限定して実行し、全6件で逃げ遅れ0を確認した。市区町村別評価CSV、Phase 1/2比較CSV、全域SUMO結果HTML、トップページ導線も生成済みである。

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-REGION-1 | Phase 1対象地域リストを固定する | ✅ | Phase 1成果物 | `output/sumo/regions/_management/phase2_region_targets.csv` | 41市区町村を対象、Phase 1対象外3市町村は含めない判断を記録 |
| P2-REGION-2 | 市区町村別に必要なPhase 1入力・成果物を棚卸しする | ✅ | REGION-1 | `phase2_region_inventory.md`, `phase2_region_inventory.csv` | 44管理単位を確認、対象41件は `phase2_precheck_ready=yes` |
| P2-REGION-3 | 市区町村別SUMO出力ディレクトリと命名規則を決める | ✅ | REGION-2 | `output/sumo/regions/{city_code}/...` 方針 | 既存の常総市 `output/sumo/` 成果物と衝突しない分離方針を記録 |
| P2-REGION-4 | 道路ネットワーク生成を市区町村パラメータ対応にする | ✅ | REGION-2, REGION-3 | `p2_sumo_network.py --city-code` | 常総市代表確認でOSM XML、net.xml、対応CSVを地域別に生成、通常SUMO edge 49,356件 |
| P2-REGION-5 | Phase 1閉鎖edgeとSUMO edgeの市別対応表を生成する | ✅ | REGION-4 | 市別 `edge_id_mapping.csv`、統合 `region_edge_mapping_summary.csv` | 実行器実装済み。常総市代表確認で1,900件すべてmatched、未対応0件 |
| P2-REGION-6 | 出発地・避難所・時間軸・閉鎖タイムラインを市別に生成する | ✅ | REGION-5 | 市別 `agent_origins_10pct.csv`, `shelters_safety.csv`, `closure_timeline_sumo.json` | 実行器実装済み。常総市代表確認で出発地405点、safe shelter 9件、閉鎖未対応0件 |
| P2-REGION-6A | 全域バッチ状態管理・失敗隔離を実装する | ✅ | REGION-5, REGION-6 | `region_batch_status.csv/md`, `region_batch_failures.csv` | `status`、`--codes`、`--skip-completed`、`--continue-on-error`、`--max-process`、未対応edge調査・除外ポリシーを実装し、日立市を `inspect_mapping` から復帰確認済み |
| P2-REGION-7 | 全対象地域でsmall試行を実行する | ✅ | REGION-6 | `region_run_summary.csv` | 全41市区町村で完了 |
| P2-REGION-8 | 全対象地域で10pct試行を実行する | ✅ | REGION-7 | `region_run_summary.csv` | 全41市区町村で完了、逃げ遅れ合計0 |
| P2-REGION-9 | full試行の実行範囲を判断し、必要範囲を実行する | ✅ | REGION-8 | `region_full_execution_plan.md`, `region_full_execution_plan.csv` | fullは6市区町村を実行、35市区町村は代表・後続課題扱い |
| P2-REGION-10 | 市区町村別評価CSVとPhase 1/2比較表を統合する | ✅ | REGION-8 | `evacuation_summary_by_municipality.csv`, `phase1_phase2_region_comparison.csv` | 評価CSV 41行、比較CSV 164行 |
| P2-REGION-11 | 全域版のHTML導線・可視化を追加する | ✅ | REGION-10 | `sumo/regions/index.html`, `output/index.html` | Phase 1/2/3を分けたトップページから全域SUMO結果へ遷移可能 |
| P2-REGION-12 | 全域拡張テスト結果を記録する | ✅ | REGION-11 | `04_プログラム/テスト結果_phase2_region.md` | 生成件数、リンク欠損0、テスト結果を記録 |

判断済み・今後判断が必要な項目：

- `P2-REGION-1`：Phase 1対象外3市町村（鹿嶋市・神栖市・東海村）をPhase 2全域拡張に含めるかは、初回全域拡張では含めないと判断済み。理由は、Phase 1に浸水シナリオと閉鎖道路が存在しない地域を混ぜると、交通挙動の差ではなく入力データ有無の差が比較結果に入るためである。
- `P2-REGION-6A`：netconvert後に通常SUMO edgeとして生成されない閉鎖edgeが少数発生した場合、近隣edgeへの自動代替ではなく `excluded_unmapped` として明示除外する。理由は、短い接続部を補うために別の流入・流出edgeを閉鎖すると過剰閉鎖になり、交通挙動を実際以上に悪化させる可能性があるためである。日立市では2/715件のため、この扱いで後続処理へ進める。
- `P2-REGION-9`：full試行は全41市区町村で一律実行せず、10pct結果と車両数を見て、代表・軽量対象6市区町村（守谷市・那珂市・行方市・大洗町・美浦村・五霞町）を優先実行する判断を採用した。理由は、全41市区町村の比較指標は10pctで揃え、fullは実行負荷を抑えつつ妥当性確認用に使うほうが卒論整理に適しているためである。

停止条件：

- 市区町村別 `edge_id_mapping.csv` に未対応edgeが残る場合、その市区町村のTraCI実行へ進まない。
- 安全避難所が0件の市区町村は、目的地設定の再検討タスクへ回す。
- 10pct試行で実行時間・メモリ使用量が大きすぎる場合、full試行は代表地域方式へ切り替える。

直近の実行順序は完了済みである。以後の主な作業は、Phase 2本文ドラフト、Phase 1/2比較解釈、SUMO引用・バージョン記録、先生コメント対応表の更新である。

---

## 18. 最重要リスク

| リスク | 影響 | 対応 |
|---|---|---|
| Phase 1 edge ID と SUMO edge ID が対応しない | 誤った道路閉鎖になる | `edge_id_mapping.csv` を必須成果物にする |
| 出発地・避難所のスナップ失敗 | route生成不能 | `snap_status` を検査する |
| 安全避難所が0件になる | 避難目的地が成立しない | `shelters_safety.csv` 生成時に停止 |
| 車両数が多すぎて実行が重い | 全量試行が完走しない | 小規模→1/10→全量の順に進める |
| Phase 1とPhase 2の指標誤読 | 卒論の比較が不正確になる | 比較表に静的/動的の注記を付ける |
| 全域拡張で市区町村ごとの入力不足が混在する | 一括実行が途中停止する | 市区町村別棚卸しと失敗市区町村の隔離実行を先に行う |
| full試行を全41市区町村で実行して処理時間が膨らむ | テスト・卒論整理が遅れる | small/10pctを全域、fullは結果を見て代表・高リスク地域優先にする |
