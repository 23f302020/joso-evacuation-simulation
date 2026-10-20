---
name: debugging-and-error-recovery
description: 本研究の予期しないテスト失敗、ビルド失敗、SUMO/TraCI異常、SHA・人物会計・観測整合の不一致を再現して原因を絞る。既知分類済みWarningや正常な定型監視、文言修正だけでは使わない。
---

# 研究実装の原因解析

addyosmani/agent-skillsの研究向け適用版。必要な技法は[上流原文](references/upstream/skills/debugging-and-error-recovery/source.md)を参照する。起動・併用・権限の定義は[スキル・エージェント運用](../../../05_タスク管理/スキル・エージェント運用.md)に従う。

1. 失敗したcommand、終了コード、入力・実装SHA、manifest、原ログ、期待する契約と実際の差を確認する。既存証跡を保全し、原因の仮説と確認済み事実を分ける。
2. Python、CLI/validator、fixture、TraCI、SUMO native、build環境のどこで差が初めて生じるかを絞る。生成側と検証側が同じ誤りを共有していないか確認する。
3. 許可された隔離fixtureで最小再現を作り、一度に一つの仮説を検証する。凍結系列・研究coreの再実行や現在のcheckoutでのbisectを診断手段にしない。
4. 修正は対象契約の範囲に限定する。挙動修正には`test-driven-development`、Python試験には`python-testing-patterns`を併用する。
5. 最初の再現ケースと必要な回帰検証で修正を確認する。研究runの復旧・再開・採用は`joso-jdrt-runner`のゲートへ戻す。

設定欠落を既定値で埋めて研究を継続せず、失敗ログ・監査証跡を削除しない。稼働中の研究実行器・入力を編集しない。上流の広い停止・承認・全件試験の例を無関係な作業へ拡張せず、対象とリスクに応じて検証する。

成果物は、最小再現、原因または未解決仮説、最小差分、修正前後の証跡、残る開始禁止条件。単なる成功表示を原因解明や技術READYと扱わない。
