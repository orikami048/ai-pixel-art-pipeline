@echo off
chcp 65001 >nul
title TruePixel Studio
echo ========================================================
echo   🎨 TruePixel Studio - AI 像素资产生成器
echo ========================================================
echo.
echo 正在检查本地服务状态...

powershell -Command "$c = Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue; if ($c) { Start-Process 'http://127.0.0.1:7860/'; exit 0 } else { exit 1 }"
if %ERRORLEVEL% equ 0 (
    echo.
    echo ✅ 检测到 TruePixel 本地服务已在后台运行！
    echo 🌐 已自动在浏览器中打开: http://127.0.0.1:7860/
    echo ⏳ 本窗口将在 2 秒后自动退出...
    timeout /t 2 >nul
    exit /b 0
)

echo.
echo 正在启动本地 Python 服务并打开浏览器...
echo 🌐 网页地址: http://127.0.0.1:7860/
echo ⚠️  [注意] 使用期间请勿关闭此窗口（可以将其最小化）！
echo.
cd /d "%~dp0"
python app.py
pause
