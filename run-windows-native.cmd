@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup-windows-native.cmd first.
  exit /b 1
)
if not exist ".env" (
  echo Missing private configuration. Run setup-windows-native.cmd; preserve existing database files.
  exit /b 1
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m scripts.lecturer_setup --check
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -c "import pathlib,shutil,sys; expected=pathlib.Path.cwd()/'.venv/Scripts/fastapi.exe'; found=shutil.which('fastapi'); sys.exit(0 if found and pathlib.Path(found).resolve()==expected.resolve() else 1)"
if errorlevel 1 exit /b 1
echo Open http://127.0.0.1:8000/game . PostgreSQL must remain running.
fastapi dev main.py
exit /b %errorlevel%
