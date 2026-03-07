@echo off
title Faucet Bot -- Status
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" -X utf8 main.py --status
pause
