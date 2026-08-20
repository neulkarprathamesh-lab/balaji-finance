@echo off
REM ================================================================
REM  Balaji FeeHub Main Server - thin wrapper around PowerShell
REM  orchestrator install-main-server.ps1.
REM
REM  This BAT exists only so the Inno Setup [Run] entry, Start Menu
REM  Repair shortcut, and legacy documentation all keep working
REM  without change. The real orchestration lives in PowerShell so
REM  we can do multi-strategy MongoDB detection, structured error
REM  handling, real HTTP verification, and per-stage exit codes.
REM ================================================================
setlocal EnableExtensions
set PS1=%~dp0install-main-server.ps1
if not exist "%PS1%" (
    echo.
    echo INSTALLATION FAILED  --  install-main-server.ps1 not found
    echo   Expected: %PS1%
    echo   Re-download the Server installer.
    exit /b 2
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
exit /b %ERRORLEVEL%
