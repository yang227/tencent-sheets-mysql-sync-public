$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$runtime = python .\scripts\runtime_settings.py | ConvertFrom-Json

function Write-Ok($message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Write-Fail($message) {
    Write-Host "[FAIL] $message" -ForegroundColor Red
}

try {
    $pythonVersion = python --version 2>&1
    Write-Ok $pythonVersion
}
catch {
    Write-Fail "python is not available"
    exit 1
}

try {
    $nodeVersion = node --version 2>&1
    Write-Ok "Node.js $nodeVersion"
}
catch {
    Write-Warn "node is not available"
}

try {
    $dockerVersion = docker --version 2>&1
    Write-Ok $dockerVersion
}
catch {
    Write-Warn "docker is not available"
}

if (Test-Path ".env") {
    Write-Ok ".env exists"
}
else {
    Write-Warn ".env does not exist"
}

if (Test-Path "config.yaml") {
    Write-Ok "config.yaml exists"
}
else {
    Write-Warn "config.yaml does not exist"
}

if (Test-Path "frontend\\package.json") {
    Write-Ok "frontend package.json exists"
}
else {
    Write-Fail "frontend package.json is missing"
    exit 1
}

if (Test-Path "requirements.txt") {
    Write-Ok "requirements.txt exists"
}
else {
    Write-Fail "requirements.txt is missing"
    exit 1
}

try {
    $health = Invoke-RestMethod -Uri "http://$($runtime.app_url_host):$($runtime.app_port)/health" -TimeoutSec 3
    Write-Ok "backend health endpoint reachable: $($health.status)"
}
catch {
    Write-Warn "backend health endpoint is not reachable"
}

Write-Host "Deployment check completed."
