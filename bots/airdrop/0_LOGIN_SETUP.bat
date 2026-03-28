@echo off
title Airdrop Bot -- Einmaliger Login-Setup
cd /d "%~dp0"
echo.
echo ============================================================
echo   AIRDROP BOT -- EINMALIGER LOGIN SETUP
echo ============================================================
echo.
echo   Ein Chrome-Fenster oeffnet sich.
echo   Bitte einloggen bei:
echo     1. app.galxe.com  (mit X/Twitter)
echo     2. discord.com
echo     3. twitter.com / x.com
echo.
echo   Wenn alle 3 eingeloggt sind: Chrome-Fenster schliessen.
echo ============================================================
echo.
"C:\Program Files\Python312\python.exe" -X utf8 login_setup.py
pause
