# 故障排查指南 (Troubleshooting Guide)

本文档帮助系统管理员和开发人员快速定位和解决问题。

## 目录

- [问题分类](#问题分类)
- [快速诊断](#快速诊断)
- [常见问题](#常见问题)
- [错误代码](#错误代码)
- [日志分析](#日志分析)
- [调试方法](#调试方法)
- [性能问题](#性能问题)
- [网络问题](#网络问题)

## 问题分类

### 问题严重性级别

| 级别 | 说明 | 响应时间 | 示例 |
|------|------|----------|------|
| P0 - 致命 | 系统完全不可用 | 立即响应 | 服务无法启动、数据库崩溃 |
| P1 - 严重 | 核心功能不可用 | 1 小时内 | 同步失败、数据丢失 |
| P2 - 一般 | 部分功能异常 | 4 小时内 | Webhook 失败、性能下降 |
| P3 - 轻微 | 非核心功能问题 | 24 小时内 | UI 显示异常、日志错误 |

## 快速诊断

### 诊断流程图

```
开始诊断
    │
    ├─ 服务是否运行？
    │   ├─ 否 → 检查服务状态和日志
    │   └─ 是 → 继续
    │
    ├─ 健康检查是否通过？
    │   ├─ 否 → 检查依赖服务
    │   └─ 是 → 继续
    │
    ├─ 数据库连接是否正常？
    │   ├─ 否 → 检查数据库状态
    │   └─ 是 → 继续
    │
    ├─ API 是否正常响应？
    │   ├─ 否 → 检查应用日志
    │   └─ 是 → 继续
    │
    └─ 问题定位成功 → 查看对应章节
```

### 一键诊断脚本

创建 `/opt/scripts/diagnose.sh`：

```bash
#!/bin/bash
# 腾讯文档 MySQL 同步系统 - 诊断脚本

echo "=========================================="
echo "  同步系统诊断工具"
echo "=========================================="
echo ""

# 1. 检查服务状态
echo "[1/8] 检查服务状态..."
systemctl is-active --quiet sync-service && echo "  ✓ 服务运行正常" || echo "  ✗ 服务未运行"
echo ""

# 2. 检查端口监听
echo "[2/8] 检查端口监听..."
netstat -tulpn 2>/dev/null | grep -q ":8083 " && echo "  ✓ 端口 8083 正常监听" || echo "  ✗ 端口 8083 未监听"
echo ""

# 3. 检查健康检查
echo "[3/8] 检查健康检查..."
curl -sf http://localhost:8083/health > /dev/null && echo "  ✓ 健康检查通过" || echo "  ✗ 健康检查失败"
echo ""

# 4. 检查 MySQL 连接
echo "[4/8] 检查 MySQL 连接..."
mysqladmin -h localhost ping > /dev/null 2>&1 && echo "  ✓ MySQL 连接正常" || echo "  ✗ MySQL 连接失败"
echo ""

# 5. 检查磁盘空间
echo "[5/8] 检查磁盘空间..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "  ✓ 磁盘使用率正常 (${DISK_USAGE}%)"
else
    echo "  ✗ 磁盘使用率过高 (${DISK_USAGE}%)"
fi
echo ""

# 6. 检查内存使用
echo "[6/8] 检查内存使用..."
MEM_USAGE=$(free | awk 'NR==2 {printf "%.0f", $3/$2 * 100}')
if [ "$MEM_USAGE" -lt 80 ]; then
    echo "  ✓ 内存使用率正常 (${MEM_USAGE}%)"
else
    echo "  ✗ 内存使用率过高 (${MEM_USAGE}%)"
fi
echo ""

# 7. 检查日志错误
echo "[7/8] 检查最近错误..."
ERROR_COUNT=$(journalctl -u sync-service --since "1 hour ago" | grep -c "ERROR" || echo "0")
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "  ✓ 最近 1 小时无错误日志"
else
    echo "  ✗ 最近 1 小时有 ${ERROR_COUNT} 条错误"
fi
echo ""

# 8. 检查同步状态
echo "[8/8] 检查同步状态..."
CONFIG_COUNT=$(curl -sf http://localhost:8083/api/configs 2>/dev/null | jq '. | length' 2>/dev/null || echo "0")
echo "  ℹ 当前有 ${CONFIG_COUNT} 个同步配置"
echo ""

echo "=========================================="
echo "  诊断完成"
echo "=========================================="
```

运行诊断：

```bash
chmod +x /opt/scripts/diagnose.sh
sudo /opt/scripts/diagnose.sh
```

## 常见问题

### 1. 服务无法启动

#### 症状
- `systemctl start sync-service` 失败
- 端口 8083 未监听
- 浏览器无法访问管理界面

#### 排查步骤

**步骤 1：检查服务状态**

```bash
sudo systemctl status sync-service -l

# 查看详细日志
sudo journalctl -u sync-service -n 100 --no-pager
```

**步骤 2：检查配置文件**

```bash
# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 验证环境变量
cat .env

# 检查文件权限
ls -la config.yaml .env
```

**步骤 3：检查端口占用**

```bash
# 检查 8083 端口是否被占用
sudo netstat -tulpn | grep 8083

# 如果被占用，找出进程
sudo lsof -i :8083
```

**步骤 4：手动启动调试**

```bash
# 激活虚拟环境
source .venv/bin/activate

# 手动启动查看详细错误
python -m uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
```

#### 常见原因和解决方案

| 原因 | 解决方案 |
|------|----------|
| 端口被占用 | 修改 `config.yaml` 中的 `app.port` 或停止占用端口的进程 |
| 配置文件错误 | 检查 `config.yaml` 和 `.env` 文件格式 |
| 依赖缺失 | 重新运行 `pip install -r requirements.txt` |
| 权限不足 | 确保运行用户有访问日志目录和配置文件的权限 |
| MySQL 未启动 | `sudo systemctl start mysql` |

### 2. 同步失败

#### 症状
- 手动触发同步返回错误
- 同步日志显示失败状态
- Webhook 触发后数据未同步

#### 排查步骤

**步骤 1：查看同步日志**

```bash
# 查看最近同步日志
curl -s http://localhost:8083/api/sync/1/status | jq .

# 查看应用日志中的同步错误
grep "ERROR" logs/app.log | tail -50
```

**步骤 2：测试连接**

```bash
# 测试 MySQL 连接
curl -X POST http://localhost:8083/api/configs/1/test

# 手动测试 MySQL
mysql -h localhost -u root -p -e "SELECT 1"

# 手动测试腾讯文档 API
python -c "from app.services.tencent_api import TencentAPI; api = TencentAPI(); print(api.test_connection())"
```

**步骤 3：检查字段映射**

```bash
# 获取配置详情
curl -s http://localhost:8083/api/configs/1 | jq .mapping_json

# 验证映射配置是否正确
# 确保 sheet_column 和 mysql_field 都存在
```

**步骤 4：检查数据格式**

```bash
# 查看腾讯文档数据
curl -s http://localhost:8083/api/tencent/sheet-header?config_id=1

# 查看 MySQL 表结构
mysql -h localhost -u root -p -e "DESC your_table" your_database
```

#### 常见错误和解决方案

| 错误信息 | 原因 | 解决方案 |
|---------|------|----------|
| `Configuration not found` | 配置 ID 不存在 | 检查配置 ID 是否正确 |
| `MySQL connection failed` | 数据库连接失败 | 检查数据库配置和网络 |
| `Tencent API error` | 腾讯文档 API 调用失败 | 检查 App ID 和 Secret 是否正确 |
| `Field mapping error` | 字段映射配置错误 | 检查 `mapping_json` 配置 |
| `Data type mismatch` | 数据类型不匹配 | 检查字段类型转换配置 |
| `Duplicate entry` | 主键冲突 | 检查数据是否已存在 |
| `Timeout` | 请求超时 | 增加超时配置或检查网络 |

### 3. Webhook 不工作

#### 症状
- 腾讯文档变更后未触发同步
- Webhook 回调未接收到
- 日志中无 Webhook 相关记录

#### 排查步骤

**步骤 1：检查 Webhook 配置**

```bash
# 查看配置中的 callback_token
grep callback_token config.yaml

# 检查 webhook_base_url
grep webhook_base_url config.yaml
```

**步骤 2：测试 Webhook 端点**

```bash
# 测试 Webhook 健康检查
curl http://localhost:8083/webhook/tencent/health

# 手动发送测试 Webhook 请求
curl -X POST http://localhost:8083/webhook/tencent/callback \
  -H "Content-Type: application/json" \
  -H "X-Tencent-Signature: test_signature" \
  -d '{"event_type": "sheet_change", "sheet_id": "test"}'
```

**步骤 3：检查网络连通性**

```bash
# 如果 webhook_base_url 是公网地址，检查是否可以访问
curl -I https://your-domain.com/webhook/tencent/health

# 检查防火墙规则
sudo iptables -L -n | grep 8083
```

#### 解决方案

1. **配置 Webhook URL**
   - 在腾讯文档开放平台配置 Webhook URL
   - 确保 URL 可以被腾讯文档服务器访问

2. **验证 Token**
   - 确保 `callback_token` 在 config.yaml 中正确配置
   - 在腾讯文档开放平台配置的 Token 要与之匹配

3. **检查签名验证**
   - 如果启用了签名验证，确保签名计算正确
   - 可以在开发环境临时禁用签名验证进行调试

### 4. 性能问题

#### 症状
- 同步速度慢
- API 响应时间长
- 系统负载高

#### 排查步骤

**步骤 1：检查系统资源**

```bash
# 查看 CPU 使用率
top -b -n 1 | grep "Cpu(s)"

# 查看内存使用
free -h

# 查看磁盘 I/O
iostat -x 1 5
```

**步骤 2：检查数据库性能**

```sql
-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query_log';
SHOW VARIABLES LIKE 'long_query_time';

-- 查看当前连接
SHOW PROCESSLIST;

-- 查看表状态
CHECK TABLE sync_configs, sync_logs, change_tracking;
```

**步骤 3：分析应用日志**

```bash
# 查看同步耗时
grep "sync_duration" logs/app.log | tail -20

# 查看 API 响应时间
grep "request_duration" logs/app.log | tail -20
```

#### 性能优化建议

1. **数据库优化**
   - 为频繁查询的字段添加索引
   - 定期运行 `OPTIMIZE TABLE`
   - 调整 MySQL 连接池大小

2. **应用优化**
   - 增加 `batch_size` 提高批量处理效率
   - 调整 `poll_interval` 减少轮询频率
   - 使用多 worker 提高并发能力

3. **系统优化**
   - 使用 SSD 存储
   - 增加内存
   - 使用 Redis 缓存

### 5. 数据库连接问题

#### 症状
- 频繁出现数据库连接错误
- 同步任务超时
- 应用日志显示数据库连接池耗尽

#### 排查步骤

```bash
# 检查 MySQL 最大连接数
mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"

# 检查当前连接数
mysql -u root -p -e "SHOW STATUS LIKE 'Threads_connected';"

# 查看连接来源
mysql -u root -p -e "SHOW PROCESSLIST;" | grep sync
```

#### 解决方案

1. **增加数据库连接池大小**

   编辑 `config.yaml`：

   ```yaml
   database:
     host: "localhost"
     port: 3306
     user: "root"
     password: "change_this_password"
     name: "tencent_sheets_sync"
     pool_size: 20  # 增加连接池大小
     max_overflow: 10
   ```

2. **优化连接使用**

   确保应用正确释放数据库连接：
   - 检查是否有连接泄漏
   - 使用连接池管理
   - 设置合理的连接超时

## 错误代码

### API 错误代码

| 代码 | 说明 | 原因 | 解决方案 |
|------|------|------|----------|
| 400 | Bad Request | 请求参数错误 | 检查请求参数格式 |
| 401 | Unauthorized | 未授权 | 检查认证配置 |
| 404 | Not Found | 资源不存在 | 检查资源 ID |
| 409 | Conflict | 资源冲突 | 检查数据是否已存在 |
| 422 | Unprocessable Entity | 参数验证失败 | 检查参数类型和必填项 |
| 429 | Too Many Requests | 请求频率限制 | 降低请求频率 |
| 500 | Internal Server Error | 服务器内部错误 | 查看服务器日志 |
| 503 | Service Unavailable | 服务不可用 | 检查依赖服务状态 |

### 同步错误代码

| 代码 | 说明 | 解决方案 |
|------|------|----------|
| ERR_SYNC_001 | 配置不存在 | 检查配置 ID |
| ERR_SYNC_002 | MySQL 连接失败 | 检查数据库配置 |
| ERR_SYNC_003 | 腾讯文档 API 错误 | 检查 API 凭证 |
| ERR_SYNC_004 | 字段映射错误 | 检查映射配置 |
| ERR_SYNC_005 | 数据类型不匹配 | 检查字段类型 |
| ERR_SYNC_006 | 权限不足 | 检查数据库权限 |
| ERR_SYNC_007 | 超时 | 增加超时配置 |
| ERR_SYNC_008 | 数据验证失败 | 检查数据格式 |

### 数据库错误代码

| 代码 | 说明 | 解决方案 |
|------|------|----------|
| 1045 | Access denied | 检查用户名和密码 |
| 1049 | Unknown database | 创建数据库 |
| 1054 | Unknown column | 检查表结构 |
| 1062 | Duplicate entry | 检查唯一性约束 |
| 1146 | Table doesn't exist | 检查表是否存在 |
| 2002 | Connection refused | 检查 MySQL 是否运行 |
| 2003 | Can't connect | 检查网络连接 |

## 日志分析

### 日志位置

| 日志类型 | 位置 | 说明 |
|---------|------|------|
| 应用日志 | `logs/app.log` | 主应用日志 |
| 错误日志 | `logs/error.log` | 错误日志 |
| 访问日志 | `logs/access.log` | HTTP 访问日志 |
| MySQL 日志 | `/var/log/mysql/error.log` | MySQL 错误日志 |
| Systemd 日志 | `journalctl -u sync-service` | 服务日志 |

### 日志级别

```python
# 日志配置示例
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': {
        'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
        'handlers': ['file', 'console'],
    },
}
```

### 常见日志模式

#### 1. 同步成功日志

```
INFO:app.services.sync_engine:Sync completed successfully - config_id=1, direction=bidirectional, rows_affected=100, duration=2.5s
```

#### 2. 同步失败日志

```
ERROR:app.services.sync_engine:Sync failed - config_id=1, error=MySQL connection timeout, retry_attempt=1/3
```

#### 3. API 请求日志

```
INFO:uvicorn.access:127.0.0.1:12345 - "POST /api/sync/1/trigger HTTP/1.1" 200 OK - duration=350ms
```

#### 4. 数据库连接日志

```
WARNING:app.services.mysql_service:Database connection pool exhausted - active=10, pool_size=10
```

### 日志分析命令

```bash
# 统计错误数量
grep -c "ERROR" logs/app.log

# 查看最近错误
tail -50 logs/app.log | grep "ERROR"

# 统计同步成功/失败次数
grep -c "Sync completed successfully" logs/app.log
grep -c "Sync failed" logs/app.log

# 分析 API 响应时间
grep "duration=" logs/app.log | awk '{print $NF}' | sed 's/s$//' | sort -n

# 查看特定配置的日志
grep "config_id=1" logs/app.log
```

## 调试方法

### 1. 启用调试模式

#### 临时启用调试模式

```bash
# 设置日志级别为 DEBUG
export LOG_LEVEL=DEBUG

# 重启服务
sudo systemctl restart sync-service
```

#### 针对特定模块启用调试

```python
# 在代码中临时添加
import logging
logging.getLogger('app.services.sync_engine').setLevel(logging.DEBUG)
```

### 2. 使用 Python 调试器

```bash
# 安装 debugpy
pip install debugpy

# 修改启动命令
python -m debugpy --listen 5678 --wait-for-client \
  -m uvicorn app.main:app --host 0.0.0.0 --port 8083
```

然后使用 VS Code 或 PyCharm 连接到 5678 端口进行调试。

### 3. 手动测试 API

#### 使用 curl 测试

```bash
# 获取所有配置
curl -X GET http://localhost:8083/api/configs \
  -H "Content-Type: application/json" | jq .

# 创建配置
curl -X POST http://localhost:8083/api/configs \
  -H "Content-Type: application/json" \
  -d '{
    "spreadsheet_id": "test123",
    "sheet_id": "Sheet1",
    "table_name": "users",
    "database": "app_db",
    "mapping_json": {...},
    "sync_direction": "bidirectional",
    "poll_interval": 30
  }' | jq .

# 触发同步
curl -X POST http://localhost:8083/api/sync/1/trigger | jq .
```

#### 使用 Python 测试

```python
import requests

# 获取配置列表
response = requests.get('http://localhost:8083/api/configs')
print(response.json())

# 触发同步
response = requests.post('http://localhost:8083/api/sync/1/trigger')
print(response.json())
```

### 4. 数据库调试

```sql
-- 查看同步配置
SELECT * FROM sync_configs WHERE is_active = 1;

-- 查看最近同步日志
SELECT * FROM sync_logs ORDER BY started_at DESC LIMIT 10;

-- 查看变更追踪记录
SELECT * FROM change_tracking WHERE config_id = 1 LIMIT 10;

-- 检查数据一致性
SELECT
    (SELECT COUNT(*) FROM sync_configs) AS config_count,
    (SELECT COUNT(*) FROM sync_logs) AS log_count,
    (SELECT COUNT(*) FROM change_tracking) AS tracking_count;
```

## 性能问题

### 性能瓶颈定位

#### 1. CPU 瓶颈

**症状**：
- CPU 使用率持续 > 80%
- 系统负载高
- 响应时间变长

**排查**：

```bash
# 查看 CPU 使用率
top -b -n 1 | head -20

# 查看哪个进程占用 CPU 高
ps aux --sort=-%cpu | head -10

# 使用 perf 分析（Linux）
perf top -p $(pgrep -f "uvicorn app.main:app")
```

**解决方案**：
- 优化同步逻辑，减少不必要的计算
- 使用多进程/多线程
- 升级 CPU

#### 2. 内存瓶颈

**症状**：
- 内存使用率 > 80%
- 频繁触发 GC
- OOM (Out of Memory) 错误

**排查**：

```bash
# 查看内存使用
free -h
ps aux --sort=-%mem | head -10

# 查看 Python 内存使用
python -m memory_profiler your_script.py
```

**解决方案**：
- 减少批量处理大小 (`batch_size`)
- 及时释放不需要的对象
- 增加系统内存

#### 3. 磁盘 I/O 瓶颈

**症状**：
- 磁盘 I/O 等待时间高 (`%wa` in `top`)
- 数据库查询慢
- 日志写入延迟

**排查**：

```bash
# 查看磁盘 I/O 统计
iostat -x 1 5

# 查看哪个进程在频繁 I/O
iotop -o

# 查看磁盘使用
df -h
```

**解决方案**：
- 使用 SSD 替换 HDD
- 优化数据库查询
- 启用日志轮转

#### 4. 网络瓶颈

**症状**：
- 网络延迟高
- 请求超时
- 带宽饱和

**排查**：

```bash
# 查看网络流量
iftop -i eth0

# 测试网络延迟
ping docs.qq.com

# 测试带宽
speedtest-cli
```

**解决方案**：
- 升级网络带宽
- 使用 CDN 加速
- 优化 API 请求大小

### 性能调优清单

- [ ] 数据库索引优化
- [ ] 查询优化（使用 `EXPLAIN` 分析）
- [ ] 连接池配置优化
- [ ] 批量处理大小调整
- [ ] 缓存策略（Redis）
- [ ] 异步任务处理
- [ ] 限流和熔断配置

## 网络问题

### 1. 连接超时

#### 症状
- `Connection timeout` 错误
- 请求长时间无响应
- 同步任务卡住

#### 排查步骤

```bash
# 测试网络连通性
ping docs.qq.com

# 测试端口连通性
telnet docs.qq.com 443

# 使用 curl 测试超时
curl -m 10 https://docs.qq.com

# 查看防火墙规则
sudo iptables -L -n
```

#### 解决方案

1. **增加超时时间**

   编辑 `config.yaml`：

   ```yaml
   tencent:
     timeout: 30  # 增加超时时间（秒）

   sync:
     request_timeout: 60  # 同步请求超时
   ```

2. **检查防火墙配置**

   ```bash
   # 允许出方向 HTTPS 流量
   sudo ufw allow out 443/tcp
   ```

3. **使用代理（如果需要）**

   ```python
   # 在代码中配置代理
   proxies = {
       'http': 'http://proxy.example.com:8080',
       'https': 'http://proxy.example.com:8080',
   }
   ```

### 2. DNS 解析问题

#### 症状
- `Could not resolve host` 错误
- 域名无法访问
- 间歇性的连接失败

#### 排查步骤

```bash
# 测试 DNS 解析
nslookup docs.qq.com

# 查看 DNS 配置
cat /etc/resolv.conf

# 使用 dig 测试
dig docs.qq.com
```

#### 解决方案

1. **配置 DNS 服务器**

   编辑 `/etc/resolv.conf`：

   ```
   nameserver 8.8.8.8
   nameserver 114.114.114.114
   ```

2. **使用 IP 地址（临时方案）**

   如果 DNS 持续有问题，可以在 `/etc/hosts` 中添加：

   ```
   113.108.19.23 docs.qq.com
   ```

### 3. SSL/TLS 证书问题

#### 症状
- `SSL certificate verify failed` 错误
- HTTPS 请求失败

#### 解决方案

1. **更新证书**

   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install --reinstall ca-certificates

   # CentOS/RHEL
   sudo yum reinstall ca-certificates
   ```

2. **禁用证书验证（仅开发环境）**

   ```python
   import ssl
   ssl._create_default_https_context = ssl._create_unverified_context
   ```

## 联系支持

如果以上方法无法解决问题，请收集以下信息后联系技术支持：

### 收集诊断信息

```bash
# 创建诊断报告
cat > /tmp/diagnostic_report.txt << EOF
=== 诊断报告 ===
时间: $(date)
主机名: $(hostname)
系统: $(cat /etc/os-release | grep PRETTY_NAME)

=== 服务状态 ===
$(systemctl status sync-service)

=== 最近日志 ===
$(tail -100 /var/log/sync-service/app.log)

=== 配置信息 ===
$(cat config.yaml | grep -v password | grep -v secret)

=== 资源使用 ===
$(top -b -n 1 | head -20)
$(free -h)
$(df -h)

=== 网络连接 ===
$(netstat -tulpn | grep 8083)
EOF

# 查看报告
cat /tmp/diagnostic_report.txt
```

### 提交问题

- **GitHub Issues**：https://github.com/your-repo/issues
- **邮件支持**：support@example.com
- **提供信息**：
  - 错误日志
  - 配置文件（隐藏敏感信息）
  - 复现步骤
  - 环境信息（OS、Python 版本等）

---

**文档版本**：v1.0.0  
**最后更新**：2026-04-30  
**维护者**：技术支持团队
