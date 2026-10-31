@echo off
rem Teacher self-study without the server: researches the stock market topic by topic with your
rem Claude Code login and stores lessons in E:\candlecast-data\knowledge.db. Before each topic it
rem studies the models' scored mistakes and answers the help requests Narad raised. Safe to close and rerun.
rem start.bat already runs this inside the server; only one learner runs at a time.
cd /d "%~dp0"
if not exist "E:\" (
  echo E: hard disk is not connected.
  pause
  goto :eof
)
.venv\Scripts\python -X utf8 -u -m app.knowledge
pause
