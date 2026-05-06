$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
