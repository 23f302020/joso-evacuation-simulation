---
name: python-testing-patterns
description: 本研究のPython試験を新設・修正するとき、境界条件、fixture、parameterization、時刻・状態・ファイルI/Oの隔離を設計する。既存unittest/pytestを尊重し、実SUMO検証の代用や全体移行には使わない。
---

# Python試験の設計

wshobson/agentsの研究向け適用版。[上流原文](references/upstream/plugins/python-development/skills/python-testing-patterns/source.md)、[基本例](references/upstream/plugins/python-development/skills/python-testing-patterns/references/details.md)、[高度な例](references/upstream/plugins/python-development/skills/python-testing-patterns/references/advanced-patterns.md)は必要なものだけ読む。[スキル・エージェント運用](../../../05_タスク管理/スキル・エージェント運用.md)を適用する。

1. 既存のunittest/pytest、命名、実行command、入力形式を確認する。試験frameworkの入替えや追加依存を前提にしない。
2. 正常系に加え、対象に関係する空入力、重複ID、境界時刻、取消・降車・閉鎖の順序、欠損、部分書込失敗を選ぶ。必要なfixture・一時ディレクトリ・parameterizationでケースを分離する。
3. 仕様・数式・人工入力から期待値を作る。人物保存則、重複/未割当、時刻の単調性、SHA、読み書き後の一致などを対象に応じて検査する。
4. 純粋ロジック・ファイルI/Oと、TraCI/SUMO native統合を分ける。mock/monkeypatchは隔離や障害注入に限定し、物理挙動の実証に使わない。
5. 挙動変更では`test-driven-development`と併用し、意図した失敗と修正後の合格を確認する。対象試験の後、必要な回帰検証だけ行う。

観測結果のハードコード、合格目的のskip/xfail追加、受入条件の緩和、coverageの一律80%採用はしない。研究coreや凍結runを試験データ作成のため再実行・上書きしない。

成果物はケースの根拠、実行commandと結果、隔離した依存、実SUMOで別途確認する範囲。
