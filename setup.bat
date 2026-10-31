@echo off
rem One-time setup: creates .venv inside the project and installs packages.
cd /d "%~dp0"
py -3.12 -m venv .venv || python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
echo Setup done.
