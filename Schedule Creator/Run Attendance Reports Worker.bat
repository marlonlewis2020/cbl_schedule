@echo off
cd /d "%~dp0"
python report_worker.py
if errorlevel 1 (
    echo Attendance report worker stopped with an error. Check its output before restarting.
    pause
)
