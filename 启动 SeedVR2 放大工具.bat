@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONNOUSERSITE=1"
set "PROJECT_ROOT=%~dp0"
set "PYTHONPATH=%PROJECT_ROOT%"
start "" /D "%PROJECT_ROOT%" "%PROJECT_ROOT%runtime\python\pythonw.exe" -B -s -m app.gui %*
if errorlevel 1 pause
