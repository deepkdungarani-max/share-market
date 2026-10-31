# Signs CandleCast's own Codex CLI in to your ChatGPT Pro account. Its login lives in
# %LOCALAPPDATA%\candlecast\codex-home (CODEX_HOME), apart from the Codex you use in your IDE, which keeps its
# own account. Run it again to switch accounts.
$env:CODEX_HOME = Join-Path $env:LOCALAPPDATA 'candlecast\codex-home'
New-Item -ItemType Directory -Force $env:CODEX_HOME | Out-Null
$codex = Join-Path $env:LOCALAPPDATA 'candlecast\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe'
Write-Host ''
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host ' Sign in with the ChatGPT account that has Pro (deepdungarani50).' -ForegroundColor Cyan
Write-Host ' A browser page opens: pick that account and allow Codex.' -ForegroundColor Cyan
Write-Host ' When it says you are signed in, close this window.' -ForegroundColor Cyan
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host ''
& $codex login
Write-Host ''
& $codex login status
