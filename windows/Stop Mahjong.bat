@echo off
setlocal
cd /d "%~dp0"
if not exist "app-runtime\Mahjong.exe" exit /b 1
"%~dp0app-runtime\Mahjong.exe" --stop
exit /b %errorlevel%
