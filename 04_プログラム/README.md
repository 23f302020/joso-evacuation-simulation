# 04_プログラム

**境界整合Bの現在地（2026-10-17）：** BA-02〜06の完了後監査を完了。次は災害時供給/需要と入力根拠の不足整理。新runなし。監視PAUSED。[副指標報告](../06_研究結果/jdrt/realtime_b_boundary_v2/postanalysis_20261017/副指標・観測監査報告.html)。下記の過去日時付き状態は履歴。

実装・入力データ・出力・テスト。**「どう動かすか」の置き場**。仕様の正本は `../03_研究設計文書/共通設計/実装仕様書.md`。

**最終更新：** 2026-10-16

---

## フォルダ構成

| フォルダ | 内容 | Git |
|---------|------|-----|
| `scripts/` | 実装スクリプト（Python・mjs） | ✅ 追跡 |
| `tests/` | pytest（unit・regression・fixtures）＋テスト設計書 | ✅ 追跡 |
| `data/` | 入力データ（国土数値情報・国土地理院・e-Stat） | ❌ 除外（再取得可能） |
| `output/` | シミュレーション出力・可視化HTML | △ HTML/CSS/JS/CSV/JSON/mdのみ追跡 |
| `テスト結果/` | テスト実行の記録md（Phase別・28件） | ✅ 追跡 |
| `docs/` | 環境・ツール記録 | ✅ 追跡 |
| `logs/`・`cache/`・`venv/` | ログ・osmnxキャッシュ・仮想環境 | ❌ 除外 |
| `chatbot_hf_space/` | 避難チャットボット（Hugging Face Space） | ✅ 追跡 |

---

## scripts/ — 実装スクリプト

### 前提・共通

| ファイル | 役割 |
|---------|------|
| `config.py` | **共通定数（最初に読む）** |
| `download_data.py` | 入力データの自動取得・展開 |

### Phase 1（自家用車避難・静的ルート探索）

| ファイル | 役割 |
|---------|------|
| `c3_get_road_network.py` | 常総市道路ネットワーク取得（osmnx） |
| `p1_city_road_network.py` | 41市区町村の道路ネットワーク取得 |
| `e1_load_flood_data.py` | 浸水データ読み込み（KML＋A31a統合） |
| `i1_spatial_join.py` | 浸水ポリゴン × 道路エッジ 空間照合 |
| `i2_generate_closure.py` | 時刻別 道路閉鎖リスト生成 |
| `i3_route_search.py` | 迂回ルート検索（Dijkstra） |
| `city_scenario.py` | 市別シナリオHTML生成 |
| `gen_unified.py` | 統合シミュレーションページ生成 |
| `gen_index.py` | トップページ生成 ⚠️ **再実行は恒久禁止**（決定155〜158・実行ガード実装済み） |

### Phase 2（SUMO/TraCI 交通シミュレーション）

| ファイル | 役割 |
|---------|------|
| `p2_sumo_env.py` | SUMO 環境確認 |
| `p2_sumo_network.py` | GraphML → net.xml 変換 |
| `p2_sumo_mapping.py` | Phase 1 edge ID ↔ SUMO edge ID 対応 |
| `p2_sumo_snap.py` | 出発地・避難所を SUMO edge にスナップ |
| `p2_derived_data.py` | 派生データ生成（時間軸対応表ほか） |
| `p2_sumo_scenario.py` | rou.xml / sumocfg 生成 |
| `p2_traci_closure.py` | TraCI 動的道路閉鎖（シナリオA） |
| `p2_traci_common.py` | TraCI 共通処理 |
| `p2_fcd_to_json.py` | FCD → 可視化用JSON |
| `p2_evaluate_results.py` | 評価CSV生成 |
| `p2_region_inventory.py`・`p2_region_pipeline.py` | 41市区町村への全域展開（A側runner・`--sumo-seed` 対応） |
| `p2_build_phase2_excel.py` | Phase 2 Excel 生成 |
| `p2_phase3_prep_agents.py` | 出発地を Type1〜4 に分類 |

### Phase 3（バス比較・評価）

| ファイル | 役割 |
|---------|------|
| `p3_bus_scenario.py` | 確定route `scenario_b.rou.xml` 生成 ⚠️ **復元はこれのみ**（決定86） |
| `p2_traci_bus.py` | TraCI バス運行（B側runner・`--sumo-seed` 対応） |
| `p3_bus_accounting.py` | バス乗降会計 |
| `p3_person_ledger.py` | 人単位台帳 |
| `p3_e1_type_metrics.py` | Type別 完了率・完了時間（E1） |
| `p3_phase3r_e1_bands.py` | 帯付き指標・15組合せ符号表 |
| `p3_evaluate_equity.py` | 公平性指標 |
| `p3_fig48_completion_time_ecdf.py` | 完了時間ECDF図 |
| `p3_s10_sensitivity_metrics.py` | バス10台感度（S系） |
| `p3_stagnation_decomposition.py` | 滞留の三層分解 |
| `p3_allocation_shadow_reweighting.py` | 構成効果（allocation shadow）の再加重分解 |
| `p3_a_side_interpretation_diagnostics.py` | A側解釈の診断 |
| `p3_validate_b_measure_gate.py` | B計測run のゲート検証 |
| `p3_correct_bus_passenger_accounting.py` | バス乗客会計の補正 |
| `p3_prepare_rerun.py` | 再実行の準備 |
| `p3_build_visualization.py` | `output/phase3.html` 生成 |
| `p3_build_phase3_excel.mjs` | Phase 3 Excel 生成（Node） |
| `generate_research_depth_figures.py` | 研究深化用の図生成 |

### 追加研究（先生コメント対応）

| ファイル | 役割 |
|---------|------|
| `p3_car_only_detail.py` | 既存Scenario A正本3runの車のみ詳細再集計 |
| `scenario_c_car_walk.py` | Scenario Cの3感度人物配分・排他的mode台帳 |
| `scenario_c_routes.py` | Scenario C pedestrian network・徒歩OD/person・自家用車trip・軽量検証 |
| `scenario_c_static_alignment.py` | Scenario Cと同条件のt0〜t7静的経路・STRICT/WADE集計 |
| `scenario_c_integrated.py` | PRE-8 Scenario C乗員台帳・統合TraCI run・評価（C8） |

### 常総市JDRT（初期基盤）

| パス | 役割 |
|------|------|
| `jdrt/domain.py` | 避難者・要求・車両・道路状態・予測状態・配車候補の型 |
| `jdrt/dispatch.py` | 実行可能性判定とB1〜B3/P1/P2用の決定論的配車方式 |
| `jdrt/validation.py` | 人物・交通手段・最終状態・車両容量の会計検証 |
| `jdrt/workspace.py` | 自治体コードを08211へ固定し、JDRT runsだけを列挙するworkspace |
| `jdrt/input_adapter.py` | 正式設定と8入力SHAを検証し、人物・request・車両・避難所・True closureを生成 |
| `jdrt/run_records.py` | 独立runのevent JSONL・manifest・設定/Input SHA・終了状態を保存 |
| `jdrt/controller.py` | TraCIとの接続、配車・乗降状態、True closure適用、閉鎖後再経路、立ち往生を管理 |
| `jdrt/smoke.py` | 常総市実SUMOで1台・10要求の閉鎖なし／閉鎖あり技術確認を独立runへ保存 |
| `jdrt/full_run.py` | v1/v2を分離し、preflight・full run・manifest・技術ゲートを管理 |
| `jdrt/__init__.py` | JDRT初期基盤の公開API |

常総市入力アダプター、run記録、TraCI controller、情報分離・会計・route統合、v2用0.5秒観測と衝突検出まで実装済み。v2実装時点でunit全171件が通過している。実SUMO smokeは閉鎖なし`smk1_no_closure_20260811_codex02`と閉鎖あり`smk2_with_closures_20260811_codex04`が技術ゲートを通過した。v1は技術停止して保全し、v2中核全20セルがCOMPLETED/valid・独立検証PASS・正式記録済み。[全セル結果一覧](../06_研究結果/jdrt/JDRT-v2_全セル結果一覧.html)、[中核比較HTML](../06_研究結果/jdrt/JDRT-v2_中核比較.html)、[比較報告](../06_研究結果/jdrt/JDRT-v2_中核比較_報告.md)を生成・再計算確認済み。候補別Gate拒否ログと閉鎖後進入の直接検証に必要な全車両軌跡は未取得であり、全評価項目の取得完了とはしない。先行REAL-R0は保全。2026-10-16ユーザー採用の実時間Bは新PAP/Registry・入力・実行器/観測・スキルCLIを分離して新規作成。入力15検査/3条件smoke/15テストPASS、新15セルを1セルずつ開始する。[B準備・進行監査](../05_タスク管理/jdrt/JDRT-実時間B_開始準備監査.md)。現在地は`../context.md`を参照する。

常総市以外の地域別SUMO出力40自治体・約3.74GBは、`../07_アーカイブ/茨城県他市町村_SUMO_20260811/`へ移動済み。全ファイルSHAと復元手順は同フォルダーの`manifest.json`・`restore_regions.ps1`を参照する。

### その他

| ファイル | 役割 |
|---------|------|
| `v2_scenario_route_simulation.py` | シナリオ版ルート探索 |
| `_gen_boundary.py`・`_gen_kinugawa_river.py`・`patch_city_river.py` | 図版用の補助スクリプト |

---

## output/ — 出力

| パス（`04_プログラム/output/` 基準） | 内容 |
|------|------|
| `index.html` | **成果物の入口**（Phase 1/2/3 を切替） |
| `phase1.html`・`phase2.html`・`phase3.html` | Phase別ダッシュボード ⚠️ **手保守が正本**（taskbar版・決定155〜158） |
| `faq.html` | FAQ ページ |
| `unified/scenario_route_simulation.html` | Phase 1 主成果物（茨城県統合シミュレーション） |
| `scenario_cities/{code}/` | 市区町村別シナリオ（41市区町村） |
| `scenario_v2/` | シナリオ型浸水拡大版（常総市） |
| `sumo/regions/{code}/` | Phase 2/3 の SUMO 成果物（run・評価・アーカイブ） |
| `sumo/viz/phase3_viz.html` | Phase 3 可視化 |
| `agents/`・`closure/`・`flood/`・`network/`・`routes/` | 中間成果物 |

> `output/` は原則 `.gitignore` 対象。HTML/CSS/JS/CSV/JSON/md のみ allow-list で追跡している（詳細は `../.gitignore`）。

---

## tests/ — テスト

| パス | 内容 |
|------|------|
| `テスト設計書.md` | テスト方針 |
| `unit/`・`regression/`・`fixtures/` | 単体・回帰・フィクスチャ |
| `conftest.py`・`pytest.ini` | pytest 設定 |

```powershell
cd 04_プログラム
python -m pytest
```

> ⚠️ **テストに指標をハードコードしない。** 過去に不良ハードコードをテストが自己照合し、**偽の緑（64 passed）**を出す循環テスト事故が3回発生している。地上真実は tripinfo / vehicle_log に取る（決定132・134）。

---

## テスト結果/ — 実行記録

| フォルダ | 件数 | 主なファイル |
|---------|------|-------------|
| `phase1/` | 11 | `テスト結果_phase1_final_20260512.md`（最新） |
| `phase2/` | 2 | `テスト結果_phase2.md`（常総市）・`テスト結果_phase2_region.md`（全域） |
| `phase3/` | 13 | 段0〜段2の実装検証・B系スモークテスト・F系実行系是正 |
| `chatbot/` | 1 | `テスト結果_chatbot_20260522.md` |

---

## data/ — 入力データ

Git 追跡外（再取得可能）。取得元・配置先・利用条件は `data/manifest.csv`、手動取得が必要なものは `data/README.md` を参照。

```powershell
cd 04_プログラム
python scripts/download_data.py
```

---

## 実装時の禁止事項（抜粋）

1. **`git restore` / `git checkout -- output/` を使わない** — 確定route `scenario_b.rou.xml`（SHA `3d6977…8297`）はCRLF形式。restore するとLF化してSHA不一致となり全ゲートが偽陽性haltする（決定86）
2. **`gen_index.py` を再実行しない** — 多ページ副作用（決定142・155〜158）
3. **指標をハードコードしない** — 真実源はアーカイブ算出とgit実測のみ（決定129・134）
4. **バス状態機械（`step_bus`）を修正しない** — 無実であることが確認済み
5. **正本run進行中は `scripts/` を編集しない**

全文は `../CLAUDE.md`「恒久禁止事項」を参照。


**実時間Bの現在地（2026-10-16）：** 新境界整合B realtime_b_boundary_v2：15/15正式記録完了。実行中0・未記録0・次セルなし。全15セル独立PASS・6ファイル実在・新台帳一意・共通4実装SHAを確認。一次人物CSVから独立一覧/seed内主指標記述表を生成、全成果物SHAを再照合。旧B8/失敗/fixtureは分離保全。閉鎖予定T・実呼出しmax(0,T−0.5)・観測上限Tの区別と最大0.5秒先行は維持。次は完了後分析タスクBA-02の副指標集計→時間/候補/道路監査→資料取得監査。追加run/方法変更は行わない。監視PAUSED（停止確認済み）。外部送信・Drive編集なし。
