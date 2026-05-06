$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"

Set-Location $frontendRoot

if (-not (Test-Path "node_modules")) {
    npm install
}

npm run dev -- --host 0.0.0.0 --port 5173
