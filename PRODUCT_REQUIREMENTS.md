# 腾讯文档 MySQL 同步系统 - 产品需求规格说明书

## 1. 产品概述

### 1.1 产品名称
腾讯文档 MySQL 同步系统（Tencent Sheets MySQL Sync）

### 1.2 产品定位
企业级数据同步解决方案，实现腾讯文档在线表格与MySQL数据库的双向实时同步。

### 1.3 目标用户
- 企业内部数据管理员
- 数据工程师
- 运维人员
- 业务分析师

## 2. 功能需求

### 2.1 核心功能

#### F1: 配置管理
- 创建同步配置（腾讯文档URL、MySQL表、字段映射）
- 编辑配置
- 删除配置（软删除）
- 查看配置列表
- 测试连接

#### F2: 数据同步
- **实时同步**: Webhook模式（<3秒延迟）
- **定时同步**: 定时轮询模式（可配置间隔）
- **双向同步**: 支持Tencent → MySQL和MySQL → Tencent
- **单向同步**: 可配置只同步一个方向

#### F3: 字段映射
- 可视化配置腾讯文档列与MySQL字段的映射
- 支持字段类型转换
- 支持数据验证
- 支持方向控制（to_mysql_only/from_mysql_only/bidirectional）

#### F4: 变更追踪
- 基于SHA256哈希的增量同步
- 记录每行的上一次同步值
- 支持双向同步去重

#### F5: 监控和日志
- 记录每次同步的执行结果
- 记录影响行数、成功/失败数
- 支持日志导出
- 支持错误详情查看

### 2.2 用户故事

#### US1: 管理员配置同步
**作为** 管理员
**我想要** 配置腾讯文档和MySQL的同步关系
**以便** 自动同步数据

**验收标准：**
- ✅ 能够输入腾讯文档URL或ID
- ✅ 能够选择MySQL数据库和表
- ✅ 能够配置字段映射
- ✅ 能够测试连接
- ✅ 能够保存配置

#### US2: 实时数据同步
**作为** 管理员
**我想要** 当腾讯文档变更时自动同步到MySQL
**以便** 保持数据实时一致

**验收标准：**
- ✅ Webhook通知触发同步
- ✅ 同步延迟<5秒
- ✅ 记录同步日志

#### US3: 查看同步状态
**作为** 管理员
**我想要** 查看同步配置的状态和历史日志
**以便** 监控同步健康状况

**验收标准：**
- ✅ 显示配置的最后同步时间
- ✅ 显示最近的同步日志
- ✅ 显示同步成功/失败统计

#### US4: 管理多个配置
**作为** 管理员
**我想要** 管理多个同步配置
**以便** 同时同步多个数据源

**验收标准：**
- ✅ 列出所有配置
- ✅ 独立触发每个配置的同步
- ✅ 独立删除每个配置

### 2.3 非功能需求

#### NFR1: 性能
- 同步1000行数据 < 10秒
- 支持10个并发同步配置
- API响应时间 < 500ms

#### NFR2: 可靠性
- 数据一致性保证（不会丢失数据）
- 失败重试机制（最多3次）
- 事务支持（原子性操作）

#### NFR3: 可用性
- 服务运行时间 > 99%
- 错误恢复时间 < 1分钟
- 友好的错误提示

#### NFR4: 安全性
- API认证和授权
- Webhook签名验证
- 敏感信息加密存储
- SQL注入防护

#### NFR5: 可维护性
- 清晰的代码结构
- 完整的日志记录
- 配置文件外部化
- 易于部署和升级

## 3. 数据模型

### 3.1 同步配置（sync_configs）

| 字段 | 类型 | 说明 | 必填 |
|------|------|------|------|
| id | BIGINT | 主键 | 是 |
| spreadsheet_id | VARCHAR(128) | 腾讯文档表格ID | 是 |
| sheet_id | VARCHAR(64) | 工作表ID | 是 |
| table_name | VARCHAR(128) | MySQL表名 | 是 |
| database | VARCHAR(128) | 数据库名 | 是 |
| mapping_json | JSON | 字段映射配置 | 是 |
| sync_direction | ENUM | 同步方向 | 是 |
| poll_interval | INT | 轮询间隔(秒) | 是 |
| last_sync_at | DATETIME | 最后同步时间 | 否 |
| created_at | DATETIME | 创建时间 | 是 |
| updated_at | DATETIME | 更新时间 | 是 |
| is_active | TINYINT | 是否激活 | 是 |

### 3.2 同步日志（sync_logs）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| config_id | BIGINT | 配置ID |
| direction | ENUM | 同步方向 |
| rows_affected | INT | 影响行数 |
| rows_new | INT | 新增行数 |
| rows_updated | INT | 更新行数 |
| rows_skipped | INT | 跳过行数 |
| status | ENUM | 状态 |
| error_message | TEXT | 错误信息 |
| started_at | DATETIME | 开始时间 |
| completed_at | DATETIME | 完成时间 |

### 3.3 变更追踪（change_tracking）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| config_id | BIGINT | 配置ID |
| source_row_key | VARCHAR(256) | 行唯一标识 |
| source_hash | VARCHAR(64) | 行内容哈希 |
| prev_value | TEXT | 上一次的值 |
| source | ENUM | 数据来源 |
| last_sync_at | DATETIME | 最后同步时间 |

## 4. API接口规格

### 4.1 配置管理

#### GET /api/configs
获取所有同步配置列表

**响应：**
```json
[
  {
    "id": 1,
    "spreadsheet_id": "abc123",
    "sheet_id": "Sheet1",
    "table_name": "users",
    "database": "app_db",
    "mapping_json": {...},
    "sync_direction": "bidirectional",
    "poll_interval": 30,
    "last_sync_at": "2024-01-01T10:00:00",
    "is_active": true
  }
]
```

#### POST /api/configs
创建新配置

**请求：**
```json
{
  "spreadsheet_id": "abc123",
  "sheet_id": "Sheet1",
  "table_name": "users",
  "database": "app_db",
  "mapping_json": {
    "columns": [...],
    "sheet_header_row": 1,
    "data_start_row": 2
  },
  "sync_direction": "bidirectional",
  "poll_interval": 30
}
```

#### GET /api/configs/{id}
获取单个配置详情

#### PUT /api/configs/{id}
更新配置

#### DELETE /api/configs/{id}
删除配置（软删除）

#### POST /api/configs/{id}/test
测试连接

### 4.2 同步操作

#### POST /api/sync/{id}/trigger
手动触发同步

#### POST /api/sync/{id}/to-mysql
仅同步到MySQL

#### POST /api/sync/{id}/from-mysql
仅同步到腾讯文档

#### GET /api/sync/{id}/status
获取同步状态

### 4.3 MySQL浏览器

#### GET /api/mysql/databases
获取数据库列表

#### GET /api/mysql/databases/{db}/tables
获取表列表

#### GET /api/mysql/tables/{table}/columns
获取表结构

### 4.4 腾讯文档助手

#### GET /api/tencent/sheet-header
读取腾讯文档表头

## 5. 用户界面

### 5.1 页面结构

1. **首页仪表板**
   - 统计卡片：配置数、运行中、同步次数、成功率
   - 连接状态指示器
   
2. **配置管理**
   - 配置列表
   - 创建/编辑配置表单
   - 字段映射编辑器
   
3. **同步操作**
   - 快速同步按钮
   - 同步日志
   - 同步详情
   
4. **系统设置**
   - 连接配置
   - Webhook配置

### 5.2 交互流程

**创建配置流程：**
1. 输入腾讯文档URL
2. 选择MySQL数据库和表
3. 配置字段映射
4. 选择同步方向
5. 保存配置

**同步流程：**
1. 手动触发或自动触发
2. 读取源数据
3. 计算变更
4. 执行同步
5. 记录日志

## 6. 部署要求

### 6.1 环境要求

- Python 3.10+
- MySQL 8.0+
- Redis（可选，用于缓存）
- Nginx（反向代理）

### 6.2 配置要求

- 数据库连接池大小：5-10
- API超时：30秒
- 重试次数：3次
- 批处理大小：100行

### 6.3 监控要求

- 健康检查端点：/health
- 日志级别：INFO/ERROR
- 错误告警：错误率>5%

## 7. 验收标准

### 7.1 功能验收

- [ ] 所有API接口正常工作
- [ ] 配置管理功能完整
- [ ] 同步功能正常工作
- [ ] Webhook功能正常
- [ ] 前端界面功能完整

### 7.2 性能验收

- [ ] 1000行数据同步 < 10秒
- [ ] API响应时间 < 500ms
- [ ] 10个并发配置运行稳定

### 7.3 安全验收

- [ ] Webhook签名验证正常
- [ ] SQL注入防护正常
- [ ] 敏感信息加密存储

### 7.4 可靠性验收

- [ ] 失败重试正常
- [ ] 日志记录完整
- [ ] 错误提示友好

## 8. 版本规划

### v1.0.0 - MVP版本（当前）
- 基础同步功能
- 配置管理
- Webhook同步

### v1.1.0 - 增强版本
- 数据验证
- 操作审计
- 统计报表

### v1.2.0 - 企业版本
- 多租户支持
- 权限管理
- 高可用部署
