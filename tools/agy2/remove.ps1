# Undoes setup.ps1, run as administrator: stops and deletes the worker task, the candlecast2 user and its
# files. Your own Windows user and its Antigravity sign-in are not touched.
$ErrorActionPreference = 'Continue'
$name = 'candlecast2'
Unregister-ScheduledTask -TaskName 'CandleCast agy2 worker' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'agy.exe'" | Where-Object {
    (Invoke-CimMethod -InputObject $_ -MethodName GetOwner).User -eq $name } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$sid = (Get-LocalUser -Name $name -ErrorAction SilentlyContinue).SID
Remove-LocalUser -Name $name -ErrorAction SilentlyContinue
if ($sid) { Get-CimInstance Win32_UserProfile | Where-Object SID -eq $sid.Value | Remove-CimInstance -ErrorAction SilentlyContinue }
Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList' -Name $name -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force 'C:\ProgramData\candlecast\agy2' -ErrorAction SilentlyContinue
Write-Host 'Removed'
