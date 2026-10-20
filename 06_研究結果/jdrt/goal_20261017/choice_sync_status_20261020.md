# Current display同期helperの限定更新 — 2026-10-20

既存`choice_sync_status.py`へ、隔離native buildの観測表示と限定migrationを集約した。新skillは作っていない。`skill-creator`を読み、`joso-jdrt-runner`のcurrent display手順とhelperだけを更新した。研究共通5ファイル、PAP、入力、run、台帳は変更していない。実正本のpreview/apply・native起動・正式採用・公開更新は行っていない。

## 更新理由と対象

旧helperはcheckpointのplain summaryを文書へ全件置換するため、手動更新されたsummary、タグ付きHTMLとの不一致で停止していた。BOM付きcheckpoint JSONも読めず、technical HOLDを汎用core文章へ置き換え、文書全体の再保存でBOM/EOLを変える可能性があった。

変更はhelper、新専用test、`routine_operations.md`のcurrent display節に限定した。同ファイルの他の運用節は保持した。旧helper/参照原本とSHAを[audit履歴](audit_history/choice_sync_status_20261020/before_sha256.json)へ保存した。

## 現在の動作

- `--build-observation <canonical-report>`は監視JSON、原state snapshotのfile/bytes/SHA/JSON等値、報告path、falseの正式採用/READY/後続開始gate、観測内のPID identity整合を検査する。PIDは保存されたCIM情報から再照合し、現在processへの問い合わせは行わない。
- build summaryには報告の観測時刻・attempt・status・phase・owner/child identityを表示する。古い報告もその時点のポイント観測であり、現在liveとは扱わない。terminal失敗・owner不在・childなしも表示できる。compile完成をnative回帰PASSやREADYへ拡張しない。
- reportなしの通常modeは専用controllerのcore/正式数を使い、既存technical HOLD/READY=falseを汎用core文章で消さない。登録上の次セルは開始許可と分ける。
- 最初の限定migrationは、context/Markdown冒頭summary、HTMLの専用2current asideを構造から識別し、`CHOICE_CURRENT_*` markerを設置する。以後marker内だけを編集する。HTMLは`html.escape`、Markdownはtext用escapeで別encodeする。
- current日付、HTML current見出し/header/footer日付、task CH-M1の最終表示cellだけを同期する。task冒頭やMarkdownの既存技術履歴段落、HTMLの他の履歴asideは編集しない。
- 文書はbytesのprefix/suffixを保ち、BOM、CRLF/LF/既存CRCRLF、受入marker、他の履歴を変えない。NULや曖昧markerでは停止する。checkpointはUTF-8 BOM読込に対応し、実cfgのimplementation_filesから現行SHAを算出する。
- 旧READY/audit/smoke statusはSTALE/historicalと明示し、過去PASSを現行証拠にしない。完全な旧checkpointはcontent-addressed historyへ残し、その参照を新checkpointへ保持する。その他の旧証拠値も削除しない。
- 専用writer lockと部分formal record停止を維持し、apply直前にstatus/source/evidence/document bytesを再照合する。旧bytesのarchive/readback後にatomic replacement/readbackを行い、捕捉したwrite失敗は元bytesへrollbackする。同report・同stateの再applyは文書/checkpoint/operationsとも冪等である。

複数文書全体のmachine-crash atomicityを主張しない。機械中断時はarchive/lock/各文書を確認する。正式`validate → record → status`をこのhelperで代替しない。

## 検証結果

専用14 unit PASS、2.980秒、exit0。HTML/text分離、手動summary migration、部分正式record停止、BOM/EOL/受入marker保全、旧READY降格/旧checkpoint原本、snapshot/false gate/PID拒否、同report冪等、通常core表示、terminal失敗、status変化、NUL/曖昧marker、既存writer lock/壊れたarchive拒否、write/実os.replace失敗時のrollbackを一時file/mockだけで検証した。[unit結果](audit_history/choice_sync_status_20261020/unit_result.json)。

さらに、現存正本を一時directoryへコピーし、mock controllerとcanonical `nativebuild監視_20261020T082306913887.json`（08:23:06.913887 JST、a04 FAILED_PRESERVED）を用いてコピーだけへpreview/apply/reapplyした。5対象の限定migrationが成功し、再applyの変更0、実正本全bytesのSHA不変を確認した。これは実正本のpreview/applyではなく、現在buildの再観測でもない。[一時実文書コピー検証](audit_history/choice_sync_status_20261020/temporary_actual_document_migration.json)。

CLI `--help`、skill-creator `quick_validate.py`はPASS。対象AST、旧新版差分、末尾空白、`git diff --check`を確認した。研究unitの全体再実行は行っていない。指定モデルと実backend identityは別であり、この担当のbackend identityは独立確認していない。

## 正本適用の引継ぎ

親担当が最新canonical monitorを取得してから、同じreportを指定してpreview→applyを行う。ここではその権限待ちの実文書操作を実施していない。

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_sync_status.py --build-observation <canonical-report>
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_sync_status.py --build-observation <same-canonical-report> --apply
```

[変更前SHA/原本](audit_history/choice_sync_status_20261020/before_sha256.json)、[変更後SHA/check](audit_history/choice_sync_status_20261020/after_sha256_and_checks.json)、[対象差分](audit_history/choice_sync_status_20261020/changes.patch)。
