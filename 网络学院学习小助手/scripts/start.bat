@echo off
chcp 65001 >nul
title 网络学院学习小助手
cd /d "%~dp0"

set "NODE_EXE=%~dp0node\node.exe"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers"
set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

if not exist "%NODE_EXE%" (
  echo [错误] 未找到内置 Node.js（node\node.exe），请完整解压 网络学院学习小助手-windows.zip。
  pause
  exit /b 1
)

if not exist "%~dp0node_modules\express" (
  echo [错误] 未找到内置依赖（node_modules），请完整解压 网络学院学习小助手-windows.zip。
  pause
  exit /b 1
)

rem 浏览器：内置 Chromium 或 系统 Edge 任一存在即可（优先使用系统 Edge，包体更小）
if not exist "%PLAYWRIGHT_BROWSERS_PATH%\chromium-1234\chrome-win64\chrome.exe" (
  if not exist "%EDGE_EXE%" (
    echo [错误] 未找到内置 Chromium，且系统未安装 Edge。
    echo        请完整解压 网络学院学习小助手-windows.zip，或确保系统装有 Edge 浏览器。
    pause
    exit /b 1
  )
)

if exist "data\port.txt" del /q "data\port.txt" >nul 2>nul

echo [1/1] 正在启动服务（免安装、离线运行）...
start "网络学院学习小助手服务" cmd /k ""%~dp0run-server.cmd""

set PORT=3000
set /a WAITED=0
:waitport
if exist "data\port.txt" (
  set /p PORT=<data\port.txt
  goto open
)
set /a WAITED+=1
if %WAITED% GEQ 30 goto open
ping -n 2 127.0.0.1 >nul
goto waitport

:open
start "" "http://127.0.0.1:%PORT%"
echo 服务已启动，关闭弹出的服务窗口即可停止。
exit /b 0
