$ErrorActionPreference = 'Stop'
$projectRoot = (Get-Location).Path
$proofPath = Join-Path $projectRoot '07_監視システム/verification/execution_timing_20261024'
$watchPath = Join-Path $projectRoot '07_監視システム/watch.py'
$pythonPath = Join-Path $projectRoot '04_プログラム/venv/Scripts/python.exe'
$runtimePath = Join-Path $env:USERPROFILE '.jdrt-monitor/10afa40fb646'
$before = & $pythonPath -B -X utf8 $watchPath status | ConvertFrom-Json
if (-not $before.monitor_identity_matches -or $before.monitor_process.state -ne 'alive') { throw 'Monitor identity is not verified' }
$watchTask = Get-ScheduledTask -TaskName JDRT-SimulationWatch
if ($watchTask.State -eq 'Disabled') { throw 'Task is disabled; preserve original state' }
if (-not $watchTask.Actions.Arguments.Contains($watchPath)) { throw 'Unexpected task action' }
$watchPid = [int]$before.monitor_process.pid
$watchCreated = [long]$before.monitor_process.created
$watchProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$watchPid"
if (-not $watchProcess.CommandLine.Contains($watchPath)) { throw 'Unexpected monitor command' }
if ((Get-Process -Id $watchPid).StartTime.ToUniversalTime().ToFileTimeUtc() -ne $watchCreated) { throw 'PID identity changed' }
$pending = $before.events | Where-Object { $_.delivery -in @('claimed','running') }
if ($pending) { throw 'AI diagnosis active; defer restart' }
Copy-Item -LiteralPath (Join-Path $runtimePath 'state.json') -Destination (Join-Path $proofPath 'state.before.json')
$eventHashes = @{}
Get-ChildItem -LiteralPath (Join-Path $runtimePath 'events') -Filter '*.json' | ForEach-Object {
    $eventHashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
}
$eventHashes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $proofPath 'events.before.sha.json') -Encoding utf8
Disable-ScheduledTask -TaskName JDRT-SimulationWatch | Out-Null
try {
    Stop-ScheduledTask -TaskName JDRT-SimulationWatch
    Start-Sleep -Milliseconds 800
    $remaining = Get-Process -Id $watchPid -ErrorAction SilentlyContinue
    if ($remaining) {
        if ($remaining.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $watchCreated) { throw 'Old PID reused; do not stop' }
        $command = (Get-CimInstance Win32_Process -Filter "ProcessId=$watchPid").CommandLine
        if (-not $command.Contains($watchPath)) { throw 'Command changed; do not stop' }
        Stop-Process -Id $watchPid
        $remaining.WaitForExit(10000) | Out-Null
    }
    if (Get-Process -Id $watchPid -ErrorAction SilentlyContinue) { throw 'Old monitor still present' }
} finally {
    Enable-ScheduledTask -TaskName JDRT-SimulationWatch | Out-Null
}
Start-ScheduledTask -TaskName JDRT-SimulationWatch
$expectedSha = (Get-FileHash -LiteralPath $watchPath -Algorithm SHA256).Hash.ToLowerInvariant()
$confirmed = $false
for ($attempt = 0; $attempt -lt 25; $attempt++) {
    Start-Sleep -Seconds 2
    $after = & $pythonPath -B -X utf8 $watchPath status | ConvertFrom-Json
    $state = Get-Content -LiteralPath (Join-Path $runtimePath 'state.json') -Raw | ConvertFrom-Json
    if ($after.monitor_identity_matches -and $after.monitor_process.state -eq 'alive' -and
        $after.monitor_process.pid -ne $watchPid -and $after.observation_age_sec -lt 40 -and
        $state.monitor_source_sha256 -eq $expectedSha) { $confirmed = $true; break }
}
if (-not $confirmed) { throw 'New monitor/source not confirmed' }
foreach ($name in $eventHashes.Keys) {
    if ((Get-FileHash -LiteralPath (Join-Path $runtimePath "events/$name") -Algorithm SHA256).Hash -ne $eventHashes[$name]) {
        throw "Existing event changed: $name"
    }
}
$timedTargets = @($state.targets.PSObject.Properties | Where-Object { $_.Value.execution_timing })
if (-not $timedTargets.Count) { throw 'Timing fields missing in deployed state' }
if (-not (Get-Content -LiteralPath (Join-Path $runtimePath 'status.html') -Raw).Contains('所要時間：')) { throw 'Inbox timing missing' }
Copy-Item -LiteralPath (Join-Path $runtimePath 'state.json') -Destination (Join-Path $proofPath 'state.after.json')
$after | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $proofPath 'status.after.json') -Encoding utf8
[ordered]@{ status='DEPLOYED'; at_jst=(Get-Date).ToString('o'); old_pid=$watchPid;
    new_pid=$after.monitor_process.pid; source_sha256=$expectedSha; old_events_unchanged=$eventHashes.Count;
    timed_targets=$timedTargets.Count; research_processes_modified=$false; ai_replayed=$false
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $proofPath 'deployment.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $proofPath 'deployment.json')
