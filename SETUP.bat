@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements-unified.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m cael_unified --download
if errorlevel 1 goto failed
echo Ready. Run RUN.bat, then open http://127.0.0.1:8765
pause
exit /b 0
:failed
echo Setup failed. Read the error above before retrying.
pause
exit /b 1
