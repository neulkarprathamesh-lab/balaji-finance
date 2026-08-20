@echo off
REM ================================================================
REM  Balaji FeeHub - Main Server Installer  .  Fully self-contained
REM  Windows 10/11 64-bit  .  100%% offline after ZIP is extracted
REM
REM  This is the repo-tracked source of truth. The GitHub Actions
REM  workflow overlays this file onto the CORE.zip payload before
REM  Inno Setup packs the installer, so future stealth-broken
REM  wheelhouses / silent failures cannot slip through again.
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

REM ---------- Create tree ----------
echo.
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

REM ---------- Copy backend + prebuilt frontend ----------
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
)

REM ---------- MongoDB config (127.0.0.1 only) ----------
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
REM  Services are ONLY registered after the Python venv is proven working above.
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

REM ---------- Post-install health check ----------
echo [12/14] Running post-install health checks ...
set HEALTH_OK=1
where curl >nul 2>&1 && (
    curl -s -o nul -w "backend:%%{http_code} " http://127.0.0.1:8001/api/version
    curl -s -o nul -w "frontend:%%{http_code}\n" http://127.0.0.1:3000
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8001/api/version | findstr "200" >nul || set HEALTH_OK=0
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:3000            | findstr "200" >nul || set HEALTH_OK=0
)

REM ---------- Desktop shortcut ----------
echo [13/14] Creating desktop shortcut ...
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([Environment]::GetFolderPath('CommonDesktopDirectory')+'\Balaji FeeHub.lnk'); $s.TargetPath='http://%LAN_IP%:3000'; $s.IconLocation='%APP_FRONTEND%\build\school-logo.jpeg,0'; $s.Save()" >nul 2>&1

REM ---------- Autostart on reboot ----------
echo [14/14] Verifying services set to auto-start on boot ...
sc config BalajiFeeHub-Mongo    start= auto >nul 2>&1
sc config BalajiFeeHub-Backend  start= auto >nul 2>&1
sc config BalajiFeeHub-Frontend start= auto >nul 2>&1

echo.
echo ================================================================
if "%HEALTH_OK%"=="1" (
    echo   INSTALLATION SUCCESSFUL
    echo.
    echo   Main Server IP : %LAN_IP%
    echo   Application    : http://%LAN_IP%:3000
    echo   Backend API    : http://%LAN_IP%:8001/api
    echo   Data dir       : %MONGO_DATA%
    echo   Backups dir    : %APP_BACKUPS%
    echo.
    echo   Default admin  : admin@balajiconvent.in
    echo   Default pass   : ChangeMeOnFirstLogin@2026
    echo   Factory PIN    : 2580  (change immediately from Administration ^> Factory Reset^)
    echo   ^>^>^> CHANGE THE ADMIN PASSWORD IMMEDIATELY AFTER FIRST LOGIN ^<^<^<
) else (
    echo   INSTALLATION FAILED  .  one or more services did not return HTTP 200
    echo   Inspect logs at %APP_LOGS%\  and services in services.msc
    exit /b 12
)
echo ================================================================
exit /b 0
