@echo off
rem Like start.bat, but Drona works through the queued topics instead of growing the queue:
rem   CANDLECAST_MAX_DEPTH=1       lessons stop proposing subtopics (each one used to add 3-6 more)
rem   CANDLECAST_LEARN_PAUSE=5     5 s between topics instead of 20
rem   CANDLECAST_EXTRA_LEARNERS=2  two extra learners per Google account (the plans' quotas run out sooner)
rem Use start.bat again once the queue is small and the curriculum should go deeper.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo .venv missing - run setup.bat first.
  pause
  goto :eof
)
set CANDLECAST_MAX_DEPTH=1
set CANDLECAST_LEARN_PAUSE=5
set CANDLECAST_EXTRA_LEARNERS=2
start "" http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
