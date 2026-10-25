@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo MVK01 TCP/10230 PASSIVE RECEIVE-ONLY TEST
echo NO APPLICATION COMMANDS ARE SENT
 echo ============================================
echo.
echo [1] 10.13.42.84
echo [2] 10.13.42.83
set /p CHOICE=Select device [1/2] (default 1): 
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
  py -3 "%~dp0passive_test.py" --host %HOST% --seconds 12 --max-mb 40
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3 was not found. Install Python or run from an existing Python environment.
    pause
    exit /b 1
  )
  python "%~dp0passive_test.py" --host %HOST% --seconds 12 --max-mb 40
)
echo.
echo Save the results folder and, if captured, the Wireshark PCAPNG.
pause
