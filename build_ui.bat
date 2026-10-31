@echo off
rem Builds the React UI into web\dist (needs Node.js). Only required after changing web\src.
cd /d "%~dp0web"
call npm install || goto :eof
call npm run build
pause
