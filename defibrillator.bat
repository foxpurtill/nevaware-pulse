@echo off
title NeveWare-Pulse Defibrillator
echo.
echo  NeveWare-Pulse Defibrillator
echo  ==============================
echo  Restarting Pulse...
echo.
:: Kill Pulse processes
wmic process where "name='pythonw.exe' and commandline like '%%launcher.pyw%%'" delete >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%launcher.pyw%%'" delete >nul 2>&1
wmic process where "name='pythonw.exe' and commandline like '%%tray_app.py%%'" delete >nul 2>&1
:: Clear PID file so new instance doesn't see false positive
if exist "%APPDATA%\NeveWare\pulse.pid" del "%APPDATA%\NeveWare\pulse.pid" >nul 2>&1
timeout /t 2 /nobreak >nul
:: Relaunch
start "" "C:\Python314\pythonw.exe" "C:\FoxPur-Studios\NeveWare-Pulse\launcher.pyw"
echo  Pulse restarted.
timeout /t 2 /nobreak >nul
