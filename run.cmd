@echo off
rem Starts FitShot at http://127.0.0.1:8000
cd /d "%~dp0frontend"
if not exist node_modules (
  call npm install || exit /b 1
)
rem Rebuild every start so the app always shows the latest screens (takes a few seconds).
call npm run build || exit /b 1
cd /d "%~dp0backend"
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn fitshot.api:app --host 127.0.0.1 --port 8000
