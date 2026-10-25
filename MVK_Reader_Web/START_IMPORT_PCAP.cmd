@echo off
cd /d "%~dp0"
if "%~1"=="" (echo Usage: START_IMPORT_PCAP.cmd "capture.pcapng" 192.0.2.83 & pause & exit /b 1)
python -m signal_bridge.import_capture "%~1" --device "%~2" --output signal_data
pause
