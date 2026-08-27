@echo off
pushd "%~dp0"

if not exist python.exe (
    echo [ERROR] python.exe not found in this folder.
    echo Folder: %CD%
    pause
    exit /b 1
)

echo Starting in DEBUG mode (console window stays open)...
echo Folder: %CD%
python.exe server.py
pause
