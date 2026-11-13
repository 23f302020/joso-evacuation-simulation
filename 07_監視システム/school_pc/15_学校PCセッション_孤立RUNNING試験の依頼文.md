# 学校PCセッションへの依頼文：孤立した RUNNING の実機試験（人工の対象のみ）

> 設計：Opus 5.5（effort high）の設計＋別の Opus 5.5（effort high）の独立レビューを反映（2026-11-13）。研究 run は使わない。
> 前提：学校PCは `git pull --ff-only` で本リポジトリの最新を取り込み済み（`git status` に、(b)(c) 以外の変更がない）。

## 目的と、確かめないこと

- 目的：監視が、**止まった対象（process が消えた RUNNING）を、停止・再起動をまたいで検知し、保全・通知する**ことを、人工の対象で実機確認する。単体試験で確認済みの部分は繰り返さない。実機でしか確認できないのは、(G1)実体プロセスだけを止めたときの救済起動、(G2)**監視の起動時に、残っていた RUNNING を孤立として検出する経路（単体試験にもない）**、(G3)実際の PID・作成時刻の照合、(G4)イベント→ワーカー→Gmail→受信箱の全経路。
- 確かめない・主張しないこと：強制再起動のあとに誰もサインインしない場合、PID の再利用、実際の研究 run の連なり（親ループ→core→sumo）、スリープ、自動復旧（自動の再実行・kill はしない仕様）。

## 守ること

- 研究 run・READY・start-next・validate・record・親ループの `run` は実行しない。`runs\`・`smoke\`・`technical\`・`driver_logs\` には何も作らない。
- 秘密情報（`smtp_secret.bin` など）とメールアドレスの値は、読まない・表示しない。
- `state.json`・`events`・`outbox` を手で編集・削除しない。タスクの登録解除をしない。
- kill する前に、**必ず CommandLine に対象の id が入っていること**を確認する（`Get-CimInstance Win32_Process`）。
- **対象は、シナリオごとに別の id・別のフォルダにする。** イベントは「パス＋種類」で重複が抑止されるため、使い回すと試験が成り立たない。
- 記録は `school_pc_local\livetest_<日付>\` に保存する（git の管理外）。git が管理するファイルは編集しない。
- 人工の対象は、`/runs/` を含まないパスに置き、purpose を `core` にしない（`all_complete` に数えられない）。

## 前提条件（満たさないなら中止）

1. 研究のセルが実行中・未記録でない（監視の停止中は、研究の開始前確認が ObserverGap で止まるため）。
2. `watch.py status` で、state の RUNNING/STARTING が0件。sumo・親ループ・sequence のプロセスがない。
3. 送信キューに `auth_expired`・`failed_preserved`・`uncertain_preserved`・3回以上の再試行中が0件。
4. ユーザーの了承：**試験メールが最大で5〜6通届く**（A の process_absent、B の process_absent、後片付けの state_missing が対象ごとに1通など）。件名で試験と分かる。

## 手順

### P. 準備（Claude）
1. 前後比較の記録：`record_files`（7件）の SHA-256、`runs\`・`driver_logs\` の一覧（名前・サイズ・更新時刻）、`git status --porcelain=v1 --untracked-files=all`、`config.json` の SHA-256、`events\` と `outbox\` の id 一覧、`state.json` の対象 id 一覧。
2. 人工の対象のスクリプトを `%USERPROFILE%\.jdrt-livetest\sleeper.py` に作る（リポジトリと runtime の外）：

```python
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

root, rid = Path(sys.argv[1]), sys.argv[2]
folder = root / rid
folder.mkdir(parents=True)  # 既に存在すれば失敗する（id の使い回しを防ぐ）


def put(name, value):
    temp = folder / (name + '.tmp')
    temp.write_text(json.dumps(value), encoding='utf-8')
    os.replace(temp, folder / name)  # 書きかけを読ませない（3回連続で読めないと unreadable_state がメールされる）


started = time.time()
put('manifest.json', {'run_id': rid, 'status': 'RUNNING', 'pid': os.getpid(), 'purpose': 'monitor_live_test',
                      'research_adoption_permitted': False,
                      'started_at_utc': datetime.now(timezone.utc).isoformat()})
while time.time() - started < 7200:
    put('progress.json', {'time_sec': int(time.time() - started)})  # 増え続ける数値（これが無いと10分後に stalled がメールされる）
    time.sleep(30)
```

3. 起動は、**ベースの Python**（`py -3` の本体。venv のシムは PID が別になる）で、引数は `<python> sleeper.py <root> <id>`（id は独立した引数）。`<root>` は `%USERPROFILE%\.jdrt-livetest\targets`。

### Q. 監視の `patterns` に1件追加（Claude。ユーザーの了承を得てから）
4. `config.json` を `config.json.bak_livetest_<時刻>` に複製（`.gitignore` の `config.json*` で除外される）。`watch.atomic_json` で `<root>\*\manifest.json` を `patterns` の末尾に追加する。変わったのが `patterns` だけであることを、True/False だけで確認する（メールアドレスの値は表示しない）。
5. 監視を再起動する（設定は起動時に1回しか読まれない）：`Disable-ScheduledTask` → `Stop-ScheduledTask` → `watch.py status` の `monitor_process` が absent になるまで待つ（残っていたら、CommandLine が `watch.py … run` であることを確かめてからその PID だけ止める）→ `Enable-ScheduledTask` → `Start-ScheduledTask`。最後に **タスクが Enabled に戻ったこと**を確認する。
   - 合格：新しい PID、`monitor_identity_matches=true`、観測から20秒以内、新しいイベント0件。

### A. 監視が動いている間に、対象を止める（Claude）
6. id `jdrtlive-<日付>-a` を起動する。20秒以上あけた次の呼び出しで、生存と、state の該当エントリ（status RUNNING、process が alive、`process.created` が `(Get-Process -Id <pid>).StartTime.ToFileTimeUtc()` と一致、flags が空）を確認する。progress が進んでいること（`state.json` の該当エントリの progress の項目が、40秒あけた2回の読取で変わっていること）を確認する。
   - Claude のツールのプロセスと一緒に終了していたら、ユーザーが自分の PowerShell で起動する。
7. CommandLine に `jdrtlive-<日付>-a` が入っていることを確認して、`Stop-Process`。
8. **合格条件**
   - 15秒以内に新しいイベントが**1件だけ**：kind=`process_absent`、`evidence.target_id`=a。
   - 2分以内に outbox が `accepted`。ユーザーが、件名 `[JDRT監視] process_absent jdrtlive-<日付>-a` のメールを**ちょうど1通**受け取る。
   - 想定外の種類が0件：`stalled`・`process_identity_changed`・`process_command_mismatch`・`unreadable_state`。既存イベントの `at_utc` が変わっていない。
   - 3分待って、a の id を持つプロセスが0件（CIM）、manifest の SHA が変わらない（自動で再実行も削除もしない）。
9. **10分以内に**、a の manifest の `status` を `LIVE_TEST_ENDED` に書き換える（原子的に）。期待：`unknown_status` が1件（ローカルのトーストだけ。メールは出ない）。

### B. 監視の停止・救済起動と、起動時の孤立検出（Claude）
10. id `jdrtlive-<日付>-b` を起動して、手順6と同じ確認をする。
11. **（G1）** `state.json` の `monitor_pid` が実体の Python であることを（CommandLine に `watch.py` と `run`）確認して、その PID だけ止める。タスクは有効のまま。
    - 合格：kill の後に、タスクの状態が Ready になり、起動シムの PID が消えたことを確認してから、3分以内に新しい PID で復帰し、本人確認が一致する。b は同じ PID・同じ作成時刻のまま生きていて、新しいイベントがない（`monitoring_gap` が1件出るのは許容。メールは出ない）。
    - 3分を超えたら FAIL。タスクの状態と PID を記録してから、Stop→Start で戻す。
12. **（G2）** 監視を止める（Disable→Stop→absent を確認）。**止まったことを確認してから10秒以内に** b を止める（CommandLine を確認）。監視を Enable→Start する。
    - 合格：復帰後15秒以内に、b について `process_absent` が1件、メールが1通（件名 `[JDRT監視] process_absent jdrtlive-<日付>-b`）。`monitoring_gap` は許容。a には新しいイベントがない。想定外の種類が0件。
13. 監視をもう一度止めて、救済起動させる。合格：`process_absent` も新しいメールも増えない（`monitoring_gap` だけは増えてよい）。
14. 10分以内に b を `LIVE_TEST_ENDED` にする。

### C.（任意）再起動をまたぐ
15. ユーザーが選んだときだけ。夜間・無人では行わない。まず報告を途中まで保存する（再起動で Claude のセッションも終わる）。A と B の終端化（手順9・14）が済んでいることが前提。id `jdrtlive-<日付>-c` を起動して確認し、ユーザーが再起動（または、サインアウトで代用）する。サインインして3分待ち、新しいセッションで確認する。
    - 合格：両タスクが新しい PID で動いている。c について孤立系のイベントが**1件**、メールが1通。種類は `process_absent`（PID が再利用された場合は `process_identity_changed` か `process_unknown` になり得るので、どれだったか記録する）。停止が10分を超えた場合は `stalled` が1件増えるのを許容。a・b に新しいイベントとメールがない。最後に c も `LIVE_TEST_ENDED` にする。

### K. 後片付けと、元に戻したことの確認（Claude）
16. **削除の前に**：state 上の試験の対象が、すべて `LIVE_TEST_ENDED` になっていること（`state.json` の status）と、それぞれに `unknown_status` のイベントがあることを確認する。**満たさないまま、フォルダを削除してはいけない**（最後に観測された状態が RUNNING のままのフォルダが消えると、その対象が永久に「実行中」扱いになり、`all_complete` が永久に出なくなる。直すには `state.json` の手編集しかない）。
17. 各対象のフォルダを削除する。対象ごとに `state_missing` のメールが1通届く（件名は id ではなく、**manifest のフルパス**になる：`[JDRT監視] state_missing <…\manifest.json>`）。
18. 監視の `patterns` を戻す：Disable→Stop→absent を確認→`config.json.bak_livetest_<時刻>` を**バイト単位でそのまま**コピーして戻す→SHA-256 が手順P1 と一致することを確認→バックアップを削除→Enable→Start。**Enabled に戻り、新しい PID で動いていること**を確認する。
19. `%USERPROFILE%\.jdrt-livetest` を削除する。
20. **終了の条件**：送信キューが、試験の通知を含めて**すべて `accepted`**（`failed_preserved`・`auth_expired`・3回以上の再試行が残ると、親ループの起動前確認が止まる）。
21. 前後比較：`record_files`・`runs\`・`driver_logs\`・`git status`・`config.json` が、手順P1 と一致する。`events\`・`outbox\`・`state.json` は差分が出て当然なので、**その差分が、予定した id だけ**であることを確認する。親ループの `preflight`（読取のみ）で、`monitor` と `mail_path` が ok であることを確認する。

## 報告（Claude）
`school_pc_local\reports\学校PC_孤立RUNNING試験_<日付>.md` に、「学校PCで確認済み／未確認／未実施」に分けて書く。シナリオごとに、時刻・PID・イベントの種類と件数・受け取ったメールの件名と通数・合否を書く。受け取ったメールの本文は、ユーザーが開発PCのセッションに貼る。不合格・想定外はそのまま書き、原因を推測で断定しない。C を行わなかったときは「未実施」とする。

## 開発PC側の記録（参考）
- 単体試験の網羅表：孤立判定、PID 再利用と3秒の猶予、実際の OpenProcess、イベントの重複防止、メールを送る種類は確認済み。**未確認の穴**は、監視の起動時に残っていた RUNNING を孤立として検出する経路（watch.py 661-691・407-413）と、実際のイベントからメールまでの全経路。
- 判断行（曖昧さの3点）：(1) 対象の置き場所：リポジトリ外に置き、`patterns` を一時的に足す（研究の作業フォルダに書かず、別の config・runtime での監視を作らない）。(2) 終端化：独自の `LIVE_TEST_ENDED`（成功とも失敗とも主張せず、メールも出ない）にしてから削除する（`state.json` の手編集を避ける）。代償は、`state_missing` のメールが数通届くこと。(3) 監視の停止の模擬：実体プロセスの kill（異常終了と救済起動を再現）。