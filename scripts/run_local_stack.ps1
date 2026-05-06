param(
    [switch]$WithFrontend
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

& (Join-Path $PSScriptRoot "start_metadata_mysql.ps1")

$backendCommand = "Set-Location '$projectRoot'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand

if ($WithFrontend) {
    $frontendRoot = Join-Path $projectRoot "frontend"
    $frontendCommand = "Set-Location '$frontendRoot'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev -- --host 0.0.0.0 --port 5173"
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand
}

Write-Host "Backend started at http://127.0.0.1:8083" -ForegroundColor Green
if ($WithFrontend) {
    Write-Host "Frontend dev server started at http://127.0.0.1:5173" -ForegroundColor Green
}
