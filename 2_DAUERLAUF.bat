@echo off
title Cash Mashine — Dauerlauf (alle 60 Min)
cd /d "%~dp0"
echo.
echo  ==========================================
echo   CASH MASHINE — DAUERLAUF GESTARTET
echo   Rennen alle 60 Minuten
echo   Stopp: Ctrl+C oder Fenster schliessen
echo  ==========================================
echo.
"C:\Program Files\Python312\python.exe" dauerlauf.py
echo.
pause
