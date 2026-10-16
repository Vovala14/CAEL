@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m cael_unified --ui
) else (
  python -m cael_unified --ui
)
pause
