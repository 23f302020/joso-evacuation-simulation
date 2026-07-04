# Phase 3 実装タスク管理

> 作成日：2026/05/19  
> 目的：Phase 3（デマンド交通バス活用シナリオ）の実装タスクを細分化し、進捗を管理する。

> **⚠️ 実装の詳細・再開手順（2026-07-03）：新規セッションで着手できる粒度のタスクカードは `Phase3_実装タスク詳細_常総先行.md`（A0/R1〜R4/B1〜B5/E1〜E3/S1〜S2/V1〜V4）を参照。方針判断（規模＝A31a想定最大約2万人・車両会計案A・時間軸＝加速シナリオ）と会計式は `Phase3実装前仕様_P3-IMPL-0.md` が正本。手順は `Phase3実装指示書_常総先行_Codex向け.md`。本表の I-系旧命名より P3-IMPL/詳細カードを優先。**

---

## 1. 実装方針

Phase 3では、Phase 2のシナリオA（自家用車のみ）を比較基準として、シナリオB（自家用車＋デマンド交通バス）を追加する。  
最初は常総市で小規模試行を作り、挙動確認後に10pct、full、必要に応じて全域拡張へ進む。

---

## 2. 実装タスク

### 2026-07-04 進捗記録

- A0（対象規模是正・常総full origins再生成）完了。`04_プログラム/venv` で `python scripts/p2_region_pipeline.py derived-city --city-code 08211` を再実行し、`output/sumo/regions/08211/derived/agent_origins_10pct.csv` が405メッシュ、総人口21,539人、高齢者6,191人、`vehicle_count_full` 9,569台であることを確認した。`derived_data_validation.json` は `origin_unmatched_count=0`、`safe_shelter_unmatched_count=0`、`can_proceed_to_small=true`。
- R1（救出走行パラメータのconfig化）完了。`scripts/config.py` に救出走行・車両会計パラメータを追加し、`HOUSEHOLD_SIZE` と `NON_CAR_RATE` の既存ローカル定数を config 参照へ寄せた。`py_compile` と定数読み出しで import 互換を確認済み。
- R2（メッシュ別 非保有世帯数・救出走行OD算出）完了。`scripts/p2_region_pipeline.py derived-city --city-code 08211` で `output/sumo/regions/08211/derived/rescue_od.csv` を生成し、405行、救出走行1,405台、自家用車8,164台、edge欠損0を確認した。`derived_data_validation.json` に `phase3_private_vehicle_count_total=8164`、`phase3_rescue_vehicle_count_total=1405`、`phase3_non_car_households_total=1404.717` を追加。
- R3（救出走行2レグtrip生成→scenario_a.rou.xml注入）完了。`scenario_a.rou.xml` は自家用車trip 8,164、救出走行vehicle 1,405、pickup stop 1,405、合計9,569。`scenario_a_vehicle_assignments.csv` は private 8,164 / rescue 1,405 / edge欠損0。SUMO 1秒ロード確認は exit 0。

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P3-IMPL-0 | Phase 3実装前仕様書を作成する | ✅ | P3-JUDGE | `Phase3実装前仕様_P3-IMPL-0.md`（2026-07-03作成） | 判断事項と採用理由が記録されている（規模・会計・時間軸の3判断＋会計式を集約） |
| P3-IMPL-1 | エージェント4種別を既存データへ付与する | ✅ | Phase 3前処理 | `agent_types.csv` | Type1〜4の件数を集計済み |
| P3-IMPL-2 | バス利用候補者を抽出する | ✅ | P3-IMPL-1 | `bus_demand_candidates.csv` | 車非保有者・高齢者優先の候補を抽出済み |
| P3-IMPL-3 | バス拠点・目的地・乗降地点を設定する | ❌ | P3-IMPL-0 | `bus_stops.csv`, `bus_depots.csv` | SUMO edgeへスナップできる |
| P3-IMPL-4 | バスroute生成処理を実装する | ❌ | P3-IMPL-2, P3-IMPL-3 | `scenario_b_buses.rou.xml` | SUMOでrouteエラーが出ない |
| P3-IMPL-5 | シナリオBの車両routeを生成する | ❌ | P3-IMPL-1 | `scenario_b_cars.rou.xml` | 自家用車とバス対象者の重複がない |
| P3-IMPL-6 | TraCI実行をシナリオB対応にする | ❌ | P3-IMPL-4, P3-IMPL-5 | `scenario_b_traci_summary.json` | 道路閉鎖とバス走行が同時に動く |
| P3-IMPL-7 | A/B比較CSVを生成する | ❌ | P3-IMPL-6 | `phase2_phase3_comparison.csv` | 到着人数、逃げ遅れ候補、旅行時間、主要避難路混雑を比較できる |
| P3-IMPL-8 | Phase 3 Excel成果物を生成する | ❌ | P3-IMPL-7 | `phase3_results_excel.xlsx` | 比較表をExcelで確認できる |
| P3-IMPL-9 | Phase 3アニメーションHTMLを作成する | ❌ | P3-IMPL-6 | `sumo/viz/phase3_viz.html` | バスと自家用車を区別して表示できる |
| P3-IMPL-10 | `phase3.html` を更新する | ❌ | P3-IMPL-8, P3-IMPL-9 | `output/phase3.html` | Excel欄とアニメーション欄に分けて表示される |
| P3-IMPL-11 | Phase 3テスト結果を記録する | ❌ | P3-IMPL-10 | `テスト結果_phase3.md` | 実行結果、警告、限界が記録されている |

---

## 3. 検証タスク

| ID | タスク | 状態 | 理由 |
|---|---|---:|---|
| P3-TEST-1 | 小規模試行でroute生成を確認する | ❌ | バスrouteの不成立を早期に見つけるため |
| P3-TEST-2 | 10pct試行で輸送人数・逃げ遅れ候補を確認する | ❌ | Phase 2の10pct結果と比較するため |
| P3-TEST-3 | full試行を行うか判断する | ❌ | 実行負荷と必要性を比較するため |
| P3-TEST-4 | A/B比較CSVの値を検算する | ❌ | バス利用者の二重計上を防ぐため |
| P3-TEST-5 | HTMLリンク・Excelリンクを検証する | ❌ | 成果物入口の欠損を防ぐため |

---

## 4. 停止条件

| 条件 | 対応 |
|---|---|
| バス利用候補者が0件 | 対象者条件を見直す |
| バス拠点または乗降地点がSUMO edgeへスナップできない | スナップ距離・候補地点を確認する |
| バスrouteがSUMOで成立しない | 経路生成条件または閉鎖時刻との関係を確認する |
| 自家用車対象者とバス対象者が重複する | エージェント分類を修正する |
| シナリオBの結果がPhase 2基準と比較できない | 比較CSV仕様を見直す |

---

## 5. 推奨する最初の実装単位

最初の実装は、**常総市 small 試行のみ** とする。  
理由は、バスroute、乗降、道路閉鎖、エージェント分類が同時に入るため、いきなり10pctや全域へ進むと不具合の切り分けが難しくなるからである。
