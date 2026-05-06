$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

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

$existing = docker ps -a --filter "name=^tencent-sync-metadata-mysql$" --format "{{.Names}}"

if ($existing -eq "tencent-sync-metadata-mysql") {
    docker start tencent-sync-metadata-mysql | Out-Null
}
else {
    docker compose -f docker-compose.metadata.yml up -d
}

if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or start container tencent-sync-metadata-mysql"
}

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    docker exec tencent-sync-metadata-mysql sh -lc "mysqladmin -h127.0.0.1 -uroot -p'$rootPassword' ping >/dev/null 2>&1" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    throw "Metadata MySQL container started, but MySQL did not become ready in time"
}

Get-Content migrations\init.sql -Raw | docker exec -i tencent-sync-metadata-mysql sh -lc "mysql -h127.0.0.1 -uroot -p'$rootPassword' tencent_sheets_sync"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply migrations/init.sql"
}

Get-Content migrations\add_config_tables.sql -Raw | docker exec -i tencent-sync-metadata-mysql sh -lc "mysql -h127.0.0.1 -uroot -p'$rootPassword' tencent_sheets_sync"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply migrations/add_config_tables.sql"
}

Write-Host "Metadata MySQL is ready on 127.0.0.1:13306" -ForegroundColor Green
