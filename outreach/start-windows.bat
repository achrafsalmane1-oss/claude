@echo off
REM Double-click this file to start Outreach. Close this window to stop it.
cd /d "%~dp0"

set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" (where py >nul 2>nul && set PY=py)

if "%PY%"=="" (
  echo.
  echo   Python isn't installed on this PC.
  echo   Install it from https://www.python.org/downloads/
  echo   IMPORTANT: on the first install screen, tick "Add python.exe to PATH".
  echo   Then double-click this file again.
  echo.
  pause
  exit /b 1
)

echo Starting Outreach... your browser will open in a second.
echo Leave this window open while you use the app. Close it to stop.
echo.
%PY% app.py --open
pause
