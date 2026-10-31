# Runs in the background as the Windows user candlecast2 (Task Scheduler, from setup.ps1). Answers Drona's and
# Narad's prompts with the Antigravity CLI signed in to the second Google AI Pro account, up to $MaxJobs at once
# (Drona's lessons take minutes; Narad's news batches must not wait behind them).
#
# The app (app/agy_cli.py) drops a job in in\<id>.json: {"args": "<agy command line>", "timeout": seconds}.
# The reply goes to out\<id>.json: {"stdout", "stderr", "code"}. out\heartbeat.json says the worker is alive,
# how many jobs it runs at once and which account agy is signed in as (read from agy's own log; the login token
# is never touched).
$ErrorActionPreference = 'Continue'
$MaxJobs = 3
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$in = Join-Path $root 'in'
$out = Join-Path $root 'out'
$agy = Join-Path $env:LOCALAPPDATA 'agy\bin\agy.exe'
$work = Join-Path $env:LOCALAPPDATA 'candlecast\agy-work'
$log = Join-Path $env:USERPROFILE '.gemini\antigravity-cli\cli.log'
New-Item -ItemType Directory -Force $work | Out-Null

function Write-Json($path, $value) {
    # Write then rename, so the app never reads half a file
    $tmp = "$path.tmp"
    $value | ConvertTo-Json -Depth 4 -Compress | Set-Content -Path $tmp -Encoding UTF8
    Move-Item -Path $tmp -Destination $path -Force
}

function Get-Account {
    if (-not (Test-Path $log)) { return $null }
    $hit = Select-String -Path $log -Pattern 'authenticated successfully as (\S+@\S+)' | Select-Object -Last 1
    if ($hit) { return $hit.Matches[0].Groups[1].Value }
    return $null
}

function Write-Heartbeat($busy) {
    Write-Json (Join-Path $out 'heartbeat.json') @{
        at = (Get-Date).ToUniversalTime().ToString('o'); account = $script:account; agy = (Test-Path $agy)
        busy = $busy; parallel = $MaxJobs
    }
}

function Start-Job-Process($job) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $agy
    $psi.Arguments = $job.args
    $psi.WorkingDirectory = $work
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.Close()
    return $p
}

$account = Get-Account
$checked = Get-Date
$running = @()  # one hashtable per job in progress: name, proc, out, err, deadline, timeout
while ($true) {
    if (((Get-Date) - $checked).TotalMinutes -ge 5) { $account = Get-Account; $checked = Get-Date }
    Write-Heartbeat ($running.Count -gt 0)

    # Jobs that finished, or ran past their time
    foreach ($j in @($running)) {
        if ($j.proc.HasExited) {
            $j.proc.WaitForExit()
            Write-Json (Join-Path $out $j.name) @{ stdout = $j.out.Result; stderr = $j.err.Result; code = $j.proc.ExitCode }
        } elseif ((Get-Date) -gt $j.deadline) {
            try { $j.proc.Kill() } catch {}
            Write-Json (Join-Path $out $j.name) @{ stdout = ''; stderr = "agy took longer than $($j.timeout)s"; code = -1 }
        } else {
            continue
        }
        $running = @($running | Where-Object { $_ -ne $j })
    }

    # New jobs, while there is room
    foreach ($f in Get-ChildItem -Path $in -Filter '*.json' -ErrorAction SilentlyContinue) {
        if ($running.Count -ge $MaxJobs) { break }
        try { $job = Get-Content -Path $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json } catch { continue }
        Remove-Item -Path $f.FullName -Force -ErrorAction SilentlyContinue
        try {
            $p = Start-Job-Process $job
            $running += , @{ name = $f.Name; proc = $p; out = $p.StandardOutput.ReadToEndAsync();
                             err = $p.StandardError.ReadToEndAsync(); timeout = $job.timeout;
                             deadline = (Get-Date).AddSeconds([int]$job.timeout) }
        } catch {
            Write-Json (Join-Path $out $f.Name) @{ stdout = ''; stderr = "worker: $($_.Exception.Message)"; code = -1 }
        }
    }
    Start-Sleep -Seconds 2
}
