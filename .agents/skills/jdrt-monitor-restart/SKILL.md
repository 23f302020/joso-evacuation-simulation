---
name: jdrt-monitor-restart
description: 独立監視 JDRT-SimulationWatch を、ソース更新後に安全に再起動して反映を確かめる手順。watch.py や mail_outbox 等を変更した後、稼働中の監視が旧ソースのままのときに使う。再起動は稼働中の監視を変える操作なので、ユーザーの指示があるときだけ行う。
---

# jdrt-monitor-restart

稼働中の監視プロセスは起動時に読み込んだソースのまま動く。`watch.py` などを変更しても、再起動するまで反映されない。**反映済みと主張する前に、再起動して新しいソースSHAを確かめる。**

## いつ使うか
- 監視のソース（`07_監視システム/*.py`）を変更し、稼働中の監視に反映したいとき。
- 再起動は稼働中の監視と通知を一時的に止める（空白が生じる）。ユーザーが指示したときだけ行う。実行中のrunがあるときは、空白が出ることを先に伝える。

## 手順
1. **現状を記録する**：`04_プログラム\venv\Scripts\python.exe 07_監視システム\watch.py status` を実行し、`monitor_process.pid`・作成FILETIME・`last_observed` を控える。
2. **旧プロセスを止める**：`Stop-ScheduledTask -TaskName JDRT-SimulationWatch`。旧PIDが存在しないことを確認する（`Get-Process -Id <旧PID>` がエラーになること）。タスクには1分ごとの救済トリガがあるため、止めた後1分以内に自動で再起動されうる。それでよい（新ソースで起動する）。
3. **起動する**：`Start-ScheduledTask -TaskName JDRT-SimulationWatch`（または救済トリガを最大1分待つ）。多重起動は IgnoreNew と排他ロックで防がれる。再登録が必要なときだけ `07_監視システム\install.ps1` を実行する（`config.json` が必須）。
4. **反映を確かめる**（すべて満たすこと）：
   - `watch.py status` の `monitor_process.pid` が旧PIDと異なり、`monitor_identity_matches` が `true`。
   - `observation_age_sec` が小さい（目安：サンプル間隔の数倍以内）。
   - `runtime\state.json` の `monitor_source_sha256` が、ディスク上の `watch.py` のSHA-256と一致する（`Get-FileHash`）。
   - `python -m unittest test_watch test_ai_less test_mail_outbox test_mail_wiring test_graph_mail` が全件PASS（ディスク上のソースに対して）。
5. **記録する**：旧PID・新PID・作成時刻・新ソースSHA・空白の長さを、該当の進捗文書に書く。既存のイベントファイルは改変・再送しない。

## 注意
- 研究run・`config.json` の研究パラメータには触れない。
- 再起動後に `monitoring_gap` イベントが出ることがある（空白が60秒を超え、実行中の対象があった場合）。通常の挙動として記録する。
- 反映を確かめずに「反映済み」と報告しない。確かめていないときは「稼働中は旧ソース」と書く。
- `watch.py run` のプロセスが2つ見えるのは正常：venv の `pythonw.exe`（ランチャー）が実インタプリタ（`...\Python313\pythonw.exe`）を子として起動する。`state.json` の `monitor_pid` が実インタプリタ。二重起動かどうかは、親子関係（CIMの ParentProcessId）で確認する。
- 再起動の前に、`events` に配送が `pending` のものが無いことを確認する（稼働中の config が AI 診断ありの場合、再起動後に診断が始まる）。
