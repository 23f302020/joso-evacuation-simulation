# 受付・代替行動：正式run検証器の統合手順

2026-10-17。研究core 0、技術未READY。最終goalはACTIVE。人工16ケースの実行・一次再計算と、候補10種/統合9種の故意改変拒否を終えた。次の1件は、これらを正式検証器へ統合すること。

## 再利用する一次証拠と正本

- 実行器：`04_プログラム/scripts/jdrt_realtime_choice.py`。
- 入力：workspace `inputs/registered02`。独立入力28検査。人口・需要マスク・準備時刻・D0/D1・70セルは不変。
- 正式検証器の配置先：`04_プログラム/scripts/jdrt_realtime_choice_validate.py`。現在は入力検証だけ。正式runをPASS/recordする機能は未提供。
- 共通実行器による人工ケース：`technical/cf26101710`と同prefixの`_c01`〜`_c16`。protocol=`realtime_choice_fixture_v1`、purpose=`fixture`、研究採用不可。
- 独立再計算：`06_研究結果/jdrt/goal_20261017/G4_統合fixture独立監査.py`、同`G4_候補選択独立監査.py`。producerの判定関数をimportしない。
- 既存smoke会計：同`G4_smoke一次会計監査.py`、同`G4_位置・観測一次監査.py`。旧実装SHAのsmokeは履歴であり現行READYへ使わない。
- 一次監査結果：同`cf26101710_統合fixture独立監査.json`。監査器バイト原本は同`auditor_history/`。
- 現行の故意改変試験：同`G4_候補監査_故意改変試験.py`（10種）、同`G4_統合監査_故意改変試験.py`（9種）。原runは変更しない。

## 実装する検証の順序

1. **採用対象の識別と原本拘束。** 正式coreは正しいprotocol/purpose、登録セル、seed、D/需要/方式、6時間・0.5秒・controller/snapshot/dispatchの固定条件、canonical設定と入力、共通5実装SHA/原本、実SUMO/runtimeのSHAを検査する。人工fixtureやsmokeをcoreへ昇格しない。入力source/artifactとrun出力のSHAを読取前後で照合し、不完全/失敗/動作中/孤児はPASSにしない。
2. **全人口・共通実現と要求。** coreの全11,965人を登録共通CSVと照合し、原属性、元車乗員、準備時刻、意思マスク、固定終点が一致することを確認する。除外や完了者だけの分母を作らない。人物/要求/車両の一意性、要求セット、別終状態、有限待ち期限、取消後の徒歩1回、乗車後の原点回帰なし、300秒乗降・H境界をイベントから再計算する。
3. **毎stepの実actor。** `after_step_before_control`の人物/乗員と車両を結合し、二重移動/乗車、速度上限・速度積分、空車距離、経路index/版、閉鎖進入、例外/欠測を再計算する。初回出発待ちはSUMO確認済みの状態、再出庫は既知の制御に限り区別する。説明できない欠測を0へ置き換えない。
4. **制御後snapshotと全道路。** `snapshot_actor_observations.csv.gz`の`after_control_before_step`からraw件数/平均速度、路上・駐車・再出庫・未配置を集計し、道路CSVと全時刻/全edge/全modeを照合する。0件行も必須。SUMOの道路別車両IDが路上判定と一致することを確認する。coreの大きなキー集合はbitset/ストリーム等で検証し、メモリ上の巨大なPython行リストを避ける。
5. **全候補と選択。** 既存のreverse最短距離による独立計算を統合する。現在位置/partial edge・forward cycle・閉鎖グラフ・過去snapshotの路上速度、free-flow delivery、予測オフセット、全boolean/排他的拒否理由、正規化score、tie選択/受付、全vehicle×pending候補、0候補cycleを検査する。R1には未来情報が入らない。数値和の許容差とGateの厳密不等号を混同しない。
6. **徒歩距離と車両VKT。** 予定長・旧経路残り・通過部分・速度積分・残予算を別に検査する。stage長の単純合算を実距離へ採用しない。車両は実odometer増分と空車部分を再計算し、到着直前にsubscriptionから消える区間を終点/最終lane位置・経路indexから検証する。SUMOの丸め幅は出力文字列から導く。最終観測が終点edgeにない場合を無条件に補完せず、接続/内部laneを含む再計算または明示した厳密な範囲で検証し、証明できなければFAILとして保全する。
7. **状態・会計と原出力の一致。** 施設のmode共通容量、退出別計上、Type別/全員の理由別終状態、未受入時間積分、待ち/打切り、全event/transition/候補/cycle/道路/actor件数、Nativeログの例外・衝突・teleportを照合する。閉鎖によるstop中断警告は原文と対応イベントを分類し、未知の警告を一括無視しない。
8. **拒否能力と採用境界。** 現在の19改変試験に加え、全人口の欠落/重複、入力/コード/成果物改変、未完了/fixture混入、会計・閉鎖・観測欠落を拒否する反例を用意する。ファイルを壊す試験は隔離した所有fixture/一時領域だけで行い、正本runを編集しない。検証器の存在や部分検査のPASSだけでREADY/recordしない。

## その後の依存タスク

正式検証器と改変試験 → 現行コードの全14設定smoke → 新専用CLIのstart-next/check/validate/record/recover/preflightと6ファイル同期・rollback/単一writer/保存容量検査 → 共通実装SHA固定・READY → 70セルを1件ずつ開始・15分監視・一次検証と正式記録 → 全件比較/数理診断/限界/文書同期。

CLIのPID確認はWindowsでsignalを送らない方式を維持する。実行中セル/完了未記録セルがあれば次を開始しない。旧監視は旧系列完了のPAUSEDを維持し、本実験開始時に新系列へ整合させる。Drive読取のみ、外部送信/公開更新禁止、旧研究/run保全。


## 統合済み範囲と残件（2026-10-17T16:53:46.174880+09:00）

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY・実行中0。正式検証器へ全人口/共通実現・要求FSM/期限/容量・候補の独立CSR最短時間/Gate/score/選択・道路全時刻0件行再集計・毎step欠落/二重所属/経路index/徒歩積分/空車距離/VKT末端を統合。旧人工cf26101710の16ケースを原本/SHA拘束した履歴診断として再検算PASS、改変18種類を拒否し原成果物272ファイル不変。現行30unit・registered02独立入力28検査PASS。検証器SHA更新後の旧suiteは現行ゲートで拒否し、本実験へ採用しない。公開CLIの部分監査はINCOMPLETE・core採用falseを維持。次は網羅的遷移再構成・徒歩stage予算・移動中空車の制動条件・native警告分類を完成→現行統合suite/全14設定smoke→6ファイルrecord/preflight→70セル逐次実行・15分監視。旧監視PAUSED、Drive読取のみ・外部送信なし。

詳細は同タスクの「正式検証器の部分統合」と `06_研究結果/jdrt/goal_20261017/正式検証器_表会計候補_20261017T165147.json` を参照。形式上の関数名はaudit_run_tablesであり、正式validate/recordの代替ではない。


### 次の実装順の更新 2026-10-17T17:12:31.773696+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY・実行中0。遷移アンカー保持とnative減速度観測を追加し、専用スキルcf26101711の人工16ケースを完走。検証器6成分（人口/要求、候補、道路、actor/VKT、全進入/徒歩予算、nativeログ）を一次再計算。人物FSM追加後の履歴診断・28種改変拒否、現行35unit・入力28検査PASS。6ファイル記録プリミティブの成功/重複/rollback/部分修復/ロック/未解決journal阻止を隔離試験し、実研究台帳へは未接続。開始条件監査で、受理済迎車の期限同時取消・直前乗車継続・internal取消の共通run実証が不足と確認。次はその追加fixture→専用CLI/正式validate/復旧/READY→最終共通5実装のsuite/全14設定→70セル逐次実行・15分監視。旧suite/全試行を保全し、SHA混在や未実装ゲートを通さない。新図v4を独立作成。旧監視PAUSED、Drive読取のみ・外部送信なし。

正本の次の1件：`05_タスク管理/jdrt/JDRT-受付代替行動_専用CLI・開始ゲート実装手順.md`。


### native21caseと技術validate接続 2026-10-17T17:31:45.228882+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY・実行中0。人工cf26101713の21ケースが完走し、先行native CSV由来の期限等号/直前乗車/internal取消/次external閉鎖を共通実行器で実証。検証器6成分＋境界来歴の独立再計算、35種改変拒否、現行37unit・入力28検査PASS。cf12の評価器gzip衝突は全試行保全・修正・新IDで解消。CLIのvalidateを接続し、現行単独cf14で技術PASS・研究採用falseを確認。全21はその後のCLI/検証入口更新で履歴扱いとし、最終共通SHAのsuite/全14設定は未実施。次はcore開始時READY原本の拘束、正式採用validate、record/復旧/単一writer/status/start-next/容量ゲートを接続・検証→最終版を固定→全21/全14→70セル逐次実行と15分監視。新図v5を別作成、旧系列/全失敗/既存図を保全。旧監視PAUSED、Drive読取のみ・外部送信なし。
