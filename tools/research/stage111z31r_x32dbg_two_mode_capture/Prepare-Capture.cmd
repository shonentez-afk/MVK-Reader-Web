@echo off
REM Only prepares one unique offline folder. Does not run the debugger.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-Capture.ps1" -Adc 4 -N 262144 -SpectrumType 2
if errorlevel 1 (
 echo Capture preparation failed. Read the error above.
 pause
 exit /b 1
)
pause
