# 腾讯文档在线表格 MySQL 同步平台

企业级腾讯文档在线表格与 MySQL 双向同步项目，包含：

- FastAPI 后端接口
- Vue 3 前端工作台
- MySQL 元数据存储
- Linux / macOS / Windows 本地启动脚本
- Docker 一键部署方案

## 环境要求

- Python 3.10+
- Node.js 20+（仅前端本地开发需要）
- Docker + Docker Compose

## 配置原则

部署依赖不写死在逻辑中：

- `config.yaml` 控制应用参数
  - `database.*`
  - `app.*`
  - `frontend.*`
- `.env` 控制容器和部署参数
  - `APP_CONTAINER_NAME`
  - `DATABASE_*`
  - `METADATA_MYSQL_*`
  - `TENCENT_*`

## 本地启动

初始化：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_local.ps1
```

Linux / macOS:

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_local.sh
```

启动后端：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_backend.ps1
```

Linux / macOS:

```bash
./scripts/start_backend.sh
```

启动前端开发环境：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_frontend.ps1
```

Linux / macOS:

```bash
./scripts/start_frontend.sh
```

## Docker 一键部署

复制配置模板：

```powershell
Copy-Item .env.example .env
```

至少补齐：

- `DATABASE_PASSWORD`
- `TENCENT_APP_ID`
- `TENCENT_OPEN_ID`
- `TENCENT_DOCS_ACCESS_TOKEN`
- `ENCRYPTION_KEY`

一键启动：

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

停止：

```bash
docker compose down
```

## 访问地址

- 健康检查：`http://127.0.0.1:8083/health`
- 接口文档：`http://127.0.0.1:8083/docs`
- 前后端一体入口：`http://127.0.0.1:8083/`
- 前端开发环境：`http://127.0.0.1:5173/`

## 核心文件

- `docker-compose.yml`：一键部署编排
- `Dockerfile`：应用镜像构建
- `docker-compose.metadata.yml`：仅元数据库编排
- `scripts/docker_bootstrap.py`：容器启动后等待数据库并执行迁移

## 发布规则

当前只维护 3 个仓库版本：

- 私有版
- 公开版
- GitHub 精简版

生成命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```
