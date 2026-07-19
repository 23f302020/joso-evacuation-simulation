# Phase 3 実装タスク管理

> 作成日：2026/05/19  
> 目的：Phase 3（デマンド交通バス活用シナリオ）の実装タスクを細分化し、進捗を管理する。

> **⚠️ 実装の詳細・再開手順（2026-07-03）：新規セッションで着手できる粒度のタスクカードは `Phase3_実装タスク詳細_常総先行.md`（A0/R1〜R4/B1〜B5/E1〜E3/S1〜S2/V1〜V4）を参照。方針判断（規模＝A31a想定最大約2万人・車両会計案A・時間軸＝加速シナリオ）と会計式は `Phase3実装前仕様_P3-IMPL-0.md` が正本。手順は `Phase3実装指示書_常総先行_Codex向け.md`。本表の I-系旧命名より P3-IMPL/詳細カードを優先。**

> **2026-07-18 追加：V5系＝HTMLダッシュボード最新化（index/phase1/phase2/faq）。** 主結論ヌル・E3確定稿に整合させる文言是正（gen_index.pyソース是正＋G1〜G5ゲート付き再生成／faq手編集）。方針＝[[段4_HTMLダッシュボード最新化判断_方針判断_fable5]]（決定150〜154）・カード V5-1〜V5-5 は `Phase3_実装タスク詳細_常総先行.md`。

> **2026-07-18 V5実装状況：** V5-1（生成器のindex/phase2文言是正）とV5-3（faq本文・検索KB同期）は完了。V5-2はG3で`assets/phase1.css`の内容ドリフトを検出し停止した。生成器の`write_css()`が現物のナビ・FAQ・チャット等の追加スタイルを保持していないため、CSSはscratchpadから復旧済み。`write_css()`へ現物差分を取り込むか、CSSを再生成対象から外すかの判断後にV5-2から再開する。V5-4/V5-5は依存未達のため未着手。

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

### 2026-07-09 進捗記録

- R4（救出走行込みシナリオAの常総full再実行・比較基準再固定）完了。`scenario_a.rou.xml` は9,569台、到着9,569台、逃げ遅れ0、600秒以上停止102台を比較基準として採用する。
- B1〜B5（バス拠点・停留所、route生成、TraCI動的往復、シナリオB車両会計、実測ログ出力）を常総市fullで実装・実行した。短すぎるpickup edgeは除外し、旧問題地点 `origin_0132` 由来のdespawnは解消した。
- バス単独検証では、5台・候補247人のうち215人乗車・215人到着・未到着0・打切り0・`conservation_ok=true` を確認した。
- full交通同時実行では、候補247人のうち91人乗車・67人到着・24人未到着・残queue156人・`conservation_ok=true`。3便はSUMO側despawnとなったため、判断メモに従い到着人数へ計上せず、`termination_by_reason={"despawn":3}` として残リスク扱いにした。
- シナリオBの車両会計は、バス実到着67人、`k=2.3` による救出走行削減29台として固定。B側routeは合計9,540台（自家用車8,164台、救出走行1,376台）で生成した。
- E2（A/B比較の従指標CSV）を生成。`phase3_ab_comparison.csv` には `vehicle_count` A=9,569 / B=9,540、`bus_transport_people`=67、`bus_not_arrived_people`=24、`rescue_reduction_integer_k2_3`=29、`selected_stop_demand_satisfaction_rate`=0.271255、`all_type34_demand_satisfaction_rate`=0.020584 を記録した。

### ⚠️ 2026-07-09 差し戻し（上記 B3〜B5・E2 の記録を撤回）

正本＝`開発メモ/方針判断_fable5/02_実行系是正/シナリオB再実行_方針判断_fable5.md`（論点整理 opus → 判断 fable-5 → 記録 sonnet-5）。

- **完走した「車＋バス」のシナリオB runは一度も存在しない。** B側成果物は 14:48:43 の計測run（バスログ）と 15:24:14 の中断run（fcd／tripinfo、`write_bus_outputs` 未到達）の混合物。バスログは現存する `scenario_b.rou.xml`（14:50:06）・`scenario_b.sumocfg`（14:51:09）より前に書かれており、**14:48 runの実行条件は復元不能**。
- 根本原因：`p2_traci_bus.py:779` が `route_file = SCENARIOS_DIR / "scenario_a.rou.xml"` をハードコード既定にしていたため、**B4で生成した `scenario_b.rou.xml`（9,540台）は一度もSUMOに読み込まれていない**。
- 併発する欠陥：`close_edges_with_bus()`（同 244行）が乗用車をリルートしない（A側 `p2_region_pipeline.py:1600` は毎閉鎖でリルート＋出発前ブロック）／`p2_traci_bus.py:616` の過剰break／`time-to-teleport` がA=既定300秒・B=-1で不統一（B側の `-1` は手編集起源）／B側に `traci_summary`・`vehicle_log` が無い。
- **撤回する数値**：バス乗車91・到着67・未到着24・残queue156／救出走行削減29台／B側9,540台／`selected_stop_demand_satisfaction_rate=0.271255`／`all_type34_demand_satisfaction_rate=0.020584`。`phase3_ab_comparison.csv` は破棄。
- **シナリオAも再実行対象**：`scenario_a.sumocfg` に `time-to-teleport` 指定がなくSUMO既定300秒テレポートが有効。「9,569台全到着」がテレポート非依存であることは未証明であり、**床効果はまだ確定できない**。
- **バス状態機械は無実**：`step_bus` の `sim_time` はTraCIループの `traci.simulation.getTime()` 由来（独立時計なし）。バス状態機械のコードは修正しない。
- 次は F系（実行系是正：共通モジュール抽出／break削除／teleport=-1統一／route既定値廃止＋出所マニフェスト）→ R4'（シナリオA再実行）→ B計測run → B確定run → E1 → E2 → E3 の順。詳細カードは `Phase3_実装タスク詳細_常総先行.md`。

### 2026-07-09 F系実装記録

- P3-IMPL-F（実行系是正）はコード実装済み。`p2_traci_common.py` を追加し、閉鎖適用、乗用車リルート、出発前ブロック、vehicle_log、traci_summary生成をA/B共通化した。
- A側 `p2_region_pipeline.py` は共通関数経由で `vehicle_log` / `traci_summary` を生成し、sumocfgに `time-to-teleport=-1` を明示する。
- B側 `p2_traci_bus.py` は過剰breakを削除し、`run-bus --route-file ... --phase measure|final` を必須化した。routeファイル名とassignments台数を検査し、summaryに `run_id`、route SHA256、route台数内訳、sumocfg内容、last_sim_timeを記録する。B側 `scenario_b_vehicle_log.csv` と `scenario_b_traci_summary.json` もA側と同一スキーマで出力する。
- `py_compile` は通過。`test_p3_bus_accounting.py` は venv で 28 passed。`run-bus --help` と measure/final のroute台数アサーションは通過確認済み。
- R4'は未完走。`scenario_a.sumocfg` に `time-to-teleport=-1` が書かれることを確認後、A' fullを実行したが、約26分でsim時刻1260秒までしか進まず、完走には数時間規模を要する見込みだったため停止した。AC1は未達。

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P3-IMPL-0 | Phase 3実装前仕様書を作成する | ✅ | P3-JUDGE | `Phase3実装前仕様_P3-IMPL-0.md`（2026-07-03作成） | 判断事項と採用理由が記録されている（規模・会計・時間軸の3判断＋会計式を集約） |
| P3-IMPL-1 | エージェント4種別を既存データへ付与する | ✅ | Phase 3前処理 | `agent_types.csv` | Type1〜4の件数を集計済み |
| P3-IMPL-2 | バス利用候補者を抽出する | ✅ | P3-IMPL-1 | `bus_demand_candidates.csv` | 車非保有者・高齢者優先の候補を抽出済み |
| P3-IMPL-3 | バス拠点・目的地・乗降地点を設定する | ✅ | P3-IMPL-0 | `bus_plan.csv`, `bus_stops.add.xml` | 5停留所をSUMO edgeへスナップ済み。短すぎるpickup edgeは除外 |
| P3-IMPL-4 | バスroute生成処理を実装する | ✅ | P3-IMPL-2, P3-IMPL-3 | `scenario_b_smoke.rou.xml`, `scenario_b.rou.xml` | repeat撤廃＋TraCI動的往復。バス単独で route error なし |
| P3-IMPL-F | 実行系是正（共通モジュール抽出／break削除／teleport=-1統一／route既定値廃止＋出所マニフェスト） | ✅ コード実装済み | — | `p2_traci_common.py`, 改修後の `p2_traci_bus.py` | `py_compile`、pytest 28 passed、route台数アサーション確認済み。AC1はR4'未完走のため未達 |
| P3-IMPL-5 | シナリオBの車両routeを生成する | ⚠️ 要再生成 | P3-IMPL-1, P3-IMPL-F | `scenario_b.rou.xml`, `scenario_b_vehicle_assignments.csv` | **9,540台・削減29台は撤回**（入力のバス到着67人が出所不明run由来／かつ本routeは一度もSUMOに読まれていない）。AC3で再固定 |
| P3-IMPL-6 | TraCI実行をシナリオB対応にする | ⚠️ 実測値撤回・再計測待ち | P3-IMPL-4, P3-IMPL-5 | `scenario_b_bus_summary.json`, `scenario_b_passenger_log.csv`, `scenario_b_bus_log.csv`, `scenario_b_traci_summary.json`, `scenario_b_vehicle_log.csv` | **完走した車＋バスrunが存在しない**（成果物がrun混合）。AC2・AC5・AC6で再計測 |
| P3-IMPL-7 | A/B比較CSVを生成する | ⚠️ ✅取消 | P3-IMPL-6 | `phase3_ab_comparison.csv` | **既存CSVは破棄**（A=到着台数・B=route行数という異種量の引き算／未到着1,010台が不可視）。AC8で再生成 |
| P3-IMPL-8 | Phase 3 Excel成果物を生成する | ✅ | P3-IMPL-7 | `outputs/p3-impl-8/phase3_results_excel.xlsx` | 8run完了率・15組符号表・raw/保守帯・S系10台を7シートへ集約し、全シート目視QA済み |
| P3-IMPL-9 | Phase 3アニメーションHTMLを作成する | ❌ | P3-IMPL-6 | `sumo/viz/phase3_viz.html` | バスと自家用車を区別して表示できる |
| P3-IMPL-10 | `phase3.html` を更新する | ❌ | P3-IMPL-8, P3-IMPL-9 | `output/phase3.html` | Excel欄とアニメーション欄に分けて表示される |
| P3-IMPL-11 | Phase 3テスト結果を記録する | ❌ | P3-IMPL-10 | `テスト結果_phase3.md` | 実行結果、警告、限界が記録されている |

---

## 3. 検証タスク

| ID | タスク | 状態 | 理由 |
|---|---|---:|---|
| P3-TEST-1 | 小規模試行でroute生成を確認する | ✅ | repeat方式の不成立を確認後、repeat撤廃版でSUMO完走・busStop 2停を確認 |
| P3-TEST-2 | 10pct試行で輸送人数・逃げ遅れ候補を確認する | ❌ | Phase 2の10pct結果と比較するため |
| P3-TEST-3 | full試行を行うか判断する | ✅ | 常総市fullでA/Bを実行済み |
| P3-TEST-4 | A/B比較CSVの値を検算する | ⚠️ ✅取消 | 既存CSVと29台削減は撤回。B確定run後にAC8で再検算 |
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
