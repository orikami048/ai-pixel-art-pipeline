@echo off
chcp 65001 >nul
title TruePixel Studio
echo ========================================================
echo   TruePixel Studio - AI 像素资产生成器
echo ========================================================
echo.

powershell -Command "$c = Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue; if ($c) { Start-Process 'http://127.0.0.1:7860/'; exit 0 } else { exit 1 }"
if %ERRORLEVEL% equ 0 (
    echo 检测到服务已在运行，已在浏览器打开 http://127.0.0.1:7860/
    timeout /t 2 >nul
    exit /b 0
)

echo 正在启动本地服务：http://127.0.0.1:7860/
echo [注意] 使用期间请勿关闭此窗口（可以最小化）
echo.
cd /d "%~dp0"
python -m truepixel serve
pause
