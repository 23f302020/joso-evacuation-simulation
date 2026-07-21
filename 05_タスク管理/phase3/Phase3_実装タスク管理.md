# Phase 3 実装タスク管理

> 作成日：2026/05/19  
> 目的：Phase 3（デマンド交通バス活用シナリオ）の実装タスクを細分化し、進捗を管理する。

> **⚠️ 実装の詳細・再開手順（2026-07-03）：新規セッションで着手できる粒度のタスクカードは `Phase3_実装タスク詳細_常総先行.md`（A0/R1〜R4/B1〜B5/E1〜E3/S1〜S2/V1〜V4）を参照。方針判断（規模＝A31a想定最大約2万人・車両会計案A・時間軸＝加速シナリオ）と会計式は `Phase3実装前仕様_P3-IMPL-0.md` が正本。手順は `Phase3実装指示書_常総先行_Codex向け.md`。本表の I-系旧命名より P3-IMPL/詳細カードを優先。**

> **2026-07-20 V5完了：** HTMLダッシュボード最新化V5-1〜V5-5は完了（commit/push `86a5990`）。G3不合格後の再判断（決定155〜158）により、HTML5ページ＋CSSはtaskbar版の手保守を正本とし、`gen_index.py`再生成を恒久禁止して実行ガードを追加した。V5-5のallowlist 7ファイル以外、assets・phase3.html・route・既存変更は非混入。詳細カードは `Phase3_実装タスク詳細_常総先行.md`。

> **2026-07-20 AUD系完了・実装終了再監査：** 研究結果充足性監査の修正タスクAUD-0〜AUD-6を完了し、AUD-7で実装終了時点を再監査した。Phase 1〜3の正本、Phase 3の正式判定・記述報告・感度分析・限界・V4検証記録が存在し、正本SHAとunit 78件を再確認したため、**確定RQに必要な研究結果は充足、追加run・追加実装は不要**と判定する。残るP2-DOC-2と論文用静的図表は年末の編集タスクとして分離する。正本＝`開発メモ/研究結果充足性監査_20260720.md` §10、詳細カード＝`Phase3_実装タスク詳細_常総先行.md`。

> **2026-07-20 P3-DOC-COMP-1完了：** Scenario A/Bの取得済み結果を、正式判定、試行別値、記述・診断指標、解釈制約に分けた `06_研究結果/phase3/Phase3_A_B比較表.md` として記録した。主結果文書からの参照も追加し、全15組合せ差が0をまたぐため方向差を断定しない既存結論と同期した。

> **2026-07-20 P3-HTML-COMP-1実装完了：** `04_プログラム/output/phase3.html` に正式判定比較、8run詳細、診断指標比較、比較表Markdownへの導線を追加し、`assets/phase1.css` に横スクロール対応の比較表専用スタイルを追加した。HTML構文・リンク10件・禁止表現・撤回値・`git diff --check` は合格。アプリ内ブラウザQAは接続初期化が `Cannot redefine property: process` で2回失敗したため環境ブロックとして残し、許可なしの別ブラウザ切替は行っていない。

> **2026-07-20 P3-HTML-AUDIT-1完了：** 公開HTML5ページとPhase 3可視化HTMLを正本・充足性監査へ横断照合した。Scenario Aを「自家用車のみ」とする旧説明3箇所を救出走行込みの定義へ修正し、トップページの「二峰性を確認」を「強い初期条件感応性を観測し、複数regimeの存在を示唆」へ格下げした。あわせて本表のV4未完、A/B検算取消、リンク検証未完等の旧状態と、ルート引継ぎ文書の次作業を最新化した。HTML構文・全5ページのローカルリンク・撤回値・禁止表現・`git diff --check` は合格。

> **2026-07-20 P3-FAQ-Q49-51完了：** 警報を避難判断へ結び付けるレベル、警報直後と決壊後に避難する場合の逃げ遅れ差、デマンド交通導入のメリットを想定質問Q49〜Q51として`faq.html`へ追加し、統合版`経過報告20260729.md`にも同じ結論を記録した。Q50の定量差は対応する一対比較runがないため未算出と明記し、推測と取得に必要な追加実験を分離した。HTML構造・ローカルリンク23件・JavaScript構文を静的検証済み。

> **2026-07-20 P3-DOC-PLAIN-1完了：** `Phase3_A_B比較表.md`の冒頭に、専門用語を用いない一般読者向け説明を追加した。比較した避難方法、バスが75〜165人を輸送して迎えの車を54台減らせたこと、代表的な到着割合、結果のばらつき、全体への改善をまだ断定できない理由を平易な文章で整理した。

> **2026-07-20 P3-PROGRESS-CONSOLIDATE完了：** 07/15以降に25件へ分割・未来日付へ仮配置していた経過報告を`経過報告20260729.md`へ統合した。冒頭に番号付き更新目次、本文に番号付き22節を設け、未記録だったV5、AUD-7、V4、A/B比較表、HTML監査、FAQ、一般読者向け説明も追加した。未実施の卒論完成・提出・最終発表は実績へ含めず今後の編集作業へ戻した。8〜12月フォルダは`.gitkeep`のみとした。

> **2026-07-21 P3-HTML-NAV-FIX完了：** `phase3.html`だけ共通`global-taskbar`が欠落し、上部Phase 3メニューの「評価結果」「Phase 3成果物」を開くと共通タブが消える不具合を修正した。トップ・Phase 1・Phase 2・Phase 3・想定質問の共通タスクバーを追加し、Phase 3を選択中表示にした。HTML構造、2アンカー、ローカルリンクは合格。アプリ内ブラウザは`Cannot redefine property: process`により描画操作のみ環境ブロック。

> **2026-07-21 P3-RESEARCH-LIT-1完了：** 洪水避難ABM、公共交通避難、SUMO公式DRT、公開GitHub、ODD、常総市の実避難調査を一次資料中心に調査し、`開発メモ/類似研究調査_研究深化改善案_20260721.md`へ記録した。現研究の充足判定を維持したまま、追加run不要の文書・既存データ改善、別実験が必要な発展案、外部データが必要な案を分離し、優先度A〜Dと判断保留事項を明記した。

---

## 1. 実装方針

Phase 3では、自家用車避難を基本として救出走行を含むシナリオAを比較基準とし、デマンド交通バスを導入したシナリオBを比較した。
常総市で小規模試行による挙動確認後、fullのA側3run・B側5runとバス10台感度5runを完了した。41市区町村へのPhase 3拡張は将来課題とし、現研究では追加run・追加実装を行わない。

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
| P3-IMPL-F | 実行系是正（共通モジュール抽出／break削除／teleport=-1統一／route既定値廃止＋出所マニフェスト） | ✅ | — | `p2_traci_common.py`, 改修後の `p2_traci_bus.py` | 後続のA側3run・B側5runを共通実行系で完走し、V4統合記録で検証済み |
| P3-IMPL-5 | シナリオBの車両routeを生成する | ✅ | P3-IMPL-1, P3-IMPL-F | `scenario_b.rou.xml`, `scenario_b_vehicle_assignments.csv` | 削減54台、B側9,515台（private 8,164/rescue 1,351）でAC3一致。確定SHAを固定 |
| P3-IMPL-6 | TraCI実行をシナリオB対応にする | ✅ | P3-IMPL-4, P3-IMPL-5 | `scenario_b_bus_summary.json`, `scenario_b_passenger_log.csv`, `scenario_b_bus_log.csv`, `scenario_b_traci_summary.json`, `scenario_b_vehicle_log.csv` | 共通TraCI・マニフェスト・会計ゲート下でB側5runと感度runを完走 |
| P3-IMPL-7 | A/B比較CSVを生成する | ✅ | P3-IMPL-6 | `phase3_ab_comparison.csv`, `phase3r_e1_replicate_metrics.csv`, `phase3r_e1_15_combination_signs.csv`, `phase3r_e1_band_summary.json` | 8run・15組合せを同一定義で再集計し、raw/保守帯とヌル結論を確定 |
| P3-IMPL-8 | Phase 3 Excel成果物を生成する | ✅ | P3-IMPL-7 | `outputs/p3-impl-8/phase3_results_excel.xlsx` | 8run完了率・15組符号表・raw/保守帯・S系10台を7シートへ集約し、全シート目視QA済み |
| P3-IMPL-9 | Phase 3アニメーションHTMLを作成する | ✅ | P3-IMPL-6 | `sumo/viz/phase3_viz.html` | バス/自家用車、完了率帯、強い初期条件感応性と複数regimeの示唆を表示。視覚QA済み |
| P3-IMPL-10 | `phase3.html` を更新する | ✅ | P3-IMPL-8, P3-IMPL-9 | `output/phase3.html` | Excel、アニメーション、E2、符号表、感度成果物へのリンクを確認済み |
| P3-IMPL-11 | Phase 3テスト結果を記録する | ✅ | P3-IMPL-10 | `テスト結果_phase3.md` | V4統合記録へ実行結果、警告、限界、unit 78件の結果を集約済み |
| P3-DOC-COMP-1 | Scenario A/Bの比較表を研究結果へ記録する | ✅ | P3-IMPL-7 | `06_研究結果/phase3/Phase3_A_B比較表.md` | 正本値と照合し、正式判定と診断指標を分離して記載 |
| P3-HTML-COMP-1 | 新しいA/B比較内容をPhase 3 HTMLへ反映する | ⚠️ 実装完了 | P3-DOC-COMP-1 | `04_プログラム/output/phase3.html`, `output/assets/phase1.css` | 静的QA合格。アプリ内ブラウザ初期化エラーにより描画QAのみ環境ブロック |
| P3-HTML-AUDIT-1 | 公開HTMLと現行状態文書の最新性を横断監査する | ✅ | P3-HTML-COMP-1 | HTML5ページ、`AGENTS.md`, `CLAUDE.md`, 本タスク表 | 旧定義・過大な二峰性断定・完了状態の不整合を修正。静的QA合格 |
| P3-FAQ-Q49-51 | 警報・避難開始時期・デマンド交通の想定質問を追加する | ✅ | P3-HTML-AUDIT-1 | `04_プログラム/output/faq.html`, `01_経過報告/経過報告2026年07月/経過報告20260729.md` | Q49〜Q51、根拠リンク、未評価事項を確認。HTML・リンク・JavaScript静的QA合格 |
| P3-DOC-PLAIN-1 | A/B比較結果へ一般読者向けの説明を追加する | ✅ | P3-DOC-COMP-1 | `06_研究結果/phase3/Phase3_A_B比較表.md` | 専門用語なしで比較条件、確認できた利点、断定できない点を説明し、既存の正式判定と整合 |
| P3-PROGRESS-CONSOLIDATE | 分割経過報告を20260729へ統合し、未来月を空に戻す | ✅ | P3-DOC-PLAIN-1 | `01_経過報告/経過報告2026年07月/経過報告20260729.md`, 8〜12月`.gitkeep` | 実施済み内容と未実施予定を分離し、番号付き目次・本文・残作業を確認 |
| P3-HTML-NAV-FIX | Phase 3の2項目を開いても上部タブを保持する | ✅ | P3-HTML-AUDIT-1 | `04_プログラム/output/phase3.html` | 共通タスクバー1件、2アンカー、リンク切れ0件を確認。描画QAのみ環境ブロック |
| P3-RESEARCH-LIT-1 | 類似研究・公開GitHubを調査し、研究深化の改善案を記録する | ✅ | AUD-7 | `開発メモ/類似研究調査_研究深化改善案_20260721.md` | 公式・論文・GitHub 15件を記録し、追加run不要／別実験／外部協力の境界と優先度A〜Dを確認 |

---

## 3. 検証タスク

| ID | タスク | 状態 | 理由 |
|---|---|---:|---|
| P3-TEST-1 | 小規模試行でroute生成を確認する | ✅ | repeat方式の不成立を確認後、repeat撤廃版でSUMO完走・busStop 2停を確認 |
| P3-TEST-2 | 10pct試行で輸送人数・逃げ遅れ候補を確認する | ➖ 不採用 | 常総市fullを正式評価へ採用したため、中間規模の追加実行は不要と判断 |
| P3-TEST-3 | full試行を行うか判断する | ✅ | 常総市fullでA/Bを実行済み |
| P3-TEST-4 | A/B比較CSVの値を検算する | ✅ | 正本8runと15組合せから再集計し、raw・保守帯、車両会計を検算済み |
| P3-TEST-5 | HTMLリンク・Excelリンクを検証する | ✅ | V3/V4および今回の全5ページ静的監査で成果物リンクを確認済み |

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
