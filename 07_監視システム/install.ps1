param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$watchBase = $PSScriptRoot
$watchScript = Join-Path $watchBase 'watch.py'
$watchTask = 'JDRT-SimulationWatch'
if ($Uninstall) {
    Stop-ScheduledTask -TaskName $watchTask -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $watchTask -Confirm:$false -ErrorAction SilentlyContinue
    exit
}
$watchConfig = Get-Content -LiteralPath (Join-Path $watchBase 'config.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$watchPython = $watchConfig.pythonw_exe
if (-not (Test-Path -LiteralPath $watchPython)) { throw 'Project pythonw.exe missing' }
if (-not (Test-Path -LiteralPath (Join-Path $watchBase 'config.json'))) { throw 'Create config.json first' }
$watchAction = New-ScheduledTaskAction -Execute $watchPython -Argument ('-B -X utf8 "' + $watchScript + '" run') -WorkingDirectory $watchBase
$watchTrigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$watchRescue = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5) -RepetitionInterval (New-TimeSpan -Minutes 1)
$watchSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$watchPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $watchTask -Action $watchAction -Trigger @($watchTrigger,$watchRescue) -Settings $watchSettings -Principal $watchPrincipal -Description 'Local JDRT event monitor; no periodic AI calls; one-minute process rescue, duplicate starts ignored.' -Force | Out-Null
Start-ScheduledTask -TaskName $watchTask
Get-ScheduledTask -TaskName $watchTask | Select-Object TaskName,State
