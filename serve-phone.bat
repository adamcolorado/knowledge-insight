@echo off
REM Knowledge InSight - serve to phones and tablets on the same Wi-Fi.
REM Prints the address to type into the phone's browser. Ctrl+C stops it.
REM
REM This exposes the site to everything on your local network while it runs.
REM For solo work, use serve.bat instead, which stays on this machine.

cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python was not found on the PATH.
  echo Install Python 3 from https://www.python.org/downloads/ and try again.
  echo.
  pause
  exit /b 1
)

py -3 tools\serve.py --lan --no-open %*

if errorlevel 1 pause
