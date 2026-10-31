# Run as administrator when account 2's worker doesn't start: writes the task's state, its last result and
# recent Task Scheduler events to C:\ProgramData\candlecast\agy2\diag.txt (readable by CandleCast), then
# starts the task once more.
$out = 'C:\ProgramData\candlecast\agy2\diag.txt'
$name = 'CandleCast agy2 worker'
& {
    "== $(Get-Date)"
    Get-ScheduledTask -TaskName $name | Select-Object TaskName, State | Format-List | Out-String
    $info = Get-ScheduledTaskInfo -TaskName $name
    $info | Select-Object LastRunTime, NextRunTime, NumberOfMissedRuns | Format-List | Out-String
    'LastTaskResult: 0x{0:X8}' -f $info.LastTaskResult
    (Get-ScheduledTask -TaskName $name).Principal | Format-List | Out-String
    '== user'
    Get-LocalUser -Name candlecast2 | Select-Object Name, Enabled, PasswordExpires | Format-List | Out-String
    '== batch logon right'
    $cfg = Join-Path $env:TEMP 'secpol.cfg'
    secedit /export /cfg $cfg /areas USER_RIGHTS | Out-Null
    Select-String -Path $cfg -Pattern 'SeBatchLogonRight|SeDenyBatchLogonRight' | ForEach-Object { $_.Line }
    Remove-Item $cfg -ErrorAction SilentlyContinue
    '== processes of candlecast2'
    Get-Process -IncludeUserName | Where-Object { $_.UserName -like '*candlecast2*' } |
        Select-Object Id, ProcessName, StartTime | Format-Table | Out-String
    '== start again'
    Start-ScheduledTask -TaskName $name
    Start-Sleep -Seconds 8
    'LastTaskResult after start: 0x{0:X8}' -f (Get-ScheduledTaskInfo -TaskName $name).LastTaskResult
    (Get-ScheduledTask -TaskName $name).State
} *>&1 | Out-File -FilePath $out -Encoding UTF8
Write-Host "Written to $out"
