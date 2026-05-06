# 项目版本说明

本项目只维护 3 个 GitHub 仓库版本。

## 1. 私有版

目录：

`D:\Downloads\tencent-sheets-mysql-sync-private`

用途：

- 自己继续开发
- 保留内部迭代资料
- 保留项目记忆文件

包含：

- `PROJECT_MEMORY_RULES.md`
- `AGENT_MEMORY_LOG.md`
- 源码、前端、测试、文档、脚本

## 2. 公开版

目录：

`D:\Downloads\tencent-sheets-mysql-sync-public`

用途：

- 对外共享
- 不暴露项目记忆

移除：

- `PROJECT_MEMORY_RULES.md`
- `AGENT_MEMORY_LOG.md`
- `.env`

## 3. GitHub 精简版

目录：

`D:\Downloads\tencent-sheets-mysql-sync-github`

用途：

- 面向 GitHub 公开发布
- 只保留真正需要对外展示和运行的内容

保留：

- `app/`
- `frontend/`
- `migrations/`
- `scripts/`
- `tests/`
- `README.md`
- `OPERATIONS.md`
- `TROUBLESHOOTING.md`
- `API_REFERENCE.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `.env.example`
- `config.example.yaml`
- `docker-compose.metadata.yml`
- `requirements.txt`
- `pytest.ini`

## 4. 生成方式

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```

## 5. 维护原则

- 以后只更新这 3 个仓库
- Windows 和 Linux/macOS 脚本必须同步存在
- 公开仓库不得包含记忆文件、本地日志、缓存、虚拟环境和真实配置
