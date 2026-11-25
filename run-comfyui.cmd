@echo off
rem Starts the local ComfyUI server used by the FitShot ComfyUI generator.
cd /d "%~dp0comfyui"
.venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --lowvram --disable-auto-launch
