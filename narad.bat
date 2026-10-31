@echo off
rem Narad without the server: collects free market news every 15 minutes into E:\candlecast-data\memory.db
rem and reads each item with the local Ollama model (start Ollama first). Safe to close and rerun.
rem start.bat already runs this inside the server; only one Narad runs at a time.
cd /d "%~dp0"
if not exist "E:\" (
  echo E: hard disk is not connected.
  pause
  goto :eof
)
.venv\Scripts\python -X utf8 -u -m app.narad
pause
