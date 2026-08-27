@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM ============================================================
REM  抽卡建议分析器 · 启动器
REM  优先用 VBS（隐藏窗口 + 托盘版 launcher.py）；
REM  若 VBS 不可用则退回 Python 直启 backend\server.py。
REM  注意：此前打包的 GachaAdvisor.exe 存在逻辑错误，已不再使用。
REM  便携版：若存在 runtime\python 内置运行时则优先使用（无需安装 Python）。
REM ============================================================

IF EXIST "start.vbs" (
  echo 启动 VBS 启动器（隐藏窗口 + 托盘）...
  start "" wscript "start.vbs"
  goto :eof
)

REM --- 退回 Python 直启：定位 python（优先内置运行时） ---
set "PY="
if exist "runtime\python\python.exe" (
  set "PY=runtime\python\python.exe"
) else if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
  set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
) else (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  where python3 >nul 2>nul && set "PY=python3"
)
if not defined PY (
  echo Python not found. 请安装 Python 3.10+ 或放入 PATH，或使用 WorkBuddy 托管运行时。
  pause
  exit /b 1
)

echo Using Python: %PY%
echo Starting gacha-advisor on http://localhost:8787 ...
start "gacha-advisor" cmd /k "%PY% backend\server.py"
timeout /t 2 >nul
start "" http://localhost:8787
