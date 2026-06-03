@echo off
chcp 65001 > nul
REM 碳管师收资系统启动脚本
REM 端口被占用时自动切换到下一个可用端口

setlocal enabledelayedexpansion

REM 获取项目根目录（tantan/tantan/）
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM 标准化路径
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"

set "DEFAULT_PORT=8000"
set "MAX_PORT=8010"
set "PORT=%DEFAULT_PORT%"

REM 查找可用端口
:CHECK_PORT
netstat -ano 2>nul | findstr /r "^.*:%PORT%.*LISTENING$" > nul
if !errorlevel! equ 0 (
    if %PORT% lss %MAX_PORT% (
        echo 端口 %PORT% 已被占用，尝试 %PORT%+1 ...
        set /a PORT+=1
        goto CHECK_PORT
    ) else (
        echo 错误: 所有端口 (%DEFAULT_PORT%-%MAX_PORT%) 都被占用
        exit /b 1
    )
)

echo 使用端口: %PORT%

REM 激活虚拟环境
if exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%venv\Scripts\activate.bat"
) else (
    echo 警告: 虚拟环境不存在，使用系统Python
)

REM 设置 PYTHONPATH 让 tantan 包可被导入
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

echo 正在启动后端服务...
echo 访问地址: http://localhost:%PORT%
echo.

REM 从项目根目录运行 main.py
cd /d "%PROJECT_ROOT%"
python -m tantan.backend.main --port %PORT%