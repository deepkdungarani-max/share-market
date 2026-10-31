# Runs once as candlecast2 in its own window (opened by setup.ps1): installs the Antigravity CLI for this
# Windows user and opens it so you can sign in with your second Google AI Pro account.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$agy = Join-Path $env:LOCALAPPDATA 'agy\bin\agy.exe'
if (-not (Test-Path $agy)) {
    Write-Host 'Installing the Antigravity CLI for candlecast2...'
    & (Join-Path $root 'install.ps1')
}
Write-Host ''
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host ' Sign in with your SECOND Google AI Pro account.' -ForegroundColor Cyan
Write-Host ' agy opens next: follow its sign-in (a browser page or a link).' -ForegroundColor Cyan
Write-Host ' If it is already signed in, type /logout then /login.' -ForegroundColor Cyan
Write-Host ' When it says you are signed in, type /exit (or close this window).' -ForegroundColor Cyan
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host ''
Set-Location (Join-Path $env:LOCALAPPDATA 'agy')
& $agy
