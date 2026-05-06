# 腾讯文档在线表格 MySQL 同步平台

面向企业内部使用的腾讯文档在线表格与 MySQL 双向同步平台，包含：

- FastAPI 后端接口
- Vue 3 前端工作台
- MySQL 元数据存储
- Linux / macOS / Windows 本地启动脚本
- Docker 一键构建与启动方案

## 1. 项目目标

本项目用于完成以下能力：

- 读取腾讯文档在线表格表头和数据
- 读取 MySQL 表结构与字段信息
- 在表格字段和数据库字段之间直接做映射
- 按配置执行表格写入 MySQL、MySQL 回写表格
- 通过前端界面完成配置、映射、触发和验证

## 2. 配置原则

所有运行参数都通过配置文件或环境变量注入，不在业务逻辑里写死。

应用运行配置来源：

- `config.yaml`
  - `database.*`
  - `app.*`
  - `frontend.*`

容器和部署配置来源：

- `.env`
  - `APP_CONTAINER_NAME`
  - `APP_BASE_IMAGE`
  - `DATABASE_*`
  - `METADATA_MYSQL_*`
  - `TENCENT_*`
  - `ENCRYPTION_KEY`

示例配置文件：

- `.env.example`
- `config.example.yaml`

## 3. 环境要求

### 本地脚本模式

- Python 3.10+
- Node.js 20+（仅前端本地开发需要）
- 可访问的 MySQL 实例

### Docker 模式

- 本机已安装 Docker 和 Docker Compose
- 本机本地已有 `mysql:8.0` 镜像

说明：

- 当前 Docker 方案默认使用 `APP_BASE_IMAGE=mysql:8.0`
- 应用镜像直接基于本地 `mysql:8.0` 构建
- 不依赖再去拉取 `python:3.12-slim`、`node:20-alpine` 之类的基础镜像
- 前端静态资源直接使用仓库中已提交的 `frontend/dist`

## 4. 本地启动

### 4.1 初始化

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_local.ps1
```

Linux / macOS:

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_local.sh
```

### 4.2 启动元数据库

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_metadata_mysql.ps1
```

Linux / macOS:

```bash
./scripts/start_metadata_mysql.sh
```

### 4.3 启动后端

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_backend.ps1
```

Linux / macOS:

```bash
./scripts/start_backend.sh
```

### 4.4 启动前端开发环境

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_frontend.ps1
```

Linux / macOS:

```bash
./scripts/start_frontend.sh
```

### 4.5 一次性联动启动

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_stack.ps1
```

Linux / macOS:

```bash
./scripts/run_local_stack.sh
```

## 5. Docker 一键部署

### 5.1 初始化配置

```powershell
Copy-Item .env.example .env
```

至少需要按实际环境补齐以下配置：

- `DATABASE_PASSWORD`
- `TENCENT_APP_ID`
- `TENCENT_OPEN_ID`
- `TENCENT_DOCS_ACCESS_TOKEN`
- `ENCRYPTION_KEY`

如果本机本地镜像名不是 `mysql:8.0`，可以改：

- `APP_BASE_IMAGE`
- `METADATA_MYSQL_IMAGE`

### 5.2 一键启动

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker_up.ps1
```

Linux / macOS:

```bash
chmod +x scripts/*.sh
./scripts/docker_up.sh
```

等价命令：

```bash
docker compose up -d --build
```

### 5.3 一键停止

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker_down.ps1
```

Linux / macOS:

```bash
./scripts/docker_down.sh
```

等价命令：

```bash
docker compose down
```

## 6. Docker 启动过程

`docker-compose.yml` 会启动两个服务：

- `metadata-mysql`
- `app`

应用容器启动后会自动执行：

1. 等待 MySQL 健康
2. 执行 `migrations/init.sql`
3. 执行 `migrations/add_config_tables.sql`
4. 启动 `uvicorn`

相关文件：

- `Dockerfile`
- `docker-compose.yml`
- `scripts/docker_bootstrap.py`

## 7. 访问地址

- 健康检查：`http://127.0.0.1:8083/health`
- Swagger 文档：`http://127.0.0.1:8083/docs`
- 前后端一体入口：`http://127.0.0.1:8083/`
- 前端开发模式：`http://127.0.0.1:5173/`

## 8. 关键目录

- `app/`：后端应用
- `frontend/`：前端应用与静态资源
- `migrations/`：数据库初始化与变更脚本
- `scripts/`：本地启动、部署、验证脚本
- `tests/`：自动化测试

## 9. 发布版本管理

当前只维护 3 个 GitHub 仓库版本：

- 私有版：`yang227/tencent-sheets-mysql-sync-private`
- 公开版：`yang227/tencent-sheets-mysql-sync-public`
- GitHub 精简版：`yang227/tencent-sheets-mysql-sync-github`

生成命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```

说明：

- 私有版保留项目记忆与内部过程文件
- 公开版移除项目记忆和本地敏感配置
- GitHub 精简版只保留真正适合公开发布和运行的文件
