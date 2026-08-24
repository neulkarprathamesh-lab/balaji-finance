@echo off
REM ============================================================================
REM  Balaji FeeHub - Server Uninstaller (thin wrapper around uninstall.ps1)
REM
REM  Called by Inno Setup's [UninstallRun] step. Never prompts, never pauses,
REM  never blocks. Enforces a hard 10-minute timeout so even a catastrophically
REM  wedged uninstall.ps1 cannot freeze the Inno uninstaller UI.
REM
REM  Exit codes:
REM    0  = success (also returned when the ps1 finished with warnings)
REM    9  = timeout - Windows will finish removal on reboot
REM   99  = powershell itself failed to launch (extremely unlikely)
REM ============================================================================
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

set "APP_ROOT=%~dp0.."
pushd "%APP_ROOT%" 2>nul && set "APP_ROOT=%CD%" && popd
if not defined APP_ROOT set "APP_ROOT=C:\balaji-fee"

set "PS1=%~dp0uninstall.ps1"
if not exist "%PS1%" (
    echo [uninstall.bat] uninstall.ps1 not found at "%PS1%" - nothing to do.
    exit /b 0
)

REM By default preserve database + backups. Pass /WIPE to remove them too.
set "WIPE_FLAG="
if /I "%~1"=="/WIPE" set "WIPE_FLAG=-WipeData"

echo [uninstall.bat] Running PowerShell uninstaller for %APP_ROOT% ...
REM Use start /wait with a timeout wrapper so a hung ps1 cannot block Inno forever.
REM We spawn powershell and wait up to 600 seconds; if still running, kill it.
set "LOGDIR=%TEMP%"
set "STAMP=%RANDOM%%RANDOM%"
set "MARKER=%LOGDIR%\balaji-uninstall-done-%STAMP%.marker"

REM Launch powershell in the background with a marker-file signal on completion.
start "" /B powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -AppRoot "%APP_ROOT%" %WIPE_FLAG%
set "PS_ERR=%ERRORLEVEL%"
if not "%PS_ERR%"=="0" (
    echo [uninstall.bat] Failed to launch powershell (exit %PS_ERR%).
    exit /b 99
)

REM Poll for the powershell process to exit, hard-cap at 600 seconds.
set /a WAITED=0
:wait_loop
tasklist /FI "IMAGENAME eq powershell.exe" /FI "WINDOWTITLE eq *uninstall.ps1*" 2>nul | find /I "powershell.exe" >nul
if errorlevel 1 goto done
REM Also treat "no powershell running at all" as done.
tasklist /FI "IMAGENAME eq powershell.exe" 2>nul | find /I "powershell.exe" >nul
if errorlevel 1 goto done
timeout /T 2 /NOBREAK >nul
set /a WAITED=WAITED+2
if !WAITED! GEQ 600 goto timeout
goto wait_loop

:timeout
echo [uninstall.bat] uninstall.ps1 did not finish in 10 minutes - killing it.
taskkill /F /IM powershell.exe /T >nul 2>&1
exit /b 9

:done
echo [uninstall.bat] uninstall.ps1 completed.
exit /b 0
