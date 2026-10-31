@echo off
rem Fills E:\candlecast-data\market.db with every NSE bhavcopy since Nov 1994 and everything
rem Yahoo keeps (1-minute ~30 days, 15-minute ~60 days, 1-hour ~2 years, daily since listing).
rem Safe to close and run again: both downloaders resume where they stopped.
rem Run it at least every 3 weeks (daily is best): Yahoo deletes 1-minute bars after ~30 days.
cd /d "%~dp0"
if not exist "E:\" (
  echo E: hard disk is not connected.
  pause
  goto :eof
)
if not exist "E:\candlecast-data\logs" mkdir "E:\candlecast-data\logs"
start "NSE bhavcopy 1994-today" cmd /k .venv\Scripts\python -X utf8 -u -m app.download_nse
start "Yahoo 1m/15m/1h/daily" cmd /k .venv\Scripts\python -X utf8 -u -m app.download_yahoo
