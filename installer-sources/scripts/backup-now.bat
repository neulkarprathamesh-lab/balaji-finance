@echo off
REM ================================================================
REM  Balaji FeeHub - Manual Backup
REM  Creates a full mongodump into %APP_ROOT%\backups\manual-<timestamp>
REM  Called from Start Menu > Balaji FeeHub > Backup
REM ================================================================
setlocal EnableExtensions EnableDelayedExpansion

set APP_ROOT=C:\balaji-fee
set APP_BACKUPS=%APP_ROOT%\backups
set APP_LOGS=%APP_ROOT%\logs

if not exist "%APP_ROOT%\mongodb\data\WiredTiger" (
    echo No Balaji FeeHub installation detected at %APP_ROOT%.
    echo Nothing to back up.
    pause
    exit /b 1
)

for /f "tokens=1-3 delims=/- " %%a in ("%DATE%") do set DPART=%%c-%%b-%%a
for /f "tokens=1-3 delims=:." %%a in ("%TIME%") do set TPART=%%a-%%b-%%c
set TPART=!TPART: =0!
set BKP_DIR=%APP_BACKUPS%\manual-!DPART!_!TPART!
mkdir "!BKP_DIR!" 2>nul

echo.
echo ================================================================
echo   Balaji FeeHub  .  Manual Backup
echo ================================================================
echo   Destination: !BKP_DIR!
echo.

where mongodump >nul 2>&1
if !ERRORLEVEL!==0 (
    mongodump --host 127.0.0.1:27017 --out "!BKP_DIR!\db" > "%APP_LOGS%\manual-backup.log" 2>&1
    if !ERRORLEVEL! neq 0 (
        echo   FAIL  mongodump returned !ERRORLEVEL!  --  see %APP_LOGS%\manual-backup.log
        pause
        exit /b 2
    )
    echo   OK    Database dumped to !BKP_DIR!\db
) else (
    echo   WARN  mongodump not on PATH  --  copying raw data files as fallback
    xcopy /E /Y /I /Q "%APP_ROOT%\mongodb\data" "!BKP_DIR!\raw-data" >nul
    echo   OK    Raw data copied to !BKP_DIR!\raw-data
)

if exist "%APP_ROOT%\backend\.env"  copy /Y "%APP_ROOT%\backend\.env"  "!BKP_DIR!\backend.env.bak"  >nul
if exist "%APP_ROOT%\frontend\.env" copy /Y "%APP_ROOT%\frontend\.env" "!BKP_DIR!\frontend.env.bak" >nul

echo.
echo ================================================================
echo   BACKUP SUCCESSFUL
echo   Location: !BKP_DIR!
echo ================================================================
pause
exit /b 0
