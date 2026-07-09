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

## ⚠️ 2026-07-09 差し戻し（[[シナリオB再実行_方針判断_fable5]]）

**B側成果物は「計測run（14:48台）」と「未完走run（15:24台）」の混合物であり、完走した『車＋バス』のシナリオB runは一度も存在しない。** 既報の「バス到着67人」「救出走行29台削減」「B側9,540台」「充足率0.271／0.0206」はすべて**撤回**。あわせて、シナリオAは `time-to-teleport` がSUMO既定300秒のままで、**「9,569台全到着」がテレポート非依存であることが未証明**のため、R4も再実行（A'）対象とする。

先に F系（実行系是正）を完了させること。F系の完了前に B3〜B5・E系・S系・V系を進めてはならない。

## 進捗ボード（状態一覧）
| ID | タスク | 担当 | 依存 | 状態 |
|----|--------|------|------|------|
| **A0** | 対象規模是正・常総full origins再生成 | Codex | — | ✅ |
| **R1** | 救出走行パラメータのconfig化 | Claude | — | ✅ |
| **R2** | メッシュ別 非保有世帯数・救出走行OD算出 | Claude | A0,R1 | ✅ |
| **R3** | 救出走行2レグtrip生成→scenario_a.rou.xml注入 | Claude | R2 | ✅ |
| **F1** | 共通モジュール抽出（閉鎖適用＋リルート＋出発前ブロック／終了条件述語／vehicle_log・summary書き出し） | Claude | — | ✅ コード実装済み（A'回帰ゲート未完走） |
| **F2** | `p2_traci_bus.py:616` の過剰break削除 | Claude | F1 | ✅ |
| **F3** | `time-to-teleport=-1` をA・B両sumocfg生成コードで統一 | Claude | F1 | ✅ |
| **F4** | route_file既定値廃止＋`--phase {measure\|final}`＋台数アサーション＋出所マニフェスト（run_id/SHA256） | Claude | F1 | ✅ |
| **R4'** | シナリオA再実行（teleport=-1・共通モジュール経由）・基準再固定 | Codex | F1〜F4 | 未完走（実行時間問題。約26分でsim時刻1260秒） |
| **B1** | バス拠点・停・乗降地点の設定（SUMO edgeスナップ） | Claude | A0 | ✅ |
| **B2** | バスroute生成（固定ルート・9往復上限） | Claude | B1 | ✅ |
| **B3** | 救出走行削減の会計連動（バス実輸送÷k） | Claude | R4',B2 | **要再実行**（実測値撤回・再計測待ち） |
| **B4** | シナリオB車両route生成（自家用車＋救出走行(削減後)＋バス） | Claude | B3 | **要再生成**（9,540台は無効） |
| **B5** | TraCIシナリオB実行（乗降＋動的閉鎖＋乗車人数集計） | Claude+Codex | B4 | **実測値撤回・再計測待ち** |
| **E1** | 評価を人単位・Type別へ拡張（逃げ遅れ人/完了時間/渋滞/公平性） | Claude | R4',B5 | 未着手（差し戻し） |
| **E2** | A/B比較CSV生成（人単位・Type別） | Claude+Codex | E1 | 未着手（✅取消・既存CSVは破棄） |
| **E3** | 床効果判定・主指標の確定 | Claude(判断) | E2 | 指標定義は凍結済／床効果はR4'後・数値はB確定run後 |
| **S1** | バス台数感度 3/5/10 実行 | Codex | B5 | 未着手（確定パイプライン上でのみ実行） |
| **S2** | 圧縮率感度でA/B順位の不変性確認 | Claude+Codex | E2 | 未着手（確定パイプライン上でのみ実行） |
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
- **完了記録（2026-07-09 Codex）**：`output/sumo/regions/08211/results/scenario_a_traci_summary.json` を確認。車両9,569台、到着9,569台、未到着0、long_stopped=102、閉鎖イベント8、最終閉鎖SUMO edge=8,968。R4基準として利用。
- **⚠️ 2026-07-09 ✅取消（[[シナリオB再実行_方針判断_fable5]] 決定3）**：`scenario_a.sumocfg` に `time-to-teleport` 指定がなくSUMO既定300秒のテレポートが有効。テレポート発生数は記録されていないため、**「9,569台全到着」がテレポート非依存であることは未証明**。床効果はこの結果では確定できない。F1〜F4完了後に `teleport=-1` で再実行（R4'）し再固定する。**旧R4の到着数に合わせる操作は禁止**（不一致なら不一致のまま再固定）。

## R4'：シナリオA再実行（teleport=-1・共通モジュール経由）・基準再固定
- **担当**：Codex ／ **依存**：F1〜F4 ／ **読む正本**：[[シナリオB再実行_方針判断_fable5]] 決定1・決定3
- **作業内容**：F1の共通モジュール経由・`time-to-teleport=-1` でシナリオAをfull再実行する。
- **完了条件（AC1）**：`arrived=9,569`・`not_arrived=0` なら床効果確定かつR4数値維持（設定記録のみ更新）。不一致ならそのまま再固定し、床効果の記述を「テレポート補正後」の数値で書き直す。この場合 `long_stopped=102` の扱い（滞留か遅延か）を再判定する。
- **注意**：旧R4との一致確認は共通モジュール抽出（F1）の回帰ゲートを兼ねる。
- **試行記録（2026-07-09 Codex）**：F1〜F4実装後、`scenario-city --city-code 08211 --scenario full` で `scenario_a.sumocfg` を再生成し、`time-to-teleport=-1` が書き出されることを確認。その後 `run-city --city-code 08211 --scenario full` を実行したが、約26分で `scenario_a_fcd.xml` の最終timestepは1260秒までしか進まず、full完走には数時間規模を要する見込みだったため停止。AC1は未達。次はFCD出力抑制・ログ間隔・実行方式の軽量化を検討してR4'を完走させる。

## B1：バス拠点・停・乗降地点の設定（SUMO edgeスナップ）
- **担当**：Claude Code ／ **依存**：A0 ／ **読む正本**：H1・P3-IMPL-0 §4・既存 `bus_demand_candidates.csv`（P3-IMPL-2✅済）
- **作業内容**：バス拠点（デポ）・避難所側バス停・住宅密集メッシュ側乗降地点を定義し SUMO edge へスナップ。出力 `bus_stops.add.xml`（busStop要素）・`bus_stops.csv`・`bus_depots.csv`。乗車対象はType3/4（`agent_types.csv`／`bus_demand_candidates.csv`）。
- **完了条件**：全busStopが有効edgeにスナップ、避難所16〜19箇所付近をカバー。
- **完了記録（2026-07-09 Codex）**：`p2_phase3_prep_agents.py --city-code 08211` で405メッシュ版 `agent_types.csv` / `bus_demand_candidates.csv` を生成。`p3_bus_scenario.py smoke --city-code 08211 --buses 5` で `bus_plan.csv` / `bus_stops.add.xml` を生成。短すぎる乗車edgeはdespawn原因として除外し、5停（origin_0057/0084/0176/0089/0085）を採用。

## B2：バスroute生成（固定ルート・9往復上限）
- **担当**：Claude Code ／ **依存**：B1 ／ **読む正本**：H1（5台・8人/4人・20km/h・9往復）
- **作業内容**：バス5台（標準8人×4＋福祉4人×1）の固定ルート（乗降地点→避難所のピストン、6h・上限9往復）を `.rou.xml` の `<vehicle>`＋`<stop>` で生成 → `scenario_b_buses.rou.xml`。台数は `BUS_SENSITIVITY` で差し替え可能に。
- **完了条件**：SUMOでバスが走行し停車する（route検証OK）。
- **完了記録（2026-07-09 Codex）**：`p3_bus_scenario.py` を地域別ディレクトリ対応に拡張。`<route repeat>` はSUMO仕様上不可のため、TraCI `setRoute` による動的往復方式を採用。busonly検証で5台・36便・215人輸送、despawn=0、conservation_ok=true。

## B3：救出走行削減の会計連動（バス実輸送÷k）
- **担当**：Claude Code ／ **依存**：R3,B2 ／ **読む正本**：車両会計判断・P3-IMPL-0 §2
- **作業内容**：シナリオBの救出走行台数 = 非保有世帯数×R −（**バス実輸送人数**÷k）。バス実輸送人数はB5のTraCI集計を用いる（初回は机上324人で仮置き→B5後に実測で再生成）。**バス定員を超えて乗れないType3/4はシナリオAと同一（救出走行を残す）**＝会計クローズ。削減対象の救出走行tripを除外するロジックを実装。
- **完了条件**：シナリオBの救出走行台数＝A基準−(バス輸送÷k)。乗れない層の救出走行が残り、A/Bで人・車両総数が閉じる。
- **完了記録（2026-07-09 Codex）**：`バス輸送実測_方針判断_fable5.md` に従い、despawn未到着を輸送完了から除外。交通流込み実測は `bus_transport_total=67`、`bus_not_arrived=24`、`residual_queue=156`。k=2.3では raw=29.13台、整数削減29台。k=1.0感度では67台。
- **⚠️ 2026-07-09 撤回（[[シナリオB再実行_方針判断_fable5]] 決定5）**：上記の実測値（候補247・乗車91・到着67・残queue156）は**実行条件が特定不能なrun由来**（バスログのmtime 14:48:43 が現存 `scenario_b.rou.xml` 14:50:06・`scenario_b.sumocfg` 14:51:09 より前）。**全面破棄**。したがって削減29台も無効。F系完了後の計測run（第0巡・`--phase measure`）で再計測する。撤回理由は「シミュレーションに反映されなかったから」ではなく**分子の67人の出所が不明だから**であり、再計測後は会計量として従指標に復帰できる。

## B4：シナリオB車両route生成（自家用車＋救出走行(削減後)＋バス）
- **担当**：Claude Code ／ **依存**：B3 ／ **読む正本**：実装指示書A-3
- **作業内容**：自家用車route（Aと同一）＋救出走行(削減後)＋バス を統合し `scenario_b.rou.xml` を生成。Type3/4のうちバス乗車者は自家用車/救出走行から除外し二重計上を防ぐ。
- **完了条件**：バス対象者と自家用車/救出走行の重複がない。SUMO route検証OK。
- **完了記録（2026-07-09 Codex）**：`p3_bus_scenario.py build-scenario-b --city-code 08211` で `scenario_b.rou.xml` と `scenario_b_vehicle_assignments.csv` を生成。A基準9,569台から救出走行29台を除外し、B車両は9,540台（private 8,164 / rescue 1,376）。
- **⚠️ 2026-07-09 要再生成（[[シナリオB再実行_方針判断_fable5]] 決定5・決定6）**：削減29台の入力（バス到着67人）が撤回されたため **9,540台は無効**。さらに `p2_traci_bus.py:779` が `scenario_a.rou.xml` を既定にしていたため、**この `scenario_b.rou.xml` は一度もSUMOに読み込まれていない**。F4完了後、計測run（第0巡）の到着人数 n から `floor(n/2.3)` で削減台数を再算出して再生成する。
- **AC3（受け入れ条件）**：route XML台数 = 8,164 +（1,405 − 削減台数）と厳密一致（アサーション通過）。`settle_stranded_to_rescue` の丸め（`rescue_after_bus_vehicles_raw: 1375.585` → 1,376台）とrouteの整数台数の対応は、丸め方向を1箇所に固定すること。

## B5：TraCIシナリオB実行（乗降＋動的閉鎖＋乗車人数集計）
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：B4 ／ **読む正本**：既存 `p2_traci_closure.py`
- **作業内容**：既存TraCI動的閉鎖にバス乗降処理を追加し、シナリオBを実行。各バスの往復数・乗車人数・所要時間を `scenario_b_bus_log.csv` に出力。`scenario_b_traci_summary.json` 生成。実輸送人数をB3へフィードバックし救出走行削減を確定（B3→B4→B5を1巡）。
- **完了条件**：道路閉鎖とバス走行が同時に動作。バス運行ログが出力され、実輸送人数で削減式が確定。
- **完了記録（2026-07-09 Codex）**：`p2_traci_bus.py` を地域別・Windows SUMOパス対応に拡張し、乗降ログ `scenario_b_passenger_log.csv`、便ログ `scenario_b_bus_log.csv`、summary `scenario_b_bus_summary.json` を生成。閉鎖打切りのみ送届完了扱いとし、despawnは未到着として別掲するよう修正。最終summaryは boarded=91、arrived=67、not_arrived=24、terminated_by_reason={despawn:3}、conservation_ok=true。despawnは残存リスクとしてE3/V4で扱う。
- **⚠️ 2026-07-09 実測値撤回・再計測待ち（[[シナリオB再実行_方針判断_fable5]]）**：**完走した「車＋バス」のシナリオB runは一度も存在しない。** 上記summaryは 14:48:43 のrun、`scenario_b_fcd.xml`／`scenario_b_tripinfo.xml` は 15:24:14 の**中断run**（`write_bus_outputs` に未到達）。両者は別runであり、E2はこの断片を結合して報告していた。boarded=91／arrived=67／not_arrived=24／residual_queue=156 は**全面破棄**。
  - なお **バス状態機械は無実**：`step_bus` の `sim_time` はTraCIループの `int(traci.simulation.getTime())` 由来で独立時計を持たない（`p2_traci_bus.py:330,340,344,593`）。バスログが17,048秒までありfcd最終が9,900秒なのは、両者が別runだから。**バス状態機械のコードは修正しないこと。**
  - 15:24 runは `scenario_a.rou.xml`（9,569台）で走っており、最終timestepで1,010台（private 860／rescue 146／bus 4）が走行中のまま終了した。原因は `close_edges_with_bus()`（`p2_traci_bus.py:244`）が乗用車をリルートしないこと（→F1で是正）。
- **再計測時の完了条件（AC2・AC5・AC6）**：`departed=9,569`／`arrived+not_arrived+departure_blocked=9,569`（厳密一致）。全B成果物が単一run（run_id一致）で、fcd閉じタグ完全、バス/乗客ログの全時刻 ≤ fcd最終timestep。`boarded=arrived+not_arrived`／`candidates=boarded+residual_queue`。
- **再計測後の検証（決定5）**：各便の所要時間をfcd軌跡と突合し、渋滞区間通過便の所要が自由流所要（バス単独スモークで取得）を上回ることを確認する。`bus_wf_1` の「947秒一定周期」（全19便中15便を占める）は、交通量依存の分散が出るか、経路が実際に無渋滞であることをfcd重畳で説明できるか、いずれかで決着させる。

---

# F系タスクカード（実行系是正・[[シナリオB再実行_方針判断_fable5]]）

## F1：共通モジュール抽出
- **担当**：Claude Code ／ **依存**：なし ／ **読む正本**：[[シナリオB再実行_方針判断_fable5]] 決定1
- **作業内容**：`p2_region_pipeline.py` から**次の3点のみ**を共通モジュール（例：`p2_traci_common.py`）へ抽出し、A・B両方が呼ぶ。
  1. 閉鎖適用＋全車リルート＋出発前ブロック（`reroute_active_vehicles()` 相当・`p2_region_pipeline.py:1600` 付近、出発前ブロックは同 1684-1694 付近）
  2. 終了条件述語
  3. `vehicle_log` / `traci_summary` の書き出し
- **やらないこと**：ループ統合。B独自のバス状態機械には触れない。
- **完了条件**：A側が共通モジュール経由で旧R4と同一結果を再現（回帰ゲート）。B側に `scenario_b_traci_summary.json`・`scenario_b_vehicle_log.csv` がA側と同一スキーマで出る（AC9）。
- **根拠**：本研究は「A/Bの差＝バスの有無のみ」を主張する比較研究であり、閉鎖時挙動が実装差で非対称だと差分すべてが疑わしくなる。二重実装ではS1〜S2（感度＝繰返し実行）で乖離が再発する。
- **実装記録（2026-07-09 Codex）**：`p2_traci_common.py` を追加し、閉鎖適用、乗用車リルート、出発前ブロック、depart/arrival/長時間停止記録、vehicle_log生成、traci_summary生成、route SHA256/台数集計を共通化。A側 `p2_region_pipeline.py` は共通関数経由でvehicle_log/summaryを生成するよう変更。B側 `p2_traci_bus.py` も同一スキーマの `scenario_b_vehicle_log.csv` と `scenario_b_traci_summary.json` を出力するよう変更。A'回帰ゲートは実行時間問題で未完走。

## F2：過剰breakの削除
- **担当**：Claude Code ／ **依存**：F1 ／ **読む正本**：決定2
- **作業内容**：`p2_traci_bus.py:616` の `if all(rt.terminated for rt in runtime.values()) and closure_index >= len(closures): break` を**削除**する。代替コードは追加しない。
- **理由**：while条件（`getTime() <= SIM_END_SEC and (MinExpectedNumber>0 or closures残 or バス未終了)`）は既に正しく、breakがそれを無効化しているだけ。バス全終了後は `step_bus` 冒頭の `rt.terminated` ガードでno-opになる。
- **完了条件**：SIM_END_SEC到達時の残存車両が not_arrived として vehicle_log／summary に計上される（A側と同一スキーマ）。
- **実装記録（2026-07-09 Codex）**：B側TraCIループから「全バス終了＋閉鎖適用完了でbreak」を削除。while条件のみで進行し、SIM_END到達時の残存車両をvehicle_log/summaryへ残す構成に変更。

## F3：time-to-teleport の統一
- **担当**：Claude Code ／ **依存**：F1 ／ **読む正本**：決定3
- **作業内容**：A・Bとも `time-to-teleport = -1`（テレポート無効）を**両シナリオのsumocfg生成コードで明示的に設定**する。現状 `scenario_b.sumocfg` の `-1` は手編集起源（`scripts/` 内に書き出しコードが存在しない）、`scenario_a.sumocfg` は無指定＝SUMO既定300秒。
- **理由**：テレポートは (a) 閉鎖edgeの疑似通過、(b) 渋滞消去による完了時間の下方バイアス、の2つの測定破壊を持つ。床効果をテレポート補助つきで主張することはできない。滞留はA側既存分類（reroute_failed／long_stopped／departure_blocked／stranded）で正直に計上する。
- **留意（決定3・留意点2）**：`-1` 下でB側に数百台規模の not_arrived が出た場合、「政策差」か「モデルアーチファクト（交差点ブロック等のデッドロック）」かを **fcdの滞留位置で切り分けてから**解釈する。自動判定しない。
- **実装記録（2026-07-09 Codex）**：A側 `generate_region_scenario()` とB側 `write_bus_sumocfg()` の `<processing>` に `time-to-teleport value="-1"` を明示出力するよう変更。

## F4：route_file既定値の廃止＋出所管理
- **担当**：Claude Code ／ **依存**：F1 ／ **読む正本**：決定4
- **作業内容**：
  - `run-bus` の `--route-file` を必須引数化し、`p2_traci_bus.py:779` の `scenario_a.rou.xml` フォールバックを**削除**。
  - `--phase {measure|final}` 相当の明示引数を追加。`measure` は `scenario_a.rou.xml`、`final` は `scenario_b.rou.xml` を要求し、**逆の組合せをアサーションで拒否**（route XML内の車両数をパースし、期待台数と厳密一致を検査。9,569台のrouteを `final` に渡すと即死する）。
  - `write_bus_sumocfg` が route-files・time-to-teleport を含む**全設定を書き出す**よう修正し、sumocfgの手編集を禁止。
  - summary JSON に route fileパス・SHA256・車両数内訳・sumocfg内容・run_id・開始/終了時刻を記録（マニフェスト）。
- **理由**：今回の事故の根因は「同じツールが計測（第0巡）と確定（第1巡）の2目的で使われるのに、コードが区別しない」こと。**既定値を `scenario_b.rou.xml` に付け替えるだけでは第0巡が壊れる**（B3の実測はB4の削減反映routeより論理的に先行するため、計測runがAのrouteで走ること自体は正しい）。台数アサーションは「29台差」という目視で気づけない差を機械検査に変える。
- **完了条件**：AC3・AC5。
- **実装記録（2026-07-09 Codex）**：`run-bus` の `--route-file` を必須化し、`--phase {measure,final}` を追加。`measure` は `scenario_a.rou.xml`、`final` は `scenario_b.rou.xml` 以外を拒否し、route XML台数と対応assignments行数を厳密検査する。summaryには `run_id`、phase、route SHA256、route台数内訳、sumocfg内容、last_sim_timeを記録する。CLI helpと measure/final のroute台数検査は通過確認済み。

---

## E1：評価を人単位・Type別へ拡張
- **担当**：Claude Code ／ **依存**：R4',B5 ／ **読む正本**：用語定義集・評価フレーム設計（公平性注記）
- **状態**：未着手（2026-07-09 差し戻し）
- **作業内容**：`p2_evaluate_results.py` を拡張：**逃げ遅れ（人単位）**（世帯車×2.3／救出走行×k／バス実乗車）、**避難完了時間分布**（全体・Type別）、**渋滞指標**（区間平均速度・最大停止台数・総旅行時間）、**公平性指標**（Type3/4の避難完了率・平均完了時間）。
- **完了条件**：A・B双方で上記指標がCSV化され、人単位で整合。`p3_evaluate_equity.py` の `compute_equity_metrics()`（worst-off分位）が**両側で走る**こと（B側 `vehicle_log.csv` の整備＝AC9が前提）。

## E2：A/B比較CSV生成（人単位・Type別）
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：E1 ／ **読む正本**：論文構成Phase3 4.7
- **状態**：**✅取消・未着手**（2026-07-09 差し戻し）
- **作業内容**：シナリオA/Bの比較CSV（逃げ遅れ人・避難完了時間・渋滞・バス輸送・Type別）を生成。**逃げ遅れは絶対数でなくA/B差・Type別分布差**を主表に。
- **完了条件**：`phase3_ab_comparison.csv`（人単位・Type別）。検算でバス利用者の二重計上ゼロ（P3-TEST-4）。
- **AC8**：`vehicle_count` 行はA・Bとも**route台数**（またはともに到着台数）で統一する。**異種量の引き算を禁止。**
- **旧記録（2026-07-09 Codex・撤回済み）**：`p3_evaluate_equity.py region-phase3 --city-code 08211` を追加・実行し `phase3_ab_comparison.csv` を生成した。
- **⚠️ 撤回理由**：同CSVの `vehicle_count: A=9569（到着台数）, B=9540（route file行数）, difference=-29` は**異なる量を引き算**していた。またB側の未到着1,010台がどの行にも現れない。`bus_transport_people=67`・`rescue_reduction_integer_k2_3=29`・`selected_stop_demand_satisfaction_rate=0.271255`・`all_type34_demand_satisfaction_rate=0.020584` はすべて出所不明runの数値。**既存CSVは破棄**し、E1完了後に再生成する。

## E3：床効果判定・主指標の確定
- **担当**：Claude Code（判断） ／ **依存**：E2 ／ **読む正本**：時間軸判断・fableチェックCRITICAL-2・[[シナリオB再実行_方針判断_fable5]] 決定7
- **状態**：**指標定義は凍結済（数値なし）／床効果はR4'後・数値はB確定run後**（三分割）
- **凍結済みの指標定義（決定7）**：
  - **主指標**：① Type3/4の避難完了時間（個人単位。バス乗客＝バス到着時刻、救出走行対象＝該当車両到着時刻）／② 需要充足率（**分母は全Type3/4**。選定5停留所分母は運用指標として従へ格下げ）／③ Type別公平性（`p3_evaluate_equity.py` のworst-off分位）
  - **従指標**：逃げ遅れ数／選定停留所充足率／救出走行削減台数／despawn便数
  - **分母入替の理由**：バスが自ら選んだ需要だけを分母にした充足率（0.271系列）を主に据えるのは選択バイアスの自己採点であり、公平性RQと矛盾する。全Type3/4分母の低い値こそが「床効果下でのバス5台の限界」という本研究の正直な発見。
- **残りの作業**：(i) 床効果の確定＝R4'（teleport=-1）再実行後。(ii) 数値の充填＝B確定run後。`評価フレーム設計.md` の成功基準を確定形に更新。
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
- `Phase3_実装タスク管理.md`（ID正本）・`開発メモ/方針判断_fable5/fableチェック_修正タスク.md`（**T-D-F1=F1〜F4**・T-D-H1=R3/R4'/B*・T-D-C2=E3・T-D-M2=S1/S2）・`CLAUDE.md` 現在フェーズ。

## 撤回済み成果物（再生成まで参照禁止）
- `output/sumo/regions/08211/evaluation/phase3_ab_comparison.csv`（破棄対象）
- `output/sumo/regions/08211/results/scenario_b_bus_summary.json`・`scenario_b_bus_log.csv`・`scenario_b_passenger_log.csv`（14:48 run・実行条件不明）
- `output/sumo/regions/08211/results/scenario_b_fcd.xml`・`scenario_b_tripinfo.xml`（15:24 中断run）
- `output/sumo/regions/08211/scenarios/scenario_b.rou.xml`（削減29台が無効・未読込）／`scenario_b.sumocfg`（手編集・route-filesがscenario_a.rou.xmlを指す）
- `output/sumo/regions/08211/results/scenario_a_*`（R4分・teleport既定300秒。R4'で再生成）

> **14:48 runの実行条件は事後特定不能**（当時のsumocfgが上書き済み）。特定を試みる工数は掛けない。破棄で足りる。

## 卒論本文への波及
- 「救出走行29台削減」「充足率0.271」を引用済みの箇所があれば**撤回対象としてマーク**すること。
- S系（感度）は**確定パイプライン（共通モジュール＋マニフェスト）上でのみ実行**する。旧パイプラインでの感度実行は禁止。
