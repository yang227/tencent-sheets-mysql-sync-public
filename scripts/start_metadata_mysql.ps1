$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$runtime = python .\scripts\runtime_settings.py | ConvertFrom-Json

$rootPassword = $env:METADATA_MYSQL_ROOT_PASSWORD
if ([string]::IsNullOrWhiteSpace($rootPassword) -and (Test-Path ".env")) {
    $rootPassword = (
        Get-Content ".env" |
        Where-Object { $_ -match '^METADATA_MYSQL_ROOT_PASSWORD=' } |
        Select-Object -First 1
    ) -replace '^METADATA_MYSQL_ROOT_PASSWORD=', ''
}

if ([string]::IsNullOrWhiteSpace($rootPassword) -or $rootPassword -eq "change_this_root_password") {
    throw "METADATA_MYSQL_ROOT_PASSWORD is required. Copy .env.example to .env and fill it with a real password."
}

$existing = docker ps -a --filter "name=^$($runtime.metadata_container_name)$" --format "{{.Names}}"

if ($existing -eq $runtime.metadata_container_name) {
    docker start $runtime.metadata_container_name | Out-Null
}
else {
    docker compose -f $runtime.metadata_compose_file up -d
}

if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or start container $($runtime.metadata_container_name)"
}

$ready = $false
for ($i = 0; $i -lt [Math]::Ceiling($runtime.metadata_ready_timeout / 2); $i++) {
    docker exec $runtime.metadata_container_name sh -lc "mysqladmin -h127.0.0.1 -u$($runtime.metadata_root_user) -p'$rootPassword' ping >/dev/null 2>&1" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    throw "Metadata MySQL container started, but MySQL did not become ready in time"
}

Get-Content migrations\init.sql -Raw | docker exec -i $runtime.metadata_container_name sh -lc "mysql -h127.0.0.1 -u$($runtime.metadata_root_user) -p'$rootPassword' $($runtime.metadata_database)"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply migrations/init.sql"
}

Get-Content migrations\add_config_tables.sql -Raw | docker exec -i $runtime.metadata_container_name sh -lc "mysql -h127.0.0.1 -u$($runtime.metadata_root_user) -p'$rootPassword' $($runtime.metadata_database)"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply migrations/add_config_tables.sql"
}

Write-Host "Metadata MySQL is ready on $($runtime.metadata_host):$($runtime.metadata_port)" -ForegroundColor Green
