@echo off
setlocal
cd /d "%~dp0"
if /i "%~1"=="--native" goto native
docker compose up
exit /b %errorlevel%
:native
if not exist ".venv\Scripts\python.exe" (
  echo Run setup-windows.cmd --native first. See README_START_HERE.md.
  exit /b 1
)
".venv\Scripts\python.exe" -m scripts.lecturer_setup --run
exit /b %errorlevel%
