@echo off
rem Starts everything for the free pipeline: ComfyUI, CatVTON and FASHN in their own windows, then FitShot.
rem Keep all four windows open while you use FitShot. Close them to stop it.
cd /d "%~dp0"
start "FitShot - ComfyUI" cmd /k "%~dp0run-comfyui.cmd"
start "FitShot - CatVTON" cmd /k "%~dp0run-catvton.cmd"
start "FitShot - FASHN" cmd /k "%~dp0run-fashn.cmd"
echo ComfyUI, CatVTON and FASHN are starting in their own windows. They take about a minute to load.
call "%~dp0run.cmd"
