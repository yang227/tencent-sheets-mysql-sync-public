# API 参考文档 (API Reference)

本文档提供腾讯文档 MySQL 同步系统完整的 API 参考。

## 目录

- [API 概览](#api-概览)
- [认证方式](#认证方式)
- [通用响应格式](#通用响应格式)
- [错误代码](#错误代码)
- [系统 API](#系统-api)
- [配置管理 API](#配置管理-api)
- [同步操作 API](#同步操作-api)
- [监控 Dashboard API](#监控-dashboard-api)
- [MySQL 浏览器 API](#mysql-浏览器-api)
- [腾讯文档助手 API](#腾讯文档助手-api)
- [Webhook API](#webhook-api)
- [Prometheus 指标](#prometheus-指标)

## API 概览

### 基础信息

| 项目 | 说明 |
|------|------|
| 基础 URL | `http://localhost:8083` (默认) |
| API 版本 | v1.0.0 |
| 协议 | HTTP/HTTPS |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |

### API 端点列表

| 模块 | 端点数量 | 说明 |
|------|----------|------|
| 系统 API | 3 | 健康检查、初始化 |
| 配置管理 API | 6 | 同步配置的 CRUD |
| 同步操作 API | 5 | 触发同步、查询状态 |
| 监控 Dashboard API | 12 | 监控指标、审计日志 |
| MySQL 浏览器 API | 3 | 浏览数据库和表 |
| 腾讯文档助手 API | 1 | 读取表头 |
| Webhook API | 2 | Webhook 接收 |
| **总计** | **32** | - |

## 认证方式

### 当前认证方式

当前版本使用简单的 API Key 认证（可选）：

#### 请求头认证

```http
X-API-Key: your_api_key_here
```

#### Webhook 签名验证

Webhook 请求使用 HMAC-SHA256 签名验证：

```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, token: str) -> bool:
    expected = hmac.new(
        token.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

## 通用响应格式

### 成功响应

```json
{
  "message": "操作成功",
  "data": {...}
}
```

### 错误响应

```json
{
  "detail": "错误描述信息"
}
```

### 分页响应

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## 错误代码

### HTTP 状态码

| 状态码 | 说明 | 原因 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable Entity | 参数验证失败 |
| 429 | Too Many Requests | 请求频率限制 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务不可用 |

### 业务错误代码

| 代码 | 说明 | 解决方案 |
|------|------|----------|
| ERR_DB_CONNECTION | 数据库连接失败 | 检查数据库配置 |
| ERR_TENCENT_API | 腾讯文档 API 错误 | 检查 API 凭证 |
| ERR_MAPPING | 字段映射错误 | 检查 mapping_json 配置 |
| ERR_SYNC_TIMEOUT | 同步超时 | 增加超时配置 |
| ERR_WEBHOOK_VERIFY | Webhook 签名验证失败 | 检查 callback_token |

## 系统 API

### GET /health

检查服务健康状态。

**端点**：`GET /health`

**请求示例**：

```bash
curl http://localhost:8083/health
```

**响应示例**：

```json
{
  "status": "healthy",
  "service": "tencent-sheets-mysql-sync",
  "timestamp": "2026-04-30T12:00:00"
}
```

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 健康状态（`healthy`/`unhealthy`) |
| service | string | 服务名称 |
| timestamp | string | 时间戳（ISO 8601） |

### POST /init

初始化系统表（首次部署时调用一次）。

**端点**：`POST /init`

**请求示例**：

```bash
curl -X POST http://localhost:8083/init
```

**响应示例**：

```json
{
  "message": "系统表初始化完成"
}
```

**错误响应**：

```json
{
  "detail": "初始化失败: Table 'sync_configs' already exists"
}
```

### GET /

返回管理界面（index.html）。

**端点**：`GET /`

**说明**：返回前端管理界面 HTML 页面。

## 配置管理 API

### GET /api/configs

获取所有同步配置列表。

**端点**：`GET /api/configs`

**请求示例**：

```bash
curl http://localhost:8083/api/configs
```

**响应示例**：

```json
[
  {
    "id": 1,
    "spreadsheet_id": "abc123",
    "sheet_id": "Sheet1",
    "table_name": "users",
    "database": "app_db",
    "mapping_json": {
      "columns": [
        {
          "sheet_column": "A",
          "mysql_field": "id",
          "field_type": "INT",
          "direction": "bidirectional"
        }
      ],
      "sheet_header_row": 1,
      "data_start_row": 2
    },
    "sync_direction": "bidirectional",
    "poll_interval": 30,
    "last_sync_at": "2026-04-30T10:00:00",
    "is_active": true,
    "created_at": "2026-04-29T08:00:00",
    "updated_at": "2026-04-30T10:00:00"
  }
]
```

### POST /api/configs

创建新的同步配置。

**端点**：`POST /api/configs`

**请求体**：

```json
{
  "spreadsheet_id": "abc123",
  "sheet_id": "Sheet1",
  "table_name": "users",
  "database": "app_db",
  "mapping_json": {
    "columns": [
      {
        "sheet_column": "A",
        "mysql_field": "id",
        "field_type": "INT",
        "direction": "bidirectional"
      }
    ],
    "sheet_header_row": 1,
    "data_start_row": 2
  },
  "sync_direction": "bidirectional",
  "poll_interval": 30
}
```

**请求字段**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spreadsheet_id | string | 是 | 腾讯文档表格 ID |
| sheet_id | string | 是 | 工作表 ID 或名称 |
| table_name | string | 是 | MySQL 表名 |
| database | string | 是 | 数据库名 |
| mapping_json | object | 是 | 字段映射配置 |
| sync_direction | string | 否 | 同步方向（bidirectional/to_mysql_only/from_mysql_only） |
| poll_interval | int | 否 | 轮询间隔（秒），默认 30 |

**响应示例**：

```json
{
  "id": 1,
  "spreadsheet_id": "abc123",
  "sheet_id": "Sheet1",
  "table_name": "users",
  "database": "app_db",
  "mapping_json": {...},
  "sync_direction": "bidirectional",
  "poll_interval": 30,
  "is_active": true,
  "created_at": "2026-04-30T12:00:00",
  "updated_at": "2026-04-30T12:00:00"
}
```

### GET /api/configs/{config_id}

获取单个配置详情。

**端点**：`GET /api/configs/{config_id}`

**请求示例**：

```bash
curl http://localhost:8083/api/configs/1
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| config_id | int | 是 | 配置 ID |

**响应示例**：同 POST /api/configs 的响应

### PUT /api/configs/{config_id}

更新配置。

**端点**：`PUT /api/configs/{config_id}`

**请求体**（所有字段可选）：

```json
{
  "sheet_id": "Sheet2",
  "table_name": "new_users",
  "mapping_json": {...},
  "sync_direction": "to_mysql_only",
  "poll_interval": 60,
  "is_active": false
}
```

**响应示例**：同 POST /api/configs 的响应

### DELETE /api/configs/{config_id}

删除配置（软删除）。

**端点**：`DELETE /api/configs/{config_id}`

**请求示例**：

```bash
curl -X DELETE http://localhost:8083/api/configs/1
```

**响应示例**：

```json
{
  "message": "配置已删除"
}
```

### POST /api/configs/{config_id}/test

测试连接（腾讯文档 + MySQL）。

**端点**：`POST /api/configs/{config_id}/test`

**请求示例**：

```bash
curl -X POST http://localhost:8083/api/configs/1/test
```

**响应示例**：

```json
{
  "mysql": {
    "connected": true,
    "message": "MySQL 连接正常"
  },
  "tencent": {
    "connected": true,
    "message": "腾讯文档 API 连接正常"
  },
  "all_connected": true
}
```

## 同步操作 API

### POST /api/sync/{config_id}/trigger

手动触发一次完整同步。

**端点**：`POST /api/sync/{config_id}/trigger`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| direction | string | 否 | 指定同步方向（to_mysql/from_mysql/auto） |

**请求示例**：

```bash
curl -X POST "http://localhost:8083/api/sync/1/trigger?direction=to_mysql"
```

**响应示例**：

```json
{
  "message": "同步完成",
  "success": true,
  "direction": "to_mysql",
  "rows_affected": 100,
  "rows_new": 20,
  "rows_updated": 80,
  "rows_skipped": 5,
  "errors": [],
  "details": {
    "duration_seconds": 2.5,
    "batch_count": 1
  }
}
```

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| direction | string | 同步方向 |
| rows_affected | int | 影响行数 |
| rows_new | int | 新增行数 |
| rows_updated | int | 更新行数 |
| rows_skipped | int | 跳过行数 |
| errors | array | 错误列表 |
| details | object | 详细信息 |

### POST /api/sync/{config_id}/to-mysql

仅同步：腾讯文档 → MySQL。

**端点**：`POST /api/sync/{config_id}/to-mysql`

**请求示例**：

```bash
curl -X POST http://localhost:8083/api/sync/1/to-mysql
```

**响应示例**：同 trigger 接口

### POST /api/sync/{config_id}/from-mysql

仅同步：MySQL → 腾讯文档。

**端点**：`POST /api/sync/{config_id}/from-mysql`

**请求示例**：

```bash
curl -X POST http://localhost:8083/api/sync/1/from-mysql
```

**响应示例**：同 trigger 接口

### GET /api/sync/{config_id}/status

查看同步配置状态和最近日志。

**端点**：`GET /api/sync/{config_id}/status`

**请求示例**：

```bash
curl http://localhost:8083/api/sync/1/status
```

**响应示例**：

```json
{
  "config_id": 1,
  "is_active": true,
  "last_sync_at": "2026-04-30T10:00:00",
  "sync_status": "idle",
  "recent_logs": [
    {
      "id": 123,
      "config_id": 1,
      "direction": "to_mysql",
      "rows_affected": 100,
      "status": "success",
      "started_at": "2026-04-30T10:00:00",
      "completed_at": "2026-04-30T10:00:02"
    }
  ]
}
```

### GET /api/sync/statistics

获取同步统计信息。

**端点**：`GET /api/sync/statistics`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| config_id | int | 否 | 特定配置 ID |
| period | string | 否 | 时间周期（1h/6h/24h/7d） |

**请求示例**：

```bash
curl "http://localhost:8083/api/sync/statistics?config_id=1&period=24h"
```

**响应示例**：

```json
{
  "period": "24h",
  "config_id": 1,
  "statistics": {
    "total_syncs": 48,
    "successful_syncs": 48,
    "failed_syncs": 0,
    "success_rate": 100.0,
    "rows_synced": 4800,
    "avg_duration": 2.5,
    "p95_duration": 3.2
  }
}
```

### GET /api/sync/audit/logs

获取审计日志。

**端点**：`GET /api/sync/audit/logs`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| config_id | int | 否 | 按配置 ID 过滤 |
| event_type | string | 否 | 按事件类型过滤 |
| limit | int | 否 | 返回数量限制，默认 50 |

**请求示例**：

```bash
curl "http://localhost:8083/api/sync/audit/logs?config_id=1&limit=10"
```

### GET /api/sync/audit/export

导出审计日志。

**端点**：`GET /api/sync/audit/export`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| format | string | 否 | 导出格式（json/csv），默认 json |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**请求示例**：

```bash
curl "http://localhost:8083/api/sync/audit/export?format=csv" -o audit_logs.csv
```

## 监控 Dashboard API

### GET /api/dashboard/overview

获取系统总览。

**端点**：`GET /api/dashboard/overview`

**请求示例**：

```bash
curl http://localhost:8083/api/dashboard/overview
```

**响应示例**：

```json
{
  "timestamp": "2026-04-30T12:00:00",
  "system_health": {
    "status": "healthy",
    "uptime_seconds": 86400
  },
  "sync_overview": {
    "total_syncs": 100,
    "successful_syncs": 95,
    "failed_syncs": 5,
    "success_rate": 95.0,
    "rows_synced": 10000,
    "avg_duration": 2.5
  },
  "api_overview": {
    "total_calls": 1000,
    "successful_calls": 980,
    "failed_calls": 20,
    "avg_latency": 0.5,
    "p95_latency": 1.2
  },
  "audit_overview": {
    "total_events": 150,
    "event_types": {
      "config_created": 10,
      "sync_completed": 95,
      "sync_failed": 5
    }
  },
  "error_overview": {
    "total_errors": 20,
    "retryable_errors": 15,
    "non_retryable_errors": 5
  },
  "dead_letter_queue": {
    "total_items": 3,
    "items_24h": 1
  }
}
```

### GET /api/dashboard/sync/statistics

获取同步统计信息（详细）。

**端点**：`GET /api/dashboard/sync/statistics`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| config_id | int | 否 | 特定配置 ID |
| period | string | 否 | 时间周期（1h/6h/24h/7d） |

**响应示例**：同 /api/sync/statistics

### GET /api/dashboard/api/statistics

获取 API 调用统计。

**端点**：`GET /api/dashboard/api/statistics`

**响应示例**：

```json
{
  "calls_total": 1000,
  "calls_success": 980,
  "calls_error": 20,
  "avg_latency": 0.5,
  "p95_latency": 1.2,
  "p99_latency": 2.5,
  "by_endpoint": {
    "/api/configs": 200,
    "/api/sync/1/trigger": 150
  }
}
```

### GET /api/dashboard/errors/statistics

获取错误统计。

**端点**：`GET /api/dashboard/errors/statistics`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| period | string | 否 | 时间周期 |

**响应示例**：

```json
{
  "period": "24h",
  "total_errors": 20,
  "by_severity": {
    "critical": 2,
    "high": 5,
    "medium": 8,
    "low": 5
  },
  "by_operation": {
    "sync_to_mysql": 10,
    "sync_from_mysql": 5,
    "test_connection": 5
  },
  "retryable_count": 15,
  "non_retryable_count": 5
}
```

### GET /api/dashboard/dead-letter-queue

获取死信队列。

**端点**：`GET /api/dashboard/dead-letter-queue`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| operation | string | 否 | 按操作类型过滤 |
| limit | int | 否 | 返回数量限制，默认 100 |

**响应示例**：

```json
{
  "items": [
    {
      "index": 0,
      "operation": "sync_to_mysql",
      "config_id": 1,
      "error": "MySQL connection timeout",
      "timestamp": "2026-04-30T10:00:00",
      "retry_count": 3
    }
  ],
  "total": 3,
  "statistics": {
    "total": 3,
    "by_operation": {
      "sync_to_mysql": 3
    }
  }
}
```

### POST /api/dashboard/dead-letter-queue/{index}/retry

重试死信队列中的项目。

**端点**：`POST /api/dashboard/dead-letter-queue/{index}/retry`

**请求示例**：

```bash
curl -X POST http://localhost:8083/api/dashboard/dead-letter-queue/0/retry
```

**响应示例**：

```json
{
  "success": true,
  "message": "项目已取出，准备重试",
  "item": {
    "operation": "sync_to_mysql",
    "config_id": 1,
    "error": "..."
  }
}
```

### GET /api/dashboard/audit/statistics

获取审计统计。

**端点**：`GET /api/dashboard/audit/statistics`

**响应示例**：

```json
{
  "total_events": 150,
  "event_types": {
    "config_created": 10,
    "config_updated": 20,
    "sync_triggered": 100,
    "sync_completed": 95,
    "sync_failed": 5
  },
  "by_resource_type": {
    "config": 30,
    "sync": 100,
    "system": 20
  }
}
```

### GET /api/dashboard/audit/recent

获取最近的审计事件。

**端点**：`GET /api/dashboard/audit/recent`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| event_type | string | 否 | 按事件类型过滤 |
| limit | int | 否 | 返回数量限制，默认 50 |

**响应示例**：

```json
{
  "events": [
    {
      "timestamp": "2026-04-30T12:00:00",
      "event_type": "sync_completed",
      "operator": "127.0.0.1",
      "resource_type": "sync",
      "resource_id": "1",
      "details": {
        "direction": "to_mysql",
        "rows_affected": 100
      }
    }
  ],
  "total": 50
}
```

### GET /api/dashboard/performance/histograms

获取性能直方图数据。

**端点**：`GET /api/dashboard/performance/histograms`

**响应示例**：

```json
{
  "histograms": {
    "sync_duration": {
      "buckets": {
        "0.1": 10,
        "0.5": 50,
        "1.0": 30,
        "2.0": 10
      },
      "count": 100,
      "sum": 85.5
    },
    "api_latency": {
      "buckets": {...},
      "count": 1000,
      "sum": 450.0
    }
  }
}
```

### GET /api/sync/metrics/prometheus

获取 Prometheus 格式的指标。

**端点**：`GET /api/sync/metrics/prometheus`

**请求示例**：

```bash
curl http://localhost:8083/api/sync/metrics/prometheus
```

**响应示例**：

```
# HELP sync_requests_total Total number of sync requests
# TYPE sync_requests_total counter
sync_requests_total{status="success"} 95
sync_requests_total{status="failed"} 5

# HELP sync_duration_seconds Sync duration in seconds
# TYPE sync_duration_seconds histogram
sync_duration_seconds_bucket{le="0.1"} 10
sync_duration_seconds_bucket{le="0.5"} 60
sync_duration_seconds_bucket{le="1.0"} 90
sync_duration_seconds_bucket{le="+Inf"} 100
sync_duration_seconds_sum 85.5
sync_duration_seconds_count 100

# HELP api_requests_total Total number of API requests
# TYPE api_requests_total counter
api_requests_total{endpoint="/api/configs",method="GET",status="200"} 200
```

## MySQL 浏览器 API

### GET /api/mysql/databases

获取数据库列表。

**端点**：`GET /api/mysql/databases`

**请求示例**：

```bash
curl http://localhost:8083/api/mysql/databases
```

**响应示例**：

```json
[
  "information_schema",
  "mysql",
  "performance_schema",
  "tencent_sheets_sync",
  "app_db"
]
```

### GET /api/mysql/databases/{database}/tables

获取指定数据库的表列表。

**端点**：`GET /api/mysql/databases/{database}/tables`

**请求示例**：

```bash
curl http://localhost:8083/api/mysql/databases/app_db/tables
```

**响应示例**：

```json
[
  {
    "name": "users",
    "rows": 100,
    "engine": "InnoDB",
    "created_at": "2026-04-29T08:00:00"
  },
  {
    "name": "orders",
    "rows": 500,
    "engine": "InnoDB",
    "created_at": "2026-04-29T09:00:00"
  }
]
```

### GET /api/mysql/tables/{table_name}/columns

获取指定表的列定义。

**端点**：`GET /api/mysql/tables/{table_name}/columns`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| database | string | 否 | 数据库名，默认使用配置中的数据库 |

**请求示例**：

```bash
curl "http://localhost:8083/api/mysql/tables/users/columns?database=app_db"
```

**响应示例**：

```json
[
  {
    "name": "id",
    "type": "int",
    "nullable": false,
    "key": "PRI",
    "default": null,
    "extra": "auto_increment"
  },
  {
    "name": "name",
    "type": "varchar(255)",
    "nullable": true,
    "key": "",
    "default": null,
    "extra": ""
  },
  {
    "name": "created_at",
    "type": "datetime",
    "nullable": true,
    "key": "",
    "default": null,
    "extra": ""
  }
]
```

## 腾讯文档助手 API

### GET /api/tencent/sheet-header

读取腾讯文档的表头行。

**端点**：`GET /api/tencent/sheet-header`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spreadsheetId | string | 是 | 腾讯文档表格 ID |
| sheetName | string | 否 | 工作表名称，默认 Sheet1 |
| headerRow | int | 否 | 表头所在行，默认 1 |

**请求示例**：

```bash
curl "http://localhost:8083/api/tencent/sheet-header?spreadsheetId=abc123&sheetName=Sheet1&headerRow=1"
```

**响应示例**：

```json
{
  "spreadsheetId": "abc123",
  "sheetName": "Sheet1",
  "columns": [
    "A_ID",
    "B_姓名",
    "C_年龄",
    "D_城市"
  ],
  "headerRow": 1
}
```

## Webhook API

### POST /webhook/tencent/callback

接收腾讯文档变更回调。

**端点**：`POST /webhook/tencent/callback`

**请求头**：

| Header | 说明 |
|--------|------|
| X-Signature | HMAC-SHA256 签名 |
| X-Timestamp | 时间戳 |

**请求体示例**：

```json
{
  "event": "sheet_change",
  "spreadsheetId": "abc123",
  "changedRange": "Sheet1!A1:Z100"
}
```

**响应示例**：

```json
{
  "status": "ok",
  "message": "已接收，正在处理"
}
```

**说明**：
- 该接口会立即返回 200，同步任务在后台执行
- 如果配置了 `callback_token`，会验证签名
- 签名计算方法：`HMAC-SHA256(payload + timestamp, token)`

### GET /webhook/tencent/health

Webhook 端点健康检查。

**端点**：`GET /webhook/tencent/health`

**请求示例**：

```bash
curl http://localhost:8083/webhook/tencent/health
```

**响应示例**：

```json
{
  "status": "ok"
}
```

## Prometheus 指标

### 可用指标

| 指标名称 | 类型 | 标签 | 说明 |
|---------|------|------|------|
| `sync_requests_total` | Counter | status | 同步请求总数 |
| `sync_duration_seconds` | Histogram | - | 同步耗时 |
| `sync_rows_affected` | Counter | - | 同步影响行数 |
| `api_requests_total` | Counter | endpoint, method, status | API 请求总数 |
| `api_request_duration_seconds` | Histogram | endpoint | API 响应时间 |
| `mysql_connections_active` | Gauge | - | MySQL 活跃连接数 |
| `webhook_requests_total` | Counter | status | Webhook 请求总数 |
| `audit_events_total` | Counter | event_type | 审计事件总数 |
| `retry_attempts_total` | Counter | operation | 重试次数总数 |
| `dead_letter_queue_size` | Gauge | - | 死信队列大小 |

### 使用 Prometheus 采集

在 `prometheus.yml` 中添加：

```yaml
scrape_configs:
  - job_name: 'sync-service'
    static_configs:
      - targets: ['localhost:8083']
    metrics_path: '/api/sync/metrics/prometheus'
    scrape_interval: 5s
```

### Grafana 仪表板

导入预配置的 Grafana 仪表板（JSON 文件位于 `grafana/dashboards/sync-service.json`）。

关键面板：
1. **系统概览**：服务健康状态、运行时间
2. **同步统计**：成功/失败次数、同步速率
3. **API 性能**：请求量、响应时间、错误率
4. **数据库性能**：连接数、查询性能
5. **资源使用**：CPU、内存、磁盘

---

**文档版本**：v1.0.0  
**最后更新**：2026-04-30  
**维护者**：API 团队
