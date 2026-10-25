@echo off
cd /d "%~dp0"
py -m uvicorn server:app --host 0.0.0.0 --port 8080
pause
