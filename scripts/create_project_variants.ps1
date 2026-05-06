$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $PSScriptRoot
$parentDir = Split-Path -Parent $sourceRoot

$privateTarget = Join-Path $parentDir "tencent-sheets-mysql-sync-private"
$publicTarget = Join-Path $parentDir "tencent-sheets-mysql-sync-public"
$githubTarget = Join-Path $parentDir "tencent-sheets-mysql-sync-github"

$commonExcludeDirs = @(
    ".git",
    ".venv",
    ".pytest_cache",
    ".workbuddy",
    "__pycache__",
    "node_modules"
)

$commonExcludeFiles = @(
    ".coverage",
    "coverage.json",
    "server.err.log",
    "server.out.log",
    "server8083.err.log",
    "server8083.out.log",
    "server8090.err.log",
    "server8090.out.log"
)

$publicExcludeFiles = @(
    "PROJECT_MEMORY_RULES.md",
    "AGENT_MEMORY_LOG.md",
    ".env"
)

$githubKeepTopLevelFiles = @(
    ".env.example",
    ".gitignore",
    "API_REFERENCE.md",
    "CHANGELOG.md",
    "config.example.yaml",
    "CONTRIBUTING.md",
    "docker-compose.metadata.yml",
    "OPERATIONS.md",
    "pytest.ini",
    "README.md",
    "requirements.txt",
    "TROUBLESHOOTING.md"
)

$githubKeepDirectories = @(
    "app",
    "frontend",
    "migrations",
    "tests"
)

function Reset-TargetDirectory {
    param(
        [string]$Path
    )

    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Remove-ExcludedContent {
    param(
        [string]$TargetPath,
        [string[]]$ExcludeFiles
    )

    foreach ($excludeDir in $commonExcludeDirs) {
        Get-ChildItem -LiteralPath $TargetPath -Directory -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq $excludeDir } |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    foreach ($excludeFile in $ExcludeFiles) {
        Get-ChildItem -LiteralPath $TargetPath -File -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq $excludeFile } |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Copy-ProjectVariant {
    param(
        [string]$TargetPath,
        [string[]]$ExtraExcludeFiles = @()
    )

    Reset-TargetDirectory -Path $TargetPath
    $allExcludeFiles = $commonExcludeFiles + $ExtraExcludeFiles

    Get-ChildItem -LiteralPath $sourceRoot -Force | ForEach-Object {
        if ($commonExcludeDirs -contains $_.Name) {
            return
        }

        if ($allExcludeFiles -contains $_.Name) {
            return
        }

        $destination = Join-Path $TargetPath $_.Name
        Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
    }

    Remove-ExcludedContent -TargetPath $TargetPath -ExcludeFiles $allExcludeFiles
}

function Copy-GitHubVariant {
    param(
        [string]$TargetPath
    )

    Reset-TargetDirectory -Path $TargetPath

    foreach ($fileName in $githubKeepTopLevelFiles) {
        $sourcePath = Join-Path $sourceRoot $fileName
        if (Test-Path $sourcePath) {
            Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $TargetPath $fileName) -Force
        }
    }

    foreach ($dirName in $githubKeepDirectories) {
        $sourcePath = Join-Path $sourceRoot $dirName
        if (-not (Test-Path $sourcePath)) {
            continue
        }

        Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $TargetPath $dirName) -Recurse -Force
    }

    $scriptsTarget = Join-Path $TargetPath "scripts"
    New-Item -ItemType Directory -Path $scriptsTarget | Out-Null
    $startupScript = Join-Path $sourceRoot "scripts\start_metadata_mysql.ps1"
    if (Test-Path $startupScript) {
        Copy-Item -LiteralPath $startupScript -Destination (Join-Path $scriptsTarget "start_metadata_mysql.ps1") -Force
    }

    Remove-ExcludedContent -TargetPath $TargetPath -ExcludeFiles ($commonExcludeFiles + $publicExcludeFiles)
}

Copy-ProjectVariant -TargetPath $privateTarget
Copy-ProjectVariant -TargetPath $publicTarget -ExtraExcludeFiles $publicExcludeFiles
Copy-GitHubVariant -TargetPath $githubTarget

$privateReadme = @"
# 私有版说明

这是面向你自己持续开发和协作的私有项目版本。

特征：
- 保留项目记忆文件
- 保留内部过程文档
- 适合继续迭代、排查、补充验证记录

包含的记忆文件：
- PROJECT_MEMORY_RULES.md
- AGENT_MEMORY_LOG.md
"@

$publicReadme = @"
# 公开版说明

这是面向公共分发或公开仓库的项目版本。

特征：
- 不包含任何项目记忆文件
- 不包含本地 .env
- 不包含本地缓存、日志、虚拟环境

明确移除：
- PROJECT_MEMORY_RULES.md
- AGENT_MEMORY_LOG.md
- .env
"@

$githubReadme = @"
# GitHub 公开版说明

这是面向 GitHub 发布的精简版项目。

特征：
- 只保留源码、前端、测试、迁移、必要脚本与对外文档
- 不包含任何记忆文件
- 不包含本地 .env
- 不包含内部过程报告、迭代记录、交付草稿和杂项脚本
"@

Set-Content -LiteralPath (Join-Path $privateTarget "VARIANT.md") -Value $privateReadme -Encoding UTF8
Set-Content -LiteralPath (Join-Path $publicTarget "VARIANT.md") -Value $publicReadme -Encoding UTF8
Set-Content -LiteralPath (Join-Path $githubTarget "VARIANT.md") -Value $githubReadme -Encoding UTF8

Write-Host "Created private project: $privateTarget" -ForegroundColor Green
Write-Host "Created public project:  $publicTarget" -ForegroundColor Green
Write-Host "Created GitHub project:  $githubTarget" -ForegroundColor Green
