@echo off
cd /d "%~dp0"
python billing_worker.py
if errorlevel 1 (
    echo Billing worker stopped with an error. Check its output before restarting.
    pause
)
