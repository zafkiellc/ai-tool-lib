@echo off
setlocal
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
set "PLAYWRIGHT_BROWSERS_PATH=%APP_DIR%browsers"
"%APP_DIR%node\node.exe" server.js
if errorlevel 1 (
  echo.
  echo [错误] 服务异常退出，请把上面的日志发给开发者。
  pause
)
endlocal
