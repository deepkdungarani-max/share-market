@echo off
rem Starts the candlecast server and opens the UI. Close this window to stop it.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo .venv missing - run setup.bat first.
  pause
  goto :eof
)
start "" http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
