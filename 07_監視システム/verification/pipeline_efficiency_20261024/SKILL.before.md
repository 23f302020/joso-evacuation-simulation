---
name: python-performance-optimization
description: 本研究のPython処理が遅い／メモリを消費するとの依頼、または測定で性能退行が確認された時に、CPU・メモリ・I/Oを解析する。正常な定型監視、正しさ未解決のSUMO異常、単なる高速化の思い付きでは使わない。
---

# 実測に基づくPython性能解析

wshobson/agentsの研究向け適用版。[上流原文](references/upstream/plugins/python-development/skills/python-performance-optimization/source.md)、[基本例](references/upstream/plugins/python-development/skills/python-performance-optimization/references/details.md)、[高度な例](references/upstream/plugins/python-development/skills/python-performance-optimization/references/advanced-patterns.md)は測定対象に必要なものだけ読む。[スキル・エージェント運用](../../../05_タスク管理/スキル・エージェント運用.md)を適用する。

1. 対象command、入力規模・SHA、環境、所要時間、ピークメモリ、出力契約を確認する。Python、SUMO/native、build、CSV I/Oの時間を混同しない。
2. 保存済み成果物の読取や許可済み隔離fixtureで基準を測る。まずcProfile、time/perf_counter、tracemalloc等の既存利用可能な手段から選び、必要のない依存を追加しない。
3. 実測で支配的な箇所を特定し、結果の意味と順序を保つ最小改善を選ぶ。全CSV監査の抜き取り化や受入検査の省略を高速化と扱わない。
4. 同じ入力・条件で時間とメモリを比較し、結果の会計・時刻・SHA等を契約に応じて独立照合する。挙動変更の懸念はTDD/Python試験で検証する。

研究coreの追加実行・並列化、seed削減、step/時間刻み・PAP・精度・情報条件の変更を提案から自動実施へ進めない。凍結実装と稼働中実行器は編集せず、上流のcache・並列処理・近似の例を無条件に採用しない。

成果物は測定条件、ボトルネックの証拠、修正前後の時間/メモリ、意味同一性の検証と残る限界。性能改善だけで技術READYやセル採用としない。
