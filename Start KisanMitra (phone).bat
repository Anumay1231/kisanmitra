@echo off
title KisanMitra (phone access)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 launch.py --phone %*
) else (
    python launch.py --phone %*
)
pause
