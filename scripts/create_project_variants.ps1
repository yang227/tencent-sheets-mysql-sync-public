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
    "server8090.out.log",
    "server5173.err.log",
    "server5173.out.log"
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
    "PROJECT_VARIANTS.md",
    "pytest.ini",
    "README.md",
    "requirements.txt",
    "TROUBLESHOOTING.md"
)

$githubKeepDirectories = @(
    "app",
    "frontend",
    "migrations",
    "scripts",
    "tests"
)

function Reset-TargetDirectory {
    param(
        [string]$Path
    )

    if (Test-Path $Path) {
        if (Test-Path (Join-Path $Path ".git")) {
            Get-ChildItem -LiteralPath $Path -Force | Where-Object { $_.Name -ne ".git" } | ForEach-Object {
                Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
                    try {
                        $_.IsReadOnly = $false
                    }
                    catch {
                    }
                }
                try {
                    $_.IsReadOnly = $false
                }
                catch {
                }
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
            return
        }

        Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $_.IsReadOnly = $false
            }
            catch {
            }
        }
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Copy-DirectoryTree {
    param(
        [string]$SourcePath,
        [string]$DestinationPath,
        [string[]]$ExcludeDirs = @(),
        [string[]]$ExcludeFiles = @()
    )

    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null

    $arguments = @(
        $SourcePath,
        $DestinationPath,
        "/E",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NC",
        "/NS",
        "/NP"
    )

    if ($ExcludeDirs.Count -gt 0) {
        $arguments += "/XD"
        $arguments += $ExcludeDirs
    }

    if ($ExcludeFiles.Count -gt 0) {
        $arguments += "/XF"
        $arguments += $ExcludeFiles
    }

    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed for $SourcePath"
    }
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
        if ($_.PSIsContainer) {
            Copy-DirectoryTree -SourcePath $_.FullName -DestinationPath $destination -ExcludeDirs $commonExcludeDirs -ExcludeFiles $allExcludeFiles
        }
        else {
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }
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
        if (Test-Path $sourcePath) {
            Copy-DirectoryTree -SourcePath $sourcePath -DestinationPath (Join-Path $TargetPath $dirName) -ExcludeDirs $commonExcludeDirs -ExcludeFiles ($commonExcludeFiles + $publicExcludeFiles)
        }
    }

    Remove-ExcludedContent -TargetPath $TargetPath -ExcludeFiles ($commonExcludeFiles + $publicExcludeFiles)
}

Copy-ProjectVariant -TargetPath $privateTarget
Copy-ProjectVariant -TargetPath $publicTarget -ExtraExcludeFiles $publicExcludeFiles
Copy-GitHubVariant -TargetPath $githubTarget

$privateReadme = @"
# 私有版说明
这是面向你自己持续开发和协作的私有项目版本。

特点：
- 保留项目记忆文件
- 保留内部过程文档
- 适合继续迭代、排查和补充验证记录

包含的记忆文件：
- PROJECT_MEMORY_RULES.md
- AGENT_MEMORY_LOG.md
"@

$publicReadme = @"
# 公开版说明
这是面向公共分发或公开仓库的项目版本。

特点：
- 不包含任何项目记忆文件
- 不包含本地 `.env`
- 不包含本地缓存、日志和虚拟环境

明确移除：
- PROJECT_MEMORY_RULES.md
- AGENT_MEMORY_LOG.md
- .env
"@

$githubReadme = @"
# GitHub 精简版说明
这是面向 GitHub 发布的精简项目版本。

特点：
- 只保留源码、前端、测试、迁移、部署脚本和对外文档
- 不包含任何项目记忆文件
- 不包含本地 `.env`
- 不包含内部过程报告、交付草稿和杂项脚本
"@

Set-Content -LiteralPath (Join-Path $privateTarget "VARIANT.md") -Value $privateReadme -Encoding UTF8
Set-Content -LiteralPath (Join-Path $publicTarget "VARIANT.md") -Value $publicReadme -Encoding UTF8
Set-Content -LiteralPath (Join-Path $githubTarget "VARIANT.md") -Value $githubReadme -Encoding UTF8

Write-Host "Created private project: $privateTarget" -ForegroundColor Green
Write-Host "Created public project:  $publicTarget" -ForegroundColor Green
Write-Host "Created GitHub project:  $githubTarget" -ForegroundColor Green
