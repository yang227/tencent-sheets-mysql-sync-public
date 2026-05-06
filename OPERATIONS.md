# 运维手册

## 1. 目标

本手册只覆盖当前项目已经落地并验证过的部署方式：

- 本地脚本启动
- Docker 一键构建并启动

## 2. 启动矩阵

| 场景 | Windows | Linux / macOS |
| --- | --- | --- |
| 初始化环境 | `scripts/bootstrap_local.ps1` | `scripts/bootstrap_local.sh` |
| 启动元数据库 | `scripts/start_metadata_mysql.ps1` | `scripts/start_metadata_mysql.sh` |
| 启动后端 | `scripts/start_backend.ps1` | `scripts/start_backend.sh` |
| 启动前端 | `scripts/start_frontend.ps1` | `scripts/start_frontend.sh` |
| 本地全链路启动 | `scripts/run_local_stack.ps1` | `scripts/run_local_stack.sh` |
| Docker 一键启动 | `scripts/docker_up.ps1` | `scripts/docker_up.sh` |
| Docker 停止 | `scripts/docker_down.ps1` | `scripts/docker_down.sh` |
| 部署检查 | `scripts/deployment_check.ps1` | `scripts/deployment_check.sh` |

## 3. 参数来源

### 应用参数

来自 `config.yaml`：

- `database.host`
- `database.port`
- `database.user`
- `database.password`
- `database.name`
- `app.host`
- `app.port`
- `frontend.host`
- `frontend.port`
- `frontend.backend_url`

### 容器参数

来自 `.env`：

- `APP_CONTAINER_NAME`
- `APP_BASE_IMAGE`
- `APP_PORT`
- `DATABASE_*`
- `METADATA_MYSQL_*`
- `TENCENT_*`
- `ENCRYPTION_KEY`
- `METADATA_MYSQL_READY_TIMEOUT`

结论：端口、容器名、镜像名、数据库地址、前端后端地址都已经从逻辑中抽离，不再写死在脚本或代码流程中。

## 4. Docker 当前落地方案

主编排文件：

- `docker-compose.yml`

服务：

- `metadata-mysql`
- `app`

### 4.1 设计约束

当前方案的目标不是依赖 Docker Hub 在线拉取一套新基础镜像，而是满足“本机已有 Docker 即可本地构建和启动”。

因此当前实现采用以下策略：

- `app` 镜像默认基于本机已有 `mysql:8.0` 镜像构建
- 通过 `APP_BASE_IMAGE` 可改成其他本地可用镜像
- 容器内使用 `python3 -m ensurepip` 和 `pip install -r requirements.txt`
- 前端不在容器构建时再执行 Node 打包
- 直接使用仓库中已提交的 `frontend/dist`

### 4.2 启动命令

```bash
docker compose up -d --build
```

或：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker_up.ps1
```

Linux / macOS:

```bash
./scripts/docker_up.sh
```

### 4.3 停止命令

```bash
docker compose down
```

## 5. 容器启动流程

1. `metadata-mysql` 启动并通过健康检查
2. `app` 容器启动
3. `scripts/docker_bootstrap.py` 轮询等待数据库可连接
4. 自动执行：
   - `migrations/init.sql`
   - `migrations/add_config_tables.sql`
5. 启动 `uvicorn app.main:app`

补充说明：

- SQL 初始化执行方式已经改为调用容器内 `mysql` CLI
- 不再依赖 `mysql-connector` 的 `multi=True`
- 这是为了避免多语句执行在容器里失败

## 6. 验证命令

查看容器状态：

```bash
docker compose ps
```

健康检查：

```bash
curl http://127.0.0.1:8083/health
```

查看应用日志：

```bash
docker logs --tail 120 tencent-sheets-mysql-sync-app
```

浏览器访问：

- `http://127.0.0.1:8083/`
- `http://127.0.0.1:8083/docs`

## 7. 当前已验证结果

当前仓库下已验证过的结果：

- `docker compose ps` 显示：
  - `tencent-sheets-mysql-sync-app` healthy
  - `tencent-sync-metadata-mysql` healthy
- 应用容器日志已出现：
  - `Application startup complete.`
  - `Uvicorn running on http://0.0.0.0:8083`

## 8. 已知限制

### 8.1 基础镜像要求

如果本机没有本地 `mysql:8.0` 镜像，则当前默认 `APP_BASE_IMAGE=mysql:8.0` 无法直接构建。

处理方式：

- 先确保本机存在该镜像
- 或在 `.env` 中改成其他本地可用镜像

### 8.2 继承暴露端口

由于 `app` 镜像当前基于 `mysql:8.0`，镜像元数据会继承 MySQL 的 `3306/tcp`、`33060/tcp` 暴露信息。

这不影响应用在 `8083` 端口提供服务，但镜像展示信息会显得不够干净。

### 8.3 Python 版本兼容

当前本地基础镜像链路里实际使用的是 Python 3.9 运行环境，因此代码里不能继续使用 `int | None` 这类只适合较高版本解释器的类型写法。

已修正的文件：

- `app/routers/tencent_helper.py`
- `app/scheduler/sync_scheduler.py`
