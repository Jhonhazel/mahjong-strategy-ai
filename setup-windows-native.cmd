@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Install CPython 3.12 x64 with the Python launcher, then retry.
  exit /b 1
)
echo Native Windows setup: Python environment, pinned dependencies, original model, local PostgreSQL.
py -3.12 -m scripts.lecturer_setup
if errorlevel 1 exit /b 1
call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -c "import pathlib,shutil,sys; expected=pathlib.Path.cwd()/'.venv/Scripts/fastapi.exe'; found=shutil.which('fastapi'); sys.exit(0 if found and pathlib.Path(found).resolve()==expected.resolve() else 1)"
if errorlevel 1 (
  echo Project FastAPI executable was not activated. Setup did not complete.
  exit /b 1
)
echo Ready in this CMD session. Run: fastapi dev main.py
echo Open http://127.0.0.1:8000/game . Next time: run-windows-native.cmd
exit /b 0
