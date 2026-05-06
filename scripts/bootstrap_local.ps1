$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

if (-not (Test-Path "config.yaml")) {
    Copy-Item "config.example.yaml" "config.yaml"
    Write-Host "Created config.yaml from config.example.yaml"
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt

$frontendRoot = Join-Path $projectRoot "frontend"
if (Test-Path $frontendRoot) {
    Push-Location $frontendRoot
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

Write-Host "Local bootstrap complete. Fill .env and config.yaml before starting the stack." -ForegroundColor Green
