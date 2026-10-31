# One-time setup, run as administrator: a second Windows user (candlecast2) whose Antigravity CLI is signed in
# to your second Google AI Pro account, plus a background task that answers Drona's prompts with it.
#
# agy keeps one Google sign-in per Windows user (in Credential Manager), so a second account needs a second
# Windows user. The user is hidden from the sign-in screen. Its random password is handed to Windows (Task
# Scheduler stores it) and never written anywhere. Undo with: tools\agy2\remove.ps1 (as administrator).
$ErrorActionPreference = 'Stop'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = 'C:\ProgramData\candlecast\agy2'
$name = 'candlecast2'
$owner = $args[0]  # the Windows user running CandleCast, e.g. WINDOWS-D8BFEDG\Deep
New-Item -ItemType Directory -Force $root | Out-Null
Start-Transcript -Path (Join-Path $root 'setup.log') -Force | Out-Null
try {
    # 1. The user, with a random password nobody needs to know
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $plain = [Convert]::ToBase64String($bytes) + 'a1!'
    $secure = ConvertTo-SecureString $plain -AsPlainText -Force
    if (Get-LocalUser -Name $name -ErrorAction SilentlyContinue) {
        Set-LocalUser -Name $name -Password $secure
        Write-Host "User $name exists: password reset"
    } else {
        New-LocalUser -Name $name -Password $secure -PasswordNeverExpires -AccountNeverExpires `
            -Description 'CandleCast: agy on 2nd Google AI Pro account' | Out-Null  # Windows allows 48 characters
        Write-Host "User $name created"
    }
    $users = Get-LocalGroup -SID 'S-1-5-32-545'
    if (-not (Get-LocalGroupMember -Group $users -Member $name -ErrorAction SilentlyContinue)) {
        Add-LocalGroupMember -Group $users -Member $name
    }
    $list = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList'
    New-Item -Path $list -Force | Out-Null
    New-ItemProperty -Path $list -Name $name -Value 0 -PropertyType DWord -Force | Out-Null  # hide from sign-in screen

    # 2. Files and folders: only admins and the owner may change the scripts; candlecast2 runs them and
    #    reads and writes the job folders
    foreach ($f in 'worker.ps1', 'login.ps1', 'install.ps1') { Copy-Item (Join-Path $src $f) $root -Force }
    foreach ($d in 'in', 'out') { New-Item -ItemType Directory -Force (Join-Path $root $d) | Out-Null }
    & icacls $root /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' "${owner}:(OI)(CI)F" "${name}:(OI)(CI)RX" | Out-Null
    foreach ($d in 'in', 'out') { & icacls (Join-Path $root $d) /grant "${name}:(OI)(CI)M" | Out-Null }
    Write-Host 'Folders ready'

    # 3. Sign in: a window as candlecast2 installs agy and opens it; wait until it is closed
    $cred = New-Object System.Management.Automation.PSCredential("$env:COMPUTERNAME\$name", $secure)
    Write-Host 'Opening the sign-in window as candlecast2...'
    $p = Start-Process powershell.exe -Credential $cred -WorkingDirectory $root -PassThru -ArgumentList `
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'login.ps1')
    $p.WaitForExit()
    Write-Host 'Sign-in window closed'

    # 4. The background worker: at startup and whenever the owner signs in; restarts if it ever stops
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $root -Argument `
        "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\worker.ps1`""
    $triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn -User $owner))
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName 'CandleCast agy2 worker' -Action $action -Trigger $triggers -Settings $settings `
        -User "$env:COMPUTERNAME\$name" -Password $plain -RunLevel Limited -Force | Out-Null
    Write-Host 'Worker task registered'
    # Task Scheduler needs "Log on as a batch job" to run it while nobody is signed in as candlecast2;
    # grant-batch.ps1 gives that right and starts the worker
    & (Join-Path $src 'grant-batch.ps1')
    Write-Host 'SETUP DONE'
} catch {
    Write-Host "SETUP FAILED: $($_.Exception.Message)"
} finally {
    $plain = $null
    Stop-Transcript | Out-Null
}
