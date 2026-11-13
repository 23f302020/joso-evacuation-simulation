# 05_bootstrap.ps1 の純粋関数の試験（ファイル・タスク・ネットワークには触れない）
# 実行: powershell -NoProfile -File test_bootstrap.ps1   （失敗があれば終了コード1）
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '05_bootstrap.ps1')

$script:failed = 0
function Assert-Equal($Actual, $Expected, $Name) {
    if (($Actual | ConvertTo-Json -Compress -Depth 5) -ceq ($Expected | ConvertTo-Json -Compress -Depth 5)) { "PASS  $Name" }
    else { "FAIL  $Name : expected=$($Expected | ConvertTo-Json -Compress) actual=$($Actual | ConvertTo-Json -Compress)"; $script:failed++ }
}

# 日本語パスの検出
Assert-Equal (Test-NonAscii 'D:\Research\jdrt') $false 'ASCIIパスはfalse'
Assert-Equal (Test-NonAscii 'C:\Users\x\研究室\4年次本研究') $true '日本語パスはtrue'

# requirements の版固定の読み取り
$pins = Get-PinnedRequirements @('# comment', '', 'numpy==2.4.4', 'Sumolib==1.26.0', 'noversion', 'pandas>=3')
Assert-Equal ($pins.Keys | Sort-Object) @('numpy', 'sumolib') '==の行だけを小文字名で取る'
Assert-Equal $pins['numpy'] '2.4.4' '版の値'

# pip freeze との突合
$pins2 = @{ numpy = '2.4.4'; pandas = '3.0.2'; traci = '1.26.0' }
$freeze = @('numpy==2.4.4', 'Pandas==3.0.1', 'extra==1.0')
$diff = Compare-Freeze $pins2 $freeze
Assert-Equal $diff.Count 2 '不一致は2件（版違いと欠落）'
Assert-Equal (($diff -join '|').Contains('pandas')) $true '版違いを報告'
Assert-Equal (($diff -join '|').Contains('traci')) $true '欠落を報告'
Assert-Equal ((Compare-Freeze @{ numpy = '2.4.4' } @('numpy==2.4.4')).Count) 0 '一致なら0件'

# 既存タスクの所有判定（他の配置先のタスクを上書きしない）
$root = 'C:\Users\x\研究室\4年次本研究'
Assert-Equal (Test-TaskOwnership $null $root) 'none' 'タスクなし'
Assert-Equal (Test-TaskOwnership ('-B -X utf8 "' + $root + '\07_監視システム\watch.py" run') $root) 'same' '同じ配置先'
Assert-Equal (Test-TaskOwnership ('-B -X utf8 "' + $root.ToUpper() + '\07_監視システム\watch.py" run') $root) 'same' '大文字小文字を区別しない'
Assert-Equal (Test-TaskOwnership '-B -X utf8 "D:\other\07_監視システム\watch.py" run' $root) 'other' '別の配置先'

# 終了コード（STOP=2 > TODO=1 > OK=0）
Assert-Equal (Get-ExitCode @(@{ Verdict = 'OK' }, @{ Verdict = 'OK' })) 0 '全OK'
Assert-Equal (Get-ExitCode @(@{ Verdict = 'OK' }, @{ Verdict = 'TODO' })) 1 'TODOあり'
Assert-Equal (Get-ExitCode @(@{ Verdict = 'TODO' }, @{ Verdict = 'STOP' })) 2 'STOPあり'

Assert-Equal (Get-ExitCode @(@{ Verdict = 'OK' }, @{ Verdict = 'SKIP' })) 0 'SKIPは失敗にしない'
Assert-Equal (Get-ExitCode @(@{ Verdict = 'STOP' }, @{ Verdict = 'SKIP' })) 2 'STOPとSKIPならSTOP'

# 独立レビュー A11 の修正
Assert-Equal (Test-TaskOwnership '' $root $true) 'other' '引数が空の既存タスクは他の配置先として扱う'
Assert-Equal (Test-TaskOwnership $null $root $false) 'none' 'タスクなしなら none'
Assert-Equal (Select-JsonLine @('warn', '{\"a\":1}', 'trailing warning')) '{\"a\":1}' '末尾の警告を飛ばして JSON 行を取る'
Assert-Equal (Select-JsonLine @('only text')) $null 'JSON 行が無ければ null'
Assert-Equal (Select-Sha256Line @('x', ('a' * 64), 'warning')) ('a' * 64) 'SHA 行を取る（末尾の警告を無視）'
Assert-Equal (Select-Sha256Line @('x')) $null 'SHA 行が無ければ null'

# 段8：監視の子孫だけを AI プロセスとして数える（ChatGPT アプリ等の codex は無関係として扱う）
function P($id, $parent, $name) { [pscustomobject]@{ ProcessId = $id; ParentProcessId = $parent; Name = $name } }
$procs = @(
    (P 100 4 'explorer.exe'),
    (P 200 100 'pythonw.exe'), (P 201 200 'pythonw.exe'),          # 監視（venv の起動シム → 実体）
    (P 300 201 'codex.exe'),                                      # 監視が起動した AI
    (P 400 100 'ChatGPT.exe'), (P 401 400 'codex.exe'),            # 無関係
    (P 402 700 'codex-windows-sandbox-service.exe'),              # 無関係（親は services 等）
    (P 500 201 'cmd.exe'), (P 501 500 'Claude.exe')               # 孫の AI（大文字小文字は区別しない）
)
Assert-Equal (@(Find-AiDescendants $procs @(200)) | ForEach-Object ProcessId | Sort-Object) @(300, 501) '監視の子孫の AI だけを見つける'
Assert-Equal (@(Get-UnrelatedAi $procs @(200)) | ForEach-Object ProcessId | Sort-Object) @(401, 402) '無関係の AI は別に数える'
$clean = @((P 200 100 'pythonw.exe'), (P 201 200 'pythonw.exe'), (P 401 400 'codex.exe'))
Assert-Equal @(Find-AiDescendants $clean @(200)).Count 0 '監視の子孫に AI がなければ 0 件'
$loop = @((P 600 601 'pythonw.exe'), (P 601 600 'pythonw.exe'))
Assert-Equal @(Find-AiDescendants $loop @(600)).Count 0 '親子の循環があっても止まる'
Assert-Equal (Get-Stage8Verdict -AiDescendants 0 -Pending 0 -MonitorFound $true) 'OK' '段8：AIなし・pendingなしは OK'
Assert-Equal (Get-Stage8Verdict -AiDescendants 1 -Pending 0 -MonitorFound $true) 'STOP' '段8：監視の子孫に AI があれば STOP'
Assert-Equal (Get-Stage8Verdict -AiDescendants 0 -Pending 2 -MonitorFound $true) 'STOP' '段8：pending が残れば STOP'
Assert-Equal (Get-Stage8Verdict -AiDescendants 0 -Pending 0 -MonitorFound $false) 'STOP' '段8：監視プロセスが見つからなければ STOP'
if ($script:failed) { "`n$($script:failed) 件失敗"; exit 1 } else { "`n全件PASS" }
