@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: installing dependencies with Python 3.12...
  py -3.12 scripts\setup.py
  if errorlevel 1 (
    echo Setup failed. Install Python 3.12 and Node.js, then try again.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" scripts\run.py
if errorlevel 1 pause
