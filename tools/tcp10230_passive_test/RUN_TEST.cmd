@echo off
setlocal
cd /d "%~dp0"
echo MVK01 TCP/10230 PASSIVE RECEIVE-ONLY TEST
echo Network adapter: Ethernet
echo [1] Device .84
echo [2] Device .83
set /p CHOICE=Device [1/2] (default 1):
if "%CHOICE%"=="" set "CHOICE=1"
if "%CHOICE%"=="1" set "HOST=10.13.42.84"
if "%CHOICE%"=="2" set "HOST=10.13.42.83"
if not defined HOST (
 echo Invalid choice.
 pause
 exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
 py -3 "%~dp0passive_test.py" --host %HOST% --adapter Ethernet --seconds 12 --max-mb 40
) else (
 python "%~dp0passive_test.py" --host %HOST% --adapter Ethernet --seconds 12 --max-mb 40
)
pause
