# Phase 2 最終検証チェックリスト

作成日：2026/05/19  
対象：Phase 2成果物、評価CSV、Excel、HTML、Phase 3前処理

---

## 1. 最終判定

Phase 2は、シナリオA（自家用車のみ）の比較基準として固定可能である。

| 区分 | 判定 | 根拠 |
|---|---:|---|
| 実装スクリプト | ✅ | `p2_*.py` と `gen_index.py` の構文チェック合格 |
| SUMO環境 | ✅ | SUMO 1.26.0、TraCI、sumolibを確認済み |
| ネットワーク変換 | ✅ | `joso.net.xml` 生成済み |
| edge対応 | ✅ | Phase 1閉鎖edge 764件がすべてSUMO edgeへ対応 |
| 派生データ | ✅ | 時間軸、避難所安全性、出発地、車両台数、スナップ表を生成済み |
| TraCI実行 | ✅ | small / 10pct / full を実行済み |
| 評価CSV | ✅ | 避難結果、混雑ログ、主要避難路、Phase 1/2比較を生成済み |
| Excel | ✅ | `phase2_results_excel.xlsx` を8シート構成で生成済み |
| HTML | ✅ | `index.html`、`phase1.html`、`phase2.html`、`phase3.html` を生成済み |
| アニメーション | ✅ | `sumo_viz.html` でsmall / 10pctを確認可能 |

---

## 2. 試行別の扱い

| 試行 | 車両数 | 到着 | 未到着 | 卒論での扱い |
|---|---:|---:|---:|---|
| small | 40 | 40 | 0 | 動作確認・説明用 |
| 10pct | 120 | 120 | 0 | 常総市および全域横比較の主指標 |
| full | 1,001 | 987 | 14 | 常総市詳細・限界確認・逃げ遅れ候補確認 |

full試行の未到着14台は、すべて閉鎖済み出発edgeにより発車できなかった車両である。  
したがって、単純な実行エラーではなく、Phase 2における逃げ遅れ候補・未完走として扱う。

---

## 3. 固定する主要値

| 指標 | 値 | 参照元 |
|---|---:|---|
| small到着率 | 100% | `evacuation_summary.csv` |
| 10pct到着率 | 100% | `evacuation_summary.csv` |
| full到着率 | 98.6014% | `evacuation_summary.csv` |
| full逃げ遅れ主指標 | 14台 | `trial_settings_comparison.csv` |
| full最終到着時刻 | 9,037秒 | `trial_settings_comparison.csv` |
| Phase 2 Excelシート数 | 8 | `phase2_results_excel.xlsx` |
| HTML/JS相対リンク確認数 | 82件 | `テスト結果_phase2.md` |
| バス優先人口 | 118人 | `agent_type_summary.csv` |

---

## 4. HTML・成果物確認

| 成果物 | 判定 | 用途 |
|---|---:|---|
| `04_プログラム/output/index.html` | ✅ | Phase 1 / Phase 2 / Phase 3入口 |
| `04_プログラム/output/phase2.html` | ✅ | Phase 2成果物入口 |
| `04_プログラム/output/sumo/viz/sumo_viz.html` | ✅ | small / 10pctアニメーション |
| `04_プログラム/output/sumo/regions/index.html` | ✅ | 41市区町村のSUMO結果確認 |
| `04_プログラム/output/sumo/evaluation/phase2_results_excel.xlsx` | ✅ | Excel成果物 |

---

## 5. 卒論での注意書き

- Phase 1の到達不可はメッシュ・人口単位、Phase 2の逃げ遅れ主指標は車両単位である。
- Phase 2は、実災害を完全再現するものではなく、Phase 3でバス活用を評価するための自家用車避難ベースラインである。
- 一斉出発条件は、交通集中が起きやすい基準ケースとして採用した。
- full試行は常総市と代表6市区町村を対象とし、41市区町村の横比較では10pct試行を主指標にする。
- SUMOのteleport警告は交通流モデル上の制約として注記し、主要評価値は到着・未到着・出発edge閉鎖・主要避難路混雑とする。

---

## 6. 次フェーズへの引き継ぎ

Phase 3では、このPhase 2結果をシナリオA（自家用車のみ）として固定し、シナリオB（デマンド交通バス活用）と比較する。  
Phase 3で新たに必要な作業は、バス台数・定員・運行方式・需要地点・最大往復回数の仕様固定であり、Phase 2側に追加実装は行わない。

