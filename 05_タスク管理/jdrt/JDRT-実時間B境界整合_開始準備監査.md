# 実時間B 境界整合系列：提案1採用、新規15セルの開始準備

開始：2026-10-16T18:07:07.801640+09:00。protocol=`realtime_b_boundary_v2`。ユーザーの明示回答「提案1：移動前制御を登録し15セルを再実行（推奨）」を受領済み。旧`realtime_b_v1`の8正式記録・全失敗run・旧PAP/入力/実行器は保全し、新主比較へ混ぜない。旧系列HOLDは維持する。

## 実行契約と権限

新PAP：[境界整合v2](../../03_研究設計文書/jdrt/常総市JDRT_実時間B_境界整合_PreAnalysisPlan_v2.md)。新Registry：`04_プログラム/config/jdrt_realtime_b_boundary_v2.json`。native閉鎖予定Tはそのまま、実制御呼出しmax(0,T−0.5)、観測上限Tを分離する。初期0と末尾21600を含め、先行量を隠さない。R0/R1に未来Trueを配車入力として渡さず、R2予測は予定T+900のまま。全15セルは共通実装SHAの新runだけ。退出は施設受入と別計上、主要Type4分母は全域内人物を保持する。

スキル専用CLI：`.agents/skills/joso-jdrt-runner/scripts/realtime_b_boundary_cell.py --project-root .`。project venvを使う。旧CLIで再開せず、新CLIは旧系列の記録を読んで完了数に加えない。監視は既存jdrt-b-15を新系列へ更新し、重複作成しない。外部送信・Drive編集・公開更新は禁止。

## 詳細タスクと検証責任

| ID | 責任 | 作業 | 成功条件 | 状態 |
|---|---|---|---|---|
| BB-01 | 現chat統括 | 人間の採用判断・新PAP/Registry・旧8分離 | 承認引用/出典/SHA、事前登録 | 完了 |
| BB-02 | 入力処理 | 旧物理artifact同一バイトで別workspaceへ継承、新manifest結合 | 原本HDF/terrainから再計算・SHA・新時計契約PASS | 完了 |
| BB-03 | 実装処理 | 移動前制御と予定/呼出し/上限時計、車/徒歩全step処理 | 初期/末尾/等号/交差点/無閉鎖/過去区間のunit・実SUMO PASS | 完了 |
| BB-04 | 独立検証処理 | 会計/観測/候補/時計/遷移を一次成果物から再計算 | kind自己申告に依存せず境界≥T進入0、共通実装一致 | 完了 |
| BB-05 | スキルCLI | 同一実装・1セル・6ファイルrollback同期 | 外来protocol/重複/版混在拒否、partial write保全、各smoke PASS | 完了 |
| BB-06 | 文書処理 | 新独立図解/Registry閲覧版/現状把握md/html/索引/進行 | 新0/15と旧8参考を区別、0.5秒先行明記 | 完了 |
| BB-07 | 実行処理 | 入力/unit/実SUMO/3smoke→preflight→R0 seed23423を1セル開始 | PID/manifest/進捗、重複なし、15分監視 | 完了：初回R0開始済み |
| BB-08 | 監視/記録処理 | 各seed R0→R1→R2、15分監視→validate→record | 全15セル、各PASS・新台帳一意・6ファイル実在後のみ後続 | 完了：新15/15正式記録・全5seed |
| BB-09 | 事前登録分析 | 共通実装の新15セルだけで対応seed比較・一覧 | 全5seed採用、旧8/失敗/fixtureの混在0 | 一覧/主指標記述表完了。副指標/取得監査はBA-02以降へ |

同一chatが順次に役割を担う。サブエージェント/別chat/モデル変更を行わない。通常の技術修正は権限内で実施し、研究条件を追加変更する場合だけ別の明示判断を得る。

## 操作記録

- 新PAP/Registryを入力準備・研究run前に作成。新workspace=`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_b_boundary_v2`。
- 新入力準備器は旧登録artifactと出典SHAを検査し、コピー後SHAを独立照合。原本への書き込みなし。
- 新実行器は閉鎖制御call=max(0,T−dt)を事前計算し、全イベントへ3時計/phaseを保存。元のnative Tと予測T+900は保持。
- 新検証器はclosureの3時計/一意性、transition分類と時刻をhazardから再計算する。
- 新CLIは4実装SHAの共通性・外来protocol/台帳重複を検査し、旧workspaceでrunが動いている場合も起動を拒否する。
- 18既存回帰テストを新系列へ分離し、境界/情報分離の対象テストを追加。テスト結果をまだ先取りしない。
- 最後の実監視ログ14:34以降のheartbeat到着は監視実行の証拠としない。18:00の再読込時までの監視記録空白も隠さず、保留中に実行していたとは記載しない。

0/15記録、研究run未開始。入力・実SUMO・smoke・文書反映・開始の操作結果を順次追記する。


### 境界整合系列：開始前READY・検証詳細（2026-10-16T18:21:32.459239+09:00）

提案1採用の新境界整合系列realtime_b_boundary_v2、0/15正式記録・実行中0。入力17検査/23テスト/実SUMO9ケース/現行3条件smokeすべてPASS、preflight READY。予定T・呼出しmax(0,T−0.5)・観測上限Tを分離する新PAP/Registry/独立図解を作成済み。次は新CLIでR0 seed23423を1セル開始し15分監視→独立validate→6ファイルrecord。旧B8記録/全失敗/旧HOLDを保全し新主比較へ混ぜず、全15セルを同じ4実装SHAでそろえる。既存監視jdrt-b-15は新系列へ更新済み。外部送信・Drive編集なし。

物理入力11artifactのSHA一致、原本から35,366道路/手段行を再計算して17検査PASS。unit23件PASS（追加テストの仮ディレクトリmock漏れ1試行を保全後修正）、実SUMO9ケースPASS。新R0/R1/R2 smoke IDは{'R0': 'rtbb2_smoke_r0_seed23423_20261016T181244', 'R1': 'rtbb2_smoke_r1_seed23423_20261016T181432', 'R2': 'rtbb2_smoke_r2_seed23423_20261016T181624'}、全clock/会計/観測/遷移/Error等PASS。preview.state.jsonが専用CLIのrun-state globへ衝突したstatus失敗はoperationsに記録し、表示確認用metadataをpreview_server.jsonへ名前分離して解消、研究コード/入力変更なし。新図解を狭い表示幅で実見し、小さかった時計SVGを縦カードへ切り替えて可読性確認。新CLI/4実装SHA・単体ソースSHA・timing証拠SHAをpreflightで確認。監視jdrt-b-15を新系列のCLI/準備監査へ更新し、ACTIVE/15分・同じchatで重複作成なし。


### 新境界整合R0 seed23423開始（2026-10-16T18:23:44.103453+09:00）

新境界整合B realtime_b_boundary_v2：0/15正式記録。R0 seed23423 `rtbb2_core_r0_seed23423_20261016T182150`を18:21:50 JSTに開始、status=RUNNING・PID alive=True。入力17検査/23テスト/実SUMO9ケース/現行3条件smoke PASS、preflight READY後の新規開始。閉鎖予定T・実呼出しmax(0,T−0.5)・観測上限Tを分離し、共通4実装SHAで新15セルをそろえる。旧B8記録/全失敗/旧HOLDは保全して新主比較へ混ぜない。次はこのrunのcheck→終了後validate→新6ファイルrecord・台帳一意確認→status。監視jdrt-b-15は新系列で15分ACTIVE、全5seed前に方向解釈しない。主run稼働中はscripts/入力を編集しない。外部送信・Drive編集なし。

実manifest PID=10428、4実装SHAは全てunit/timing/3smokeと一致。開始操作・実コマンド・時刻はoperations.jsonl/stateへ自動記録。今回のスコープのFact-Forcing Gateは新CLI/新runの1セル開始、固定入力を読み別IDへ3時計と全観測を保存、ユーザーの採用回答を根拠として実施。正式記録数0で本runの採用を先取りしない。新台帳に旧8/失敗/fixtureは混在なし。ローカルリンク77件検証・表示確認、metadata再結合済み。


### 最終参照整合・表示確認後片付け（2026-10-16T18:27:42.735847+09:00）

contextに新PAP/Registry/準備監査/専用CLIの参照を追加。output/jdrt.htmlの旧15テスト表示を新17入力検査/23テスト/実SUMO9ケース/3smoke PASSへ更新、旧8分離と独立図解リンクを反映。一時IABタブを閉じ、所有PID26540のhttp.server 8774 --bind 127.0.0.1を実コマンド照合後停止。研究runと実装/入力設定は変更なし、外部送信/Drive編集なし。


### 境界整合R0正式記録・R1開始（2026-10-16T18:32:43.346279+09:00）

新境界整合B realtime_b_boundary_v2：1/15正式記録。R0 seed23423 `rtbb2_core_r0_seed23423_20261016T182150`は独立検証PASS・6ファイル同期・新台帳一意確認済み。R1 seed23423 `rtbb2_core_r1_seed23423_20261016T183134`を18:31:34 JSTに開始し、RUNNING・PID生存を確認。共通4実装SHA・入力17検査/23テスト/実SUMO9ケース/3smokeは維持。次はR1のcheck→終了後validate→record・6ファイル同期確認→status。旧8は分離保全、最大0.5秒先行を明示し、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0は2026-10-16T18:27:59.812533+09:00にsim21600.0秒・43200step・361snapshot。全人物終端11965人、Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行、遷移268049、候補0、閉鎖後進入/曖昧遷移/Error/teleport/衝突/観測欠損0。閉鎖13665件（初期6172・0.5秒先行7493・末尾73）の3時計/phase一致。急減速警告2件は原ログ保全。警告をErrorと混同せず、方式効果の解釈はしない。record内の再検証もPASS、新6ファイルの実run IDと台帳1件を確認後、statusの次セルR1・preflight READY・共通SHAを確認して1セルだけ開始。新R1 manifest PID=7700、今回check sim=2160.0秒、counts={"steps": 4320, "controller_ticks": 2161, "snapshots": 37, "teleports": 0, "collisions": 0, "transition_rows": 70595, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 4993, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T18:47:34.638258+09:00）

新境界整合B realtime_b_boundary_v2：2/15正式記録。R1 seed23423 `rtbb2_core_r1_seed23423_20261016T183134`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed23423 `rtbb2_core_r2_seed23423_20261016T184653`を2026-10-16T18:46:55.399168+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed23423：2026-10-16T18:37:30.852313+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出110は別計上。道路観測19197258行・遷移256318・候補722086。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 256318, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 722086, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=24184、check={"run_id": "rtbb2_core_r2_seed23423_20261016T184653", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T18:47:37.369008+09:00", "run_id": "rtbb2_core_r2_seed23423_20261016T184653", "time_sec": 960.0, "end_sec": 21600, "wall_sec": 25.79474189999746, "people_states": {"not_ready": 10398, "admitted": 241, "travelling": 246, "waiting": 109, "onboard": 3, "no_route": 67, "boundary_exit": 754, "assigned": 1, "walk_limit": 19, "no_origin_connection": 87, "initial_or_current_closed": 40}, "active_vehicles": 96, "counts": {"steps": 1920, "controller_ticks": 961, "snapshots": 17, "teleports": 0, "collisions": 0, "transition_rows": 29562, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 239, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 文書同期補助の運用記録（2026-10-16T18:48:11.278524+09:00）

監視文書更新の反復をそろえるため、driver_logs/update_monitor_documents.pyを新規保存。研究実行・validate・正式record・後続起動は引き続き専用スキルCLIのみが担当し、この補助はstatus/checkと既PASS成果物/台帳を読んで14文書・図解metadata・monitoringを更新する。初回は新R2の入力読込中でprogress=Noneのため文書変更前にTypeError停止。例外をmonitoringとdocument_helper_initialization_attempt.jsonへ保全し、最初のprogress確認後の再実行は成功。今後は同状態を明示RuntimeErrorで通知する事前ガードを追加。補助処理は4実装SHA・研究入力・PAP・台帳を編集しない。現runの全人物会計一致、72ローカルリンク切れ0、図解metadata結合・git diff --check PASS。次回はCLIの6ファイル同期確認→status/preflight→1セルstart-next後、初回progressを確認してproject venvでこの補助へ「完了run ID 新実行run ID」を渡せる。補助によるPASSは正式validateやrecordの代用ではない。


### R2閉鎖結果の分類・文書同期欠落の補修（2026-10-16T19:03:46.576552+09:00）

R2 seed23423は独立PASSで正式record、新系列3/15。候補617262行・遷移255175・道路観測19197258行、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。b_drt_0は4199.5秒に現道路3915#9の閉鎖で除去（予定4200秒）。2760秒割当・3978秒乗車処理開始のType4対象1人は乗車完了前にstranded_drtとなり、施設受入/退出に加えず分母保持。停止中止警告1件との対応を一次event/person/request/vehicle CSVで照合し、driver_logsの当該drt_closure_audit.jsonへ保存。方式の方向解釈なし。全3記録の6ファイル横断確認で、過去の文書現在地置換がcontextの最初のR0 run IDを落とした不備を検知し、start-next前に遮断。一次成果物・台帳3件は不変。専用CLI recordでR0を再検証PASSしてcontext欠落を補修し、全3ID×6ファイル存在・台帳重複0を再確認。文書補助は前回現在地の履歴保全と全採用ID保持の検査を追加。研究4実装SHA/入力/PAP変更なし。status次R0 seed42・preflight READY後、19:03:25 JSTにrtbb2_core_r0_seed42_20261016T190325を1セル開始。途中の遮断・例外・補修コマンドはoperations/monitoringとcross_record_document_presence_failure.json、all_three_six_file_sync_repaired.jsonへ保全。外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:03:54.030563+09:00）

新境界整合B realtime_b_boundary_v2：3/15正式記録。R2 seed23423 `rtbb2_core_r2_seed23423_20261016T184653`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed42 `rtbb2_core_r0_seed42_20261016T190325`を2026-10-16T19:03:27.779577+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed23423：2026-10-16T18:52:43.597441+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出96は別計上。道路観測19197258行・遷移255175・候補617262。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 255175, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 617262, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告1件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=27312、check={"run_id": "rtbb2_core_r0_seed42_20261016T190325", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:03:57.442381+09:00", "run_id": "rtbb2_core_r0_seed42_20261016T190325", "time_sec": 660.0, "end_sec": 21600, "wall_sec": 18.78571140000713, "people_states": {"not_ready": 10933, "no_origin_connection": 49, "admitted": 110, "travelling": 247, "no_route": 85, "boundary_exit": 480, "walk_limit": 41, "initial_or_current_closed": 20}, "active_vehicles": 83, "counts": {"steps": 1320, "controller_ticks": 661, "snapshots": 12, "teleports": 0, "collisions": 0, "transition_rows": 17765, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R0 seed42採用・警告分類と次セル開始（2026-10-16T19:16:05.841131+09:00）

R0 seed42の一次検証とrecord内再検証がPASS、新系列4/15正式記録。警告は歩行開始位置のedge末端補正3件と急減速2件に分類し、対象人物/車両・時刻・原文を当該completion_monitor.json/warning_clock_audit.jsonとmonitoringへ保持。警告0をゲートに追加せず、研究共通実装/入力/PAPの変更なし。閉鎖13665件（初期6172、0.5秒先行7493、評価末尾73）の3時計/phase一致。全4セル×6ファイルのrun ID実在・台帳4件一意・全4実装SHA共通を確認後、status次R1 seed42・preflight READYを経て19:15:43 JSTにrtbb2_core_r1_seed42_20261016T191543を1セル開始。旧8記録は新比較/新台帳へ混在なし、全5seed前の方向解釈なし。外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:16:13.176667+09:00）

新境界整合B realtime_b_boundary_v2：4/15正式記録。R0 seed42 `rtbb2_core_r0_seed42_20261016T190325`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed42 `rtbb2_core_r1_seed42_20261016T191543`を2026-10-16T19:15:46.646693+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed42：2026-10-16T19:09:24.244912+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移269019・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 269019, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告5件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=23052、check={"run_id": "rtbb2_core_r1_seed42_20261016T191543", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:16:16.817988+09:00", "run_id": "rtbb2_core_r1_seed42_20261016T191543", "time_sec": 420.0, "end_sec": 21600, "wall_sec": 14.899428600008832, "people_states": {"not_ready": 11299, "admitted": 60, "travelling": 180, "waiting": 45, "no_route": 46, "assigned": 4, "boundary_exit": 285, "walk_limit": 9, "no_origin_connection": 28, "initial_or_current_closed": 9}, "active_vehicles": 76, "counts": {"steps": 840, "controller_ticks": 421, "snapshots": 8, "teleports": 0, "collisions": 0, "transition_rows": 10665, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 43, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R1 seed42採用・R2開始監査（2026-10-16T19:30:53.380978+09:00）

R1 seed42は独立validateとrecord内再検証がPASS、新系列5/15正式記録。人物11965・道路観測19197258行・候補303860行・遷移261853行、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。警告分類={"depart_position_fallback": 2}、原文/対象人物/道路はcompletion_monitor.jsonとmonitoringへ保全。閉鎖3時計・phaseは全13665件一致、最大0.5秒先行を維持。全5採用ID×6ファイルの実在・台帳5件一意・共通4SHAを確認後、status次R2 seed42・preflight READYを経て19:30:33 JSTにrtbb2_core_r2_seed42_20261016T193033を1セル開始。前回現在地と全採用IDを文書補助で保持し、更新後も6ファイルを再確認する。旧8記録は新台帳/主比較に混ぜず、全5seed前の方向解釈なし。外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:31:02.369206+09:00）

新境界整合B realtime_b_boundary_v2：5/15正式記録。R1 seed42 `rtbb2_core_r1_seed42_20261016T191543`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed42 `rtbb2_core_r2_seed42_20261016T193033`を2026-10-16T19:30:35.177397+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed42：2026-10-16T19:21:42.441230+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出137は別計上。道路観測19197258行・遷移261853・候補303860。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 261853, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 303860, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告2件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=24808、check={"run_id": "rtbb2_core_r2_seed42_20261016T193033", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:31:05.381143+09:00", "run_id": "rtbb2_core_r2_seed42_20261016T193033", "time_sec": 300.0, "end_sec": 21600, "wall_sec": 14.903746399999363, "people_states": {"not_ready": 11488, "admitted": 28, "travelling": 194, "waiting": 31, "no_route": 37, "assigned": 4, "boundary_exit": 158, "walk_limit": 6, "no_origin_connection": 16, "initial_or_current_closed": 3}, "active_vehicles": 85, "counts": {"steps": 600, "controller_ticks": 301, "snapshots": 6, "teleports": 0, "collisions": 0, "transition_rows": 7245, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 43, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R2 seed42採用・次seed開始監査（2026-10-16T19:46:00.498602+09:00）

R2 seed42は独立validateとrecord内再検証PASS、新系列6/15正式記録、最初の2seedの全3条件が採用済み。人物11965・道路観測19197258行・候補637681行・遷移256052、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。警告分類={"depart_position_fallback": 2, "stop_abort": 1}。DRT b_drt_3が4199.5秒に閉鎖道路3915#9上で除去され、4174秒から乗車処理中の割当対象Type4 1人はstranded_drt、分母保持・施設受入/退出には加算なし。原文/人物/request/vehicle/eventをcompletion_monitor.jsonとmonitoringへ保全。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。全6採用ID×6ファイル実在・台帳6件一意・共通4SHAを確認後、status次R0 seed1・preflight READYを経て19:45:41 JSTにrtbb2_core_r0_seed1_20261016T194541を1セル開始。全5seed前に方式の方向解釈なし、旧8/失敗/fixture混在なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:46:32.904715+09:00）

新境界整合B realtime_b_boundary_v2：6/15正式記録。R2 seed42 `rtbb2_core_r2_seed42_20261016T193033`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed1 `rtbb2_core_r0_seed1_20261016T194541`を2026-10-16T19:45:43.695126+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed42：2026-10-16T19:36:45.706704+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出101は別計上。道路観測19197258行・遷移256052・候補637681。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 256052, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 637681, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告3件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=15632、check={"run_id": "rtbb2_core_r0_seed1_20261016T194541", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:46:35.602416+09:00", "run_id": "rtbb2_core_r0_seed1_20261016T194541", "time_sec": 960.0, "end_sec": 21600, "wall_sec": 32.39618250000058, "people_states": {"not_ready": 10319, "admitted": 263, "no_origin_connection": 78, "travelling": 335, "no_route": 81, "boundary_exit": 793, "walk_limit": 63, "initial_or_current_closed": 33}, "active_vehicles": 101, "counts": {"steps": 1920, "controller_ticks": 961, "snapshots": 17, "teleports": 0, "collisions": 0, "transition_rows": 30492, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R0 seed1採用・R1開始監査（2026-10-16T20:01:00.012082+09:00）

R0 seed1は独立validateとrecord内再検証PASS、新系列7/15正式記録。人物11965・道路観測19197258行・候補0行・遷移268419、警告/Error/閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損0。閉鎖全13665件（初期6172、評価末尾73）の3時計/phaseを照合、最大0.5秒先行を明示。全7採用ID×6ファイル実在・台帳7件一意・共通4SHAを確認後、status次R1 seed1・preflight READYを経て20:00:38 JSTにrtbb2_core_r1_seed1_20261016T200038を1セル開始。前回現在地/採用履歴を保持して文書同期、更新後も6ファイルを再確認する。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:01:09.321578+09:00）

新境界整合B realtime_b_boundary_v2：7/15正式記録。R0 seed1 `rtbb2_core_r0_seed1_20261016T194541`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed1 `rtbb2_core_r1_seed1_20261016T200038`を2026-10-16T20:00:41.182660+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed1：2026-10-16T19:51:53.720398+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移268419・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 268419, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=23688、check={"run_id": "rtbb2_core_r1_seed1_20261016T200038", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:01:16.814214+09:00", "run_id": "rtbb2_core_r1_seed1_20261016T200038", "time_sec": 480.0, "end_sec": 21600, "wall_sec": 21.82809749999433, "people_states": {"not_ready": 11168, "travelling": 242, "no_origin_connection": 39, "admitted": 123, "assigned": 4, "no_route": 38, "waiting": 48, "boundary_exit": 269, "walk_limit": 14, "initial_or_current_closed": 20}, "active_vehicles": 103, "counts": {"steps": 960, "controller_ticks": 481, "snapshots": 9, "teleports": 0, "collisions": 0, "transition_rows": 13036, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 163, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R1 seed1採用・最終人物会計とR2開始監査（2026-10-16T20:16:04.709264+09:00）

R1 seed1は独立validateとrecord内再検証PASS、新系列8/15正式記録。人物11965・道路観測19197258行・候補293919行・遷移259227、警告/Error/閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損0。最後のprogressには待機732・乗車中1・割当1が残るが、一次person_results.csvと最終manifestではtime_limit734へ確定して一致、未受入/未退出のまま全人物分母へ保持する。b_drt_1は2399.5秒にroute_cutで除去され、割当対象Type4 1人がstranded_drt。event/request/person/vehicle照合をcompletion_monitor.jsonへ保存。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。全8採用ID×6ファイル実在・台帳8件一意・共通4SHAを確認後、status次R2 seed1・preflight READYを経て20:15:45 JSTにrtbb2_core_r2_seed1_20261016T201545を1セル開始。旧B8記録とは別系列であり混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:16:12.692985+09:00）

新境界整合B realtime_b_boundary_v2：8/15正式記録。R1 seed1 `rtbb2_core_r1_seed1_20261016T200038`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed1 `rtbb2_core_r2_seed1_20261016T201545`を2026-10-16T20:15:48.184318+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed1：2026-10-16T20:06:30.644742+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出131は別計上。道路観測19197258行・遷移259227・候補293919。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 259227, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 293919, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=12704、check={"run_id": "rtbb2_core_r2_seed1_20261016T201545", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:16:15.605715+09:00", "run_id": "rtbb2_core_r2_seed1_20261016T201545", "time_sec": 240.0, "end_sec": 21600, "wall_sec": 11.385691999996197, "people_states": {"not_ready": 11590, "no_origin_connection": 19, "admitted": 34, "assigned": 4, "travelling": 184, "no_route": 23, "boundary_exit": 75, "waiting": 17, "walk_limit": 6, "initial_or_current_closed": 13}, "active_vehicles": 81, "counts": {"steps": 480, "controller_ticks": 241, "snapshots": 5, "teleports": 0, "collisions": 0, "transition_rows": 4253, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 163, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R2 seed1採用・次seed開始監査（2026-10-16T20:30:47.083135+09:00）

R2 seed1は独立validateとrecord内再検証PASS、新系列9/15正式記録、seed23423/42/1の全3条件が採用済み。人物11965・道路観測19197258行・候補450390行・遷移255415、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。警告分類={"stop_abort": 1, "emergency_braking": 1}。b_drt_1が2399.5秒route_cut、b_drt_2が4199.5秒の現道路3915#9閉鎖で除去され、各割当対象Type4 1人ずつがstranded_drt。後者は4145秒から乗車処理中でpickup未完了。2人とも分母保持、施設受入/退出には加算しない。一次CSVのtime_limit775と最終manifest会計も一致。対象人物/request/vehicle/eventと原警告をcompletion_monitor.jsonへ保全。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。全9採用ID×6ファイル実在・台帳9件一意・共通4SHAを確認後、status次R0 seed7・preflight READYを経て20:30:31 JSTにrtbb2_core_r0_seed7_20261016T203031を1セル開始。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:31:22.012428+09:00）

新境界整合B realtime_b_boundary_v2：9/15正式記録。R2 seed1 `rtbb2_core_r2_seed1_20261016T201545`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed7 `rtbb2_core_r0_seed7_20261016T203031`を2026-10-16T20:30:33.429765+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed1：2026-10-16T20:21:51.034447+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出102は別計上。道路観測19197258行・遷移255415・候補450390。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 255415, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 450390, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告2件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=7988、check={"run_id": "rtbb2_core_r0_seed7_20261016T203031", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:31:23.993266+09:00", "run_id": "rtbb2_core_r0_seed7_20261016T203031", "time_sec": 900.0, "end_sec": 21600, "wall_sec": 34.814884100007475, "people_states": {"not_ready": 10559, "no_route": 79, "no_origin_connection": 48, "travelling": 293, "admitted": 183, "boundary_exit": 724, "walk_limit": 46, "initial_or_current_closed": 33}, "active_vehicles": 94, "counts": {"steps": 1800, "controller_ticks": 901, "snapshots": 16, "teleports": 0, "collisions": 0, "transition_rows": 26996, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R0 seed7採用・R1開始監査（2026-10-16T20:45:58.147760+09:00）

R0 seed7は独立validateとrecord内再検証PASS、新系列10/15正式記録。人物11965・道路観測19197258行・候補0行・遷移268506、警告/Error/閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損0。一次person_results.csvの終了状態会計と最終manifestが一致。閉鎖全13665件（初期6172・評価末尾73）の3時計/phase一致、最大0.5秒先行を明示。全10採用ID×6ファイル実在・台帳10件一意・共通4SHAを確認後、status次R1 seed7・preflight READYを経て20:45:41 JSTにrtbb2_core_r1_seed7_20261016T204541を1セル開始。前回現在地/採用履歴を保持して文書同期、更新後も6ファイルを再確認する。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:46:05.952610+09:00）

新境界整合B realtime_b_boundary_v2：10/15正式記録。R0 seed7 `rtbb2_core_r0_seed7_20261016T203031`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed7 `rtbb2_core_r1_seed7_20261016T204541`を2026-10-16T20:45:43.693994+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed7：2026-10-16T20:37:11.685513+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移268506・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 268506, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=19504、check={"run_id": "rtbb2_core_r1_seed7_20261016T204541", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:46:09.902841+09:00", "run_id": "rtbb2_core_r1_seed7_20261016T204541", "time_sec": 480.0, "end_sec": 21600, "wall_sec": 14.737934500008123, "people_states": {"not_ready": 11193, "no_route": 22, "no_origin_connection": 35, "travelling": 231, "admitted": 94, "waiting": 49, "boundary_exit": 313, "onboard": 2, "walk_limit": 13, "assigned": 2, "initial_or_current_closed": 11}, "active_vehicles": 93, "counts": {"steps": 960, "controller_ticks": 481, "snapshots": 9, "teleports": 0, "collisions": 0, "transition_rows": 13639, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 50, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R1 seed7採用・R2開始監査（2026-10-16T21:01:03.266327+09:00）

R1 seed7は独立validateとrecord内再検証PASS、新系列11/15正式記録。人物11965・道路観測19197258行・候補305015行・遷移262110、警告/Error/閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損0。最後のprogressの待機702・乗車中1・割当2は一次person_results.csvでtime_limit705へ確定し、最終manifestと一致、施設受入/退出へ補完しない。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。全11採用ID×6ファイル実在・台帳11件一意・共通4SHAを確認後、status次R2 seed7・preflight READYを経て21:00:45 JSTにrtbb2_core_r2_seed7_20261016T210045を1セル開始。前回現在地/採用履歴を保持して文書同期、更新後も6ファイルを再確認する。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T21:01:30.618515+09:00）

新境界整合B realtime_b_boundary_v2：11/15正式記録。R1 seed7 `rtbb2_core_r1_seed7_20261016T204541`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed7 `rtbb2_core_r2_seed7_20261016T210045`を2026-10-16T21:00:48.558798+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed7：2026-10-16T20:51:30.985740+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出135は別計上。道路観測19197258行・遷移262110・候補305015。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 262110, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 305015, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=17144、check={"run_id": "rtbb2_core_r2_seed7_20261016T210045", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T21:01:33.205953+09:00", "run_id": "rtbb2_core_r2_seed7_20261016T210045", "time_sec": 840.0, "end_sec": 21600, "wall_sec": 29.70029059999797, "people_states": {"not_ready": 10653, "no_route": 53, "no_origin_connection": 48, "travelling": 240, "admitted": 168, "waiting": 78, "boundary_exit": 669, "walk_limit": 25, "assigned": 2, "onboard": 2, "initial_or_current_closed": 27}, "active_vehicles": 93, "counts": {"steps": 1680, "controller_ticks": 841, "snapshots": 15, "teleports": 0, "collisions": 0, "transition_rows": 24985, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 283, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R2 seed7採用・最終seed開始監査（2026-10-16T21:16:02.848225+09:00）

R2 seed7は独立validateとrecord内再検証PASS、新系列12/15正式記録、seed23423/42/1/7の全3条件採用済み。人物11965・道路観測19197258行・候補828313行・遷移255986、警告/Error/閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損0。一次CSVのtime_limit764と最終manifest会計が一致、未受入/未退出のまま全人物分母保持。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。全12採用ID×6ファイル実在・台帳12件一意・共通4SHAを確認後、status次R0 seed101・preflight READYを経て21:15:44 JSTにrtbb2_core_r0_seed101_20261016T211544を1セル開始。残りは同seed内R0→R1→R2。前回現在地/採用履歴を保持して文書同期、更新後も6ファイルを再確認する。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T21:16:11.026302+09:00）

新境界整合B realtime_b_boundary_v2：12/15正式記録。R2 seed7 `rtbb2_core_r2_seed7_20261016T210045`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed101 `rtbb2_core_r0_seed101_20261016T211544`を2026-10-16T21:15:47.193948+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed7：2026-10-16T21:07:01.897357+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出99は別計上。道路観測19197258行・遷移255986・候補828313。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 255986, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 828313, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=23544、check={"run_id": "rtbb2_core_r0_seed101_20261016T211544", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T21:16:14.915336+09:00", "run_id": "rtbb2_core_r0_seed101_20261016T211544", "time_sec": 420.0, "end_sec": 21600, "wall_sec": 14.582149900001241, "people_states": {"not_ready": 11235, "travelling": 261, "no_origin_connection": 32, "admitted": 88, "no_route": 48, "boundary_exit": 264, "walk_limit": 24, "initial_or_current_closed": 13}, "active_vehicles": 94, "counts": {"steps": 840, "controller_ticks": 421, "snapshots": 8, "teleports": 0, "collisions": 0, "transition_rows": 11414, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 監視記録空白と再開（2026-10-16T23:13:59.466321+09:00）

21:29頃のR0 seed101独立validate PASS後、23:13再読込までrecord/start/checkの実行ログがない。21:43〜23:13のheartbeat到着を監視実施とみなさない。R0は21:21完了、12正式記録・完了未記録1・実行中0で停止していた。途中監視の時刻・sim進捗を遡って創作しない。最新CLI status/checkを実測して未記録R0から記録を再開する。外部送信・Drive編集なし。


### R0 seed101採用・監視再開後のR1開始（2026-10-16T23:16:14.699523+09:00）

R0 seed101は21:29頃の独立validate PASS後、23:13再開時点でも未記録だったため、専用record内で改めて一次成果物を再検証PASS、新系列13/15正式記録。人物11965・道路観測19197258行・候補0行・遷移268186、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。警告分類={"emergency_braking": 1, "depart_position_fallback": 1}。急減速1件・歩行開始位置補正1件の原文/対象/時刻はcompletion_monitor.jsonへ保全。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。21:29〜23:13の監視ログ空白は別節/monitoring_gap_20261016T2313_resume.jsonに明記し、到着heartbeatから実施記録を創作しない。全13採用ID×6ファイル実在・台帳13件一意・共通4SHAを確認後、status次R1 seed101・preflight READYを経て23:15:53 JSTにrtbb2_core_r1_seed101_20261016T231553を1セル開始。残りR1/R2の2セル。前回現在地/採用履歴を保持して文書同期、更新後も6ファイルを再確認する。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T23:16:22.383356+09:00）

新境界整合B realtime_b_boundary_v2：13/15正式記録。R0 seed101 `rtbb2_core_r0_seed101_20261016T211544`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed101 `rtbb2_core_r1_seed101_20261016T231553`を2026-10-16T23:15:55.867923+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed101：2026-10-16T21:21:52.313481+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移268186・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 268186, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告2件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=27156、check={"run_id": "rtbb2_core_r1_seed101_20261016T231553", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T23:16:23.720175+09:00", "run_id": "rtbb2_core_r1_seed101_20261016T231553", "time_sec": 600.0, "end_sec": 21600, "wall_sec": 14.825555500006885, "people_states": {"not_ready": 10946, "admitted": 140, "no_origin_connection": 42, "travelling": 231, "waiting": 57, "no_route": 50, "boundary_exit": 452, "onboard": 3, "walk_limit": 19, "initial_or_current_closed": 24, "assigned": 1}, "active_vehicles": 91, "counts": {"steps": 1200, "controller_ticks": 601, "snapshots": 11, "teleports": 0, "collisions": 0, "transition_rows": 17691, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 80, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### R1 seed101採用・最終セル開始監査（2026-10-16T23:31:00.322390+09:00）

R1 seed101は独立validateとrecord内再検証PASS、新系列14/15正式記録。人物11965・道路観測19197258行・候補325962行・遷移260095、警告/Error/閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損0。最後のprogressの待機710・乗車中1・割当2は一次person_results.csvでtime_limit713へ確定し、最終manifest会計と一致、施設受入/退出へ補完なし。閉鎖全13665件の3時計/phase一致、最大0.5秒先行を明示。全14採用ID×6ファイル実在・台帳14件一意・共通4SHAを確認後、status次R2 seed101・preflight READYを経て23:30:34 JSTにrtbb2_core_r2_seed101_20261016T233034を1セル開始。これが登録15セルの最後で、終了後validate PASS→record→全15件同期/一意/共通SHA確認→現在地/独立一覧・事前登録比較タスク記録→監視PAUSEDの順を守る。旧8/失敗/fixture混在なし、全5seed前の方向解釈なし、外部送信・Drive編集なし。


### 境界整合監視・正式記録と次セル開始（2026-10-16T23:31:07.386664+09:00）

新境界整合B realtime_b_boundary_v2：14/15正式記録。R1 seed101 `rtbb2_core_r1_seed101_20261016T231553`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed101 `rtbb2_core_r2_seed101_20261016T233034`を2026-10-16T23:30:36.636762+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed101：2026-10-16T23:21:32.197044+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出139は別計上。道路観測19197258行・遷移260095・候補325962。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 260095, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 325962, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=10384、check={"run_id": "rtbb2_core_r2_seed101_20261016T233034", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T23:31:08.908772+09:00", "run_id": "rtbb2_core_r2_seed101_20261016T233034", "time_sec": 900.0, "end_sec": 21600, "wall_sec": 20.706949500003248, "people_states": {"not_ready": 10451, "admitted": 229, "no_origin_connection": 71, "waiting": 91, "travelling": 219, "no_route": 86, "assigned": 3, "boundary_exit": 748, "walk_limit": 34, "initial_or_current_closed": 32, "onboard": 1}, "active_vehicles": 83, "counts": {"steps": 1800, "controller_ticks": 901, "snapshots": 16, "teleports": 0, "collisions": 0, "transition_rows": 27184, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 331, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合全15セル完了・次の方針（2026-10-16T23:51:46.375409+09:00）

新境界整合B realtime_b_boundary_v2：15/15正式記録完了。実行中0・未記録0・次セルなし。全15セル独立PASS・6ファイル実在・新台帳一意・共通4実装SHAを確認。一次人物CSVから独立一覧/seed内主指標記述表を生成、全成果物SHAを再照合。旧B8/失敗/fixtureは分離保全。閉鎖予定T・実呼出しmax(0,T−0.5)・観測上限Tの区別と最大0.5秒先行は維持。次は完了後分析タスクBA-02の副指標集計→時間/候補/道路監査→資料取得監査。追加run/方法変更は行わない。監視PAUSED（停止確認済み）。外部送信・Drive編集なし。

独立一覧：`06_研究結果/jdrt/realtime_b_boundary_v2/全セル結果一覧.html`。一次人物CSVから主指標/終了会計、車両CSVとtripinfoから距離を再計数し、正式validation/台帳と一致。全出力SHA再照合、根拠249ファイル。全道路CSVの全行検証を一覧生成時に再反復したとは記載しない。主指標のseed内記述比較までで、副指標/取得監査の完了を先取りしない。次の方針とBA-01〜06の担当役割・入力・成果物・依存/完了条件は`05_タスク管理/jdrt/JDRT-実時間B境界整合_完了後分析タスク.md`。追加runせず既登録集計と不足資料棚卸しを進める。

最終R2 seed101は23:36:24頃に終了、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。Type3人物の開始位置補正警告1件を原ログ/monitoringへ保持。time_limit765は未受入/未退出のまま分母保持。全15件で共通実装と退出別計上を維持。一覧生成初回は空欄車両距離の数値変換で出力前に停止し、旧試行ソースを保全。空欄はtripinfo欠落かつ観測距離0を照合し、修正後は一次CSV/tripinfo/validationの全15距離一致。21:29頃〜23:13等の監視ログ空白とcontext同期補修も消さず監査へ残した。


### 監視停止の実確認（2026-10-16T23:53:20.635716+09:00）

全15セル正式記録・実行中0・未記録0・次セルなしを確認し、既存jdrt-b-15をautomation_updateでPAUSEDへ更新。保存設定のstatus=PAUSEDを再読込して確認した。新しい監視/別chat/外部送信/Drive編集はなし。次の1件は完了後分析タスクBA-02。


### 2026-10-17T00:12:15.424555+09:00 完了後分析開始

ユーザー「同じように次の方針を進めて」によりBA-02〜06を同chatで順次実施。新15セルのみを用い、追加run/設定変更/Drive編集/外部送信なし。statusで15正式記録・実行中0・未記録0を確認。Driveのデータ分析と下位フォルダ計5文書を読取、証跡をpostanalysis_20261017へ保存。集計と検証の詳細は同フォルダoperations.jsonlへ記録する。


### 2026-10-17T00:25:44.596567+09:00 境界整合B 完了後監査・次段方針

新境界整合Bは15/15正式記録済み。BA-02〜06の副指標・時間・候補・道路・取得監査と方針整理を完了。道路287,958,870行・候補5,270,448行を全読取し、全人物会計・時刻・選択候補/配車event・3時計・遷移を照合。Type4の固定終点・施設空き・拠点接続を診断。次はNP-02/03の災害時供給/需要・路面高/施設条件の不足資料整理。追加run・方法変更は未採用、監視PAUSED。Driveは5文書読取のみ、外部送信なし。

Type4施設受入の対応seed人数差：{"R1−R0": [1, 1, 0, 0, 0], "R2−R1": [0, 0, 0, 0, 0]}。退出・時間切れ・配車結果を別表示し、一般的有効性/無効性へ一般化しない。待ち/所要は観測件数と未完了状態を併記。初期拠点診断は登録入力の技術診断。単純な増車/再割当やGate変更を採用せず、供給/需要・路面高/施設条件の根拠整理を優先する。

新成果物：`06_研究結果/jdrt/realtime_b_boundary_v2/postanalysis_20261017/`。道路全キー一意、0台速度空欄、人物/施設/event会計、選択候補と配車集合、3時計・遷移を独立照合。初回分類名の誤指定と非有限値の扱いで後処理が2回停止、ログと当時コード/途中出力を保全して修正。研究run失敗ではない。Drive2フォルダ5本文を読取、市通常運行案内をHTTP200再取得。災害時実測不足は未解消。外部送信/Drive編集/新runなし。詳細コマンド・時刻・チェックポイントはoperations.jsonl、コードとSHAは生成根拠。
