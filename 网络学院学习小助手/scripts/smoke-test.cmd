@echo off
chcp 65001 >nul
title 网络学院学习小助手 浏览器自检
cd /d "%~dp0"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers"
echo 正在测试内置浏览器，请稍候...
"%~dp0node\node.exe" smoke-test.mjs
if errorlevel 1 (
  echo.
  echo [错误] 浏览器自检失败，请把上面日志发出来。
) else (
  echo.
  echo [成功] 内置浏览器可以正常启动。
)
pause
