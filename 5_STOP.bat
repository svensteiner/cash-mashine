@echo off
title Cash Mashine — STOP
cd /d "%~dp0"
echo.
echo  Stoppe Cash Mashine Dauerlauf...
echo.
for /f "tokens=2" %%i in ('tasklist /FI "WINDOWTITLE eq Cash Mashine*" /FO LIST ^| find "PID:"') do (
    taskkill /PID %%i /F
    echo  Prozess %%i gestoppt.
)
if exist dauerlauf.lock del /f dauerlauf.lock && echo  Lock-File entfernt.
echo.
echo  Cash Mashine gestoppt.
pause
