@echo off
setlocal
cd /d "%~dp0"
if /i "%~1"=="--native" goto native
if not defined MAHJONG_WEB_PORT set "MAHJONG_WEB_PORT=8000"
where docker >nul 2>&1
if errorlevel 1 goto docker_missing
docker info >nul 2>&1
if errorlevel 1 goto docker_missing
docker compose build web db
if errorlevel 1 exit /b 1
if not exist ".local\compose-secrets" mkdir ".local\compose-secrets"
docker compose --profile tools run --rm --no-deps bootstrap
if errorlevel 1 exit /b 1
docker compose up -d --wait
if errorlevel 1 exit /b 1
echo Setup OK. Open http://127.0.0.1:%MAHJONG_WEB_PORT%/ . Next time run run-windows.cmd.
exit /b 0
:native
where py >nul 2>&1
if errorlevel 1 goto python_missing
py -3.12 -m scripts.lecturer_setup
exit /b %errorlevel%
:docker_missing
echo Docker Desktop with Linux containers must be installed and running. See README_START_HERE.md.
exit /b 1
:python_missing
echo Native mode needs 64-bit CPython3.12, C++ build tools and local PostgreSQL. See README_START_HERE.md.
exit /b 1
