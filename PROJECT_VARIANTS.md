# 项目拆分说明

本项目支持拆分为三套目录。

## 1. 私有版

目录名：

```text
tencent-sheets-mysql-sync-private
```

用途：

- 面向你自己继续开发
- 保留项目级记忆
- 保留内部过程记录

保留文件：

- `PROJECT_MEMORY_RULES.md`
- `AGENT_MEMORY_LOG.md`
- `.env`

## 2. 公开版

目录名：

```text
tencent-sheets-mysql-sync-public
```

用途：

- 面向公共仓库
- 面向外部演示或分发

公开版约束：

- 不包含任何记忆文件
- 不包含 `.env`
- 不包含本地日志、缓存、虚拟环境

明确移除：

- `PROJECT_MEMORY_RULES.md`
- `AGENT_MEMORY_LOG.md`
- `.env`

## 3. GitHub 精简公开版

目录名：

```text
tencent-sheets-mysql-sync-github
```

用途：

- 面向 GitHub 正式发布
- 只保留真正适合公开仓库的文件

保留内容：

- `app/`
- `frontend/`
- `migrations/`
- `tests/`
- `scripts/start_metadata_mysql.ps1`
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

移除内容：

- 所有记忆文件
- 所有内部迭代报告
- 所有交付草稿和复盘文档
- `.env`
- 本地日志、缓存、虚拟环境
- 杂项辅助脚本

## 4. 生成方式

执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```

脚本会在当前项目的同级目录生成三套目录。
