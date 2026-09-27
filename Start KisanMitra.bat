@echo off
title KisanMitra
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 launch.py %*
) else (
    python launch.py %*
)
if errorlevel 1 (
    echo.
    echo If Python is missing, install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
)
pause
