@echo off
cd /d "%~dp0"
py -m uvicorn collector.service:app --host 127.0.0.1 --port 8091
pause
