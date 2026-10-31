@echo off
setlocal
cd /d "%~dp0"

py -3 -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo Flask is not installed for Python 3.
    echo Install the project dependencies with:
    echo py -3 -m pip install -r requirements.txt
    pause
    exit /b 1
)

set "CHROME=chrome.exe"
set "ProgramFiles=C:\Program Files (x86)"
if defined ProgramFiles if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if defined ProgramFiles(x86) if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined CHROME for %%I in (chrome.exe) do set "CHROME=%%~$PATH:I"
if not defined CHROME (
    echo Google Chrome could not be found.
    pause
    exit /b 1
)

start "Schedule Creator Server" python "%~dp0scheduler.py"

powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(30); do { try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5000/' -TimeoutSec 1; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo The Schedule Creator did not start. Check the server window for errors.
    pause
    exit /b 1
)

start "" "%CHROME%" "http://127.0.0.1:5000/"
