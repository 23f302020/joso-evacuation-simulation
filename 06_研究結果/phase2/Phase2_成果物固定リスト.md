# Phase 2 成果物固定リスト

> 作成日：2026/05/19  
> 目的：Phase 3へ入る前に、シナリオA（自家用車のみ）の比較基準として使うPhase 2成果物を固定する。

---

## 1. 固定方針

Phase 3では、Phase 2のシナリオAを比較基準とする。  
比較基準として固定するのは、常総市のsmall / 10pct / full結果、41市区町村のsmall / 10pct結果、代表6市区町村のfull結果、主要避難路混雑指標である。

全41市区町村の横比較では、**10pct試行を主指標** とする。  
理由は、small / 10pct は全41市区町村で条件を揃えて完了しており、fullは実行負荷を考慮して代表6市区町村に限定しているためである。

---

## 2. HTML成果物

| 成果物 | パス | 固定用途 |
|---|---|---|
| 研究成果物トップ | `04_プログラム/output/index.html` | Phase 1 / Phase 2 / Phase 3 の入口 |
| Phase 2ページ | `04_プログラム/output/phase2.html` | Phase 2成果物の確認入口 |
| SUMO走行アニメーション | `04_プログラム/output/sumo/viz/sumo_viz.html` | small / 10pct の車両移動と道路閉鎖の確認 |
| 全域SUMO結果 | `04_プログラム/output/sumo/regions/index.html` | 41市区町村のPhase 2全域拡張結果 |

---

## 3. 評価CSV・Excel

| 成果物 | パス | 固定用途 |
|---|---|---|
| Phase 2評価結果Excel | `04_プログラム/output/sumo/evaluation/phase2_results_excel.xlsx` | 評価CSVをExcelで確認する入口 |
| 避難結果サマリ | `04_プログラム/output/sumo/evaluation/evacuation_summary.csv` | 常総市small / 10pct / fullの到着・未到着・避難完了時間 |
| 試行設定比較 | `04_プログラム/output/sumo/evaluation/trial_settings_comparison.csv` | 表P2-4の元データ |
| 混雑ログ | `04_プログラム/output/sumo/evaluation/congestion_log.csv` | 60秒間隔の平均速度・停止台数 |
| 主要避難路別混雑集計 | `04_プログラム/output/sumo/evaluation/major_route_congestion_summary.csv` | 国道294号、県道357号などの路線別評価 |
| Phase 1 / Phase 2比較 | `04_プログラム/output/sumo/evaluation/phase1_phase2_comparison.csv` | 常総市の静的/動的比較 |
| 市区町村別避難結果 | `04_プログラム/output/sumo/evaluation/evacuation_summary_by_municipality.csv` | 41市区町村のPhase 2集計 |
| Phase 1 / Phase 2全域比較 | `04_プログラム/output/sumo/evaluation/phase1_phase2_region_comparison.csv` | 41市区町村の静的/動的比較 |

---

## 4. Phase 3前処理成果物

| 成果物 | パス | 固定用途 |
|---|---|---|
| エージェント4タイプ分類 | `04_プログラム/output/sumo/derived/agent_types.csv` | Type1〜4の人口を出発地別に持つ前処理表 |
| バス需要候補 | `04_プログラム/output/sumo/derived/bus_demand_candidates.csv` | Type4とType3行動困難候補を優先順に抽出 |
| エージェント分類集計 | `04_プログラム/output/sumo/derived/agent_type_summary.csv` | Phase 3前処理の集計 |
| 前処理結果文書 | `06_研究結果/phase2/Phase3前_エージェント4タイプ前処理結果.md` | 採用率、集計値、注意点 |

---

## 5. 固定方針・検証文書

| 成果物 | パス | 固定用途 |
|---|---|---|
| SUMO引用・再現性メモ | `03_研究設計文書/phase2/Phase2_SUMO引用・再現性メモ.md` | SUMO 1.26.0、引用、導入方法、再現条件 |
| Phase 2最終検証チェックリスト | `06_研究結果/phase2/Phase2_最終検証チェックリスト.md` | 成果物・評価値・HTML・Excelの最終確認 |
| Phase 2比較基準固定 | `06_研究結果/phase2/Phase2_比較基準固定.md` | Phase 3で変えない基準と評価指標 |

---

## 6. 卒論へ転記する基準値

| 指標 | 値 | 参照元 |
|---|---:|---|
| 常総市full車両数 | 1,001台 | `evacuation_summary.csv` |
| 常総市full到着台数 | 987台 | `evacuation_summary.csv` |
| 常総市full逃げ遅れ主指標 | 14台 | `evacuation_summary.csv` |
| 常総市full最終到着時刻 | 9,037秒 | `evacuation_summary.csv` |
| 常総市full避難完了状態 | incomplete | `trial_settings_comparison.csv` |
| 全域10pct車両数 | 23,054台 | `evacuation_summary_by_municipality.csv` |
| 全域10pct逃げ遅れ主指標 | 0台 | `evacuation_summary_by_municipality.csv` |
| バス優先人口（常総市Phase 2出発地） | 118人 | `agent_type_summary.csv` |

---

## 7. 注意点

- Phase 1の到達不可はメッシュ・人口単位、Phase 2の逃げ遅れ主指標は車両単位である。
- full試行は全41市区町村ではなく、常総市と代表6市区町村で実行している。
- Phase 3の比較では、常総市先行実装では常総市full/10pctを基準にし、全域拡張では41市区町村10pctを基準にする。
- エージェント4タイプ分類はPhase 3前処理であり、まだバス運行シナリオBの結果ではない。
