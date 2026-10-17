@echo off
cd /d "%~dp0"
if exist "..\.venv-rocm\Scripts\python.exe" (
  "..\.venv-rocm\Scripts\python.exe" -m cael_unified.share
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m cael_unified.share
) else (
  python -m cael_unified.share
)
pause
