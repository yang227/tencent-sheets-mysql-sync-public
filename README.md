# 腾讯文档在线表格 MySQL 同步平台

企业级腾讯文档在线表格与 MySQL 双向同步项目，包含：

- FastAPI 后端接口
- Vue 3 前端工作台
- 元数据 MySQL 容器
- 同步配置、字段映射、任务管理
- Linux / macOS / Windows 三平台本地部署脚本

## 1. 项目结构

```text
app/          后端服务
frontend/     前端工作台
migrations/   元数据库初始化脚本
scripts/      Linux/macOS/Windows 启动与检查脚本
tests/        后端与前端相关测试
```

## 2. 环境要求

- Python 3.10+
- Node.js 20+
- Docker + Docker Compose
- MySQL 8 客户端可选

## 3. 初始化配置

首次拉取后先复制模板：

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_local.ps1
```

### Linux / macOS

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_local.sh
```

初始化后需要补充真实配置：

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

## 4. 三平台部署脚本

### 4.1 启动元数据库

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_metadata_mysql.ps1
```

Linux / macOS:

```bash
./scripts/start_metadata_mysql.sh
```

### 4.2 启动后端

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_backend.ps1
```

Linux / macOS:

```bash
./scripts/start_backend.sh
```

### 4.3 启动前端开发环境

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_frontend.ps1
```

Linux / macOS:

```bash
./scripts/start_frontend.sh
```

### 4.4 一键启动本地联调

仅后端 + 元数据库：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_stack.ps1
```

Linux / macOS:

```bash
./scripts/run_local_stack.sh
```

包含前端开发服务器：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_stack.ps1 -WithFrontend
```

Linux / macOS:

```bash
./scripts/run_local_stack.sh --with-frontend
```

## 5. 访问地址

- 后端健康检查：`http://127.0.0.1:8083/health`
- 后端接口文档：`http://127.0.0.1:8083/docs`
- 前端开发环境：`http://127.0.0.1:5173`
- 前后端一体构建结果：`http://127.0.0.1:8083/`

## 6. 构建前端静态资源

```bash
cd frontend
npm run build
```

构建完成后，后端根路径 `/` 将直接托管 `frontend/dist`。

## 7. 检查脚本

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deployment_check.ps1
```

Linux / macOS:

```bash
./scripts/deployment_check.sh
```

## 8. GitHub 发布规则

当前项目只维护 3 个仓库版本：

- 私有版：保留项目记忆文件和内部资料
- 公开版：移除项目记忆文件
- GitHub 精简版：仅保留源码、测试、迁移、脚本和对外文档

重新生成三个版本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```

## 9. 安全要求

- 不提交真实 `.env`
- 不提交真实 `config.yaml`
- 不提交真实腾讯开放平台密钥
- 不提交真实数据库密码
- 不提交本地日志、缓存、虚拟环境和 `node_modules`
