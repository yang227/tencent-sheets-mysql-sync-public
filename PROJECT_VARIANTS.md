# 项目版本说明

当前项目只维护 3 个 GitHub 仓库版本，不再扩散更多变体。

## 1. 私有版

目录：

`D:\Downloads\tencent-sheets-mysql-sync-private`

仓库：

`yang227/tencent-sheets-mysql-sync-private`

用途：

- 面向你自己的持续开发
- 保留内部迭代资料
- 保留项目级记忆文件

包含：

- `PROJECT_MEMORY_RULES.md`
- `AGENT_MEMORY_LOG.md`
- 源码、前端、测试、文档、脚本

## 2. 公开版

目录：

`D:\Downloads\tencent-sheets-mysql-sync-public`

仓库：

`yang227/tencent-sheets-mysql-sync-public`

用途：

- 面向外部公开共享
- 允许保留完整项目结构
- 不暴露项目记忆和本地敏感配置

明确移除：

- `PROJECT_MEMORY_RULES.md`
- `AGENT_MEMORY_LOG.md`
- `.env`

## 3. GitHub 精简版

目录：

`D:\Downloads\tencent-sheets-mysql-sync-github`

仓库：

`yang227/tencent-sheets-mysql-sync-github`

用途：

- 面向 GitHub 展示和分发
- 只保留真正适合公开发布的文件

保留范围：

- `app/`
- `frontend/`
- `migrations/`
- `scripts/`
- `tests/`
- `.dockerignore`
- `.env.example`
- `.gitignore`
- `API_REFERENCE.md`
- `CHANGELOG.md`
- `config.example.yaml`
- `CONTRIBUTING.md`
- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.metadata.yml`
- `OPERATIONS.md`
- `PROJECT_VARIANTS.md`
- `pytest.ini`
- `README.md`
- `requirements.txt`
- `TROUBLESHOOTING.md`

明确不保留：

- 项目记忆文件
- 本地 `.env`
- 本地日志
- 虚拟环境
- 内部迭代报告
- 临时修复脚本
- 交付草稿类文件

## 4. 生成方式

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```

## 5. 维护原则

- 以后只更新这 3 个仓库
- Windows 与 Linux / macOS 脚本必须同步存在
- Docker 相关文件在公开版和 GitHub 精简版中都必须保留
- 面向公开发布的版本不得包含项目记忆、本地缓存、真实敏感配置
