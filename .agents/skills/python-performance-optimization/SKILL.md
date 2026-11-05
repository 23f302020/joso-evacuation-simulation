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

## 研究本体を変えない工程計測（2026-10-24）

Windowsでの工程時間と資源使用量には`scripts/measure_pipeline.py`を再利用する。引数・判定条件・既存計測の保存先は[計測と改善タスク](../../../05_タスク管理/jdrt/シミュレーション進行効率_計測と改善.md)を参照する。`state.json`とPID作成時刻を確認し、稼働中の計測を重複起動しない。新しい`--output`にのみ保存し、研究run内へ書かない。終了・欠測・単なるphase推定を研究採用証拠と扱わない。起動は最長24時間で、常駐・再開・実験開始を自動化しない。

追加理由・旧版・人工6試験・実機試料・レビューは`07_監視システム/verification/pipeline_efficiency_20261024/`へ保存する。


## 保存済み計測の区間被覆（2026-10-27）

`scripts/measurement_coverage.py --project-root . --measurement-dir <計測dir> [--measurement-dir <別の計測dir>] --stages <工程定義JSON> --output <新しい監査dir>`で、同じPID+作成時刻・有限で非減少のCPU・120秒以下の隣接観測だけを数えます。欠測点を飛び越えず、複数計測の重複区間は一度だけ計上します。出力はgoal証跡または07のverification内の新規フォルダに限定し、読み取ったstate/JSONL原文を保存します。既存出力の再利用、研究runへの書込、研究操作はありません。

工程定義は`schema=pipeline_stage_definitions_v1`、`run_id`、`registration_id`、`stages`（name/pid/created/start/end）、`evidence`（project相対ファイル名→SHA256）です。工程時刻・実PIDの意味の結合は原本と作成時刻から担当が照合し、推定開始時刻を直接観測と区別してください。出力OBSERVATION_COVERAGE_ONLYや95%の数値だけでB達成、研究採用、原因、効率改善を宣言しません。取得窓の時刻誤差・計測途中のstateとJSONLの非原子性を保持します。部分JSONLは成功扱いせず、そのsnapshotと失敗を保全します。

追加理由・RED7/GREEN22（新16+既存6契約）・原文・scope reviewは`06_研究結果/jdrt/goal_20261017/audit_history/measurement_coverage_20261027/`を参照します。動作中の収集helperと凍結研究実装は変更していません。

## 保存済みCSVの層別計測（2026-10-28）

`scripts/measure_saved_csv_layers.py --project-root . --run-id <正式採用済みの現行ID> --output <goal証跡または07/verification内の新しいJSON>`をproject venvで実行します。新しい出力に限り、現行一意台帳・COMPLETED core・manifest SHAを確認し、全一次成果物のSHA読取、gzip全解凍、CSV辞書行の全件反復を別々に計時します。終了後のSHAとmanifest/configも照合し、処理途中の失敗は同じ新規診断JSONへ保全します。既存診断・runの上書き、研究コマンドやvalidator呼出しは行いません。

これはキャッシュと同時稼働の影響を含む1回の層別測定です。CSV反復にはgzip/文字復号を含み、数値変換・会計・最短経路・READY検証を含みません。層別時間を足して正式検証時間を分解したことにせず、科学的検証・採用・短縮効果の証拠と区別します。失敗時は同じ出力で再実行しません。実行中の研究入力/共通実装へ計測器を注入しません。

初回の手作業SHA/gzip計測を再利用可能な補助へ集約した理由・旧版・RED/GREEN・レビューは`goal_20261017/audit_history/saved_csv_layers_20261028/`を参照します。実成果物への適用結果は個別診断JSONを正本とします。

## CSV列アクセスの隔離比較（2026-10-30）

`scripts/benchmark_csv_access.py --project-root . --manifest <既存COMPLETED coreのmanifest> --output <07/verification内の新規ディレクトリ>`は、manifest拘束した道路CSVを全件読み、DictReaderと列番号アクセスで行数・時刻合計・台数合計を比較します。旧登録の保存物も明示した登録IDの診断として扱い、現行研究へ再採用しません。原本前後SHA・manifest不変・所要/CPU秒を保存し、失敗出力は保全します。

凍結実行器/検証器や収集helperを編集・importせず、プロファイラ注入・研究操作もしません。全フィールド/科学検証の同等性は証明せず、本番置換や総時間短縮を許可するPASSではありません。順次2走査のcache/同時負荷を記録し、別担当の処理開始と重なった場合は汚染窓を残します。研究実行/検証中に同じ重い比較を新設しません。旧版・4契約の未実装RED/GREEN・実測・レビューは`07_監視システム/verification/pipeline_efficiency_20261030/`へ保存します。

`--full-row-equivalence`（2026-11-05追加）は、DictReader互換の辞書行generator候補を同じ原本の全行と照合し、全値・キー順・末尾欠落を検査します。空入力/空行/引用内改行/列順/重複header/余剰・不足値は人工契約でも照合します。この候補は先の2列だけの列番号アクセスとは別で、過去の23.40秒を新候補の速さへ転用しません。科学的consumer全体の実行や凍結検証器への組込みを行わず、別版候補は未適用patchとしてのみ保存します。旧版・未実装RED/6契約GREEN・全行照合とレビューは`07_監視システム/verification/pipeline_efficiency_20261105/`へ保存します。
