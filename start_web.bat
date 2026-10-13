@echo off
chcp 65001 >nul
title TruePixel Studio
echo ========================================================
echo   🎨 TruePixel Studio - AI 像素资产生成器
echo ========================================================
echo.
echo 正在启动本地服务并自动打开浏览器...
echo 网页地址: http://localhost:7860
echo.
cd /d "%~dp0"
python app.py
pause
