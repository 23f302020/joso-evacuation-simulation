param([switch]$Uninstall)
# JDRT mail worker as a logon task (mirrors install.ps1). Sends only queued failure / all-complete notices.
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
$script = Join-Path $base 'mail_worker.py'
$taskName = 'JDRT-MailWorker'
if ($Uninstall) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    exit
}
$configPath = Join-Path $base 'config.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Create config.json first (configure.py --no-ai)' }
$config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
if ($config.mail_enabled -ne $true) { throw 'mail_enabled is not true: finish check / send-test, then smtp_mail.py configure --enable' }
if (-not $config.mail_to) { throw 'mail_to missing in config.json' }
if ($config.mail_provider -eq 'gmail_smtp' -and -not (Test-Path -LiteralPath (Join-Path $config.runtime 'smtp_secret.bin'))) {
    throw 'App password not saved for this user: run smtp_mail.py setup first'
}
$python = $config.pythonw_exe
if (-not (Test-Path -LiteralPath $python)) { throw 'Project pythonw.exe missing' }
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument ('-B -X utf8 "' + $script + '" run') -WorkingDirectory $base
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
$rescue = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
# Interactive: the DPAPI-protected app password can be read only in this user's session.
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($atLogon, $rescue) -Settings $settings -Principal $principal -Description 'JDRT mail worker: sends queued failure/all-complete notices only; single instance (lock); one-minute rescue; duplicate starts ignored.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State