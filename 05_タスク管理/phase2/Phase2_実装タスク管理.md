# Phase 2 実装タスク管理

> 作成日：2026/05/14  
> 目的：Phase 2（SUMO/TraCIによる自家用車避難シミュレーション）の実装作業を、実行可能な粒度まで分割して管理する。  
> 関連：`Phase2_詳細タスク管理.md`、`Phase2_判断事項一覧.md`、`03_研究設計文書/phase2/Phase2_実装前仕様.md`  
> 進捗記録先：`01_経過報告/経過報告20260520.md`

---

## 1. 実装対象

Phase 2では、まず常総市実データ版を対象に、シナリオA（自家用車のみ）の交通流ベースラインを作る。

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

## 16. 最重要リスク

| リスク | 影響 | 対応 |
|---|---|---|
| Phase 1 edge ID と SUMO edge ID が対応しない | 誤った道路閉鎖になる | `edge_id_mapping.csv` を必須成果物にする |
| 出発地・避難所のスナップ失敗 | route生成不能 | `snap_status` を検査する |
| 安全避難所が0件になる | 避難目的地が成立しない | `shelters_safety.csv` 生成時に停止 |
| 車両数が多すぎて実行が重い | 全量試行が完走しない | 小規模→1/10→全量の順に進める |
| Phase 1とPhase 2の指標誤読 | 卒論の比較が不正確になる | 比較表に静的/動的の注記を付ける |
