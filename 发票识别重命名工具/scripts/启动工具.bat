@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "PORT=27180"
set "URL=http://127.0.0.1:%PORT%/"

if not exist "runtime\win\node.exe" (
  echo [ERROR] Missing runtime\win\node.exe
  echo Please re-extract the whole tool folder and try again.
  pause
  exit /b 1
)

if not exist "app\server.js" (
  echo [ERROR] Missing app\server.js
  echo Please re-extract the whole tool folder and try again.
  pause
  exit /b 1
)

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%URL%api/ping' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
  echo Tool is already running, opening the page...
  start "" "%URL%"
  pause
  exit /b 0
)

echo Starting invoice rename tool...
"runtime\win\node.exe" "app\server.js" "%PORT%"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Tool exited with code %EXIT_CODE%.
echo If the page did not open, open this address in a browser: %URL%
pause
