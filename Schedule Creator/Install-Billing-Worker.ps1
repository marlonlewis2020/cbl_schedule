param(
    [string]$PythonPath = (Get-Command python -ErrorAction Stop).Source,
    [string]$TaskName = 'CBL Schedule Creator Billing Worker Sandbox'
)

$ErrorActionPreference = 'Stop'
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$WorkerPath = Join-Path $PSScriptRoot 'billing_worker.py'
$LogPath = Join-Path $PSScriptRoot 'data\billing_worker.log'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task '$TaskName' already exists. Review it before replacing anything."
}

Push-Location $PSScriptRoot
try {
    & $PythonPath -c 'import cryptography, flask, psycopg, segno, filelock, requests, dotenv'
    if ($LASTEXITCODE -ne 0) {
        throw 'Install requirements.txt with this Python interpreter before registering the worker.'
    }
    Write-Output 'Worker dependencies verified.'
} finally {
    Pop-Location
}

$UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "-u `"$WorkerPath`" --log-file `"$LogPath`"" `
    -WorkingDirectory $PSScriptRoot
$Triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn -User $UserId)
)
$Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType S4U -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers `
    -Principal $Principal -Settings $Settings `
    -Description 'CBL sandbox billing worker: boot/logon startup, limited privileges, rotating logs and a single-worker lock.' `
    -ErrorAction Stop | Out-Null

if (-not (Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop)) {
    throw 'Task registration could not be verified.'
}

Write-Output "Registered '$TaskName' for the current Windows user without storing a password."
Write-Output 'Close foreground billing workers before starting the scheduled task.'
Write-Output "Start-ScheduledTask -TaskName '$TaskName'"