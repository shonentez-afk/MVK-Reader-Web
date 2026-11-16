@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-windows.txt pyinstaller
if errorlevel 1 goto failed
py -3 -m PyInstaller --clean --onefile --noconsole --collect-all frida --add-data "capture_agent/frida_trace.js:capture_agent" --name MVKCaptureAgent app_gui.py
if errorlevel 1 goto failed
py -3 -m PyInstaller --clean --onefile --console --collect-all frida --add-data "capture_agent/frida_trace.js:capture_agent" --name MVKCaptureMCP app_mcp.py
if errorlevel 1 goto failed
echo Build complete. See dist\MVKCaptureAgent.exe and dist\MVKCaptureMCP.exe
exit /b 0
:failed
echo Build failed.
exit /b 1