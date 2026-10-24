@echo off
cd /d %~dp0
if not exist ".\.venv\Scripts\pythonw.exe" (
  echo Missing .venv\Scripts\pythonw.exe - run setup first
  pause
  exit /b 1
)
rem Launch GUI without console window; batch exits immediately.
rem If the app fails at startup, details go to error.log
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
