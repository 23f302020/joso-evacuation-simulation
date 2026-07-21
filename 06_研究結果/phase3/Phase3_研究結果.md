# Phase 3 研究結果

> 最終更新：2026-07-21（論文用静的図表・固定結論を接続）
> ステータス：**E3・S系・V1〜V5・V4統合記録まで完了。主結論はヌルで確定。**

## 1. 主結論

正式判定指標であるType3/4避難完了率について、Scenario A/B間の差は**本モデルの分解能では検出されなかった**。正負の方向を示す解釈、同等であるとの解釈、特定runの事後除外は行わない。

副次的には、同一モデルでseedだけを変えたrun間に強い初期条件感応性が観測され、複数regimeの存在が示唆された。これは政策効果の断定ではなく、単一runの結果を過信できないという方法論上の知見として扱う。

## 2. 正本成果物

研究指標値は本ファイルへミラーしない。正本の絶対パス、SHA-256、run ID、seed、固定route、生成commitは [Phase 3正本manifest](Phase3_正本manifest_20260720.md) を参照する。

| 用途 | 正本 |
|---|---|
| E1レプリケート帯 | `04_プログラム/output/sumo/regions/08211/evaluation/phase3r_e1_band_summary.json` |
| E1全組合せ符号 | `04_プログラム/output/sumo/regions/08211/evaluation/phase3r_e1_15_combination_signs.csv` |
| E2 A/B比較 | `04_プログラム/output/sumo/regions/08211/evaluation/phase3_ab_comparison.csv` |
| worst-off記述統計 | `04_プログラム/output/sumo/regions/08211/evaluation/phase3_worst_off_descriptive.csv` |
| A/B比較表（説明用） | [Phase3_A_B比較表.md](Phase3_A_B比較表.md) |
| 論文本文ドラフト | `03_研究設計文書/phase3/Phase3_E3本文ドラフト.md` |
| HTML成果物入口 | `04_プログラム/output/phase3.html` |
| Phase 3統合テスト記録（V4） | `04_プログラム/テスト結果/phase3/テスト結果_phase3.md` |
| 卒論用固定結論 | `06_研究結果/研究結果・結論固定_20260721.md` |
| B側運行サービス記述表 | `06_研究結果/phase3/Phase3_バス運行サービス詳細表.md` |

`outputs/retracted/decision128_pre_correction_20260713/` は撤回済み監査証跡であり、研究結果の根拠として引用しない。

## 3. 実装・評価状態

| 区分 | 状態 | 現在の位置づけ |
|---|---:|---|
| Scenario A/B実装・反復評価 | ✅ 完了 | 常総市・固定route・既存runを正本化 |
| E1/E2 | ✅ 完了 | 完了率だけを正式判定に使用 |
| E3 | ✅ 完了 | ヌル結論、補助指標、初期条件感応性、限界を同期 |
| S系 | ✅ 完了 | バス台数感度を事前登録規則に従って終了 |
| V1〜V3 | ✅ 完了 | Excel、可視化HTML、Phase 3入口を生成 |
| V4 | ✅ 完了 | 個別検証記録をPhase 3統合テスト記録へ集約 |
| V5 | ✅ 完了 | HTML手保守と再生成禁止ガードを固定 |
| AUD-0〜AUD-5 | ✅ 完了 | 正本隔離、RQ、用語、worst-off、限界、進捗を同期 |

## 4. 指標階層

- **正式判定：** Type3/4避難完了率だけを用いる。
- **記述報告：** 完了時間ECDFは完了率と対で示し、worst-offは車単位・到着者条件付き・Scenario B側バス乗客非含有の診断として示す。
- **従・限界：** 渋滞と逃げ遅れ絶対数は補助情報として扱い、主指標へ統合しない。

## 5. 解釈上の固定限界

[Phase 3限界固定文言 L1〜L4](../../03_研究設計文書/共通設計/Phase3_限界固定文言.md#phase3-limitations-fixed)をそのまま適用し、本ファイルでは再掲しない。

## 6. 論文用静的図表

| 図 | 状態 | 用途 |
|---|---:|---|
| `figures/fig4-7-1_pairwise_completion_rate_differences.svg` | ✅ | 15組差、ゼロ線、非独立注記 |
| `figures/fig4-8-1_completion_time_ecdf.svg` | ✅ | 到着者条件付き完了時間 |
| `figures/fig5-4-1_replicate_completion_rates.svg` | ✅ | A3/B5全runと初期条件感応性 |
| `figures/fig4-9-1_origin_completion_diagnostic.svg` | ✅ | A基準runの出発地別診断 |

SVGと確認用PNGを生成済みである。図5-5-1のバス10台raw/保守感度図は未作成だが、現行の正式結論固定には不要である。Phase 3の追加run・新規判定規則は追加しない。
