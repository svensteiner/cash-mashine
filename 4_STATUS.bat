@echo off
title Cash Mashine — Status
cd /d "%~dp0"
echo.
"C:\Program Files\Python312\python.exe" main.py --status
echo.
"C:\Program Files\Python312\python.exe" main.py --history
echo.
pause
