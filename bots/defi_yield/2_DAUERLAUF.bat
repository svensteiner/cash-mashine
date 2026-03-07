@echo off
title DeFi Yield Bot -- Dauerlauf (alle 6h)
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" -X utf8 dauerlauf.py 6
pause
