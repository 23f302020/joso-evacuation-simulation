<#
.SYNOPSIS
  学校PCの一括整備（段0・2・3・4・5・6 と、段8の自動確認）。既定は「確認のみ」で、何も変更しない。

.DESCRIPTION
  03_セットアップ手順_段0から8.md の自動化できる段をまとめる。段ごとに OK / TODO / STOP を判定し、
  STOP が出たらそれ以降の段は実行しない（状態を変えずに止める）。
  -Apply を付けたときだけ変更する（venv作成、config.json生成、環境変数、タスク登録）。
  やらないこと: ファイルコピー（段1: 02_robocopy.ps1）、アプリ登録・サインイン・同意（段7: ユーザー操作）、
  研究run・READY・start-next・validate・record、専用CLIの status（読取専用ではないため）。
  別の配置先のタスク JDRT-SimulationWatch が既にある場合は上書きしない。

.EXAMPLE
  .\05_bootstrap.ps1                                  # 確認のみ
  .\05_bootstrap.ps1 -ToolchainManifest '<...\toolchain.json>' -Apply
#>
[CmdletBinding()]
param(
    [string]$Root,
    [string]$ToolchainManifest,
    [string]$ExpectedManifestSha256,
    [switch]$Apply,
    [switch]$SkipTests
)
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) }
$TaskName = 'JDRT-SimulationWatch'
$MinFreeGB = 10
# 研究は選択済み native toolchain の traci/sumolib を使う（段3で検証）。venv には要求しない。
$NativeProvided = @('sumolib', 'traci')

# ---------- 純粋関数（test_bootstrap.ps1 で試験する） ----------
function Test-NonAscii([string]$Path) { return [bool]($Path -match '[^\x00-\x7F]') }

function Get-PinnedRequirements([string[]]$Lines) {
    $pins = @{}
    foreach ($line in $Lines) {
        if ($line -match '^\s*([A-Za-z0-9._-]+)==([^\s;#]+)') { $pins[$Matches[1].ToLowerInvariant()] = $Matches[2] }
    }
    return $pins
}

function ConvertTo-PackageKey([string]$Name) { return ($Name.ToLowerInvariant() -replace '[-_.]+', '-') }

function Compare-Freeze($Pins, [string[]]$Freeze) {
    $installed = @{}
    foreach ($line in $Freeze) {
        if ($line -match '^\s*([A-Za-z0-9._-]+)==([^\s;#]+)') { $installed[(ConvertTo-PackageKey $Matches[1])] = $Matches[2] }
    }
    $out = @()
    foreach ($name in ($Pins.Keys | Sort-Object)) {
        $key = ConvertTo-PackageKey $name
        if (-not $installed.ContainsKey($key)) { $out += "${name}: 未導入（要求 $($Pins[$name])）" }
        elseif ($installed[$key] -ne $Pins[$name]) { $out += "${name}: 要求 $($Pins[$name]) / 導入済み $($installed[$key])" }
    }
    return , @($out)
}

function Test-TaskOwnership([string]$Arguments, [string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Arguments)) { return 'none' }
    $needle = Join-Path $Root.TrimEnd('\') '07_監視システム\watch.py'
    if ($Arguments.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0) { return 'same' }
    return 'other'
}

function Get-ExitCode($Results) {
    $code = 0
    foreach ($r in $Results) {
        if ($r.Verdict -eq 'STOP') { return 2 }
        if ($r.Verdict -eq 'TODO') { $code = 1 }
    }
    return $code
}

# ---------- 実行系 ----------
function Invoke-External([string]$Exe, [string[]]$Arguments) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @Arguments 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prev }
    return @{ Code = $code; Out = @($out) }
}

function Invoke-Bootstrap {
    $rootPath = $Root.TrimEnd('\')
    $results = New-Object System.Collections.ArrayList
    $verdict = @{}
    $mode = if ($Apply) { 'APPLY（変更する）' } else { '確認のみ（何も変更しない）' }
    Write-Host "== JDRT 学校PC bootstrap / モード: $mode"
    Write-Host "   Root: $rootPath"
    if (Test-NonAscii $rootPath) { Write-Host "   注意: 配置先に日本語を含む。段6のタスク起動を必ず実機で確認し結果を記録する" }

    function Add-Result([string]$Stage, [string]$V, [string]$Evidence) {
        [void]$results.Add(@{ Stage = $Stage; Verdict = $V; Evidence = $Evidence })
        $verdict[$Stage] = $V
        Write-Host ("[{0}] {1}: {2}" -f $V, $Stage, $Evidence)
    }
    function Blocked([string[]]$Needs) {
        foreach ($n in $Needs) { if ($verdict[$n] -ne 'OK') { return "前段($n)が $($verdict[$n])のため実行しない" } }
        if ($results | Where-Object { $_.Verdict -eq 'STOP' }) { return '前段でSTOPが出たため実行しない' }
        return $null
    }

    $venvPy = Join-Path $rootPath '04_プログラム\venv\Scripts\python.exe'
    $watchDir = Join-Path $rootPath '07_監視システム'
    $configPath = Join-Path $watchDir 'config.json'
    $lockFile = Get-ChildItem -LiteralPath $ScriptDir -Filter 'venv_lock_*.txt' -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
    $reqFile = if ($lockFile) { $lockFile.FullName } else { Join-Path $rootPath '04_プログラム\requirements.txt' }

    # --- 段0 前提 ---
    $problems = @(); $notes = @()
    if (-not (Test-Path -LiteralPath (Join-Path $watchDir 'watch.py'))) { $problems += "$watchDir\watch.py が無い（段1のコピーが未了か、Rootが違う）" }
    if (-not (Test-Path -LiteralPath (Join-Path $rootPath '04_プログラム'))) { $problems += '04_プログラム が無い' }
    $drive = (Split-Path -Qualifier $rootPath).TrimEnd(':')
    $free = [math]::Round((Get-PSDrive -Name $drive).Free / 1GB, 1)
    if ($free -lt $MinFreeGB) { $problems += "空き容量 ${free}GB < ${MinFreeGB}GB" } else { $notes += "空き ${free}GB" }
    $pyLauncher = Invoke-External 'py' @('-3.13', '--version')
    $hasPy313 = ($pyLauncher.Code -eq 0)
    if ($hasPy313) { $notes += $pyLauncher.Out[0] }
    elseif (-not (Test-Path -LiteralPath $venvPy)) { $problems += 'Python 3.13 が無い（py -3.13 が失敗）。導入はユーザー操作' }
    $net = $false
    try { $net = Test-NetConnection -ComputerName graph.microsoft.com -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue } catch { $net = $false }
    $notes += $(if ($net) { 'graph.microsoft.com:443 到達可' } else { 'graph.microsoft.com:443 到達不可（メールのみ影響。段7で要確認）' })
    if ($problems) { Add-Result '段0 前提' 'STOP' ($problems -join ' / ') } else { Add-Result '段0 前提' 'OK' ($notes -join ' / ') }

    # --- 段2 venv ---
    $b = Blocked @('段0 前提')
    if ($b) { Add-Result '段2 venv' 'SKIP' $b }
    elseif (-not (Test-Path -LiteralPath $venvPy)) {
        if ($Apply) {
            $r = Invoke-External 'py' @('-3.13', '-m', 'venv', (Join-Path $rootPath '04_プログラム\venv'))
            if ($r.Code -ne 0) { Add-Result '段2 venv' 'STOP' ("venv作成に失敗: " + (($r.Out | Select-Object -Last 2) -join ' ')) }
            else {
                $r = Invoke-External $venvPy @('-B', '-X', 'utf8', '-m', 'pip', 'install', '-r', $reqFile)
                if ($r.Code -ne 0) { Add-Result '段2 venv' 'STOP' ("pip install に失敗（requirementsの版は変えない）: " + (($r.Out | Select-Object -Last 2) -join ' ')) }
            }
        } else { Add-Result '段2 venv' 'TODO' 'venv未作成。-Apply で py -3.13 から作成し requirements.txt を導入する' }
    }
    if (-not $verdict.ContainsKey('段2 venv') -and (Test-Path -LiteralPath $venvPy)) {
        $cfg = Join-Path $rootPath '04_プログラム\venv\pyvenv.cfg'
        $home_ = $null
        if (Test-Path -LiteralPath $cfg) { $line = Get-Content -LiteralPath $cfg -Encoding UTF8 | Where-Object { $_ -match '^\s*home\s*=' } | Select-Object -First 1; if ($line) { $home_ = ($line -split '=', 2)[1].Trim() } }
        $imp = Invoke-External $venvPy @('-B', '-X', 'utf8', '-c', 'import sys,numpy,pandas;print(sys.version.split()[0])')
        if ($home_ -and -not (Test-Path -LiteralPath $home_)) {
            Add-Result '段2 venv' 'STOP' "pyvenv.cfg の home が存在しない（元PCのvenvをコピーした疑い）: $home_ 。削除して作り直す（自動では削除しない）"
        } elseif ($imp.Code -ne 0) {
            Add-Result '段2 venv' 'STOP' ("import numpy/pandas に失敗: " + (($imp.Out | Select-Object -Last 2) -join ' '))
        } else {
            $list = Invoke-External $venvPy @('-B', '-X', 'utf8', '-m', 'pip', '--disable-pip-version-check', 'list', '--format=json')
            $items = ConvertFrom-Json ((@($list.Out | Where-Object { $_ -match '^\[' })) -join '')
            $installedLines = @(foreach ($i in @($items)) { "$($i.name)==$($i.version)" })
            $pins = Get-PinnedRequirements (Get-Content -LiteralPath $reqFile -Encoding UTF8)
            foreach ($n in $NativeProvided) { $pins.Remove($n) }
            $diff = Compare-Freeze $pins $installedLines
            if ($diff.Count) { Add-Result '段2 venv' 'STOP' ('基準(' + (Split-Path -Leaf $reqFile) + ')と不一致（版を勝手に変えない）: ' + ($diff -join '; ')) }
            else { Add-Result '段2 venv' 'OK' "Python $($imp.Out[0])。基準($(Split-Path -Leaf $reqFile))の$($pins.Count)件が一致（sumolib/traciはnative toolchain側で段3が確認）" }
        }
    }

    # --- 段3 toolchain ---
    $b = Blocked @('段2 venv')
    if ($b) { Add-Result '段3 toolchain' 'SKIP' $b }
    elseif (-not $ToolchainManifest) {
        Add-Result '段3 toolchain' 'TODO' '選択中のbundleは推測しない。元PCのstatus等で確認し -ToolchainManifest に学校PC上のtoolchain.jsonを指定する（registryには複数bundleがある）'
    } elseif (-not (Test-Path -LiteralPath $ToolchainManifest)) {
        Add-Result '段3 toolchain' 'STOP' "指定のtoolchain.jsonが無い: $ToolchainManifest"
    } else {
        $manifest = (Resolve-Path -LiteralPath $ToolchainManifest).Path
        $allowed = Join-Path $rootPath '04_プログラム\output\sumo\toolchains'
        if (-not $manifest.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
            Add-Result '段3 toolchain' 'STOP' "bundleがRoot配下の toolchains 以外: $manifest"
        } else {
            $env:JDRT_CHOICE_TOOLCHAIN_MANIFEST = $manifest
            $code = "import sys;sys.path.insert(0,r'" + (Join-Path $rootPath '04_プログラム') + "');from scripts.jdrt_choice_toolchain import resolve_choice_toolchain as r;s=r(require_manifest=True);print(s['sumo']);print(s['manifest_sha256'])"
            $r = Invoke-External $venvPy @('-B', '-X', 'utf8', '-c', $code)
            if ($r.Code -ne 0) { Add-Result '段3 toolchain' 'STOP' ("toolchain検証に失敗（manifest・SHAは書き換えない）: " + (($r.Out | Select-Object -Last 2) -join ' ')) }
            else {
                $sha = $r.Out[-1]
                if ($ExpectedManifestSha256 -and $sha -ne $ExpectedManifestSha256) {
                    Add-Result '段3 toolchain' 'STOP' "manifest_sha256 が期待値と不一致: $sha"
                } else {
                    $userValue = [Environment]::GetEnvironmentVariable('JDRT_CHOICE_TOOLCHAIN_MANIFEST', 'User')
                    if ($userValue -ne $manifest) {
                        if ($Apply) { [Environment]::SetEnvironmentVariable('JDRT_CHOICE_TOOLCHAIN_MANIFEST', $manifest, 'User'); $userValue = $manifest }
                    }
                    if ($userValue -eq $manifest) { Add-Result '段3 toolchain' 'OK' "manifest_sha256=$sha（元PCの値と突合する）。ユーザー環境変数を設定済み" }
                    else { Add-Result '段3 toolchain' 'TODO' "検証OK（manifest_sha256=$sha）。ユーザー環境変数が未設定。-Apply で設定する" }
                }
            }
        }
    }

    # --- 段4 パス（静的のみ。専用CLIのstatusは読取専用でないため実行しない） ---
    $registryPath = Join-Path $rootPath '04_プログラム\config\jdrt_realtime_choice_v1.json'
    if (-not (Test-Path -LiteralPath $registryPath)) { Add-Result '段4 パス' 'STOP' 'registryが無い' }
    else {
        $registry = Get-Content -LiteralPath $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $workspace = Join-Path $rootPath $registry.workspace
        if (-not (Test-Path -LiteralPath $workspace)) { Add-Result '段4 パス' 'STOP' "registryのworkspaceが無い: $workspace" }
        else {
            $runs = @(Get-ChildItem -LiteralPath (Join-Path $workspace 'runs') -Directory -ErrorAction SilentlyContinue).Count
            Add-Result '段4 パス' 'OK' "workspace有り（runsフォルダ $runs 件）。専用CLIのstatusは operations.jsonl へ追記するため実行していない。実機の status 確認はユーザー指示で別途"
        }
    }

    # --- 段5 監視config ---
    $b = Blocked @('段2 venv')
    if ($b) { Add-Result '段5 監視config' 'SKIP' $b }
    else {
        if (-not (Test-Path -LiteralPath $configPath)) {
            if ($Apply) {
                $r = Invoke-External $venvPy @('-B', '-X', 'utf8', (Join-Path $watchDir 'configure.py'), '--no-ai')
                if ($r.Code -ne 0) { Add-Result '段5 監視config' 'STOP' ("configure.py に失敗: " + (($r.Out | Select-Object -Last 2) -join ' ')) }
            } else { Add-Result '段5 監視config' 'TODO' 'config.json 無し。-Apply で configure.py --no-ai を実行する' }
        }
        if (-not $verdict.ContainsKey('段5 監視config') -and (Test-Path -LiteralPath $configPath)) {
            $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $expectCode = "import hashlib,pathlib;print(hashlib.sha256(str(pathlib.Path(r'" + (Join-Path $watchDir 'configure.py') + "').resolve().parent.parent).encode()).hexdigest()[:12])"
            $expect = (Invoke-External $venvPy @('-B', '-X', 'utf8', '-c', $expectCode)).Out[0]
            $problems = @()
            if ($cfg.diagnostics_enabled -ne $false) { $problems += 'diagnostics_enabled が false でない（AIなし方針に反する）' }
            if ($cfg.PSObject.Properties.Name -contains 'codex_exe') { $problems += 'codex_exe がある（AIなし方針に反する）' }
            if ((Split-Path -Leaf $cfg.runtime) -ne $expect) { $problems += "runtime の識別子が配置先と合わない（別PCのconfigの混入）: $($cfg.runtime)" }
            if (-not (Test-Path -LiteralPath $cfg.pythonw_exe)) { $problems += "pythonw_exe が無い: $($cfg.pythonw_exe)" }
            if ($problems) { Add-Result '段5 監視config' 'STOP' ($problems -join ' / ') }
            elseif ($SkipTests) { Add-Result '段5 監視config' 'OK' 'AIなしのconfig（試験は -SkipTests で省略）' }
            else {
                $t = Invoke-External $venvPy @('-B', '-X', 'utf8', '-m', 'unittest', 'discover', '-s', $watchDir, '-p', 'test_*.py')
                if ($t.Code -ne 0) { Add-Result '段5 監視config' 'STOP' ('単体試験が失敗: ' + (($t.Out | Select-Object -Last 3) -join ' ')) }
                else { Add-Result '段5 監視config' 'OK' ('AIなしのconfig。単体試験: ' + (($t.Out | Where-Object { $_ -match '^Ran ' } | Select-Object -Last 1))) }
            }
        }
    }

    # --- 段6 タスク ---
    $b = Blocked @('段5 監視config')
    if ($b) { Add-Result '段6 タスク' 'SKIP' $b }
    else {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        $owner = if ($task) { Test-TaskOwnership $task.Actions[0].Arguments $rootPath } else { 'none' }
        if ($owner -eq 'other') { Add-Result '段6 タスク' 'STOP' "別の配置先のタスク $TaskName が既にある。上書きしない（引数: $($task.Actions[0].Arguments)）" }
        elseif ($owner -eq 'none' -and -not $Apply) { Add-Result '段6 タスク' 'TODO' "$TaskName 未登録。-Apply で install.ps1 を実行する" }
        else {
            if ($owner -eq 'none') {
                $r = Invoke-External 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $watchDir 'install.ps1'))
                if ($r.Code -ne 0) { Add-Result '段6 タスク' 'STOP' ('install.ps1 に失敗: ' + (($r.Out | Select-Object -Last 2) -join ' ')) }
            }
            if (-not $verdict.ContainsKey('段6 タスク')) {
                $alive = $false; $detail = ''
                for ($i = 0; $i -lt 9 -and -not $alive; $i++) {
                    $s = Invoke-External $venvPy @('-B', '-X', 'utf8', (Join-Path $watchDir 'watch.py'), 'status')
                    try {
                        $j = $s.Out[-1] | ConvertFrom-Json
                        $alive = ($j.monitor_process.state -eq 'alive' -and $j.monitor_identity_matches -eq $true -and $j.observation_age_sec -lt 60)
                        $detail = "state=$($j.monitor_process.state) identity=$($j.monitor_identity_matches) age=$([int]$j.observation_age_sec)s"
                    } catch { $detail = 'statusを解釈できない' }
                    if (-not $alive) { Start-Sleep -Seconds 10 }
                }
                if ($alive) { Add-Result '段6 タスク' 'OK' "監視が稼働（$detail）。日本語パスの起動結果として記録する" }
                else { Add-Result '段6 タスク' 'STOP' "監視が稼働していない（$detail）。日本語パスなら ASCII パスへ移して段5〜6をやり直す" }
            }
        }
    }

    # --- 段8 自動確認（AI不起動・未処理配送なし） ---
    $b = Blocked @('段6 タスク')
    if ($b) { Add-Result '段8 自動確認' 'SKIP' $b }
    else {
        $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $codex = @(Get-Process -Name 'codex*' -ErrorAction SilentlyContinue).Count
        $pending = 0
        $events = Join-Path $cfg.runtime 'events'
        if (Test-Path -LiteralPath $events) {
            foreach ($f in Get-ChildItem -LiteralPath $events -Filter '*.json' | Where-Object { $_.Name -notmatch '\.reply' }) {
                try { if ((Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json).delivery -eq 'pending') { $pending++ } } catch { }
            }
        }
        if ($codex -gt 0) { Add-Result '段8 自動確認' 'STOP' "codex プロセスが $codex 件ある（AIなし方針に反する）" }
        elseif ($pending -gt 0) { Add-Result '段8 自動確認' 'STOP' "delivery=pending のイベントが $pending 件（AIなしでは残らないはず）" }
        else { Add-Result '段8 自動確認' 'OK' 'AIプロセスなし・pending配送なし。ロック/スリープ/サインアウトの観察は手動（04文書）' }
    }

    # --- 要約 ---
    Write-Host ''
    Write-Host '== 要約'
    foreach ($r in $results) { Write-Host ("  [{0}] {1}" -f $r.Verdict, $r.Stage) }
    Write-Host ''
    Write-Host '== ユーザー操作が必要（この関数では行わない）'
    Write-Host '  - 段1: robocopy でのコピー（02_robocopy.ps1。未了ならこの段の前に）'
    Write-Host '  - 段7: アプリ登録 → JDRT_MAIL_CLIENT_ID の設定 → graph_mail.py signin → 同意 → config の mail_enabled / mail_to / expected_completed_targets'
    Write-Host '  - 段8: ロック・スリープ・サインアウトの観察と記録、日本語パスでの起動結果の記録'
    Write-Host '  - 研究run・READY・sv26103006の再実行は、ユーザーの指示があるまで行わない'
    return $results
}

if ($MyInvocation.InvocationName -ne '.') {
    $final = Invoke-Bootstrap
    exit (Get-ExitCode $final)
}
