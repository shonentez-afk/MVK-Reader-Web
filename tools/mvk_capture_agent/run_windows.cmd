@echo off
setlocal
cd /d "%~dp0"
py -3 -m capture_agent gui
if errorlevel 1 pause