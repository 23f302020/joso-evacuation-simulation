<#
.SYNOPSIS
  研究環境(4年次本研究)を学校PCへコピーする robocopy ラッパー。既定は「一覧のみ」(コピーしない)。

.DESCRIPTION
  既定  : robocopy /L  (何も書き込まない。コピー対象の一覧とログだけ作る)
  実コピー: -Execute を明示したときだけ。
  検証  : -Verify  (コピー後に再度 /L で「まだコピーされていないファイル」を数える。0件が目標)

  使わないもの: /MIR /PURGE /MOVE (削除・移動を伴うため)。コピー先の余分なファイルは触らない(/XX)。
  再開    : /Z (再開可能モード)。途中で切れても同じコマンドを再実行すると、同一(サイズ・更新時刻)は飛ばして続きから。
            -Backup を付けると /ZB (権限不足ファイルはバックアップ権限で読む。管理者権限が必要な場合あり)。
  ログ    : robocopy は /UNILOG で UTF-16 を書く。終了後に UTF-8(BOM付き) の .log へ変換する。
  日本語パス・長いパス: robocopy は Unicode 引数と 260 文字超パスを既定で扱う(/256 は使わない)。

  実行例(学校PC側から家のPCの共有を読む場合も、家のPCから学校PCの共有へ書く場合も、パスを渡すだけ):
    # 1) 一覧だけ(安全)
    .\02_robocopy.ps1 -Source 'C:\...\4年次本研究' -Destination 'D:\Research\4年次本研究'
    # 2) 実コピー(研究run・監視が止まっていることを確認してから)
    .\02_robocopy.ps1 -Source ... -Destination ... -Execute
    # 3) 検証(0件が目標)
    .\02_robocopy.ps1 -Source ... -Destination ... -Verify

  コピーしない主なもの(詳細と理由は 01_コピーするもの_作り直すもの一覧.md):
    .git / 開発メモ / 07_アーカイブ / venv / cache / logs / 07_監視システム\runtime / 07_監視システム\config.json / .claude / .codex / __pycache__
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Destination,
    [switch]$Execute,
    [switch]$Verify,
    [switch]$Backup,
    [switch]$ExcludeFrozenExperiments,
    [switch]$AllowRunning,
    [ValidateRange(1, 16)][int]$Threads = 4,
    [string]$LogDir = (Join-Path $env:USERPROFILE 'JDRT-robocopy-logs')
)
$ErrorActionPreference = 'Stop'

if ($Execute -and $Verify) { throw '-Execute と -Verify は同時に指定できません。' }

function Get-NormalizedPath([string]$p) {
    $full = [System.IO.Path]::GetFullPath($p)
    $root = [System.IO.Path]::GetPathRoot($full)
    if ($full.Length -gt $root.Length) { $full = $full.TrimEnd('\', '/') }
    return $full
}

$src = Get-NormalizedPath $Source
$dst = Get-NormalizedPath $Destination
if ($src.Length -le [System.IO.Path]::GetPathRoot($src).Length) { throw 'Source にドライブ直下は指定できません。' }
if ($dst.Length -le [System.IO.Path]::GetPathRoot($dst).Length) { throw 'Destination にドライブ直下は指定できません(専用フォルダを指定)。' }

# 取り違え防止: 研究ルートの目印を確認(読取のみ)
$markers = @('context.md', '07_監視システム\watch.py', '04_プログラム\scripts')
foreach ($m in $markers) {
    if (-not (Test-Path -LiteralPath (Join-Path $src $m))) { throw "Source が研究ルートに見えません(目印なし: $m)。" }
}

# 入れ子禁止
$sep = [System.IO.Path]::DirectorySeparatorChar
if ($src.Equals($dst, 'OrdinalIgnoreCase') -or
    ($dst + $sep).StartsWith($src + $sep, 'OrdinalIgnoreCase') -or
    ($src + $sep).StartsWith($dst + $sep, 'OrdinalIgnoreCase')) {
    throw 'Source と Destination が同一または入れ子です。'
}

# --- 除外(フルパスは Source 基準。名前だけのものはどの階層でも除外) ---
$xdRel = @(
    '.git', '.claude', '.codex', '.github', '.pytest_cache', '.wrangler', '.hallmark',
    '07_アーカイブ', '開発メモ',
    '04_プログラム\venv', '04_プログラム\cache', '04_プログラム\logs', '04_プログラム\.pytest_cache',
    '07_監視システム\runtime'
)
$xdPaths = @($xdRel | ForEach-Object { Join-Path $src $_ })
$xdNames = @('__pycache__', '.pytest_cache')

if ($ExcludeFrozenExperiments) {
    # 注意: 現系列の validate / record が過去系列の証拠を参照するかは未検証。既定では除外しない。
    $exp = Join-Path $src '04_プログラム\output\sumo\regions\08211\experiments'
    $frozen = @('jdrt', 'jdrt_realistic', 'jdrt_realtime_b', 'jdrt_realtime_b_boundary_v2',
        'jdrt_realtime_choice_nativeaudit_v2', 'jdrt_realtime_choice_nativeaudit_v3',
        'jdrt_realtime_choice_routeaudit_v4', 'jdrt_realtime_choice_v1', 'scenario_c', 'type34_split')
    $xdPaths += @($frozen | ForEach-Object { Join-Path $exp $_ })
}

$xfPaths = @(
    (Join-Path $src '07_監視システム\config.json')   # 機械ローカル設定。学校PCで configure.py が作る
)
$xfNames = @('*.pyc', '*.pyo', 'Thumbs.db', 'desktop.ini', '~$*')

# --- 実行前の確認表示 ---
$mode = if ($Execute) { 'EXECUTE(コピーする)' } elseif ($Verify) { 'VERIFY(/L 未コピー数を数える)' } else { 'LIST(/L 既定: コピーしない)' }
Write-Host "モード      : $mode"
Write-Host "Source      : $src"
Write-Host "Destination : $dst"

if ($Execute -and -not $AllowRunning) {
    # Source がローカルのときだけ判定できる。研究run・SUMO・監視が動いている最中のコピーは不整合になる。
    $busy = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -match '^sumo(-gui)?\.exe$' -or
            ($_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -and
                ($_.CommandLine -match 'choice_|realtime_choice|jdrt|watch\.py'))
        })
    if ($busy.Count -gt 0) {
        $busy | Select-Object ProcessId, Name | Format-Table | Out-String | Write-Host
        throw '研究run・SUMO・監視らしいプロセスが動いています。停止を確認するか、承知の上なら -AllowRunning を付けてください(推奨しません)。'
    }
}

# --- robocopy 引数 ---
$null = New-Item -ItemType Directory -Force -Path $LogDir
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$tag = if ($Execute) { 'copy' } elseif ($Verify) { 'verify' } else { 'list' }
$utf16Log = Join-Path $LogDir "robocopy_${tag}_$stamp.utf16.log"
$utf8Log = Join-Path $LogDir "robocopy_${tag}_$stamp.log"

$rc = New-Object System.Collections.Generic.List[string]
$rc.Add($src); $rc.Add($dst)
$rc.Add('/E')                      # 空フォルダ含むサブツリー(削除は伴わない)
$rc.Add('/COPY:DAT'); $rc.Add('/DCOPY:DAT')
$rc.Add('/XJ')                     # ジャンクション/シンボリックリンク先を辿らない
$rc.Add('/XX')                     # コピー先だけにあるファイルは報告もしない(削除もしない)
$rc.Add('/R:2'); $rc.Add('/W:5')
if ($Backup) { $rc.Add('/ZB') } else { $rc.Add('/Z') }
$rc.Add("/MT:$Threads")
$rc.Add('/NP')
$rc.Add("/UNILOG:$utf16Log")
if (-not $Execute) { $rc.Add('/L') }
if ($Verify) { foreach ($f in '/NJH', '/NJS', '/NDL', '/NC', '/NS') { $rc.Add($f) } }
$rc.Add('/XD'); foreach ($d in ($xdPaths + $xdNames)) { $rc.Add($d) }
$rc.Add('/XF'); foreach ($f in ($xfPaths + $xfNames)) { $rc.Add($f) }

# 取り返しのつかないスイッチが混入していないことを実行前に自己確認
foreach ($a in $rc) {
    if ($a -match '^/(MIR|PURGE|MOV|MOVE)$' -or $a -match '^/MOVE?:') { throw "禁止スイッチ検出: $a" }
}

try {
    & robocopy.exe @rc
    $code = $LASTEXITCODE
}
finally {
    if (Test-Path -LiteralPath $utf16Log) {
        $text = [System.IO.File]::ReadAllText($utf16Log, [System.Text.Encoding]::Unicode)
        [System.IO.File]::WriteAllText($utf8Log, $text, (New-Object System.Text.UTF8Encoding($true)))
    }
}

Write-Host "robocopy 終了コード: $code (0〜7=成功系, 8以上=失敗あり)"
Write-Host "ログ(UTF-8)        : $utf8Log"

if ($code -ge 8) {
    Write-Host 'robocopy に失敗があります。ログを確認し、原因を解消してから同じコマンドを再実行してください。'
    exit 1
}

if ($Verify) {
    $pending = @(Get-Content -LiteralPath $utf8Log -Encoding UTF8 | Where-Object { $_.Trim() -ne '' })
    Write-Host ("未コピー(またはコピー先と差異がある)ファイル数: {0}" -f $pending.Count)
    if ($pending.Count -gt 0) {
        $pending | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
        exit 3
    }
    Write-Host 'OK: 除外を除く全ファイルがコピー先に揃っています(サイズ・更新時刻ベース。内容のSHA一致は 03 段3/4 で別に確認)。'
}
elseif (-not $Execute) {
    Write-Host 'これは一覧のみです。何もコピーしていません。実コピーは -Execute を明示してください。'
}
exit 0
