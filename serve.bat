@echo off
REM Knowledge InSight - build the site and serve it locally.
REM Double-click this file, or run it from a terminal. Ctrl+C stops the server.

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

py -3 tools\serve.py %*

REM Keep the window open if the script exited because something went wrong.
if errorlevel 1 pause
