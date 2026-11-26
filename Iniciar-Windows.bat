@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  start "Imovance" http://localhost:8000
  py -3 app.py
) else (
  start "Imovance" http://localhost:8000
  python app.py
)
pause
