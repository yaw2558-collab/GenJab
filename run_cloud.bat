@echo off
cd /d %~dp0
if not exist ".\.venv\Scripts\pythonw.exe" (
  echo Missing .venv\Scripts\pythonw.exe - run setup first
  pause
  exit /b 1
)
rem GenJab Cloud: generate images through online APIs (no GPU / local models needed)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0cloud_app.py"
