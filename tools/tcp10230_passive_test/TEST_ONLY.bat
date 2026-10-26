@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
where py >nul 2>nul
if not errorlevel 1 (
 py -3 -m unittest test_mvk_capture_diagnostic.py -v
 goto done
)
where python >nul 2>nul
if not errorlevel 1 (
 python -m unittest test_mvk_capture_diagnostic.py -v
 goto done
)
echo Python 3 not found.
:done
pause
endlocal
