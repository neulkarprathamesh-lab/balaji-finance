@echo off
REM ================================================================
REM  Balaji FeeHub Client PC - post-install information
REM
REM  With Electron, all LAN discovery + Main-Server connection happen
REM  inside BalajiFeeHub.exe itself. This script is now purely
REM  informational - it prints where the desktop app was installed
REM  and how the user should launch it.
REM ================================================================
setlocal EnableExtensions

echo.
echo ================================================================
echo   Balaji FeeHub  Client Installer  v1.0
echo ================================================================
echo   The Balaji FeeHub desktop application has been installed.
echo.
echo   How to open it:
echo     - Double-click the "Balaji FeeHub" icon on your desktop, or
echo     - Open Start Menu -^> Balaji FeeHub
echo.
echo   The application will automatically find the Main Server on
echo   your school LAN. If auto-discovery fails, enter the Main
echo   Server IP in the connection screen and click Connect.
echo   Your successful IP is saved so you never re-enter it.
echo ================================================================
exit /b 0
