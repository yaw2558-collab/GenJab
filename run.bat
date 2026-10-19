@echo off
cd /d %~dp0
.\.venv\Scripts\python.exe app.py
if errorlevel 1 (
  echo.
  echo โปรแกรมปิดแบบมีข้อผิดพลาด — ถ่ายรูปหรือก๊อปข้อความด้านบนส่งมาได้เลย
  pause
)
