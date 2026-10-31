# Run as administrator: gives candlecast2 the "Log on as a batch job" right, which Task Scheduler needs to run
# the worker while nobody is signed in as candlecast2, then starts the worker. Nothing else changes.
$ErrorActionPreference = 'Stop'
$name = 'candlecast2'
$sid = (Get-LocalUser -Name $name).SID.Value
$cfg = Join-Path $env:TEMP 'cc-rights.inf'
$db = Join-Path $env:TEMP 'cc-rights.sdb'
secedit /export /cfg $cfg /areas USER_RIGHTS | Out-Null
$line = (Select-String -Path $cfg -Pattern '^SeBatchLogonRight\s*=').Line
if ($line -notmatch [regex]::Escape($sid)) {
    $new = if ($line) { "$line,*$sid" } else { "SeBatchLogonRight = *$sid" }
    @('[Unicode]', 'Unicode=yes', '[Version]', 'signature="$CHICAGO$"', 'Revision=1', '[Privilege Rights]', $new) |
        Set-Content -Path $cfg -Encoding Unicode
    secedit /configure /db $db /cfg $cfg /areas USER_RIGHTS | Out-Null
    Write-Host "Granted 'Log on as a batch job' to $name"
} else {
    Write-Host "$name already has 'Log on as a batch job'"
}
Remove-Item $cfg, $db -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName 'CandleCast agy2 worker'
Start-Sleep -Seconds 10
$info = Get-ScheduledTaskInfo -TaskName 'CandleCast agy2 worker'
Write-Host ('Task state: {0} · last result 0x{1:X8}' -f (Get-ScheduledTask -TaskName 'CandleCast agy2 worker').State, $info.LastTaskResult)
if (Test-Path 'C:\ProgramData\candlecast\agy2\out\heartbeat.json') { Write-Host 'WORKER RUNNING' } else { Write-Host 'No heartbeat yet' }
