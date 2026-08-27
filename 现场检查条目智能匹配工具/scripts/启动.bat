@echo off
pushd "%~dp0"
rem 由 VBS 静默启动（无命令行窗口，仅在系统托盘显示图标）。
rem 直接双击「启动.vbs」效果一致且更干净；本 bat 作为兼容入口。
start "" wscript "%~dp0启动.vbs" >nul 2>&1
exit
