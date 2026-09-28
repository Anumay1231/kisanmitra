@echo off
title KisanMitra (public link)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 launch.py --share %*
) else (
    python launch.py --share %*
)
pause
