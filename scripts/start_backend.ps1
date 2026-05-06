$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$runtime = python .\scripts\runtime_settings.py | ConvertFrom-Json
python -m uvicorn app.main:app --host $runtime.app_host --port $runtime.app_port --reload
