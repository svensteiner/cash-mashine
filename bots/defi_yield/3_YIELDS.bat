@echo off
title DeFi Yield Bot -- Aktuelle Yields
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" -X utf8 main.py --yields
pause
