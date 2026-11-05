# sq26103005：CIM照会失敗による運転補助の停止と同じcoreの継続

判断ID：JD-20261030-sequence-cim-discovery。担当はこのchat。選択モデル・推論設定を維持し、実backendの独立確認はしていない。承認範囲は既登録70セルの運転・技術診断・独立検証・正式記録であり、研究条件や採用ゲートを変更する判断ではない。

## 確認した事実

- 元session28593はexit1。sequence `sq26103005` は22:13:11 JSTに `FAILED_PRESERVED`、理由は `Independent target discovery remains unproven`。stateと全commandログを元のdriver_logsへ保全し、このsequenceは再演・再開しない。
- 本体 `sv26103005` は22:11:49 JST開始、実PID12280・作成FILETIME134378394859035137で継続。専用monitorの22:14観測はsim1800、22:20観測はsim7260で、いずれもanomaly_flags空。これは監視時点の確認であり、独立validate PASSや採用ではない。
- 独立監視は同じPID2476・作成FILETIME134377494421633632。最初に確認した不完全な対象entryは、PID12280のCommandLineをGet-CimInstanceで取得するPowerShellの15秒timeoutだった。保存した `observer_state.json` はread_failures=2、scan終端22:14:54 JSTでも対象のmanifest SHA・run/command bindingを持たなかった。
- `choice_core_sequence.py` の `observer()` は対象のstate SHAがない場合Falseを返す。`wait_core()` の独立した発見猶予60秒が満たせず、後続を止めた。Error/衝突等の科学カウンタが原因という証拠はない。60秒の猶予や15秒の照会期限は変更していない。
- 既存watchの同じ関数による読取専用probeは、同じ本体の作成時刻と正確なrun引数を約2.3秒で確認した（`manual_process_probe_001.json`）。その後のdaemonも同じPIDの完全な対象entryを自動的に保存した。監視・本体の再起動、設定・source・入力の変更は行っていない。
- `observer_state_recovered.json` と `recovered_binding_readback.json` は、現行manifest SHA、run/purpose/protocol、同一PID・作成時刻、direct command binding、flags空、監視自身の同一性・source SHA、対象/scanの120秒以内の鮮度、sequenceの固定ソース13件を確認した。保存rawの対象観測時刻は22:18:53 JST。

## 原因・不確実性・判断

直接原因の確信度は高い：対象のCIM照会がtimeoutし、独立監視の対象bindingを猶予内に証明できなかった。CIM/PowerShellの遅延を発生させたOS内の要因は未確定であり、負荷・WMI障害等を断定しない。現時点で同じcore・監視へ戻ったことはPIDの数値だけでなく作成時刻・正確なrun引数・source/manifest SHAを照合した事実である。

開始22:11:49から保存済み完全bindingの22:18:53まで、独立監視の連続した対象確認を立証しない。後の正常観測で過去の空白を補作しない。科学一次観測の充足、時計、全人物/要求/容量会計等は、計算終了後の独立validatorで確認する。

選択は「同じcoreを既存専用monitorと07で確認し、完了後に最初の正常finish処理を1担当で行う」。既存の運転手順には、補助sequence失敗後も同じcoreを保全し別の正常finishへ進める先例がある。PAPの科学的停止・独立検証・正式記録の条件は維持する。外側sequenceの成功表示や後の観測だけで研究採用しない。

coreの再起動・failed sequenceの再演は重複となるため行わない。現在正常に読めている監視を再起動する必要も認めていない。期限を緩めて失敗を成功へ書き換える案は採用しない。失敗の分類と現在のbinding確認は、将来のcore開始を自動許可するものではない。

## 次の操作・停止条件

元sequence28593は終了済みで、現在の監視担当はこのchat。`choice_monitor.py --run-id sv26103005` と同じ07を用いる。COMPLETED、元executor不在、SHA/会計/現在の監視に不一致なしを確認後、未作成の `choice_finish_cell.py --run-id sv26103005` を最初の正常finishとして1回だけ開始する。独立PASS→専用record7→元終端の7ファイル読戻し→表示同期→fresh statusの順を維持する。

別のvalidate/record担当や未完のfinishが見つかれば待つ。科学カウンタ異常、PID作成時刻差、SHA差、再び確認不能な監視、部分記録があれば後続を止め、原本を保全して診断する。次セルはこのrunの採用・記録・診断の照合後に、実goal/READY/容量/07の開始条件を再確認する。全70・登録分析・後続大型バス・統合報告は未完。

## 保存証拠とスキル集約

`capture.json` は不完全な監視状態・失敗sequence・本体manifest/progressの実バイトSHAを保持する。元commandログはそこから示す正本に残す。`manual_process_probe_001.json`、回復後rawと独立readback、22:14/22:20の専用monitor報告を併せて用いる。スキルの既存反復手順へ、同じcoreを再演せず現在の監視bindingを再証明して最初の正常finishへ進む注意を追記する。旧参照は `routine_operations.before.md`。これは文書の集約のみで、実装・期限・採用ゲートの変更ではない。
