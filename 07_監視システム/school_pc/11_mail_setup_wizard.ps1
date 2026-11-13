<#
.SYNOPSIS
  学校PCのメール設定ウィザード（Gmail SMTP）。入力するのは、Gmail のアドレス・宛先・アプリパスワード・yes だけ。
.DESCRIPTION
  1) config.json に Gmail の設定を書く（smtp_mail.py configure。mail_enabled はまだ有効にしない）
  2) アプリパスワードを保存（smtp_mail.py setup。入力は表示されない。DPAPI で暗号化）
  3) 接続とサインインの確認（smtp_mail.py check。メールは送らない）
  4) 試験メール（smtp_mail.py send-test。内容を表示し、yes のときだけ1通）
  5) 届いたら、メール通知を有効にする（configure --enable）
  ワーカーの常駐登録は、別の install_mail_worker.ps1。
#>
param([string]$Root)
chcp 65001 > $null
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) }
$py = Join-Path $Root '04_プログラム\venv\Scripts\python.exe'
$watchDir = Join-Path $Root '07_監視システム'
$smtp = Join-Path $watchDir 'smtp_mail.py'
$cfg = Join-Path $watchDir 'config.json'
foreach ($need in @($py, $smtp, $cfg)) {
    if (-not (Test-Path -LiteralPath $need)) { Write-Host "見つかりません: $need（一括整備の段2・段5を先に済ませてください）"; exit 1 }
}
$current = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host '=== JDRT メール設定（学校PC） ==='
Write-Host "現在の設定: 送信元=$($current.mail_sender) / 宛先=$($current.mail_to) / 有効=$($current.mail_enabled) / この時刻以降のイベントだけ送る=$($current.mail_enabled_since)"
$sender = (Read-Host "送信専用 Gmail のアドレス [Enter で $($current.mail_sender)]").Trim()
if (-not $sender) { $sender = "$($current.mail_sender)" }
$to = (Read-Host "宛先（通知を受け取るアドレス） [Enter で $($current.mail_to)]").Trim()
if (-not $to) { $to = "$($current.mail_to)" }

Write-Host ''
Write-Host '--- 1/5 設定を書き込む（mail_enabled は、まだ有効にしません）'
& $py -B -X utf8 $smtp configure --config $cfg --sender $sender --to $to
if ($LASTEXITCODE -ne 0) { Write-Host '設定できませんでした（上の文言を確認）。中止します。'; exit 1 }

Write-Host ''
Write-Host '--- 2/5 アプリパスワードの保存（入力は画面に表示されません。16文字を貼り付けるか手で入力して Enter）'
& $py -B -X utf8 $smtp setup --config $cfg
if ($LASTEXITCODE -ne 0) { Write-Host '保存できませんでした。上の文言（文字数の内訳）を教えてください。パスワードは書かないでください。'; exit 1 }

Write-Host ''
Write-Host '--- 3/5 接続とサインインの確認（メールは送りません）'
& $py -B -X utf8 $smtp check --config $cfg
if ($LASTEXITCODE -ne 0) { Write-Host '確認に失敗しました。上の文言を教えてください。'; exit 1 }

Write-Host ''
Write-Host '--- 4/5 試験メール（内容を確認して、送る場合だけ yes と入力）'
& $py -B -X utf8 $smtp send-test --config $cfg

Write-Host ''
$answer = (Read-Host '--- 5/5 試験メールが届いた（受信箱か迷惑メールで確認）なら、メール通知を有効にします。有効にする場合は yes').Trim()
if ($answer -eq 'yes') {
    & $py -B -X utf8 $smtp configure --config $cfg --sender $sender --to $to --enable
    if ($LASTEXITCODE -ne 0) { Write-Host '有効にできませんでした。'; exit 1 }
    Write-Host '有効にしました。次は、ワーカーの常駐登録です（07_監視システム\install_mail_worker.ps1）。'
} else {
    Write-Host '有効にしていません（mail_enabled はそのまま）。届いたことを確認してから、もう一度このウィザードを実行してください。'
}