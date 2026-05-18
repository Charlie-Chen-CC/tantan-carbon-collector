@echo off
chcp 65001 > nul

echo ========================================
echo   Tantan System Stop
echo ========================================
echo.

echo [Backend] Stopping backend services...
taskkill /F /FI "WINDOWTITLE eq Backend-*" 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":800" ^| findstr LISTENING') do (
    for /f "tokens=1" %%b in ('echo %%a') do taskkill /F /PID %%b 2>nul
)

echo [Frontend] Stopping frontend services...
taskkill /F /FI "WINDOWTITLE eq Frontend-*" 2>nul
taskkill /F /IM node.exe /FI "WINDOWTITLE eq Next*" 2>nul

echo.
echo ========================================
echo   All services stopped
echo ========================================
pause