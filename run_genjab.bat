@echo off
cd /d %~dp0
if not exist ".\.venv\Scripts\pythonw.exe" (
  echo Missing .venv\Scripts\pythonw.exe - run setup first
  pause
  exit /b 1
)
rem GenJab dual backend: pick Local (this machine) or Cloud (online API),
rem switch sides anytime with the button inside the app.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0genjab.py" %*
