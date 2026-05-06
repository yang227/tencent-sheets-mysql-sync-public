# 运维手册

## 目标

提供两种启动方式：

- 本地脚本启动
- Docker 一键部署启动

## 部署矩阵

| 场景 | Windows | Linux / macOS |
| --- | --- | --- |
| 初始化环境 | `scripts/bootstrap_local.ps1` | `scripts/bootstrap_local.sh` |
| 启动元数据库 | `scripts/start_metadata_mysql.ps1` | `scripts/start_metadata_mysql.sh` |
| 启动后端 | `scripts/start_backend.ps1` | `scripts/start_backend.sh` |
| 启动前端 | `scripts/start_frontend.ps1` | `scripts/start_frontend.sh` |
| 一键联调 | `scripts/run_local_stack.ps1` | `scripts/run_local_stack.sh` |
| Docker 一键启动 | `scripts/docker_up.ps1` | `scripts/docker_up.sh` |
| Docker 停止 | `scripts/docker_down.ps1` | `scripts/docker_down.sh` |
| 部署检查 | `scripts/deployment_check.ps1` | `scripts/deployment_check.sh` |

## Docker 一键部署

主编排文件：

- `docker-compose.yml`

服务：

- `app`
- `metadata-mysql`

启动：

```bash
docker compose up -d --build
```

停止：

```bash
docker compose down
```

## 依赖参数来源

应用参数来自：

- `config.yaml`
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

容器参数来自：

- `.env`
  - `APP_CONTAINER_NAME`
  - `DATABASE_*`
  - `METADATA_MYSQL_*`
  - `TENCENT_*`

## 容器启动流程

1. `metadata-mysql` 启动并通过健康检查
2. `app` 容器启动
3. `scripts/docker_bootstrap.py` 等待数据库可连接
4. 自动执行：
   - `migrations/init.sql`
   - `migrations/add_config_tables.sql`
5. 启动 `uvicorn`

## 验收

```bash
docker compose ps
curl http://127.0.0.1:8083/health
```

浏览器访问：

- `http://127.0.0.1:8083/`

## 当前限制

如果本机 Docker 未登录 Docker Hub，拉取基础镜像时可能遇到限流。遇到 `429 Too Many Requests` 时先执行：

```bash
docker login
```
