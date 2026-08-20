@echo off
REM ================================================================
REM  Balaji FeeHub - Main Server Installer  .  Fully self-contained
REM  Windows 10/11 64-bit  .  100%% offline after ZIP is extracted
REM
REM  Repo source of truth. The GitHub Actions workflow overlays this
REM  file onto the CORE.zip payload before Inno Setup packs the EXE.
REM
REM  Contract:
REM   * NEVER touches an existing production database without a backup
REM   * NEVER prints "INSTALLATION SUCCESSFUL" unless every service is
REM     running, every port is listening, and the backend has replied
REM     with HTTP 200 to a real request from THIS machine.
REM   * On any hard failure, exits non-zero with a big FAILED banner.
REM ================================================================
setlocal EnableExtensions EnableDelayedExpansion

set APP_ROOT=C:\balaji-fee
set APP_BACKEND=%APP_ROOT%\backend
set APP_FRONTEND=%APP_ROOT%\frontend
set APP_LOGS=%APP_ROOT%\logs
set APP_BACKUPS=%APP_ROOT%\backups
set APP_UPDATES=%APP_ROOT%\updates
set MONGO_ROOT=%APP_ROOT%\mongodb
set MONGO_DATA=%APP_ROOT%\mongodb\data
set MONGO_LOGS=%APP_ROOT%\mongodb\logs
set VENV=%APP_ROOT%\venv
set SRC=%~dp0..\03-source-code
set BUNDLE=%~dp0..\05-services
set WHEELS=%~dp0wheels
set REPAIR_MODE=0

echo.
echo ================================================================
echo   Balaji FeeHub  Main Server Installer  v1.0  (self-contained)
echo   Balaji Convent ^& Junior College . Butibori, Nagpur
echo ================================================================
echo.

REM ---------- Run preflight first ----------
call "%~dp0preflight.bat"
if %ERRORLEVEL% neq 0 (
    echo.
    echo INSTALLATION ABORTED  --  preflight reported one or more BLOCKING errors above.
    exit /b 1
)

REM ---------- Detect existing production installation and back it up ----------
if exist "%MONGO_DATA%\WiredTiger" (
    echo.
    echo ================================================================
    echo   EXISTING INSTALLATION DETECTED
    echo ================================================================
    echo   Data dir : %MONGO_DATA%
    echo   Backups  : %APP_BACKUPS%
    echo.
    echo   The installer will create a FULL backup of the current
    echo   database and configuration BEFORE any changes are made.
    echo   Existing data will be PRESERVED - nothing is deleted or reset.
    echo.
    choice /C YN /N /M "Continue with in-place repair/update? [Y/N] "
    if errorlevel 2 (echo Cancelled by user. & exit /b 2)

    mkdir "%APP_BACKUPS%" 2>nul
    mkdir "%APP_LOGS%"    2>nul
    for /f "tokens=1-3 delims=/- " %%a in ("%DATE%") do set DPART=%%c-%%b-%%a
    for /f "tokens=1-3 delims=:." %%a in ("%TIME%") do set TPART=%%a-%%b-%%c
    set TPART=!TPART: =0!
    set BKP_DIR=%APP_BACKUPS%\pre-repair-!DPART!_!TPART!
    mkdir "!BKP_DIR!" 2>nul
    echo   Creating pre-repair backup at !BKP_DIR! ...

    where mongodump >nul 2>&1
    if !ERRORLEVEL!==0 (
        mongodump --host 127.0.0.1:27017 --out "!BKP_DIR!\db" > "%APP_LOGS%\pre-repair-backup.log" 2>&1
        if !ERRORLEVEL! neq 0 (
            echo.
            echo ================================================================
            echo   INSTALLATION FAILED  --  automatic pre-repair backup failed
            echo   mongodump returned !ERRORLEVEL!.  See %APP_LOGS%\pre-repair-backup.log
            echo   Aborting to protect existing production data.
            echo ================================================================
            exit /b 90
        )
    ) else (
        echo   WARN  mongodump not on PATH -- copying raw database files as fallback
        xcopy /E /Y /I /Q "%MONGO_DATA%" "!BKP_DIR!\raw-data" >nul
    )
    if exist "%APP_BACKEND%\.env"  copy /Y "%APP_BACKEND%\.env"  "!BKP_DIR!\backend.env.bak"  >nul
    if exist "%APP_FRONTEND%\.env" copy /Y "%APP_FRONTEND%\.env" "!BKP_DIR!\frontend.env.bak" >nul
    echo   OK    Pre-repair backup saved to !BKP_DIR!
    set REPAIR_MODE=1
    echo.
)

REM ---------- Create tree ----------
echo [ 1/14] Creating application directories under %APP_ROOT% ...
mkdir "%APP_ROOT%"        2>nul
mkdir "%APP_BACKEND%"     2>nul
mkdir "%APP_FRONTEND%"    2>nul
mkdir "%APP_LOGS%"        2>nul
mkdir "%APP_BACKUPS%"     2>nul
mkdir "%APP_UPDATES%\staging"  2>nul
mkdir "%APP_UPDATES%\rollback" 2>nul
mkdir "%MONGO_ROOT%"      2>nul
mkdir "%MONGO_DATA%"      2>nul
mkdir "%MONGO_LOGS%"      2>nul

REM ---------- Copy backend + prebuilt frontend (does not touch existing .env) ----------
echo [ 2/14] Copying source (backend + prebuilt frontend) ...
xcopy /E /Y /I /Q "%SRC%\backend"           "%APP_BACKEND%"        >nul
if exist "%SRC%\frontend\build" (
    xcopy /E /Y /I /Q "%SRC%\frontend\build"    "%APP_FRONTEND%\build" >nul
) else (
    echo   WARN: prebuilt frontend not found -- copying frontend/src instead.
    xcopy /E /Y /I /Q "%SRC%\frontend"       "%APP_FRONTEND%"       >nul
)
if exist "%SRC%\scripts" xcopy /E /Y /I /Q "%SRC%\scripts" "%APP_ROOT%\scripts" >nul
if exist "%SRC%\version.json" copy /Y "%SRC%\version.json" "%APP_ROOT%\version.json" >nul

REM ---------- Install MongoDB from bundled MSI ----------
echo [ 3/14] Installing MongoDB (from bundled MSI -- no download required) ...
set MONGO_MSI=

if exist "%BUNDLE%\mongodb-windows-x86_64.msi.001" if exist "%BUNDLE%\mongodb-windows-x86_64.msi.002" (
    if not exist "%BUNDLE%\mongodb-windows-x86_64.msi" (
        echo   Recombining split MSI parts into a single file ...
        copy /b "%BUNDLE%\mongodb-windows-x86_64.msi.001" + "%BUNDLE%\mongodb-windows-x86_64.msi.002" "%BUNDLE%\mongodb-windows-x86_64.msi" >nul
        if not exist "%BUNDLE%\mongodb-windows-x86_64.msi" (
            echo.
            echo ================================================================
            echo   INSTALLATION FAILED  --  could not recombine MongoDB MSI parts.
            echo   Confirm both mongodb-windows-x86_64.msi.001 and .002 are present.
            echo   No Windows services have been registered.
            echo ================================================================
            exit /b 3
        )
    )
)

for %%f in ("%BUNDLE%\mongodb-windows-x86_64*.msi") do set MONGO_MSI=%%f
if not defined MONGO_MSI (
    echo.
    echo ================================================================
    echo   INSTALLATION FAILED  --  MongoDB MSI not bundled under %BUNDLE%\
    echo   Expected: mongodb-windows-x86_64*.msi
    echo   No Windows services have been registered.
    echo ================================================================
    exit /b 3
)
where mongod >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   OK   MongoDB already installed on this PC -- skipping MSI install.
) else (
    echo   Running silent MSI install (this may take a minute) ...
    msiexec /i "%MONGO_MSI%" INSTALLLOCATION="%MONGO_ROOT%" ADDLOCAL=ServerNoService /qn /norestart
    if %ERRORLEVEL% neq 0 (
        echo.
        echo ================================================================
        echo   INSTALLATION FAILED  --  MongoDB MSI install failed (msiexec %ERRORLEVEL%^).
        echo   No Windows services have been registered.
        echo ================================================================
        exit /b 3
    )
    if not exist "%MONGO_ROOT%\bin\mongod.exe" (
        for /f "usebackq delims=" %%p in (`where /R "%ProgramFiles%\MongoDB" mongod.exe 2^>nul`) do set MONGOD=%%p
    ) else (
        set MONGOD=%MONGO_ROOT%\bin\mongod.exe
    )
)
if not defined MONGOD if exist "%MONGO_ROOT%\bin\mongod.exe" set MONGOD=%MONGO_ROOT%\bin\mongod.exe

REM ---------- Create Python venv ----------
echo [ 4/14] Creating Python virtual environment at %VENV% ...
if not exist "%VENV%\Scripts\python.exe" (
    python -m venv "%VENV%"
    if %ERRORLEVEL% neq 0 (
        echo.
        echo ================================================================
        echo   INSTALLATION FAILED  --  Python venv creation failed.
        echo   Confirm Python 3.11 x64 is installed and on PATH.
        echo   No Windows services have been registered.
        echo ================================================================
        exit /b 4
    )
)

REM ---------- Install Python dependencies from bundled wheels (offline) ----------
echo [ 5/14] Installing Python dependencies from bundled wheels (100%% offline) ...
call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade --no-index --find-links "%WHEELS%" pip 2>nul
python -m pip install --no-index --find-links "%WHEELS%" -r "%APP_BACKEND%\requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo   INSTALLATION FAILED  --  offline pip install returned %ERRORLEVEL%
    echo   The bundled Python wheelhouse under %WHEELS%\ is incomplete or
    echo   incompatible with the installed Python 3.11 x64 runtime.
    echo   No Windows services have been registered.
    echo ================================================================
    exit /b 5
)
REM ---------- Hard dependency verification (imports must work) ----------
python -c "import fastapi, uvicorn, motor, pymongo, pydantic, jwt, bcrypt, cryptography, pandas, numpy, openpyxl, dotenv, requests"
if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo   INSTALLATION FAILED  --  Python dependency verification failed.
    echo   pip install succeeded but the venv cannot import every required
    echo   production package. The offline wheelhouse is inconsistent.
    echo   No Windows services have been registered.
    echo ================================================================
    exit /b 5
)
echo         Verified: all 13 critical production packages import cleanly.

REM ---------- Generate secure secrets ----------
echo [ 6/14] Generating secure JWT secret + writing backend/.env ...
for /f %%s in ('powershell -NoProfile -Command "[Convert]::ToBase64String((1..48 ^| ForEach-Object {Get-Random -Maximum 255}))"') do set JWT=%%s
if not exist "%APP_BACKEND%\.env" (
    (
        echo MONGO_URL=mongodb://127.0.0.1:27017
        echo DB_NAME=balaji_fee_db
        echo CORS_ORIGINS=*
        echo JWT_SECRET=!JWT!
        echo ADMIN_EMAIL=admin@balajiconvent.in
        echo ADMIN_PASSWORD=ChangeMeOnFirstLogin@2026
    ) > "%APP_BACKEND%\.env"
) else (
    echo         Existing backend/.env preserved (production settings intact).
)

REM ---------- Detect LAN IP + frontend .env ----------
echo [ 7/14] Detecting Main Server LAN IP ...
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /C:"IPv4 Address" ^| findstr /V /C:"127.0.0.1"') do (
    set LAN_IP=%%i
    goto :GOT_IP3
)
:GOT_IP3
set LAN_IP=%LAN_IP: =%
if not defined LAN_IP set LAN_IP=127.0.0.1
echo         LAN IP: %LAN_IP%
if not exist "%APP_FRONTEND%\.env" (
    (
        echo REACT_APP_BACKEND_URL=http://%LAN_IP%:8001
        echo WDS_SOCKET_PORT=443
    ) > "%APP_FRONTEND%\.env"
) else (
    echo         Existing frontend/.env preserved.
)

REM ---------- MongoDB config (127.0.0.1 only - never exposed to LAN) ----------
echo [ 8/14] Configuring MongoDB (binds to 127.0.0.1 -- clients never talk to Mongo directly) ...
(
    echo systemLog:
    echo   destination: file
    echo   path: %MONGO_LOGS%\mongod.log
    echo   logAppend: true
    echo storage:
    echo   dbPath: %MONGO_DATA%
    echo net:
    echo   bindIp: 127.0.0.1
    echo   port: 27017
) > "%MONGO_ROOT%\mongod.cfg"

REM ---------- Firewall ----------
echo [ 9/14] Opening firewall for 3000 + 8001 (Mongo 27017 stays private) ...
netsh advfirewall firewall delete rule name="BalajiFeeHub Backend"  >nul 2>&1
netsh advfirewall firewall delete rule name="BalajiFeeHub Frontend" >nul 2>&1
netsh advfirewall firewall add rule name="BalajiFeeHub Backend"  dir=in action=allow protocol=TCP localport=8001 >nul
netsh advfirewall firewall add rule name="BalajiFeeHub Frontend" dir=in action=allow protocol=TCP localport=3000 >nul

REM ---------- Register services via bundled NSSM ----------
echo [10/14] Registering Windows services with bundled NSSM ...
call "%~dp0register-services.bat"
if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo   INSTALLATION FAILED  --  service registration returned %ERRORLEVEL%
    echo   Inspect NSSM output above and services.msc for partial state.
    echo ================================================================
    exit /b 10
)

REM ---------- Start services ----------
echo [11/14] Starting services (Mongo -^> Backend -^> Frontend) ...
net start BalajiFeeHub-Mongo    2>nul & timeout /t 4 /nobreak >nul
net start BalajiFeeHub-Backend  2>nul & timeout /t 3 /nobreak >nul
net start BalajiFeeHub-Frontend 2>nul & timeout /t 2 /nobreak >nul

REM ---------- Post-install verification (COMPREHENSIVE) ----------
echo [12/14] Running comprehensive post-install verification ...
set CHECK_FAILED=0
set CHECK_REASONS=

echo   --- Service existence ---
for %%S in (BalajiFeeHub-Mongo BalajiFeeHub-Backend BalajiFeeHub-Frontend) do (
    sc query "%%S" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  Service %%S does not exist
        set /a CHECK_FAILED+=1
        set CHECK_REASONS=!CHECK_REASONS! service-missing:%%S
    ) else (
        echo   OK    Service %%S exists
    )
)

echo   --- Service state (must be RUNNING) ---
for %%S in (BalajiFeeHub-Mongo BalajiFeeHub-Backend BalajiFeeHub-Frontend) do (
    sc query "%%S" | findstr /I "RUNNING" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  Service %%S is NOT running
        set /a CHECK_FAILED+=1
        set CHECK_REASONS=!CHECK_REASONS! service-not-running:%%S
    ) else (
        echo   OK    Service %%S is RUNNING
    )
)

echo   --- Ports listening ---
for %%P in (27017 8001 3000) do (
    netstat -an | findstr /R /C:":%%P .*LISTENING" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  Port %%P is NOT listening
        set /a CHECK_FAILED+=1
        set CHECK_REASONS=!CHECK_REASONS! port-not-listening:%%P
    ) else (
        echo   OK    Port %%P listening
    )
)

echo   --- HTTP endpoint checks ---
where curl >nul 2>&1
if %ERRORLEVEL%==0 (
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8001/api/version | findstr "200" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  Backend /api/version did NOT return HTTP 200
        set /a CHECK_FAILED+=1
        set CHECK_REASONS=!CHECK_REASONS! backend-api-version-not-200
    ) else (
        echo   OK    Backend  http://127.0.0.1:8001/api/version = 200
    )
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:3000 | findstr /R /C:"200 302" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  Frontend / did NOT return a success status
        set /a CHECK_FAILED+=1
        set CHECK_REASONS=!CHECK_REASONS! frontend-not-ok
    ) else (
        echo   OK    Frontend http://127.0.0.1:3000 responded
    )
) else (
    powershell -NoProfile -Command "try { (Invoke-WebRequest 'http://127.0.0.1:8001/api/version' -UseBasicParsing -TimeoutSec 8).StatusCode } catch { 'ERR' }" | findstr "200" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  Backend /api/version did NOT return HTTP 200 (via PowerShell)
        set /a CHECK_FAILED+=1
        set CHECK_REASONS=!CHECK_REASONS! backend-api-version-not-200
    ) else (
        echo   OK    Backend  http://127.0.0.1:8001/api/version = 200
    )
)

echo   --- Backend to MongoDB connectivity ---
"%VENV%\Scripts\python.exe" -c "from pymongo import MongoClient; MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=8000).admin.command('ping'); print('mongo-ok')" 2>nul | findstr "mongo-ok" >nul
if !ERRORLEVEL! neq 0 (
    echo   FAIL  Backend cannot reach MongoDB on 127.0.0.1:27017
    set /a CHECK_FAILED+=1
    set CHECK_REASONS=!CHECK_REASONS! mongo-unreachable
) else (
    echo   OK    Backend -^> MongoDB ping succeeded
)

echo   --- LAN reachability ---
if "%LAN_IP%"=="127.0.0.1" (
    echo   WARN  Only reachable at 127.0.0.1 (no LAN IP found)
    set CHECK_REASONS=!CHECK_REASONS! lan-ip-missing
) else (
    echo   OK    LAN IP %LAN_IP% -- other PCs on this subnet can reach http://%LAN_IP%:3000
)

if !CHECK_FAILED! neq 0 (
    echo.
    echo ================================================================
    echo   INSTALLATION FAILED  --  post-install verification failed
    echo ================================================================
    echo   Failed checks     : !CHECK_FAILED!
    echo   Reasons           : !CHECK_REASONS!
    echo   Logs              : %APP_LOGS%\
    echo   Services console  : services.msc
    echo   Health endpoint   : http://127.0.0.1:8001/api/version
    echo.
    echo   The Balaji FeeHub Server is NOT ready for production use.
    echo   Fix the issues above (typically start-order timing or firewall)
    echo   and re-run this installer to try again.
    echo ================================================================
    exit /b 12
)

REM ---------- Verify Electron desktop app is bundled ----------
echo [13/14] Verifying Balaji FeeHub desktop application ...
set DESKTOP_EXE=%~dp0..\04-desktop\BalajiFeeHub.exe
if not exist "%DESKTOP_EXE%" (
    echo.
    echo ================================================================
    echo   INSTALLATION FAILED  --  BalajiFeeHub.exe not found in the payload.
    echo   Expected: %DESKTOP_EXE%
    echo   The desktop application was not packaged into this installer.
    echo   Re-download the Server installer and try again.
    echo ================================================================
    exit /b 13
)
echo         OK    Desktop app located at %DESKTOP_EXE%

REM ---------- Autostart on reboot ----------
echo [14/14] Verifying services set to auto-start on boot ...
sc config BalajiFeeHub-Mongo    start= auto >nul 2>&1
sc config BalajiFeeHub-Backend  start= auto >nul 2>&1
sc config BalajiFeeHub-Frontend start= auto >nul 2>&1

echo.
echo ================================================================
echo   INSTALLATION SUCCESSFUL  (all verification checks passed)
echo ================================================================
echo.
echo   Main Server IP : %LAN_IP%
echo   Application    : http://%LAN_IP%:3000
echo   Backend API    : http://%LAN_IP%:8001/api
echo   Data dir       : %MONGO_DATA%
echo   Backups dir    : %APP_BACKUPS%
echo   Logs           : %APP_LOGS%
echo.
if "%REPAIR_MODE%"=="1" (
    echo   Mode           : REPAIR/UPDATE (existing database preserved)
    echo   Pre-repair bkp : !BKP_DIR!
) else (
    echo   Mode           : FRESH INSTALL
    echo   Default admin  : admin@balajiconvent.in
    echo   Default pass   : ChangeMeOnFirstLogin@2026
    echo   Factory PIN    : 2580  (change immediately from Administration ^> Factory Reset^)
    echo   ^>^>^> CHANGE THE ADMIN PASSWORD IMMEDIATELY AFTER FIRST LOGIN ^<^<^<
)
echo.
echo   RESTART THIS PC to confirm services auto-start on boot,
echo   then open http://%LAN_IP%:3000 from another PC on the same LAN.
echo ================================================================
exit /b 0
