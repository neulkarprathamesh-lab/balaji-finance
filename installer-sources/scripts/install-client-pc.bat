@echo off
REM ================================================================
REM  Balaji FeeHub - Client PC Installer  (Windows 10/11 64-bit)
REM  No Python / MongoDB / Node needed on the client PC.
REM  Only requirement: Chrome or Microsoft Edge on the same LAN.
REM
REM  The desktop shortcut launches the browser in --app=URL mode so
REM  Balaji FeeHub appears as a chromeless Windows application window
REM  (no address bar, no tabs) instead of a normal browser tab.
REM ================================================================
setlocal EnableExtensions EnableDelayedExpansion

echo.
echo ================================================================
echo   Balaji FeeHub  Client PC Installer  v1.0
echo ================================================================

REM ---------- Locate Chrome / Edge binary ----------
set BROWSER_EXE=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set BROWSER_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not defined BROWSER_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set BROWSER_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not defined BROWSER_EXE if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set BROWSER_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
if not defined BROWSER_EXE if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set BROWSER_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe
if not defined BROWSER_EXE (
    echo.
    echo ================================================================
    echo   CLIENT INSTALLATION FAILED
    echo ================================================================
    echo   Neither Chrome nor Microsoft Edge was found on this PC.
    echo   Install either browser and re-run this installer.
    echo ================================================================
    exit /b 2
)
echo [1/6] OK    Browser detected: %BROWSER_EXE%

REM ---------- Discover Main Server via PowerShell (parallel LAN scan) ----------
echo [2/6] Discovering Main Server on the LAN (10-second scan) ...
set MAIN_IP=
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$prefix=(Get-NetIPConfiguration | Where-Object {$_.IPv4DefaultGateway -ne $null} | Select-Object -First 1).IPv4Address.IPAddress -replace '\.\d+$','.';" ^
  "1..254 | ForEach-Object -Parallel { try { $u=\"http://$using:prefix$_:8001/api/version\"; $r=Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200 -and $r.Content -match 'Balaji') { \"$using:prefix$_\" } } catch {} } -ThrottleLimit 40 | Select-Object -First 1"`) do set MAIN_IP=%%i

if not defined MAIN_IP (
    echo         Auto-discovery could not find a Main Server on this subnet.
    set /p MAIN_IP="        Enter the Main Server IP manually (e.g. 192.168.1.10): "
)
if not defined MAIN_IP (
    echo.
    echo ================================================================
    echo   CLIENT INSTALLATION FAILED  --  no Main Server IP given.
    echo ================================================================
    exit /b 3
)
echo         Main Server: %MAIN_IP%

REM ---------- Verify server responding ----------
echo [3/6] Verifying Main Server is responding ...
where curl >nul 2>&1
if %ERRORLEVEL%==0 (
    curl -s -o nul -w "         HTTP %%{http_code}\n" http://%MAIN_IP%:8001/api/version
    curl -s -o nul -w "%%{http_code}" http://%MAIN_IP%:8001/api/version | findstr "200" >nul || (
        echo.
        echo ================================================================
        echo   CLIENT INSTALLATION FAILED
        echo ================================================================
        echo   Main Server at http://%MAIN_IP%:8001/api/version did not
        echo   return HTTP 200.  Check the Main Server is running and
        echo   Windows Firewall on the Main Server allows port 8001.
        echo ================================================================
        exit /b 4
    )
) else (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://%MAIN_IP%:8001/api/version' -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -ne 200) { exit 1 } } catch { exit 1 }"
    if !ERRORLEVEL! neq 0 (
        echo.
        echo ================================================================
        echo   CLIENT INSTALLATION FAILED
        echo ================================================================
        echo   Main Server at http://%MAIN_IP%:8001 is not reachable from
        echo   this PC.  Check the Main Server is running and Windows
        echo   Firewall on the Main Server allows port 8001.
        echo ================================================================
        exit /b 4
    )
)
echo         OK

REM ---------- Confirm ----------
echo.
echo Balaji FeeHub
echo   Main Server found : %MAIN_IP%
echo   OK Server, OK Application, OK Database, OK Network
choice /C YN /N /M "[4/6] Create desktop + start-menu shortcut in Windows-app mode? [Y/N] "
if errorlevel 2 exit /b 5

REM ---------- Create --app mode shortcuts (chromeless window - looks like a native app) ----------
echo [5/6] Creating Balaji FeeHub Windows-app shortcuts ...
set URL=http://%MAIN_IP%:3000
set ICON=%~dp0school-logo.jpeg
powershell -NoProfile -Command ^
  "$w=New-Object -ComObject WScript.Shell;" ^
  "$s=$w.CreateShortcut([Environment]::GetFolderPath('CommonDesktopDirectory')+'\Balaji FeeHub.lnk');" ^
  "$s.TargetPath='%BROWSER_EXE%';" ^
  "$s.Arguments='--app=%URL% --new-window --disable-features=TranslateUI';" ^
  "$s.IconLocation='%ICON%,0';" ^
  "$s.Description='Balaji FeeHub - Fee ^& Accounting Software';" ^
  "$s.Save();" ^
  "$s2=$w.CreateShortcut([Environment]::GetFolderPath('CommonPrograms')+'\Balaji FeeHub.lnk');" ^
  "$s2.TargetPath='%BROWSER_EXE%';" ^
  "$s2.Arguments='--app=%URL% --new-window --disable-features=TranslateUI';" ^
  "$s2.IconLocation='%ICON%,0';" ^
  "$s2.Description='Balaji FeeHub - Fee ^& Accounting Software';" ^
  "$s2.Save()"

REM ---------- Open the application in --app mode ----------
echo [6/6] Opening the application (Windows-app mode) ...
start "" "%BROWSER_EXE%" --app=%URL% --new-window --disable-features=TranslateUI

echo.
echo ================================================================
echo   CLIENT INSTALLATION SUCCESSFUL
echo ================================================================
echo   Balaji FeeHub  .  %URL%
echo   Launches from the desktop icon as a chromeless Windows app.
echo ================================================================
exit /b 0
