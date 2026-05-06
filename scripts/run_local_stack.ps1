param(
    [switch]$WithFrontend
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$runtime = python .\scripts\runtime_settings.py | ConvertFrom-Json

& (Join-Path $PSScriptRoot "start_metadata_mysql.ps1")

$backendCommand = "Set-Location '$projectRoot'; python -m uvicorn app.main:app --host $($runtime.app_host) --port $($runtime.app_port) --reload"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand

if ($WithFrontend) {
    $frontendRoot = Join-Path $projectRoot "frontend"
    $frontendCommand = "`$env:FRONTEND_HOST='$($runtime.frontend_host)'; `$env:FRONTEND_PORT='$($runtime.frontend_port)'; `$env:FRONTEND_BACKEND_URL='$($runtime.frontend_backend_url)'; Set-Location '$frontendRoot'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev -- --host $($runtime.frontend_host) --port $($runtime.frontend_port)"
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand
}

Write-Host "Backend started at http://$($runtime.app_url_host):$($runtime.app_port)" -ForegroundColor Green
if ($WithFrontend) {
    Write-Host "Frontend dev server started at http://$($runtime.frontend_url_host):$($runtime.frontend_port)" -ForegroundColor Green
}
