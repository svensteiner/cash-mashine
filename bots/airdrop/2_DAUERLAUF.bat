@echo off
title Airdrop Bot -- Dauerlauf (alle 2h)
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" -X utf8 dauerlauf.py
pause
