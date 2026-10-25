@echo off
cd /d "%~dp0"
py -3 probe_fc03.py --host 10.13.42.83 --confirm-read --output calibration_83.json
pause
