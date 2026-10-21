@echo off
setlocal
set "taskRuntime=%~dp0..\.venv-rocm\Scripts\python.exe"
if not exist "%taskRuntime%" (
  echo CAEL runtime not found. Use your configured Python with -m cael_unified.local_tools.
  exit /b 2
)
pushd "%~dp0"
"%taskRuntime%" -m cael_unified.local_tools %*
set "taskExit=%ERRORLEVEL%"
popd
exit /b %taskExit%
