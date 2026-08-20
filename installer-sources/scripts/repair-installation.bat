@echo off
REM ================================================================
REM  Balaji FeeHub - Repair Installation  (safe, non-destructive)
REM  Always creates a full DB + config backup BEFORE any change.
REM  Never touches the database. Never resets receipts or config.
REM ================================================================
setlocal EnableExtensions EnableDelayedExpansion

set APP_ROOT=C:\balaji-fee
set APP_LOGS=%APP_ROOT%\logs
set APP_BACKUPS=%APP_ROOT%\backups
set SRC=%~dp0..\03-source-code
set WHEELS=%~dp0wheels

if not exist "%APP_ROOT%" (
    echo No existing installation found at %APP_ROOT%. Run install-main-server.bat first.
    exit /b 1
)

echo.
echo ================================================================
echo   Balaji FeeHub  Repair Installation
echo ================================================================
echo   This will:
echo     1. Create a full pre-repair backup of the database + config
echo     2. Re-copy the backend + prebuilt frontend from this ZIP
echo     3. Re-install Python dependencies (offline if wheels present)
echo     4. Restart the services
echo   Your database, receipts and configuration are NEVER touched.
echo ================================================================
choice /C YN /N /M "Proceed? [Y/N] "
if errorlevel 2 exit /b 2

REM ---------- 1) Pre-repair backup ----------
mkdir "%APP_BACKUPS%" 2>nul
mkdir "%APP_LOGS%"    2>nul
for /f "tokens=1-3 delims=/- " %%a in ("%DATE%") do set DPART=%%c-%%b-%%a
for /f "tokens=1-3 delims=:." %%a in ("%TIME%") do set TPART=%%a-%%b-%%c
set TPART=!TPART: =0!
set BKP_DIR=%APP_BACKUPS%\pre-repair-!DPART!_!TPART!
mkdir "!BKP_DIR!" 2>nul
echo Creating pre-repair backup at !BKP_DIR! ...

where mongodump >nul 2>&1
if !ERRORLEVEL!==0 (
    mongodump --host 127.0.0.1:27017 --out "!BKP_DIR!\db" > "%APP_LOGS%\pre-repair-backup.log" 2>&1
    if !ERRORLEVEL! neq 0 (
        echo.
        echo ================================================================
        echo   REPAIR FAILED  --  automatic pre-repair backup failed
        echo   mongodump returned !ERRORLEVEL!.  See %APP_LOGS%\pre-repair-backup.log
        echo   Aborting to protect existing production data.
        echo ================================================================
        exit /b 3
    )
    echo   OK  Database dumped to !BKP_DIR!\db
) else (
    echo   WARN  mongodump not on PATH -- copying raw data files as fallback
    xcopy /E /Y /I /Q "%APP_ROOT%\mongodb\data" "!BKP_DIR!\raw-data" >nul
    echo   OK  Raw data copied to !BKP_DIR!\raw-data
)
if exist "%APP_ROOT%\backend\.env"  copy /Y "%APP_ROOT%\backend\.env"  "!BKP_DIR!\backend.env.bak"  >nul
if exist "%APP_ROOT%\frontend\.env" copy /Y "%APP_ROOT%\frontend\.env" "!BKP_DIR!\frontend.env.bak" >nul
echo   OK  Backup complete.

REM ---------- 2) Stop services (keep Mongo running for backup validity) ----------
echo Stopping frontend + backend services ...
net stop BalajiFeeHub-Frontend 2>nul
net stop BalajiFeeHub-Backend  2>nul

REM ---------- 3) Re-copy application source (database is NOT touched) ----------
echo Re-copying application source (database + backups are NOT touched) ...
xcopy /E /Y /I /Q "%SRC%\backend"  "%APP_ROOT%\backend"  >nul
if exist "%SRC%\frontend\build" (
    xcopy /E /Y /I /Q "%SRC%\frontend\build" "%APP_ROOT%\frontend\build" >nul
) else (
    xcopy /E /Y /I /Q "%SRC%\frontend" "%APP_ROOT%\frontend" >nul
)
if exist "%SRC%\version.json" copy /Y "%SRC%\version.json" "%APP_ROOT%\version.json" >nul

REM ---------- 4) Re-install Python dependencies (offline if possible) ----------
echo Re-installing Python dependencies ...
call "%APP_ROOT%\venv\Scripts\activate.bat"
if exist "%WHEELS%\*.whl" (
    python -m pip install --upgrade --no-index --find-links "%WHEELS%" pip 2>nul
    python -m pip install --no-index --find-links "%WHEELS%" -r "%APP_ROOT%\backend\requirements.txt"
) else (
    python -m pip install --upgrade pip >nul
    python -m pip install -r "%APP_ROOT%\backend\requirements.txt"
)
if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo   REPAIR FAILED  --  pip install returned %ERRORLEVEL%
    echo   Your database is safe at !BKP_DIR!\db
    echo   Services are stopped -- run this repair again after fixing.
    echo ================================================================
    exit /b 4
)
REM Hard dep verification
python -c "import fastapi, uvicorn, motor, pymongo, pydantic, jwt, bcrypt, cryptography, pandas, numpy, openpyxl, dotenv, requests"
if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo   REPAIR FAILED  --  dependency import verification failed
    echo   Your database is safe at !BKP_DIR!\db
    echo ================================================================
    exit /b 4
)

REM ---------- 5) Restart services ----------
echo Restarting services ...
net start BalajiFeeHub-Backend  2>nul & timeout /t 3 /nobreak >nul
net start BalajiFeeHub-Frontend 2>nul & timeout /t 2 /nobreak >nul

REM ---------- 6) Health check ----------
where curl >nul 2>&1 && (
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8001/api/version | findstr "200" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo.
        echo ================================================================
        echo   REPAIR FAILED  --  backend did not return HTTP 200 after restart
        echo   Your database is safe at !BKP_DIR!\db
        echo   Check services.msc and %APP_LOGS%\backend.err.log
        echo ================================================================
        exit /b 5
    )
)

echo.
echo ================================================================
echo   REPAIR SUCCESSFUL
echo ================================================================
echo   Application    : http://127.0.0.1:3000
echo   Pre-repair bkp : !BKP_DIR!
echo ================================================================
exit /b 0
