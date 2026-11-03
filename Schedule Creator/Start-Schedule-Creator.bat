@echo off
setlocal
cd /d "%~dp0"

python -c "import cryptography, flask, psycopg, segno" >nul 2>nul
if errorlevel 1 (
    echo Application dependencies are not installed for the active Python interpreter.
    echo Install the project dependencies with:
    echo python -m pip install -r requirements.txt
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

set "SCHEDULE_CREATOR_PORT=5001"

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if not errorlevel 1 goto start_server
echo Port 5001 is already in use. Close the existing Schedule Creator server before starting this version.
echo The older server can return 404 for employee and BambooHR APIs while still appearing to run.
pause
exit /b 1

:start_server
start "Schedule Creator Server" python "%~dp0scheduler.py"

powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(30); do { try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5001/api/tenant-auth/state' -TimeoutSec 1; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo The updated Schedule Creator API did not respond. Check the server window for startup errors.
    pause
    exit /b 1
)

start "" "%CHROME%" "http://127.0.0.1:5001/"
