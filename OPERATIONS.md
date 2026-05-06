# 运维手册

本文档用于说明本项目在开发、测试和部署阶段的最小运维要求，重点覆盖本地启动、配置管理、敏感信息管理、健康检查与故障定位。

## 1. 配置原则

### 1.1 不提交真实敏感信息

以下内容不得以真实值进入 Git 仓库：

- 腾讯应用 ID
- 腾讯 Open ID
- 腾讯访问 Token
- MySQL root 密码
- 任意环境的业务数据库账号密码
- 加密密钥

仓库中应只保留：

- `.env.example`
- `config.example.yaml`
- 脱敏后的文档和脚本

### 1.2 推荐配置方式

本地开发：

```powershell
Copy-Item .env.example .env
Copy-Item config.example.yaml config.yaml
```

生产部署：

- 使用 CI/CD Secret
- 使用容器编排平台 Secret
- 使用专门的配置中心或密钥管理服务

## 2. 本地启动流程

### 2.1 启动元数据库

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_metadata_mysql.ps1
```

脚本依赖：

- Docker Desktop 已启动
- `.env` 中存在 `METADATA_MYSQL_ROOT_PASSWORD`

### 2.2 启动后端

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8083 --reload
```

### 2.3 启动前端开发环境

```bash
cd frontend
npm install
npm run dev
```

### 2.4 访问入口

- 工作台首页：`http://127.0.0.1:8083/`
- 健康检查：`http://127.0.0.1:8083/health`
- 工作台总览：`http://127.0.0.1:8083/api/workbench/summary`

## 3. Docker 元数据库说明

### 3.1 Compose 文件

元数据库使用 `docker-compose.metadata.yml` 管理，默认容器名：

```text
tencent-sync-metadata-mysql
```

### 3.2 端口

默认映射：

```text
127.0.0.1:13306 -> 3306
```

### 3.3 初始化内容

启动脚本会在数据库可用后执行：

- `migrations/init.sql`
- `migrations/add_config_tables.sql`

## 4. 健康检查

### 4.1 服务进程

```powershell
Get-Process | Where-Object { $_.ProcessName -eq 'python' }
```

### 4.2 端口检查

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8083
Test-NetConnection -ComputerName 127.0.0.1 -Port 13306
```

### 4.3 HTTP 检查

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:8083/health' -UseBasicParsing
Invoke-RestMethod -Uri 'http://127.0.0.1:8083/api/workbench/summary'
```

## 5. 常见故障

### 5.1 页面能打开但资源 404

排查点：

- 是否使用了正确的 `app.main:app` 启动方式
- `frontend/dist/assets` 是否存在
- 后端是否正确挂载 `/assets`

### 5.2 首页打开慢或接口超时

排查点：

- `13306` 是否可用
- Docker Desktop 是否已经完全启动
- `tencent-sync-metadata-mysql` 容器是否在运行

### 5.3 启动脚本报错

优先检查：

- `.env` 是否存在
- `METADATA_MYSQL_ROOT_PASSWORD` 是否已填写
- Docker daemon 是否正常

### 5.4 腾讯接口测试失败

需要区分两类问题：

- 凭据本身无效
- 旧探针接口错误或文档接口口径不一致

不要仅依据单个“测试连接”结果判断整条读写链路已经可用。

## 6. 提交前检查

提交到 GitHub 之前，至少执行以下检查：

```bash
git status
git diff -- .env config.yaml docker-compose.metadata.yml README.md OPERATIONS.md
```

确认：

- `.env` 中没有真实值
- `config.yaml` 中没有真实值
- 文档里没有真实密码、真实 Token、真实主机
- 日志文件和缓存文件没有进入暂存区

## 7. 最小发布建议

建议至少补齐以下内容后再做生产发布：

- 真实联动验收记录
- 发布分支策略
- CI 测试与镜像构建
- 权限控制
- 告警通知
- 数据备份策略
