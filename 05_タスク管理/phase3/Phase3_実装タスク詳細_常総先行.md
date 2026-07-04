# Phase 3 実装タスク詳細（フェーズA：常総市先行）— 再開可能タスクカード集

> 作成日：2026-07-03／作成：Claude Code（opus）
> 目的：Phase 3 実装を**1タスク=1カード**に分割し、新規セッションでもカード単独で着手・再開できるようにする。
> 上位：`Phase3実装前仕様_P3-IMPL-0.md`（仕様正本）／`Phase3実装指示書_常総先行_Codex向け.md`（手順）／`Phase3_実装タスク管理.md`（ID登録の正本）

## 新規セッションでの再開手順（最初に読む）
1. 本ファイルの「進捗ボード」で `▶次にやる` のカードを見つける。
2. そのカードの「読む正本」を開く（判断の背景はここで復元できる）。
3. カードの「作業内容→完了条件」を実行。完了したら**状態を✅にし、`開発メモ/方針判断_fable5/fableチェック_修正タスク.md` の該当タスク（T-D-H1/C2/M2）と `Phase3_実装タスク管理.md` を更新**。

## 確定事実（全カード共通の前提）
- 対象＝常総市 **08211**／full解像度。避難対象＝**A31a想定最大＝21,539人・高齢6,191人・405メッシュ・世帯換算9,569台**（`Phase3_規模整合メモ.md`）。
- 会計：削減式 `救出走行台数 = 非保有世帯数 × r − (バス実輸送人数 ÷ k)`、**r=1.0（感度0.5/0.75/1.0）・k=2.3・自家用車1台/世帯・非保有率15%（感度10/20）**（`車両会計_方針判断_fable5.md`）。
- 定義：逃げ遅れ＝**人単位**（世帯車1台=2.3人／救出走行1台=k人／バス=実乗車）。避難完了＝避難所到着（`用語定義集.md`）。
- 時間軸：加速浸水シナリオ・**逃げ遅れ絶対数は主張せずA/B相対・Type別**（`時間軸_方針判断_fable5.md`）。
- 関連config：`CAR_OWNERSHIP_RATE=0.85`（非保有0.15）・`ELDERLY_RATE=0.27`・`BUS_COUNT_BASE=5`・`BUS_CAPACITY_STD=8`・`BUS_CAPACITY_WELFARE=4`・`BUS_SENSITIVITY=[3,5,10]`。`HOUSEHOLD_SIZE=2.3`（p2_region_pipeline内）。

---

## 進捗ボード（状態一覧）
| ID | タスク | 担当 | 依存 | 状態 |
|----|--------|------|------|------|
| **A0** | 対象規模是正・常総full origins再生成 | Codex | — | ✅ |
| **R1** | 救出走行パラメータのconfig化 | Claude | — | ✅ |
| **R2** | メッシュ別 非保有世帯数・救出走行OD算出 | Claude | A0,R1 | ✅ |
| **R3** | 救出走行2レグtrip生成→scenario_a.rou.xml注入 | Claude | R2 | ✅ |
| **R4** | シナリオA（救出走行込み）full再実行・基準再固定 | Codex | R3 | ▶次にやる |
| **B1** | バス拠点・停・乗降地点の設定（SUMO edgeスナップ） | Claude | A0 | 未着手 |
| **B2** | バスroute生成（固定ルート・9往復上限） | Claude | B1 | 未着手 |
| **B3** | 救出走行削減の会計連動（バス実輸送÷k） | Claude | R3,B2 | 未着手 |
| **B4** | シナリオB車両route生成（自家用車＋救出走行(削減後)＋バス） | Claude | B3 | 未着手 |
| **B5** | TraCIシナリオB実行（乗降＋動的閉鎖＋乗車人数集計） | Claude+Codex | B4 | 未着手 |
| **E1** | 評価を人単位・Type別へ拡張（逃げ遅れ人/完了時間/渋滞/公平性） | Claude | R4,B5 | 未着手 |
| **E2** | A/B比較CSV生成（人単位・Type別） | Claude+Codex | E1 | 未着手 |
| **E3** | 床効果判定・主指標の確定 | Claude(判断) | E2 | 未着手 |
| **S1** | バス台数感度 3/5/10 実行 | Codex | B5 | 未着手 |
| **S2** | 圧縮率感度でA/B順位の不変性確認 | Claude+Codex | E2 | 未着手 |
| **V1** | Excel成果物生成（P3-IMPL-8） | Claude+Codex | E2 | 未着手 |
| **V2** | アニメHTML（バス/車を区別・P3-IMPL-9） | Claude | B5 | 未着手 |
| **V3** | phase3.html更新（P3-IMPL-10） | Claude | V1,V2 | 未着手 |
| **V4** | テスト結果記録（P3-IMPL-11） | Claude | V3 | 未着手 |

---

# タスクカード

## A0：対象規模是正・常総full origins再生成
- **担当**：Codex ／ **依存**：なし ／ **読む正本**：規模乖離判断・規模整合メモ・実装指示書A-1
- **作業内容**：region pipeline で 08211 の派生データ（t7＝A31a想定最大 origins）を再生成する。
  ```
  cd 04_プログラム
  python scripts/p2_region_pipeline.py derived-city --city-code 08211
  ```
- **入出力**：出力 `output/sumo/regions/08211/derived/agent_origins_*.csv`（列：total_pop, elderly_pop, vehicle_count_full 等）。
- **完了条件**：メッシュ数≈405、total_pop合計≈21,539、vehicle_count_full合計≈9,569。旧 `output/agents/origin_points.csv`（2,257人）は主結果に使わず「t0感度ケース」ラベル。
- **注意**：旧 sumo_viz 常総パスを主に使う場合のみ `i3_route_search.py:279` を t7相当へ修正（本フェーズは region pipeline を主経路とする）。
- **完了記録（2026-07-04 Codex）**：`python scripts/p2_region_pipeline.py derived-city --city-code 08211` を `04_プログラム/venv` で再実行。`agent_origins_10pct.csv` は405行、`total_pop` 合計21,539、`elderly_pop` 合計6,191、`vehicle_count_full` 合計9,569、`vehicle_count_10pct` 合計1,151。`derived_data_validation.json` は `origin_unmatched_count=0`、`safe_shelter_unmatched_count=0`、`can_proceed_to_small=true`。

## R1：救出走行パラメータのconfig化
- **担当**：Claude Code ／ **依存**：なし ／ **読む正本**：車両会計判断・P3-IMPL-0 §2
- **作業内容**：`scripts/config.py` に救出走行パラメータを追加：`RESCUE_RATE_R = 1.0`（感度0.5/0.75/1.0）、`RESCUE_PER_VEHICLE_K = 2.3`、`NON_CAR_RATE = 0.15`（=1−CAR_OWNERSHIP_RATE、感度0.10/0.20）、`CARS_PER_HOUSEHOLD = 1.0`（感度上限1.55）。既存 `HOUSEHOLD_SIZE=2.3` を config へ集約（現状 p2_region_pipeline / p2_derived_data にローカル定義）。
- **完了条件**：定数が config に集約され、感度で振れるコメント付き。既存の import 互換を壊さない。
- **完了記録（2026-07-04 Codex）**：`scripts/config.py` に `HOUSEHOLD_SIZE=2.3`、`NON_CAR_RATE=0.15`、`RESCUE_RATE_R=1.0`、`RESCUE_RATE_SENSITIVITY=[0.5,0.75,1.0]`、`RESCUE_PER_VEHICLE_K=2.3`、`NON_CAR_RATE_SENSITIVITY=[0.10,0.15,0.20]`、`CARS_PER_HOUSEHOLD=1.0`、`CARS_PER_HOUSEHOLD_MAX=1.55`、`RESCUE_STOP_DURATION_S=60` を追加。`p2_region_pipeline.py` / `p2_derived_data.py` の `HOUSEHOLD_SIZE` と `p2_phase3_prep_agents.py` の `NON_CAR_RATE` を config 参照へ変更。`py_compile` と定数読み出し確認済み。

## R2：メッシュ別 非保有世帯数・救出走行OD算出
- **担当**：Claude Code ／ **依存**：A0,R1 ／ **読む正本**：P3-IMPL-0 §2/§3
- **作業内容**：agent_origins（08211）から**メッシュ別**に算出する新規関数：
  - 世帯数 = total_pop ÷ HOUSEHOLD_SIZE。車保有世帯 = 世帯×(1−NON_CAR_RATE)、非保有世帯 = 世帯×NON_CAR_RATE。
  - 自家用車避難台数 = ceil(車保有世帯 × CARS_PER_HOUSEHOLD)。救出走行台数 = 非保有世帯 × R（メッシュ合計で約1,405台）。
  - 救出走行OD：発＝当該メッシュ（or 最寄り車保有メッシュ）、経由乗車＝当該非保有メッシュ、着＝最寄り安全避難所（`shelters_safety.csv`）。
- **入出力**：出力 `output/sumo/regions/08211/derived/rescue_od.csv`（列：mesh, 非保有世帯数, 救出走行台数, 発edge, 乗車edge, 着shelter）。
- **完了条件**：救出走行台数の合計が会計（≈1,405台・非保有率15%時）と一致。自家用車台数合計≈8,164台。
- **完了記録（2026-07-04 Codex）**：`p2_region_pipeline.py` の `derived-city` に `rescue_od.csv` 生成を追加。`rescue_od.csv` は405行、`non_car_households` 合計1,404.715（CSV丸め後）、`rescue_vehicle_count` 合計1,405、`private_vehicle_count` 合計8,164。`rescue_start_edge_id` / `pickup_edge_id` / `shelter_edge_id` の欠損0。整数化はメッシュ別raw値にlargest remainder方式を適用し、発edge・乗車edgeは同一メッシュedge、着edgeは最寄り安全避難所edge。

## R3：救出走行2レグtrip生成→scenario_a.rou.xml注入
- **担当**：Claude Code ／ **依存**：R2 ／ **読む正本**：P3-IMPL-0 §3・実装指示書A-2・既存 `p2_region_pipeline.generate_region_scenario`
- **作業内容**：救出走行を**2レグtrip**（`発edge→乗車edge`で停車(stop duration≈60s)→`避難所edge`）としてSUMO trip/route化し、`scenario_a.rou.xml`（full）へ id接頭辞 `rescue_` で追記。既存の自家用車route生成（vehicle_count_full ベース）と別カウントで共存させる。edgeスナップは既存の snap ユーティリティ（`p2_sumo_snap`）を再利用。
- **完了条件**：`scenario_a.rou.xml` に自家用車（≈8,164）＋救出走行（≈1,405）＝合計≈9,569台。SUMOでrouteエラーが出ない（duarouter/netcheck）。
- **完了記録（2026-07-04 Codex）**：`p2_region_pipeline.py scenario-city --city-code 08211 --scenario full` で `scenario_a.rou.xml` を生成。XML内訳は自家用車trip 8,164、救出走行vehicle 1,405、pickup stop 1,405、合計9,569。`scenario_a_vehicle_assignments.csv` も private 8,164 / rescue 1,405 / edge欠損0。`sumo --net-file ../network/08211.net.xml --route-files scenario_a.rou.xml --begin 0 --end 1 ... --ignore-route-errors false` が exit 0。

## R4：シナリオA（救出走行込み）full再実行・比較基準再固定
- **担当**：Codex ／ **依存**：R3 ／ **読む正本**：実装指示書A-2
- **作業内容**：
  ```
  python scripts/p2_region_pipeline.py scenario-city --city-code 08211 --scenario full
  python scripts/p2_region_pipeline.py run-city --city-code 08211 --scenario full
  ```
- **完了条件**：`scenario_a_traci_summary.json`・`scenario_a_tripinfo.xml` 等が生成。車両内訳が会計と一致。**この結果を新しい比較基準（シナリオA）として固定**（`Phase2_比較基準固定.md` に追記）。

## B1：バス拠点・停・乗降地点の設定（SUMO edgeスナップ）
- **担当**：Claude Code ／ **依存**：A0 ／ **読む正本**：H1・P3-IMPL-0 §4・既存 `bus_demand_candidates.csv`（P3-IMPL-2✅済）
- **作業内容**：バス拠点（デポ）・避難所側バス停・住宅密集メッシュ側乗降地点を定義し SUMO edge へスナップ。出力 `bus_stops.add.xml`（busStop要素）・`bus_stops.csv`・`bus_depots.csv`。乗車対象はType3/4（`agent_types.csv`／`bus_demand_candidates.csv`）。
- **完了条件**：全busStopが有効edgeにスナップ、避難所16〜19箇所付近をカバー。

## B2：バスroute生成（固定ルート・9往復上限）
- **担当**：Claude Code ／ **依存**：B1 ／ **読む正本**：H1（5台・8人/4人・20km/h・9往復）
- **作業内容**：バス5台（標準8人×4＋福祉4人×1）の固定ルート（乗降地点→避難所のピストン、6h・上限9往復）を `.rou.xml` の `<vehicle>`＋`<stop>` で生成 → `scenario_b_buses.rou.xml`。台数は `BUS_SENSITIVITY` で差し替え可能に。
- **完了条件**：SUMOでバスが走行し停車する（route検証OK）。

## B3：救出走行削減の会計連動（バス実輸送÷k）
- **担当**：Claude Code ／ **依存**：R3,B2 ／ **読む正本**：車両会計判断・P3-IMPL-0 §2
- **作業内容**：シナリオBの救出走行台数 = 非保有世帯数×R −（**バス実輸送人数**÷k）。バス実輸送人数はB5のTraCI集計を用いる（初回は机上324人で仮置き→B5後に実測で再生成）。**バス定員を超えて乗れないType3/4はシナリオAと同一（救出走行を残す）**＝会計クローズ。削減対象の救出走行tripを除外するロジックを実装。
- **完了条件**：シナリオBの救出走行台数＝A基準−(バス輸送÷k)。乗れない層の救出走行が残り、A/Bで人・車両総数が閉じる。

## B4：シナリオB車両route生成（自家用車＋救出走行(削減後)＋バス）
- **担当**：Claude Code ／ **依存**：B3 ／ **読む正本**：実装指示書A-3
- **作業内容**：自家用車route（Aと同一）＋救出走行(削減後)＋バス を統合し `scenario_b.rou.xml` を生成。Type3/4のうちバス乗車者は自家用車/救出走行から除外し二重計上を防ぐ。
- **完了条件**：バス対象者と自家用車/救出走行の重複がない。SUMO route検証OK。

## B5：TraCIシナリオB実行（乗降＋動的閉鎖＋乗車人数集計）
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：B4 ／ **読む正本**：既存 `p2_traci_closure.py`
- **作業内容**：既存TraCI動的閉鎖にバス乗降処理を追加し、シナリオBを実行。各バスの往復数・乗車人数・所要時間を `scenario_b_bus_log.csv` に出力。`scenario_b_traci_summary.json` 生成。実輸送人数をB3へフィードバックし救出走行削減を確定（B3→B4→B5を1巡）。
- **完了条件**：道路閉鎖とバス走行が同時に動作。バス運行ログが出力され、実輸送人数で削減式が確定。

## E1：評価を人単位・Type別へ拡張
- **担当**：Claude Code ／ **依存**：R4,B5 ／ **読む正本**：用語定義集・評価フレーム設計（公平性注記）
- **作業内容**：`p2_evaluate_results.py` を拡張：**逃げ遅れ（人単位）**（世帯車×2.3／救出走行×k／バス実乗車）、**避難完了時間分布**（全体・Type別）、**渋滞指標**（区間平均速度・最大停止台数・総旅行時間）、**公平性指標**（Type3/4の避難完了率・平均完了時間）。
- **完了条件**：A・B双方で上記指標がCSV化され、人単位で整合。

## E2：A/B比較CSV生成（人単位・Type別）
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：E1 ／ **読む正本**：論文構成Phase3 4.7
- **作業内容**：シナリオA/Bの比較CSV（逃げ遅れ人・避難完了時間・渋滞・バス輸送・Type別）を生成。**逃げ遅れは絶対数でなくA/B差・Type別分布差**を主表に。
- **完了条件**：`phase3_ab_comparison.csv`（人単位・Type別）。検算でバス利用者の二重計上ゼロ（P3-TEST-4）。

## E3：床効果判定・主指標の確定
- **担当**：Claude Code（判断） ／ **依存**：E2 ／ **読む正本**：時間軸判断・fableチェックCRITICAL-2
- **作業内容**：約2万人規模で渋滞由来の逃げ遅れが発生するか判定。発生→逃げ遅れ(人)を主指標。非発生→避難完了時間分布・safety margin を主指標へ昇格。`評価フレーム設計.md` の成功基準を確定形に更新。
- **完了条件**：主指標が確定し、評価フレームに反映。T-D-C2を✅化。

## S1：バス台数感度 3/5/10 実行
- **担当**：Codex ／ **依存**：B5 ／ **読む正本**：H1（BUS_SENSITIVITY）
- **作業内容**：バス台数 3/5/10 でシナリオBを実行し、効果の飽和を確認。
- **完了条件**：台数別のA/B指標が揃う。

## S2：圧縮率感度でA/B順位の不変性確認
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：E2 ／ **読む正本**：時間軸判断 §4-1（最大の残存リスク）
- **作業内容**：閉鎖スケジュールの進行速度（圧縮率）を1軸振り（例1.0/0.5倍速）、**A/Bの順位（どちらが良いか）が入れ替わらないこと**を確認。
- **完了条件**：順位不変を確認できれば時間軸判断の確信度が中→高。T-D-M2の中核を満たす。

## V1〜V4：成果物（Excel/アニメHTML/phase3.html/テスト記録）
- V1（P3-IMPL-8・Claude+Codex）：Phase3 Excel生成。V2（P3-IMPL-9・Claude）：バス/車を区別したアニメHTML。V3（P3-IMPL-10・Claude）：`output/phase3.html` 更新。V4（P3-IMPL-11・Claude）：`テスト結果_phase3.md` に実行結果・警告・限界を記録。

---

## フェーズB（Aの完了後・データ拡大）※着手時にカード化
- B-1 感度全軸（r・非保有率・自家用車台数・福祉比率）／B-2 41市区町村へ横展開（第5章・移転可能性デモ）／B-3 追加シナリオ（浸水規模別 等）。

## 完了時に更新する台帳
- `Phase3_実装タスク管理.md`（ID正本）・`開発メモ/方針判断_fable5/fableチェック_修正タスク.md`（T-D-H1=R3/R4/B*・T-D-C2=E3・T-D-M2=S1/S2）・`CLAUDE.md` 現在フェーズ。
