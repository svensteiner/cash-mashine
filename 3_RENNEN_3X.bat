@echo off
title Cash Mashine — 3 Rennen, dann Bester gewinnt
cd /d "%~dp0"
echo.
echo  ==========================================
echo   CASH MASHINE — 3 RENNEN RACE
echo   3 Runden, Intervall: 5 Minuten
echo  ==========================================
echo.
"C:\Program Files\Python312\python.exe" dauerlauf.py --rounds 3 --interval 5
echo.
pause
