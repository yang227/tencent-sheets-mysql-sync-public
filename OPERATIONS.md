# 运维手册

## 1. 目标

本手册只覆盖与部署直接相关的最小动作：

- 初始化本地运行环境
- 启动元数据库、后端、前端
- 做基础健康检查
- 生成 3 个 GitHub 发布版本

## 2. 部署矩阵

| 场景 | Windows | Linux / macOS |
| --- | --- | --- |
| 初始化环境 | `scripts/bootstrap_local.ps1` | `scripts/bootstrap_local.sh` |
| 启动元数据库 | `scripts/start_metadata_mysql.ps1` | `scripts/start_metadata_mysql.sh` |
| 启动后端 | `scripts/start_backend.ps1` | `scripts/start_backend.sh` |
| 启动前端 | `scripts/start_frontend.ps1` | `scripts/start_frontend.sh` |
| 一键联调 | `scripts/run_local_stack.ps1` | `scripts/run_local_stack.sh` |
| 部署检查 | `scripts/deployment_check.ps1` | `scripts/deployment_check.sh` |

## 3. 启动顺序

1. 执行 `bootstrap_local`
2. 补齐 `.env` 和 `config.yaml`
3. 启动 `start_metadata_mysql`
4. 启动 `start_backend`
5. 需要前端开发时再启动 `start_frontend`

## 4. 关键端口

- `8083`: FastAPI 服务
- `5173`: Vite 开发服务器
- `13306`: 元数据 MySQL

## 5. Docker 说明

元数据库由 `docker-compose.metadata.yml` 管理：

- 容器名：`tencent-sync-metadata-mysql`
- 本地端口：`127.0.0.1:13306`
- 初始化脚本：
  - `migrations/init.sql`
  - `migrations/add_config_tables.sql`

## 6. 最小验收

后端启动后执行：

```bash
curl http://127.0.0.1:8083/health
curl http://127.0.0.1:8083/api/workbench/summary
```

浏览器访问：

- `http://127.0.0.1:8083/`
- `http://127.0.0.1:5173/`

## 7. 发布前检查

必须确认：

- `.env` 未提交
- `config.yaml` 未提交真实值
- `frontend/dist` 为当前构建结果
- `docker-compose.metadata.yml` 没有写入真实密码
- 三个平台脚本都存在

## 8. 版本发布

执行变体生成脚本后，会得到三个目录：

- `D:\Downloads\tencent-sheets-mysql-sync-private`
- `D:\Downloads\tencent-sheets-mysql-sync-public`
- `D:\Downloads\tencent-sheets-mysql-sync-github`

随后分别进入各目录执行 Git 提交与推送。
