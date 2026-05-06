$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$runtime = python .\scripts\runtime_settings.py | ConvertFrom-Json

Set-Location $frontendRoot

if (-not (Test-Path "node_modules")) {
    npm install
}

$env:FRONTEND_HOST = $runtime.frontend_host
$env:FRONTEND_PORT = [string]$runtime.frontend_port
$env:FRONTEND_BACKEND_URL = $runtime.frontend_backend_url

npm run dev -- --host $runtime.frontend_host --port $runtime.frontend_port
