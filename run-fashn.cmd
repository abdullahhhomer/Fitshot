@echo off
rem Starts the local FASHN VTON 1.5 try-on service used by FitShot (http://127.0.0.1:8191).
rem It runs in the CatVTON Python environment. Set it up once with scripts/setup_fashn.sh.
cd /d "%~dp0"
catvton\.venv\Scripts\python.exe services\fashn_server.py
