@echo off
setlocal
cd /d "%~dp0"
if not exist "app-runtime\Mahjong.exe" (
  echo Incomplete package. Extract All from the verified complete Windows ZIP.
  exit /b 1
)
"%~dp0app-runtime\Mahjong.exe"
if errorlevel 1 (
  echo Startup failed. Read the message and private diagnostics; no fallback server was started.
  pause
  exit /b 1
)
