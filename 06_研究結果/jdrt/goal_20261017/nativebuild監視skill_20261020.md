# Native build監視のスキル集約（2026-10-20）

繰返しの隔離native build監視を既存joso-jdrt-runnerに追加した。build stateとCIMが一次証跡であり、研究run向けcheckを呼ばない。研究input/common-five/PAP/旧run/build orchestratorには変更していない。

## 変更と旧版

- 新規helper: `.agents/skills/joso-jdrt-runner/scripts/choice_native_build_monitor.py`
- CLI: venv Pythonから `choice_native_build_monitor.py --state <absolute-build-state-json>`。
- `references/routine_operations.md`は専用section追記のみ。旧bytesは `audit_history/native_build_monitor_skill_20261020/routine_operations.before.md`、旧SHAは `a20977d799c7568ecc37f4956262d0fced2e5dd379833f2be14125424cec34cf`。
- prior core/technical helper SHAを保存し不変を確認。sourceSHAと関連検証は同archiveの `revision_before.json` / `verification.json`。

## 検証

- temporary/mock tests 9件PASS。PID creation一致・再利用・不在・unknown・command違い、terminal FAILED/COMPLETED、partial JSONを記録して後続禁止、原state/log不変、3JSONL同内容1回appendを確認。
- skill-creator quick_validate: `Skill is valid!`。所有3ファイルの行末空白なし、既存reference prefix不変。
- 実Windows CIM観測: 2026-10-20T08:11:05.716995+09:00（UTC 2026-10-19T23:11:05.716995+00:00）、attempt03 RUNNING / sumo_netconvert_build_static_zlib。owner5796・child22460はcreation milliseconds / command / executable / parent PIDが両方matched、anomaly=[]、exit0。
- 観測report: [nativebuild監視_20261020T081105716995.json](nativebuild監視_20261020T081105716995.json)。state raw snapshot/SHA一致、goal operationsとworkspace operations/monitoringに同一entryが各1件だけ存在することを独立再読で確認。観測中state bytes不変=True。live logは自然増加し得るため全SHAを毎回算出しない。終端時だけ全SHAを記録する。

## 運用境界

同一owner/childを15分後・以後15分ごとに点観測する。orchestratorの約20秒state更新を独立監視としない。本helper初回のprevious independent observationはnullであり、それ以前の監視継続を証明しない。build開始から今回までの経過=505.169766秒。前回helper観測があるときだけ未観測間隔を秒で記録する。

schema/必要identity不足・partial JSON・nonterminal不在/不一致・FAILEDは異常証跡を保存して終了非0。研究manifest不存在は隔離buildには適用外。build COMPLETEDでもnative regression verified / core_ready / downstream_start_permittedは常false。start/kill/rebuild/recover/validate/record権限を持たず、研究採用を代替しない。

routine workerの新規briefはgpt-6-luna/low、fork_turns=noneを使いhelper・state path・最新観測だけを渡せる。今回はparentから継承したbackendを維持し、モデルoverride要求はしていない。実backend名は独立観測不能であり、文書編集をモデル切替とは扱わない。

## 現行source SHA

- `.agents/skills/joso-jdrt-runner/scripts/choice_native_build_monitor.py`: `b2b403a2a2b7fc745c5f0e28ec13999a154c3840d160a855593627c03772d9e3`
- `.agents/skills/joso-jdrt-runner/tests/test_choice_native_build_monitor.py`: `58511598c25e4b28cdd90dfe89ad1a923e7cdf924544e71e4824d3c427de4840`
- `.agents/skills/joso-jdrt-runner/references/routine_operations.md`: `60b8d3d5684db862925e8405450e2bb340e700ac6a8aaf636afbd7b7a03f7b92`

## 実orchestrator終端statusへの追従

rebuild_attempt02.pyの実source（行128/132）とa02 previous stateを確認し、`FAILED_PRESERVED` / `COMPILED_VERSION_CHECKED_NOT_SIMULATED`をrecognized terminalへ追加した。前者はfailure anomaly、両方は終端logSHA対象。終端owner不在は合法で、未知statusは引続きfail closed。成功はcompile/version確認のみであり、native regression/core READY/後続開始などのfalse境界は維持。RUNNING観測（08:11:05、Luna08:13:53）は書換えていない。

修正前helper/test/ref bytes・SHAとsource/previous state SHAは`audit_history/native_build_monitor_skill_20261020/failed_preserved_revision/`へ保全。関連12 unittest PASS・skill quick_validate PASS。現行helper SHA=`557faf3834d0295e3301cfaa00f7bd089cac330c6cac2c9cd27d00c7261e7eba`。上段の9testsとsourceSHAは初版時点の履歴である。

親からの実障害共有を受け、定型文書追記の既存bytes/EOL/BOM保全、PowerShell backtick解釈回避、追加域NUL/空白/diff確認を既存routine referenceへ短く追記した。byte appendで旧prefix完全一致・所有3ファイルNULなし/行末空白なしを確認。global diff-checkの他担当経過報告EOL問題は親が修正中で、本担当は未編集。
