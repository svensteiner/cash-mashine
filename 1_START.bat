@echo off
title Cash Mashine — Einzelnes Rennen
cd /d "%~dp0"
echo.
echo  ==========================================
echo   CASH MASHINE — EIN RENNEN STARTEN
echo  ==========================================
echo.
"C:\Program Files\Python312\python.exe" main.py
echo.
echo  Rennen abgeschlossen! Ergebnisse in state/
pause
