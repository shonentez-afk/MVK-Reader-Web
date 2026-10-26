@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
where py >nul 2>nul
if not errorlevel 1 (
 py -3 "%~dp0start_menu.py"
 goto done
)
where python >nul 2>nul
if not errorlevel 1 (
 python "%~dp0start_menu.py"
 goto done
)
echo Python 3 not found.
:done
pause
endlocal
