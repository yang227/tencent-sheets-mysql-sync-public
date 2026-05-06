# 腾讯表格 MySQL 同步平台

这是一个面向企业内部数据同步场景的项目，用于打通腾讯表格/腾讯文档在线表格与 MySQL 之间的读写联动。当前仓库包含后端服务、前端工作台、元数据存储、配置管理、同步任务与基础测试。

## 当前状态

- 前端工作台可本地打开，默认入口为 `http://127.0.0.1:8083/`
- 支持管理 MySQL 配置、腾讯配置、同步任务配置
- 支持读取表头、读取 MySQL 字段、自动映射字段
- 支持本地 Docker 元数据库启动
- 已完成基础工作台接口和前端构建验证

当前仓库已经完成敏感信息脱敏处理，不再包含真实腾讯凭据、真实 Token 或本地数据库口令。

## 项目结构

```text
app/
  main.py                      FastAPI 入口
  routers/                     业务接口
  services/                    同步、配置、连接与工具服务
  models/                      Pydantic 模型
  scheduler/                   定时任务调度
  webhooks/                    腾讯回调入口

frontend/
  src/
    views/                     工作台页面
    api/                       前端请求封装
    components/                复用组件

migrations/                    元数据库初始化脚本
scripts/                       启动与运维脚本
tests/                         后端测试
```

## 主要能力

### 1. 连接管理

- MySQL 连接配置管理
- 腾讯开放平台配置管理
- 配置连通性测试

### 2. 同步任务管理

- 创建同步任务
- 维护字段映射
- 设置同步方向
- 手动触发同步
- 查看同步状态与最近执行记录

### 3. 工作台

- 首页总览
- 连接中心
- 同步任务页
- 监控页

## 本地启动

### 1. 准备配置

复制示例配置并填写你自己的值：

```powershell
Copy-Item .env.example .env
Copy-Item config.example.yaml config.yaml
```

必须填写的关键项：

- `.env`
  - `TENCENT_APP_ID`
  - `TENCENT_OPEN_ID`
  - `TENCENT_DOCS_ACCESS_TOKEN`
  - `ENCRYPTION_KEY`
  - `METADATA_MYSQL_ROOT_PASSWORD`
- `config.yaml`
  - `database.password`
  - `tencent.app_id`
  - `tencent.open_id`
  - `tencent.callback_token`

### 2. 启动元数据库

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_metadata_mysql.ps1
```

也可以直接使用 Docker Compose：

```bash
docker compose -f docker-compose.metadata.yml up -d
```

### 3. 启动后端

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8083 --reload
```

### 4. 启动前端开发环境

```bash
cd frontend
npm install
npm run dev
```

前端开发环境会把 `/api` 和 `/health` 代理到 `http://127.0.0.1:8083`。

### 5. 构建前端

```bash
cd frontend
npm run build
```

构建完成后，后端根路径 `/` 会直接托管 `frontend/dist`。

## 常用命令

### 后端测试

```bash
python -m pytest tests/test_workbench_router.py -q
python -m pytest tests/test_tencent_helper_router.py -q
```

### 前端测试

```bash
cd frontend
npm test -- --run
```

### 健康检查

```bash
curl http://127.0.0.1:8083/health
```

### 工作台总览

```bash
curl http://127.0.0.1:8083/api/workbench/summary
```

## 配置文件说明

### `.env`

只保存敏感环境变量，不应提交真实值。仓库已提供 `.env.example`。

### `config.yaml`

用于保存运行时配置。提交到 GitHub 前请确保只保留示例值，或者优先使用 `config.example.yaml` 作为共享模板。

## 安全约束

- 不要把真实腾讯 Token、Open ID、应用 ID 直接提交到仓库
- 不要把真实数据库口令写入文档、脚本或 Compose 文件
- 建议通过 CI/CD Secret、环境变量或部署平台 Secret Manager 注入生产凭据

## 当前边界

当前仓库已经具备企业级项目骨架和本地工作台能力，但以下内容仍建议在部署前继续完善：

- 真实腾讯在线表格写入回读验收
- 同步任务配置与连接配置的完整运行时绑定
- 权限、审计、告警与发布流程
- 更完整的集成测试与回归测试

## 交付建议

如果你准备把仓库公开或提交到团队 GitHub，建议按下面顺序执行：

1. 复制 `.env.example` 和 `config.example.yaml` 作为本地私有配置
2. 确认 `.env`、日志文件、`.venv`、缓存文件未进入提交
3. 运行一次基础测试
4. 再执行 Git 提交和推送
