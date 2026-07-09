# 4年次本研究 — CLAUDE.md

## プロジェクト概要

**テーマ：** 河川氾濫時における自家用車避難とデマンド交通バス活用の比較シミュレーション  
**事例：** 2015年9月 鬼怒川氾濫（茨城県常総市）  
**フェーズ：** Phase 1 完了 → Phase 2（SUMO）→ Phase 3（バス比較）

---

## Fact-Forcing Gate（フック対応）

Edit/Write/Bash の直前テキストとして以下を明示すること：

```
**Fact-Forcing Gate 回答：**
1. [対象ファイルを参照/インポートしているファイル、なければ「なし」]
2. [影響する公開関数/クラス、なければ「なし」]
3. [読み書きするデータファイルの構造、なければ「なし」]
4. [ユーザー指示の引用（verbatim）]
```

---

## 現在フェーズ（最終更新：2026/07/09）

**Phase 3 は差し戻し中。シナリオBの実測値を全面撤回し、F系（実行系是正）→ R4'（シナリオA再実行）→ B再計測 → E1/E2 → E3 の順で再構築する。**

> **⚠️ 撤回済みの数値（引用禁止）：** バス乗車91・到着67・未到着24・残queue156／救出走行削減29台／シナリオB 9,540台／`selected_stop_demand_satisfaction_rate=0.271255`／`all_type34_demand_satisfaction_rate=0.020584`。`phase3_ab_comparison.csv` は破棄。**床効果もまだ確定していない。**
>
> 理由：**完走した「車＋バス」のシナリオB runは一度も存在しない。** `p2_traci_bus.py:779` が `scenario_a.rou.xml` をハードコード既定にしていたため B4 の `scenario_b.rou.xml`（9,540台）は一度もSUMOに読み込まれず、B側成果物は 14:48 の計測run（バスログ）と 15:24 の中断run（fcd/tripinfo）の混合物だった。あわせて `close_edges_with_bus()` が乗用車をリルートせず（A側は毎閉鎖でリルート＋出発前ブロック）、`p2_traci_bus.py:616` の過剰break、`time-to-teleport` のA/B不統一（A=既定300秒・B=-1）、B側 `traci_summary`／`vehicle_log` の欠如がある。シナリオAもテレポート非依存が未証明のため再実行対象。
>
> **バス状態機械は無実**（`step_bus` の `sim_time` は `traci.simulation.getTime()` 由来・独立時計なし）。バス状態機械のコードは修正しないこと。
>
> 正本＝`開発メモ/方針判断_fable5/シナリオB再実行_方針判断_fable5.md`（論点整理 opus → 判断 fable-5 → 記録 sonnet-5）。進捗の正本＝`05_タスク管理/phase3/Phase3_実装タスク詳細_常総先行.md`。

- Phase 1（自家用車避難・41市区町村）完了済み
- Phase 2（SUMO/TraCIシミュレーション）全実装完了：
  - 常総市 SUMO ネットワーク変換・TraCI 動的閉鎖・small/10pct/full 実行
  - FCD 出力・Leaflet.js 可視化（`sumo_viz.html`、シナリオ切替UI）
  - 全 41 市区町村の small/10pct 実行完了（逃げ遅れ合計 0）
  - full は代表 6 市区町村（守谷市・那珂市・行方市・大洗町・美浦村・五霞町）で実行
  - 市区町村別評価 CSV（41行）・Phase 1/2 比較 CSV（164行）・全域 HTML 生成済み
- Phase 2 比較基準固定（2026/05/19）：
  - `p2_evaluate_results.py` に避難完了時間列を追加
  - `p2_phase3_prep_agents.py` で出発地をType1〜4分類（agent_types.csv 生成）
  - `p2_build_phase2_excel.py` で Phase 2 Excelを8シート構成に生成
  - 先生コメント対応表・成果物固定リスト・試行設定比較表・図P2-5を作成
- 次フェーズ：Phase 3（バス比較・集計）

**2026-07-03：研究設計チェック（fableチェック）に基づきPhase 3方針判断3件を確定（規模乖離・車両会計・時間軸）。正本＝`05_タスク管理/phase3/Phase3実装前仕様_P3-IMPL-0.md`・`03_研究設計文書/phase3/Phase3_規模整合メモ.md`・`03_研究設計文書/共通設計/用語定義集.md`。詳細は`開発メモ/方針判断_fable5/fableチェック_修正タスク.md`。**

**2026-07-09追記：上記B系完了記録は撤回済み。F1〜F4の実行系是正はコード実装済み（`p2_traci_common.py` 追加、B側break削除、A/B `time-to-teleport=-1` 明示、`run-bus --phase measure|final --route-file` 必須化、route台数アサーション、B側 `scenario_b_vehicle_log.csv` / `scenario_b_traci_summary.json` / run manifest 出力）。ただしR4' full再実行は `teleport=-1` で処理が非常に重く、約26分でシミュレーション時刻1260秒までしか進まず、今回開始したプロセスは停止した。床効果・B再計測・E1/E2数値は未確定のまま。**

---

## 次セッションの優先タスク

1. **Phase 3 R4'実行時間問題の解決：** `teleport=-1` full実行が長時間化しているため、FCD出力抑制・ログ間隔・実行方式を見直してAC1を完走させる。旧R4値に合わせる操作は禁止
2. **Phase 3 B再計測：** R4'完了後、B計測run（第0巡・`--phase measure --route-file scenario_a.rou.xml`）→ 削減台数再算出 → B確定run（第1巡・`--phase final --route-file scenario_b.rou.xml`）。不動点判定は `|削減台数差| ≤ 2台`・上限2巡
3. **Phase 3 E1/E2：** B側 `scenario_b_vehicle_log.csv` と `scenario_b_traci_summary.json` を使い、A/B同種量比較とType別公平性を再生成する
4. **卒論本文ドラフト：** Phase 2 本文ドラフト（第3〜4章）の執筆開始

> E3の**指標定義は凍結済**（主：Type3/4の避難完了時間・需要充足率〔**分母は全Type3/4**〕・Type別公平性／従：逃げ遅れ数・選定停留所充足率・救出走行削減台数・despawn便数）。床効果の確定はR4'後、数値の充填はB確定run後。

---

## データ取得状況（全取得済み）

| データ | パス（`04_プログラム/data/` 基準） |
| --- | --- |
| GSI KML 8時点 | `flood_kml/D1-No917_joso/` |
| A31a GML 国管理（鬼怒川含む） | `flood_hazard_a31/A31a-24_08_10_GML/` |
| A31a GML 都道府県管理 | `flood_hazard_a31/A31a-24_08_20_GML/` |
| A31a GML 埼玉県国管理（五霞町調査用） | `flood_hazard_a31/A31a-24_11_10_GML/` |
| A31a GML 千葉県国管理（五霞町調査用） | `flood_hazard_a31/A31a-24_12_10_GML/` |
| N03 茨城県行政区域（2015年版） | `admin_boundary/N03-150101_08_GML/` |
| 避難施設 P20（常総市洪水対応19件） | `shelters/避難施設データ_茨城/P20-12_08.dbf` |
| 人口250mメッシュ（T001178/T001208） | `population_mesh/5歳階級別人口250メッシュ_茨城/` |
| 浸水ナビ BP030（11メッシュ×8時点） | `suiboumap/hydrograph_origins_BP030.json` |

---

## タスク状態（未完了のみ）

| ID | 内容 | Phase |
|----|------|-------|
| P2-DOC-2 | Phase 2 本文ドラフト | 2 |
| P3-F1〜F4 | Phase 3 実行系是正（共通モジュール抽出・break削除・teleport統一・route既定値廃止） | 3 |
| P3-R4' | Phase 3 シナリオA再実行（teleport=-1）・比較基準再固定 | 3 |
| P3-B3〜B5 | Phase 3 シナリオB再計測（実測値撤回済み） | 3 |
| P3-E1/E2 | Phase 3 人単位・Type別評価と A/B比較CSV（✅取消・やり直し） | 3 |
| P3-E3/S/V | Phase 3 主指標の数値確定・感度分析・成果物HTML/Excel化 | 3 |

完了済み（P2-DOC系）：比較解釈（P2-DOC-3）・先生コメント対応表（P2-DOC-5）・図P2-5・表P2-4・表P2-6・SUMO引用・バージョン記録（P2-DOC-4、`03_研究設計文書/phase2/Phase2_SUMO引用・再現性メモ.md`）・実装後検証チェックリスト（P2-DOC-6、`06_研究結果/phase2/Phase2_最終検証チェックリスト.md`）

完了済みタスク詳細 → `05_タスク管理/phase2/Phase2_実装タスク管理.md`

---

## エージェント分担

> 正本＝`05_タスク管理/モデル運用基準.md`（モデル選択と方針判断の3段階分離）

| 作業 | 担当 |
|------|------|
| Python スクリプト新規実装 | Claude Code（Opus） |
| コード修正・テスト・動作確認 | `/codex:rescue` |
| 研究方針の判断 | Fable 5（論点整理 Opus → 判断 Fable 5 → 記録 Sonnet 5） |
| 文書作成・調査・タスク管理 | Claude Code（Opus） |

---

## 重要ファイルパス

| ファイル | パス |
|---------|------|
| 共通定数 | `04_プログラム/scripts/config.py` |
| 実装手順書 | `05_タスク管理/phase1/実装手順書_Phase1.md` |
| 実装仕様書 | `03_研究設計文書/共通設計/実装仕様書.md` |
| 最新経過報告 | `01_経過報告/経過報告2026年05月/経過報告20260527.md` |
| テスト結果 Phase 1（最新） | `04_プログラム/テスト結果/phase1/テスト結果_phase1_final_20260512.md` |
| テスト結果 Phase 2 常総市 | `04_プログラム/テスト結果/phase2/テスト結果_phase2.md` |
| テスト結果 Phase 2 全域 | `04_プログラム/テスト結果/phase2/テスト結果_phase2_region.md` |
| Phase 1 本文ドラフト | `03_研究設計文書/phase1/Phase1_本文ドラフト.md` |
| Phase 1 経路検索説明 | `03_研究設計文書/phase1/論文用説明_Phase1_経路検索方法.md` |
| Phase 1 成果物固定リスト | `06_研究結果/phase1/Phase1_成果物固定リスト.md` |
| Phase 1 研究結果 | `06_研究結果/phase1/Phase1_研究結果.md` |
