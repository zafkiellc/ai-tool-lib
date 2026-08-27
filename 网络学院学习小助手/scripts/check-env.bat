@echo off
chcp 65001 >nul
title 网络学院学习小助手 环境检查
cd /d "%~dp0"

echo === 网络学院学习小助手 环境检查 ===
echo.
echo 目录: %~dp0

set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

if exist "node\node.exe" (
  echo Node.exe: 存在
) else (
  echo Node.exe: 缺失
)

if exist "node_modules\express" (
  echo 运行依赖: 存在
) else (
  echo 运行依赖: 缺失
)

if exist "browsers\chromium-1234\chrome-win64\chrome.exe" (
  echo 内置 Chromium: 存在
) else (
  echo 内置 Chromium: 未打包（可减包，改用系统浏览器）
)

if exist "%EDGE_EXE%" (
  echo 系统 Edge: 存在
) else (
  echo 系统 Edge: 未检测到
)

echo 浏览器可用性: 内置 Chromium 或 系统 Edge 任一存在即可。

if exist "data\tasks.json" (
  echo 任务配置: 存在
) else (
  echo 任务配置: 缺失
)

echo.
echo Node、运行依赖、任务配置必须“存在”；浏览器只需内置 Chromium 或 系统 Edge 任一可用。
echo 检查通过后，先运行 smoke-test.cmd，再双击 start.bat 启动。
pause
