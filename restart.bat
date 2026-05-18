@echo off
chcp 65001 > nul

echo ========================================
echo   Tantan System Restart
echo ========================================
echo.

echo [Step 1] Stopping existing services...

taskkill /F /FI "WINDOWTITLE eq Backend-*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Frontend-*" 2>nul

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":800" ^| findstr LISTENING') do (
    for /f "tokens=1" %%b in ('echo %%a') do (
        taskkill /F /PID %%b 2>nul
    )
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":300" ^| findstr LISTENING') do (
    for /f "tokens=1" %%b in ('echo %%a') do (
        taskkill /F /PID %%b 2>nul
    )
)

echo [Step 2] Services stopped
echo.

C:\Windows\System32\timeout.exe /t 2 /nobreak > nul

echo [Step 3] Starting services...
call "%~dp0start.bat"