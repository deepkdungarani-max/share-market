@echo off
rem Download latest candles into trading.db (on the data disk, see app\config.py), then retrain the 15m, 1h and 1d models.
cd /d "%~dp0"
.venv\Scripts\python -m app.fetch || goto :eof
.venv\Scripts\python -m app.train 15m
.venv\Scripts\python -m app.train 1h
.venv\Scripts\python -m app.train 1d
pause
