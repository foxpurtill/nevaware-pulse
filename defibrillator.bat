@echo off
setlocal enabledelayedexpansion

:: NeveWare-Pulse Defibrillator
:: Kills the running Pulse instance and relaunches it.
:: All paths are relative to this bat file (%~dp0) - no hardcoding.

set "BASE=%~dp0"
set "PID_FILE=%APPDATA%\NeveWare\pulse.pid"
set "LAUNCHER=%BASE%launcher.pyw"

:: --- Kill by PID (fast and precise) ---
if exist "%PID_FILE%" (
    set /p OLD_PID=<"%PID_FILE%"
    taskkill /PID !OLD_PID! /F >nul 2>&1
    del "%PID_FILE%" >nul 2>&1
)

:: --- Fallback: kill any pythonw still holding tray_app or launcher ---
wmic process where "name='pythonw.exe' and commandline like '%%tray_app%%'" delete >nul 2>&1
wmic process where "name='pythonw.exe' and commandline like '%%launcher%%'" delete >nul 2>&1

:: --- Brief pause so tray icon and sockets release ---
timeout /t 2 /nobreak >nul

:: --- Relaunch (.pyw association runs via pythonw.exe automatically) ---
start "" "%LAUNCHER%"
