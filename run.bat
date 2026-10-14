@echo off
rem Launch PyLocal Studio (Windows). No internet and no pip install needed.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 backend\server.py & goto :end)
where python >nul 2>nul && (python backend\server.py & goto :end)
echo Python 3.8+ not found. Install it from https://www.python.org/downloads/ (tick "Add to PATH").
:end
pause
