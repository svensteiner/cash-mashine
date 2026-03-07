@echo off
title Airdrop Bot -- Nur Quests scannen
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" -X utf8 main.py --scan
pause
