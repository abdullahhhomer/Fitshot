@echo off
rem Starts the local CatVTON try-on service used by FitShot's "catvton" generator.
cd /d "%~dp0"
catvton\.venv\Scripts\python.exe services\catvton_server.py
