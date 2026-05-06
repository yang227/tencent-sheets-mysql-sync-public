# 腾讯文档在线表格 ↔ MySQL 双向同步系统

## 1. 项目概述

**项目名称**: Tencent Sheets MySQL Sync（tencent-sheets-mysql-sync）
**核心功能**: 腾讯文档在线表格与 MySQL 数据库之间的双向数据同步
**目标用户**: 需要将腾讯文档表格作为前端数据录入入口，MySQL 作为后端持久化存储的团队

---

## 2. 技术架构

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  腾讯文档在线表格    │────▶│   Sync Engine    │────▶│    MySQL     │
│  (Tencent Sheets)   │◀────│  (双向同步核心)   │◀────│   Database   │
└─────────────────────┘     └──────────────────┘     └──────────────┘
                                   │
                          ┌────────┴────────┐
                          │  Mapping Config  │
                          │  (字段映射表)    │
                          └─────────────────┘
```

**同步方向**:
- `腾讯文档 → MySQL`: 定时轮询腾讯文档 API，检测变更行，INSERT/UPDATE 到 MySQL
- `MySQL → 腾讯文档`: 定时轮询 MySQL，检测变更记录，PATCH 回腾讯文档

---

## 3. 腾讯文档 API 分析

### 3.1 可用 API 端点

**基础信息**:
- API Base: `https://docs.tencent.com`（或通过 OAuth 获取 token）
- 认证: OAuth 2.0 / JWT
- 频率限制: 约 100次/分钟

**核心接口**:
| 接口 | 方法 | 用途 |
|------|------|------|
| `/open-api/sheets/v3/spreadsheet/{spreadsheetId}` | GET | 获取表格元信息 |
| `/open-api/sheets/v3/spreadsheet/{spreadsheetId}/sheets/{sheetId}` | GET | 获取工作表信息 |
| `/open-api/sheets/v3/spreadsheet/{spreadsheetId}/values/{range}` | GET | 读取指定范围数据 |
| `/open-api/sheets/v3/spreadsheet/{spreadsheetId}/values/{range}` | PUT | 写入数据 |
| `/open-api/sheets/v3/spreadsheet/{spreadsheetId}/values/batch` | batch PUT | 批量写入 |

### 3.2 数据格式

腾讯文档单元格值格式：
```json
{
  "value": "文本内容",
  "type": "string"  // string, number, boolean, date, error
}
```

范围格式: `A1:Z100` 或 `Sheet1!A1:Z100`

### 3.3 Webhook（推荐方案）

腾讯文档支持 Webhook 通知，当表格变更时主动推送，避免轮询：
- 配置 Webhook URL 到本服务
- 服务接收变更事件，获取 changedRange
- 增量读取变更区域
- 同步到 MySQL

---

## 4. 数据库设计

### 4.1 MySQL Schema

```sql
-- 同步配置表：记录每个表格对应的库表映射
CREATE TABLE sync_configs (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    spreadsheet_id VARCHAR(128) NOT NULL UNIQUE COMMENT '腾讯文档表格ID',
    sheet_id      VARCHAR(64)  NOT NULL COMMENT '工作表ID',
    table_name    VARCHAR(128) NOT NULL COMMENT 'MySQL目标表名',
    mapping_json  JSON         NOT NULL COMMENT '字段映射配置',
    sync_direction ENUM('to_mysql','from_mysql','bidirectional') DEFAULT 'bidirectional',
    last_sync_at  DATETIME     DEFAULT NULL,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active     TINYINT(1)  DEFAULT 1,
    INDEX idx_spreadsheet (spreadsheet_id),
    INDEX idx_active (is_active)
);

-- 同步日志表
CREATE TABLE sync_logs (
    id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_id      BIGINT NOT NULL,
    direction      ENUM('to_mysql','from_mysql') NOT NULL,
    rows_affected  INT DEFAULT 0,
    status         ENUM('success','partial','failed') DEFAULT 'success',
    error_message  TEXT,
    started_at     DATETIME,
    completed_at   DATETIME,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_config_time (config_id, created_at)
);

-- 变更追踪表（用于双向同步去重）
CREATE TABLE change_tracking (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_id       BIGINT NOT NULL,
    source_row_key  VARCHAR(256) NOT NULL COMMENT '行唯一标识（腾讯文档行号或MySQL主键）',
    source_hash     VARCHAR(64) NOT NULL COMMENT '行内容hash，用于变更检测',
    last_value      TEXT COMMENT '上一次的值（JSON）',
    last_sync_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    source          ENUM('tencent','mysql') NOT NULL,
    INDEX idx_config_row (config_id, source_row_key),
    UNIQUE KEY uk_config_row (config_id, source_row_key)
);
```

### 4.2 映射配置格式 (mapping_json)

```json
{
  "columns": [
    {
      "sheet_col": "A",
      "sheet_header": "姓名",
      "db_column": "name",
      "db_type": "VARCHAR(64)",
      "direction": "bidirectional",
      "primary_key": true,
      "transform": null
    },
    {
      "sheet_col": "B",
      "sheet_header": "年龄",
      "db_column": "age",
      "db_type": "INT",
      "direction": "bidirectional",
      "transform": "int"
    },
    {
      "sheet_col": "C",
      "sheet_header": "创建时间",
      "db_column": "created_at",
      "db_type": "DATETIME",
      "direction": "to_mysql_only",
      "transform": "parse_datetime"
    }
  ],
  "sheet_header_row": 1,
  "data_start_row": 2
}
```

---

## 5. 功能模块

### 5.1 配置管理 API

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/configs` | GET | 列出所有同步配置 |
| `/api/configs` | POST | 创建新的同步配置（同时自动建表） |
| `/api/configs/{id}` | GET | 获取单个配置详情 |
| `/api/configs/{id}` | PUT | 更新配置 |
| `/api/configs/{id}` | DELETE | 删除配置（软删除） |
| `/api/configs/{id}/test` | POST | 测试连接（腾讯文档 + MySQL） |

### 5.2 同步操作 API

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/sync/{config_id}/trigger` | POST | 手动触发一次同步（双向） |
| `/api/sync/{config_id}/to-mysql` | POST | 仅腾讯文档 → MySQL |
| `/api/sync/{config_id}/from-mysql` | POST | 仅 MySQL → 腾讯文档 |
| `/api/sync/{config_id}/status` | GET | 查看同步状态和最近日志 |

### 5.3 监控 Dashboard API

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/dashboard/overview` | GET | 系统总览（健康状态、同步统计、API统计） |
| `/api/dashboard/health` | GET | 健康检查（健康分数 + 各检查项状态） |
| `/api/dashboard/prometheus` | GET | Prometheus 格式指标 |
| `/api/dashboard/sync/statistics` | GET | 同步统计（支持时间周期过滤） |
| `/api/dashboard/api/statistics` | GET | API 调用统计（延迟 P50/P90/P95/P99） |
| `/api/dashboard/errors/statistics` | GET | 错误统计（按类型、严重级别） |
| `/api/dashboard/dead-letter-queue` | GET | 死信队列查询 |
| `/api/dashboard/dead-letter-queue/{index}/retry` | POST | 死信队列单项重试 |
| `/api/dashboard/audit/statistics` | GET | 审计统计 |
| `/api/dashboard/audit/recent` | GET | 最近审计事件 |
| `/api/dashboard/performance/histograms` | GET | 性能直方图 |

### 5.4 MySQL 浏览器 API

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/mysql/databases` | GET | 数据库列表 |
| `/api/mysql/databases/{db}/tables` | GET | 指定数据库的表列表 |
| `/api/mysql/tables/{table}/columns` | GET | 指定表的列信息 |

### 5.5 腾讯文档助手 API

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/tencent/sheet-header` | GET | 读取腾讯文档表头（用于映射配置） |

### 5.6 Webhook API

| 接口 | 方法 | 功能 |
|------|------|------|
| `/webhook/tencent/callback` | POST | 腾讯文档变更 Webhook 回调 |

### 5.7 系统 API

| 接口 | 方法 | 功能 |
|------|------|------|
| `GET /health` | GET | 健康检查 |
| `POST /init` | POST | 初始化系统表 |

### 5.3 前端映射管理页面

**映射关联页面** — 用户在网页上：
1. 输入腾讯文档 URL 或 ID
2. 选择要同步的工作表
3. 系统自动读取表头（第一行）
4. 用户为每个列选择/映射到 MySQL 表的字段
5. 指定 MySQL 表名（不存在则自动创建）
6. 选择同步方向和频率
7. 保存配置，开始同步

---

## 6. 同步策略

### 6.1 腾讯文档 → MySQL

```
1. 按配置的轮询间隔（如 30秒）执行
2. 调用腾讯文档 API 读取配置范围（header_row:data_end）
3. 对比 change_tracking 表的 hash
4. 只同步 hash 发生变化的行
5. 按 mapping_json 转换数据类型
6. 执行 MySQL INSERT ... ON DUPLICATE KEY UPDATE
7. 更新 change_tracking 表
8. 记录 sync_logs
```

### 6.2 MySQL → 腾讯文档

```
1. 按配置的轮询间隔执行
2. 查询 MySQL 表，比对 change_tracking 的 hash
3. 找出变化的行
4. 按 mapping_json 转换为腾讯文档格式
5. 调用腾讯文档 batch update API 写入
6. 更新 change_tracking 表
7. 记录 sync_logs
```

### 6.3 Webhook 实时同步（优先）

如腾讯文档支持变更 Webhook：
```
1. 用户在腾讯文档配置 Webhook 回调到本服务
2. 接收变更事件 {spreadsheetId, sheetId, changedRange}
3. 立即增量读取 changedRange
4. 执行增量同步到 MySQL
5. 响应 200（要在 3 秒内响应）
```

---

## 7. 项目结构

```
tencent-sheets-mysql-sync/
├── SPEC.md
├── README.md
├── requirements.txt              # Python 依赖
├── config.yaml                   # 服务配置（数据库连接、腾讯API凭证）
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置加载
│   ├── models/
│   │   ├── __init__.py
│   │   ├── sync_config.py       # Pydantic 模型：SyncConfig
│   │   └── sync_log.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── config_router.py     # 配置管理 API
│   │   └── sync_router.py       # 同步操作 API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tencent_api.py       # 腾讯文档 API 封装
│   │   ├── mysql_service.py     # MySQL 操作封装
│   │   ├── sync_engine.py       # 双向同步核心逻辑
│   │   └── mapping.py           # 字段映射转换
│   ├── webhooks/
│   │   ├── __init__.py
│   │   └── tencent_webhook.py   # 腾讯文档 Webhook 处理
│   └── scheduler/
│       ├── __init__.py
│       └── sync_scheduler.py     # APScheduler 定时任务
├── migrations/
│   └── init.sql                 # 初始化数据库脚本
└── tests/
    ├── __init__.py
    ├── test_sync_engine.py
    ├── test_tencent_api.py
    └── test_mapping.py
```

---

## 8. 依赖

```
fastapi>=0.115.0
uvicorn>=0.30.0
httpx>=0.27.0           # 异步 HTTP 客户端（腾讯文档 API）
mysql-connector-python>=9.0.0  # MySQL 驱动
sqlalchemy>=2.0.0        # ORM（用于表创建）
pydantic>=2.0.0
pyyaml>=6.0.0
apscheduler>=3.10.0      # 定时任务
python-dotenv>=1.0.0
```

---

## 9. 配置示例 (config.yaml)

```yaml
database:
  host: "localhost"
  port: 3306
  user: "root"
  password: "your_password"
  name: "tencent_sheets_sync"

tencent:
  app_id: "your_app_id"
  app_secret: "your_app_secret"
  callback_token: "your_webhook_token"  # 用于验证 Webhook

app:
  host: "0.0.0.0"
  port: 8083
  webhook_base_url: "https://your-domain.com/webhook/tencent"

sync:
  default_poll_interval: 30  # 秒
  batch_size: 100           # 每批处理行数
  retry_times: 3
```

---

## 10. 用户使用流程

```
┌──────────────────────────────────────────────────────────────┐
│  前端映射关联页面                                              │
│                                                              │
│  1. 粘贴腾讯文档在线表格链接                                   │
│     ↓                                                         │
│  2. 系统自动读取表格元信息 + 表头行                            │
│     ↓                                                         │
│  3. 用户映射：腾讯文档列 A → MySQL字段 name (VARCHAR)          │
│              腾讯文档列 B → MySQL字段 age (INT)                │
│              ...                                              │
│     ↓                                                         │
│  4. 指定 MySQL 表名（如 user_info），点"创建并同步"            │
│     ↓                                                         │
│  5. 系统自动建表 → 初始化同步 → 定时轮询开始                   │
│     ↓                                                         │
│  6. 用户在腾讯文档编辑 → 30秒内自动落库 MySQL                  │
│     ↓                                                         │
│  7. MySQL 数据变更 → 自动回写腾讯文档                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. 验收标准

1. ✅ 用户在前端完成映射配置，系统自动在 MySQL 创建对应表
2. ✅ 腾讯文档新增/修改行，30 秒内写入 MySQL
3. ✅ MySQL INSERT/UPDATE，30 秒内回写腾讯文档
4. ✅ 支持多张表格配置，共存独立同步
5. ✅ 同步日志可查，成功/失败状态清晰
6. ✅ Webhook 模式下实时同步（<3 秒延迟）
7. ✅ 配置管理 API 完整（CRUD + 测试连接）
8. ✅ 字段类型自动转换（字符串/数字/日期/布尔）
9. ✅ 主键冲突时 UPDATE，非主键INSERT
10. ✅ 断点恢复，网络失败自动重试

---

## 12. 已知问题与解决方案（FAQ）

### Q1: 腾讯文档 API 调用失败，提示 token 过期
**问题**: `TokenExpiredError` 或 401 错误
**解决**: 系统会自动刷新 token。若持续失败，请检查 `config.yaml` 中的 `app_id` 和 `app_secret` 是否正确配置。

### Q2: 同步成功但数据未写入 MySQL
**问题**: `rows_affected=0` 但无报错
**解决**: 
1. 检查 `change_tracking` 表——相同 hash 的行会被跳过
2. 确认映射配置中 `sheet_col` 与实际表头列对应
3. 确认 MySQL 表已创建且字段类型匹配

### Q3: Webhook 收不到通知
**问题**: 腾讯文档变更后同步未触发
**解决**:
1. 确认 Webhook URL 可公网访问（腾讯文档需要推送到此地址）
2. 检查 `/webhook/tencent/callback` 返回状态码是否为 200
3. 确认 `callback_token` 与腾讯文档后台配置一致

### Q4: `config.tencent.get()` 报错
**问题**: `Pydantic model 没有 .get() 方法`
**解决**: 这是旧代码 bug，已在 v1.1.0 中修复。请更新到最新版本。

### Q5: MySQL 连接超时
**问题**: `MySQLServiceError: 2003: Can't connect to MySQL server`
**解决**:
1. 确认 MySQL 服务正在运行
2. 检查 `config.yaml` 中的 `host`、`port`、`user`、`password`
3. 确认 MySQL 用户有访问权限

---

## 13. Docker 部署指南

### 13.1 环境要求
- Docker >= 20.10
- Docker Compose >= 2.0

### 13.2 docker-compose.yml 示例

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8083:8083"
    environment:
      - CONFIG_PATH=/app/config.yaml
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    depends_on:
      mysql:
        condition: service_healthy
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${METADATA_MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: tencent_sheets_sync
    ports:
      - "13306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  mysql_data:
```

### 13.3 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8083
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8083"]
```

### 13.4 快速启动

```bash
# 1. 克隆项目
git clone <repo_url>
cd tencent-sheets-mysql-sync

# 2. 配置 config.yaml
cp config.yaml.example config.yaml
vim config.yaml

# 3. 启动服务
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8083

# 4. 初始化数据库
curl -X POST http://localhost:8083/init

# 5. 查看日志
# (直接运行则日志输出到 stdout，按 Ctrl+C 停止)
```

### 13.5 生产环境注意事项

1. **端口**: `8083`（默认值，可通过 `uvicorn --port` 参数覆盖）
2. **Webhook URL**: 必须使用 HTTPS 地址供腾讯文档回调
3. **环境变量**: 生产环境建议使用环境变量而非配置文件存储敏感信息
4. **日志级别**: 生产环境建议将 `logging.level` 设置为 `INFO` 或 `WARNING`

---

## 14. 完整 API 响应示例

### 14.1 配置管理 API

#### GET /api/configs
```json
{
  "configs": [
    {
      "id": 1,
      "spreadsheet_id": "abc123xxx",
      "sheet_id": "sheet001",
      "table_name": "employees",
      "database": "tencent_sheets_sync",
      "mapping_json": {...},
      "sync_direction": "bidirectional",
      "poll_interval": 30,
      "last_sync_at": "2026-04-29T10:00:00",
      "is_active": true
    }
  ]
}
```

#### POST /api/configs
**请求**:
```json
{
  "spreadsheet_id": "abc123xxx",
  "sheet_id": "sheet001",
  "table_name": "employees",
  "mapping_json": {
    "columns": [
      {"sheet_col": "A", "sheet_header": "姓名", "db_column": "name", "db_type": "VARCHAR(64)", "primary_key": true},
      {"sheet_col": "B", "sheet_header": "年龄", "db_column": "age", "db_type": "INT"}
    ],
    "sheet_header_row": 1,
    "data_start_row": 2
  },
  "sync_direction": "bidirectional",
  "poll_interval": 30
}
```
**响应** (201):
```json
{
  "id": 1,
  "message": "配置创建成功"
}
```

### 14.2 同步操作 API

#### POST /api/sync/1/trigger
**响应** (200):
```json
{
  "success": true,
  "direction": "bidirectional",
  "rows_affected": 5,
  "rows_new": 2,
  "rows_updated": 3,
  "rows_skipped": 10,
  "errors": [],
  "details": {
    "total_sheet_rows": 15
  }
}
```

#### GET /api/sync/1/status
**响应** (200):
```json
{
  "config_id": 1,
  "is_active": true,
  "last_sync_at": "2026-04-29T10:00:00",
  "sync_direction": "bidirectional",
  "recent_logs": [
    {
      "id": 100,
      "direction": "to_mysql",
      "rows_affected": 5,
      "status": "success",
      "started_at": "2026-04-29T09:59:30",
      "completed_at": "2026-04-29T09:59:35"
    }
  ]
}
```

### 14.3 Webhook API

#### POST /webhook/tencent/callback
**腾讯文档发送的请求体**:
```json
{
  "event": "edit",
  "spreadsheetId": "abc123xxx",
  "sheetId": "sheet001",
  "changedRange": "A1:D10"
}
```
**成功响应** (200):
```json
{
  "status": "ok",
  "message": "已接收，正在处理"
}
```
**错误响应** (404):
```json
{
  "detail": "未找到对应配置"
}
```

### 14.4 健康检查

#### GET /health
```json
{
  "status": "healthy",
  "service": "tencent-sheets-mysql-sync"
}
```

#### POST /init
**成功响应** (200):
```json
{
  "message": "系统表初始化完成"
}
```
**错误响应** (500):
```json
{
  "detail": "初始化失败: Table 'sync_configs' already exists"
}
```

---

## 15. 数据库 Migration 注意事项

### 15.1 手动执行 Migration

首次部署时，需要初始化系统表：

```bash
# 方式1: API 调用
curl -X POST http://localhost:8083/init

# 方式2: 直接执行 SQL
mysql -u root -p tencent_sheets_sync < migrations/init.sql
```

### 15.2 手动创建系统表

如果 API 调用失败，可以手动执行以下 SQL：

```sql
-- 同步配置表
CREATE TABLE IF NOT EXISTS sync_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    spreadsheet_id VARCHAR(128) NOT NULL,
    sheet_id VARCHAR(64) NOT NULL,
    table_name VARCHAR(128) NOT NULL,
    `database` VARCHAR(128) NOT NULL DEFAULT '',
    mapping_json JSON NOT NULL,
    sync_direction ENUM('to_mysql','from_mysql','bidirectional') DEFAULT 'bidirectional',
    poll_interval INT DEFAULT 30,
    last_sync_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active TINYINT(1) DEFAULT 1,
    UNIQUE KEY uk_spreadsheet (spreadsheet_id),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 同步日志表
CREATE TABLE IF NOT EXISTS sync_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_id BIGINT NOT NULL,
    direction ENUM('to_mysql','from_mysql','bidirectional') NOT NULL,
    rows_affected INT DEFAULT 0,
    rows_new INT DEFAULT 0,
    rows_updated INT DEFAULT 0,
    rows_skipped INT DEFAULT 0,
    status ENUM('running','success','partial','failed') DEFAULT 'running',
    error_message TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_config_time (config_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 变更追踪表
CREATE TABLE IF NOT EXISTS change_tracking (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_id BIGINT NOT NULL,
    source_row_key VARCHAR(256) NOT NULL,
    source_hash VARCHAR(64) NOT NULL,
    prev_value TEXT,
    last_sync_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    source ENUM('tencent','mysql') NOT NULL,
    INDEX idx_config_row (config_id, source_row_key),
    UNIQUE KEY uk_config_row (config_id, source_row_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 15.3 数据表名冲突

如果创建数据同步表时遇到表名冲突：
1. 检查 `sync_configs` 中是否已存在同名配置
2. 使用 `DROP TABLE IF EXISTS` 删除旧表（注意：会丢失数据）
3. 建议使用唯一的表名前缀，如 `sync_employees`

### 15.4 字符集问题

确保数据库使用 `utf8mb4` 字符集，否则特殊字符（如 emoji）可能无法正确同步。

```sql
ALTER DATABASE tencent_sheets_sync CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 16. 实施记录（2026-04-29 夜间迭代）
### 已修复问题
1. [UI 警告提示缺失] [新增 `refreshPreview()` 函数，在用户粘贴腾讯文档 URL 后自动调用 `/api/tencent/sheet-header`，根据返回字段显示警告横幅：`_demo: true` 显示橙色"演示数据"警告；`_doc_type: smartcanvas_non_table` 显示"智能文档类型不匹配"警告]
### 验证结果
- 橙色警告横幅在无有效凭证时正确显示
- 智能文档链接（docs.qq.com/dop/ 开头的文档）检测并显示提示
- URL 输入变化后 600ms 防抖触发预览
- 重置表单时自动清除警告
### 持续时间
- 约9小时（22:00 - 次日8:00）
