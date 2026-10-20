# 受付・代替行動：専用CLIと開始ゲートの実装手順

> 最新：2026-10-18。現行入力28/52unit/共通21/35改変/全14smokeと新READYの独立13検査PASS。初回core ch261018_002を開始し15分監視ACTIVE。正式記録0/70。最新状態はcontext/専用CLIを参照。本文の日付付き旧記述は実装経緯として保持する。

2026-10-17。最終goal ACTIVE、研究core 0、技術未READY。次の実装対象を固定する。研究条件・70セル・原入力・旧系列は変更しない。

## 現在までの証拠

`cf26101711` は専用スキル経由で2026-10-17T16:59:56〜17:01:28 JSTに人工16ケース完了。同一handle76025を終了まで観測した。native減速度を毎stepと候補CSVへ保存し、再経路時に道路観測のアンカーを残す修正を実SUMOで確認。検証器の人口/要求、候補、道路、actor/VKT、遷移/徒歩予算、nativeログの6成分を一次データから照合した。要求servedを人物受入へ読み替えず、退出を施設容量へ混ぜない。

その後に人物FSM検査とCLIの6ファイル記録プリミティブを追加したため、suiteは最終共通SHAの証跡としては履歴である。後続の技術診断はhistoricalを明示し、READYやcoreへ採用しない。35unitがPASS。`record_six_files`はまだCLIのrecordサブコマンドへ接続していない。実研究の架空台帳は作っていない。

## 次の1件と実装順

0. **完了：不足する共通コントローラの期限ケース（cf26101713、21/21＋一次再計算PASS）。** 状態遷移仕様§6との照合で、既存16ケースはpendingの期限取消・迎車の閉鎖失敗・乗降中閉鎖を被覆するが、accepted pickupの期限同時取消、期限直前に乗車開始して期限後も継続、internal上で期限取消して次externalで待機、残った旧pickup stopの除去を本番run経路で実証しきれていない。旧probeの物理API検査や純粋関数だけで代替しない。

   追加fixtureの値は避難結果をハードコードせず、同一suiteの先行`forecast_r1`実行のrequest/actor CSVからnative乗車開始時刻を読み、等号deadlineと1 controller後deadlineを作る。internal用は曲がる迎車経路の校正caseを先に完走し、native internal観測の整数controller時刻からdeadlineを導く。必要なら人工graphの推定時間だけの明示した過小推定をtechnical入力へ登録し、実際の迎車が予測より遅れる状況を強制する。研究条件900秒や物理入力には適用しない。先行一次成果物/manifestをSHAで入力来歴へ拘束する。native internal観測がない・受理されない場合はcase不成立として保全し、単にPASSへ緩めない。

   factory変更後は旧fixtureのsource SHAを現行へ付け替えない。historical診断だけが、当該suiteに保存済みfactory.pyと一致するSHAを参照できるようにする。current/READYでは現行sourceと共通実装の一致を要求する。ここまでを終えた後に下のCLI/最終固定・全設定へ進む。

1. **次の1件：core READY原本と正式採用validate。技術validate入口は接続済み。** 現行 `audit_run_tables` の6成分・全原本/前後SHAが通った場合だけ技術runのPASSを返す入口を作る。fixture/smokeにはcore採用権を与えない。coreは登録全人口・正しいrun位置/セル/入力・共通5実装/実SUMO/検証器依存を照合し、開始時READYの原本アーカイブをrunへ結合する。未実装ゲートをpendingとして残したまま正式PASSへ置換しない。
2. **専用CLIのstatus/check/validate/record。** Registryのrecord_filesだけを使い、`record_six_files`を正式validate後に呼ぶ。台帳のprotocol/run/cell一意、5文書の固有マーカー、manifest/入力/実装SHAを再読して整合させる。部分記録は修復するが、同一セルの別採用runや異なる既記録identityは拒否する。起動状態JSONだけで完了とせず、PID/manifest/SUMO実態を確認する。
3. **復旧と単一writer。** launch/record/recoverを同じ排他ロックへ接続する。record journalのPREPARED、孤児RUNNING、完了未記録、未診断FAILED/INVALID、別系列の実行中を次の開始の阻止条件にする。旧PIDへsignalを送らない。クラッシュ復旧はjournalの保存バイトとSHAを検証して6ファイルの状態を確定し、理由と原本を保全する。新runで旧runディレクトリを再利用しない。
4. **READY生成。** 現行の独立入力28検査、対象unit/故意改変の実行結果とsource SHA、共通実装の実SUMO全ケース、14設定の独立smoke、6ファイルrollback/再読/一意/ロック/復旧、保存容量を原証拠から確認する。必須check集合が空/欠落の場合にREADYにしない。NumPy/SciPy版とcompiled binary、SUMO/TraCI/共有コードを拘束する。READYの再生成時も前回証跡を保全する。
5. **共通5実装を固定して最終検証。** CLI完成前に14設定を回すと共通SHAの再変更で無効になる。必要な実装と対象テストを終えてから、現行suite→6成分/改変→全14設定smoke→独立検証→preflightの順にそろえる。14設定は最初の登録seedについてD0/D1それぞれR0共用1、u05の3方式、u50の3方式。R0を需要別に重複計数しない。短縮H/ready override/部分人口はtechnicalに限定する。
6. **1セル起動。** `status → start-next`は登録順の次の1件だけ。実行前にREADYと既採用セルの共通SHAを再確認する。起動コマンド/PID/manifest/出力先を保存し、15分監視を新系列へ整合させる。終了後は`validate → record → 6ファイル実在/台帳一意 → status`まで終えて次へ進む。全70件前に方式の方向を解釈しない。

## 保存容量の判断

2026-10-17のCドライブ空きは約262GBだったが、これだけで70セルの保存可能とは判断しない。実際のCSV/gzipと観測行数、全研究人口/車両、H/dtから、密な道路観測と毎step actorの必要量を計算する。残全件と現在の1件のピーク、検証レポート・コード原本・失敗保全の余裕を含めてREADYへ拘束する。容量不足時に観測を落としたり旧runを削除して通さず、保全と必要な保存先の判断へ進む。

## 成功条件と記録

単体試験は隔離した所有一時領域で、成功記録、二重呼出し、途中失敗のバイト一致rollback、部分文書修復、同一セル別run/foreign protocol、writer競合、未解決journal阻止を確認する。今の35件だけで復旧/READY/起動が実装済みとは扱わない。研究coreが本当に開始するまでは現状把握md/htmlに未開始と記録する。

全操作はgoal operationsとworkspace driver_logs、判断/経過/タスクへ追記する。正常SUMO中はscripts/入力を編集しない。Driveは読み取りのみ、先生/Dropbox/Gmail/問い合わせ/公開更新を含む外部送信は禁止。


### 最新 2026-10-17T17:31:45.228882+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY・実行中0。人工cf26101713の21ケースが完走し、先行native CSV由来の期限等号/直前乗車/internal取消/次external閉鎖を共通実行器で実証。検証器6成分＋境界来歴の独立再計算、35種改変拒否、現行37unit・入力28検査PASS。cf12の評価器gzip衝突は全試行保全・修正・新IDで解消。CLIのvalidateを接続し、現行単独cf14で技術PASS・研究採用falseを確認。全21はその後のCLI/検証入口更新で履歴扱いとし、最終共通SHAのsuite/全14設定は未実施。次はcore開始時READY原本の拘束、正式採用validate、record/復旧/単一writer/status/start-next/容量ゲートを接続・検証→最終版を固定→全21/全14→70セル逐次実行と15分監視。新図v5を別作成、旧系列/全失敗/既存図を保全。旧監視PAUSED、Drive読取のみ・外部送信なし。

詳細は実装タスクの同日native21case節。次は1のcore採用/開始証跡を実装し、record/復旧/起動へ接続する。技術PASSだけで研究採用にしない。


### 専用CLI・開始証跡の実装 2026-10-17T17:53:53.225844+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY・実行中0。READY原本のrun内保存/一次証跡拘束、正式採用validate、6ファイルrecord/途中記録rollback/孤児復旧/単一writer/status/1セル起動を実装し、隔離48unit PASS。旧cf13全21とcf14単独は共通実装更新により履歴として保全。次は固定した共通5実装で全21ケースの実SUMO・独立再計算/故意改変→全14設定smoke→容量/READY生成を検証し、通過後70セルを逐次実行・15分監視。容量は実測拡大4倍＋5GiB余裕の1セル予約を毎回再確認し、残全件投影も明示する。旧系列/失敗/図v5は保全、旧監視PAUSED、Drive読取のみ・外部送信なし。

READYは入力/全21/全14/現行unit/35種故意改変/実装5ファイル/SUMO・TraCI・NumPy/SciPy依存を一次成果物SHAへ拘束する。開始時に原本をrunへ保存し、正式採用で再照合。途中journalは保存before/plannedバイトとSHAからのみ復旧し、無関係な編集は自動上書きしない。Popen前に起動状態を確保し、child PID/セル/READY SHAが一致した内部executeだけを許す。新IDを使用、失敗も保全。

容量の技術判断：残全70件の悲観投影を一度に満たす制約ではなく、保存済みデータを保持して毎回1セル分の保守的予約を確認する。実測smokeのbytesを全人口・全時間へ拡大し4倍余裕＋5GiBを加える。全件が収まる保証とはしない。実core取得後は実容量も監視し、不足時は後続停止・保存先検討へ移る。観測縮減/旧run削除はしない。これは保存運用だけの判断でPAP/主要指標/比較/除外規則は変更しない。

48unit PASS（unittest対象4モジュール）。実READYは未生成・core開始なし。最終suite/all14とpreflightを実測するまで技術未READYを維持。


### 最終共通版21case・独立検証完了 2026-10-17T17:57:50.037328+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY。READY証跡/正式採用/6ファイル記録/復旧/単一writer/1セル起動を実装し48unit PASS。固定した共通5実装のcf26101715全21実SUMOケースと独立再計算がPASS、35種改変を拒否・一次357ファイル不変。全14設定smokeをcs261017aで逐次実行中（sequence session3285、各smoke完走・独立PASS後だけ次へ、失敗時停止）。次は全14/容量/READY生成を検証→70セル逐次実行・15分監視。旧系列/失敗/図v5は保全、旧監視PAUSED、Drive読取のみ・外部送信なし。

cf15: 17:54:03.358428〜17:56:10.390193 JST、PID29676、session79350 exit0。独立監査session76864 exit0。根拠：`06_研究結果/jdrt/goal_20261017/正式検証器_表会計候補_20261017T175640.json`。smoke14は同一common5で短縮H1800秒、各runのmanifest/CSV/独立検証を保持し、研究台帳には採用しない。稼働中コード/入力を編集しない。


### 全14設定完了・開始前再照合 2026-10-18T09:48:28.032534+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、実SUMO稼働0。専用CLI/READY来歴/正式採用/6ファイル記録/復旧/1セル起動を実装し49unit PASS。修正後cf26101716全21ケース・独立再計算/35改変・一次357ファイル不変がPASS、cs261017c全14設定smokeも2026-10-17 18:15:10 JSTに完走・各独立PASS。旧smoke時刻不整合と進行記録rename競合は理由付き保全。2026-10-18 09:45から現行入力28検査/49unit/全35技術run/容量のpreflight再照合中（session19561）。次はREADYを実証→新系列監視を整合→70セルを1件ずつ開始・15分監視・検証/記録。独立図v6を新規作成。旧研究と失敗保全、Drive読取のみ・外部送信なし。

根拠：`06_研究結果/jdrt/goal_20261017/最終14設定・共通21_技術証跡集計_20261018.json`。smoke列は18:03:06.804411〜18:15:10.291028 JSTで12分03秒、各runの開始/終了/PID/manifest/検証報告を保存。15分を超える単一技術runなし。cf16は17:59:50.796474〜18:01:52.408016 JST、PID5448・session67470 exit0。独立session75326 exit0。図v6は旧図と別ファイル、SVG XML/全ローカルリンクPASS・GUI描画未確認。


### Windows venv起動不成立・原本保全・修正 2026-10-18T09:55:18.852705+09:00

最終goal ACTIVE。受付・代替行動70セルの研究core 0・実SUMO稼働0。旧共通版は入力28/49unit/全21・35改変/全14smoke・1,190証跡でREADYだったが、初回ch261018_001はWindows venvランチャーと実行子のPID差を本人確認で拒否し、SUMO/研究run作成前に停止・原起動記録付きFAILED保全。PID親子確認と実行PID記録を修正、実project Pythonの予約executeハンドシェイクをSUMOなしで実証し52unit PASS。短期rename競合の限定再試行も試験済み。共通5実装更新で旧READY/全技術試験は履歴化、現行版をcf26101801→独立/改変→cs261018a全14→preflightの順に再検証する。監視jdrt-b-15は新系列設定を保持し再検証中PAUSED。次のREADY後に再有効化して新IDの最初の1セルを開始する。図v6/旧研究/全失敗保全、Drive読取のみ・外部送信なし。

{"at_jst": "2026-10-18T09:55:18.852705+09:00", "action": "windows_venv_redirector_identity_fix", "failed_launch": "ch261018_001", "research_run_directory_exists": false, "core_started": false, "unit_tests_pass": 52, "regression_evidence": "actual project venv Popen child/parent identities live; actual reserved execute handshake with only runtime.run mocked in isolated owned root; no SUMO/research writes", "repair": "accept exact reserved PID or Windows immediate parent launcher with liveness; save distinct launcher/executor PIDs; bounded6 PermissionError rename retries, persistent denial fails closed", "implementation_sha256": {"04_プログラム/scripts/jdrt_realtime_choice.py": "27d30780164733dc465d2874473755500cefe803c4dc068cef6051b9b61f2c68", "04_プログラム/scripts/jdrt_realtime_choice_inputs.py": "4256cecd124bd83d35ef9c0f587edabbbe0e69e5a5d40ac23fe5bfe40ab2d05f", "04_プログラム/scripts/jdrt_realtime_choice_validate.py": "9f01a5ed79446a278fed8bd9be889d8286d3b5726463257e63030af8a22de034", "04_プログラム/scripts/jdrt_choice_policy.py": "f67811982026bb83944628fabe10844c62eb665809058a4a7c8ca30296a098c7", ".agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py": "4841f1caf0399ac3e0190a2d11f9923363a84b863088891807980a1cc08c2846"}, "monitor_status": "PAUSED", "next": "new complete prerequisites via G4pipeline_20261018a", "summary": "最終goal ACTIVE。受付・代替行動70セルの研究core 0・実SUMO稼働0。旧共通版は入力28/49unit/全21・35改変/全14smoke・1,190証跡でREADYだったが、初回ch261018_001はWindows venvランチャーと実行子のPID差を本人確認で拒否し、SUMO/研究run作成前に停止・原起動記録付きFAILED保全。PID親子確認と実行PID記録を修正、実project Pythonの予約executeハンドシェイクをSUMOなしで実証し52unit PASS。短期rename競合の限定再試行も試験済み。共通5実装更新で旧READY/全技術試験は履歴化、現行版をcf26101801→独立/改変→cs261018a全14→preflightの順に再検証する。監視jdrt-b-15は新系列設定を保持し再検証中PAUSED。次のREADY後に再有効化して新IDの最初の1セルを開始する。図v6/旧研究/全失敗保全、Drive読取のみ・外部送信なし。"}


### 現行共通版の再検証・継続記録 2026-10-18T10:09:00.241034+09:00

最終goal ACTIVE。受付・代替行動70セルの研究core 0・正式記録0。Windows venv起動不成立ch261018_001はSUMO/研究run作成前のFAILEDとして原本保全し、親子PID確認を修正後52unit PASS。固定した現行共通5実装でcf26101801全21ケース・独立再計算/35改変拒否・一次357ファイル不変がPASS。cs261018aは9/14設定を独立PASS、進行状態RUNNING、同一session46869を継続監視中。上位pipelineの報告JSON型判定エラーは試験完了後・smoke起動前に停止した履歴として保全し、共通実装を変えず専用smoke列を継続。全14完了後preflightを新規実行する。旧READY/旧技術証跡/図v6は履歴、監視jdrt-b-15は再検証中PAUSED。新READY後に監視を再有効化して新IDの最初の1セルを開始する。Drive読取のみ・外部送信なし。

上位pipelineはFAILEDの原状態を残す。成功した21ケース/独立監査を再起動せず、current suiteと現行SHAを参照してsmoke列を継続した。研究入力・比較条件・主要指標・除外規則の変更なし。


### 現行共通版の再検証・継続記録 2026-10-18T10:14:11.319324+09:00

最終goal ACTIVE。受付・代替行動70セルの研究core 0・正式記録0。Windows venv起動不成立ch261018_001はSUMO/研究run作成前のFAILEDとして原本保全し、親子PID確認を修正後52unit PASS。固定した現行共通5実装でcf26101801全21ケース・独立再計算/35改変拒否・一次357ファイル不変がPASS。cs261018aは14/14設定を独立PASS、進行状態COMPLETED、同一session46869を継続監視中。上位pipelineの報告JSON型判定エラーは試験完了後・smoke起動前に停止した履歴として保全し、共通実装を変えず専用smoke列を継続。全14完了後preflightを新規実行する。旧READY/旧技術証跡/図v6は履歴、監視jdrt-b-15は再検証中PAUSED。新READY後に監視を再有効化して新IDの最初の1セルを開始する。Drive読取のみ・外部送信なし。

上位pipelineはFAILEDの原状態を残す。成功した21ケース/独立監査を再起動せず、current suiteと現行SHAを参照してsmoke列を継続した。研究入力・比較条件・主要指標・除外規則の変更なし。


### 現行受付・代替行動の初回core開始 2026-10-18T10:20:53.261173+09:00

最終goal ACTIVE。受付・代替行動70セルの最初の研究core ch261018_002（fixed_reference_r0_seed23423）を2026-10-18T10:20:30.283668+09:00開始、観測時点RUNNING・PID生存True・sim 未観測/21600秒。正式記録0/70。現行共通5実装の入力28検査/52unit/人工21ケース・独立35改変拒否/全14smokeがPASS、1190一次証跡と独立13検査で新READYを確認。15分監視jdrt-b-15を新系列でACTIVEへ戻し、単一セルを監視する。終了後validate→PASSだけ6ファイルrecord→statusを完了してから次の1件。容量は毎回1セル予約を再確認し、全70保存可能という保証はしない。旧launch失敗/旧READY/旧技術試験/旧系列を保全、独立図v7と分析対応表を新規保存。新河川縦断図・点群仕様は参考資料で橋面高未取得のまま、現行入力へ追加なし。全70採用前の方向解釈なし。Drive読取のみ・外部送信なし。

新READY: preflight/20261018T101404862963/receipt.json。旧初回起動失敗を再利用せず別ID。モデル条件・入力・共通実装を変更せず、一次成果物の検証・正式記録は専用スキルだけで行う。
