# 性能调优指南 (Performance Tuning Guide)

本文档提供腾讯文档 MySQL 同步系统的性能优化建议和最佳实践。

## 目录

- [性能目标](#性能目标)
- [系统级优化](#系统级优化)
- [数据库优化](#数据库优化)
- [应用级优化](#应用级优化)
- [同步引擎优化](#同步引擎优化)
- [API 性能优化](#api-性能优化)
- [缓存策略](#缓存策略)
- [监控性能指标](#监控性能指标)
- [性能测试](#性能测试)
- [性能调优清单](#性能调优清单)

## 性能目标

### 关键性能指标 (KPI)

| 指标 | 目标值 | 警告阈值 | 严重阈值 |
|------|--------|----------|----------|
| API 响应时间 (p95) | < 500ms | 500-1000ms | > 1000ms |
| 同步耗时 (1000 行) | < 10s | 10-30s | > 30s |
| 同步成功率 | > 99% | 95-99% | < 95% |
| 系统可用性 | > 99.9% | 99-99.9% | < 99% |
| 并发处理能力 | 100 req/s | 50-100 req/s | < 50 req/s |
| 内存使用率 | < 70% | 70-85% | > 85% |
| CPU 使用率 | < 70% | 70-85% | > 85% |

### 性能基准

在以下环境中测试得到的基准数据：

**测试环境**：
- CPU：4 核 2.5GHz
- 内存：8 GB
- 磁盘：SSD
- 网络：1 Gbps
- MySQL：8.0
- Python：3.10

**基准数据**：

| 操作 | 数据量 | 平均耗时 | p95 耗时 |
|------|--------|----------|----------|
| 创建配置 | - | 150ms | 200ms |
| 触发同步 | 100 行 | 1.2s | 1.5s |
| 触发同步 | 1000 行 | 8.5s | 10.2s |
| 触发同步 | 10000 行 | 75s | 85s |
| 查询配置 | - | 50ms | 80ms |
| Webhook 接收 | - | 100ms | 150ms |

## 系统级优化

### 1. 操作系统优化

#### Linux 系统参数调优

编辑 `/etc/sysctl.conf`：

```conf
# 增加文件描述符限制
fs.file-max = 1000000

# 网络优化
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# TCP 连接复用
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30

# 内存管理
vm.swappiness = 10
vm.dirty_ratio = 60
vm.dirty_background_ratio = 5

# 应用生效
sudo sysctl -p
```

#### 增加文件描述符限制

编辑 `/etc/security/limits.conf`：

```
* soft nofile 65535
* hard nofile 65535
* soft nproc 65535
* hard nproc 65535
```

#### 磁盘 I/O 调度器

```bash
# 查看当前调度器
cat /sys/block/sda/queue/scheduler

# 设置为 deadline（适合数据库）
echo deadline | sudo tee /sys/block/sda/queue/scheduler

# 永久生效（Ubuntu）
echo 'ACTION=="add|change", KERNEL=="sda", ATTR{queue/scheduler}="deadline"' | sudo tee /etc/udev/rules.d/60-scheduler.rules
```

### 2. Python 运行环境优化

#### 使用 PyPy 或优化 CPython

```bash
# 安装 PyPy（可选，适合 CPU 密集型任务）
sudo apt install pypy3
pypy3 -m pip install -r requirements.txt

# 启动应用
pypy3 -m uvicorn app.main:app --host 0.0.0.0 --port 8083
```

#### 编译优化

```bash
# 使用 PGO (Profile Guided Optimization) 编译 Python
# 参考：https://realpython.com/pypy-faster-python/
```

#### 使用异步运行时优化

```python
# 使用 uvloop 替代默认事件循环（仅 Linux）
# 在 app/main.py 中添加：

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
```

安装：

```bash
pip install uvloop
```

### 3. 进程管理优化

#### 使用多进程

```bash
# 启动多个 worker 进程
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8083 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker
```

#### Worker 数量计算

```
推荐的 worker 数量 = (CPU 核心数 × 2) + 1

例如：
- 4 核 CPU：(4 × 2) + 1 = 9 workers
- 8 核 CPU：(8 × 2) + 1 = 17 workers
```

#### 使用 Gunicorn 管理进程

```bash
# 安装 gunicorn
pip install gunicorn

# 使用 gunicorn + uvicorn worker
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8083 \
  --access-logfile - \
  --error-logfile - \
  --timeout 120
```

## 数据库优化

### 1. MySQL 配置优化

编辑 `/etc/mysql/mysql.conf.d/mysqld.cnf`：

```ini
[mysqld]
# 基础配置
max_connections = 200
max_connect_errors = 10000

# 缓存配置
innodb_buffer_pool_size = 4G  # 设置为系统内存的 50-70%
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2  # 提高性能，牺牲少量持久性
innodb_flush_method = O_DIRECT

# 查询缓存（MySQL 8.0 已移除，仅适用于 5.7）
# query_cache_size = 64M
# query_cache_type = 1

# 连接配置
wait_timeout = 600
interactive_timeout = 600
thread_cache_size = 16

# 临时表
tmp_table_size = 64M
max_heap_table_size = 64M

# 慢查询日志
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
```

### 2. 索引优化

#### 为同步相关表添加索引

```sql
-- sync_configs 表索引
ALTER TABLE sync_configs ADD INDEX idx_is_active (is_active);
ALTER TABLE sync_configs ADD INDEX idx_created_at (created_at);

-- sync_logs 表索引
ALTER TABLE sync_logs ADD INDEX idx_config_id (config_id);
ALTER TABLE sync_logs ADD INDEX idx_started_at (started_at);
ALTER TABLE sync_logs ADD INDEX idx_status (status);

-- change_tracking 表索引
ALTER TABLE change_tracking ADD INDEX idx_config_id (config_id);
ALTER TABLE change_tracking ADD INDEX idx_source_row_key (config_id, source_row_key);
ALTER TABLE change_tracking ADD INDEX idx_last_sync_at (last_sync_at);
```

#### 分析查询性能

```sql
-- 启用慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- 查看慢查询
SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10;

-- 使用 EXPLAIN 分析查询
EXPLAIN SELECT * FROM sync_configs WHERE is_active = 1;
```

### 3. 数据库连接池优化

#### 配置连接池

在 `app/services/mysql_service.py` 中配置：

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# 创建数据库引擎（带连接池）
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,          # 常驻连接数
    max_overflow=20,       # 超出 pool_size 后最多创建的连接数
    pool_timeout=30,        # 获取连接的超时时间（秒）
    pool_recycle=3600,     # 连接回收时间（秒），防止 MySQL 断开
    pool_pre_ping=True,    # 每次取出连接前先 ping，确保连接有效
)
```

#### 监控连接池

```python
# 在 app/services/mysql_service.py 中添加监控
from sqlalchemy import event

@event.listens_for(engine, "checkout")
def on_checkout(dbapi_conn, connection_rec, connection_proxy):
    logger.debug(f"Checkout connection: {connection_rec}")

@event.listens_for(engine, "checkin")
def on_checkin(dbapi_conn, connection_rec):
    logger.debug(f"Checkin connection: {connection_rec}")
```

### 4. 查询优化

#### 使用批量操作

```python
# 不好的做法：逐条插入
for row in rows:
    cursor.execute("INSERT INTO table VALUES (...)")

# 好的做法：批量插入
cursor.executemany(
    "INSERT INTO table VALUES (%s, %s, %s)",
    [(row['col1'], row['col2'], row['col3']) for row in rows]
)
```

#### 使用事务

```python
# 不好的做法：自动提交
for row in rows:
    session.add(row)
    session.commit()  # 每次都提交，性能差

# 好的做法：批量提交
for row in rows:
    session.add(row)
session.commit()  # 一次性提交
```

## 应用级优化

### 1. 同步引擎优化

#### 调整批量大小

在 `config.yaml` 中配置：

```yaml
sync:
  batch_size: 500  # 默认 100，可根据实际情况调整
```

#### 启用并行处理

```python
# 在 app/services/sync_engine.py 中添加并行处理
from concurrent.futures import ThreadPoolExecutor

class SyncEngine:
    def sync_to_mysql(self):
        # 将数据进行分片
        chunks = [self.data[i:i + self.batch_size] for i in range(0, len(self.data), self.batch_size)]

        # 并行处理
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._process_chunk, chunk) for chunk in chunks]
            results = [f.result() for f in futures]

        return self._aggregate_results(results)
```

#### 使用异步 I/O

```python
# 在 app/services/tencent_api.py 中使用异步 HTTP 客户端
import httpx

class TencentAPI:
    async def fetch_sheet_data(self, spreadsheet_id: str, sheet_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://docs.qq.com/v1/sheets/{spreadsheet_id}/values/{sheet_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
```

### 2. 减少不必要的查询

#### 使用缓存

```python
from functools import lru_cache

class MySQLService:
    @lru_cache(maxsize=128)
    def get_table_structure(self, table_name: str):
        """缓存表结构查询结果"""
        return self.execute(f"DESC {table_name}")
```

#### 预加载关联数据

```python
# 不好的做法：N+1 查询
configs = self.get_configs()
for config in configs:
    logs = self.get_logs_by_config_id(config.id)  # 每个 config 都查询一次
    config.logs = logs

# 好的做法：一次查询所有关联数据
configs = self.get_configs()
config_ids = [c.id for c in configs]
logs = self.get_logs_by_config_ids(config_ids)  # 一次查询
logs_by_config = {}
for log in logs:
    logs_by_config.setdefault(log.config_id, []).append(log)
for config in configs:
    config.logs = logs_by_config.get(config.id, [])
```

### 3. JSON 序列化优化

#### 使用更快的 JSON 库

```bash
# 安装 orjson（比标准库 json 快 2-3 倍）
pip install orjson
```

```python
# 在代码中使用 orjson
import orjson

# 替换 json.dumps/loads
data = orjson.loads(json_bytes)
json_bytes = orjson.dumps(data)
```

#### 延迟序列化

```python
# 不好的做法：提前序列化
data = {"key": "value"}
json_str = json.dumps(data)  # 提前序列化
self.send(json_str)

# 好的做法：延迟序列化
data = {"key": "value"}
self.send(data)  # 在真正需要时才序列化
```

## 同步引擎优化

### 1. 增量同步优化

#### 使用高效的哈希算法

```python
# 在 app/services/sync_engine.py 中优化哈希计算
import hashlib

def compute_row_hash(self, row: dict) -> str:
    """计算行的哈希值，用于增量同步"""
    # 使用更快的哈希算法
    return hashlib.sha256(
        json.dumps(row, sort_keys=True).encode()
    ).hexdigest()
```

#### 批量查询变更

```python
# 不好的做法：逐行检查变更
for row in source_data:
    existing = self.get_tracking_record(row_key)
    if existing and existing['source_hash'] == current_hash:
        continue  # 未变更
    # 同步...

# 好的做法：批量检查变更
row_keys = [self._get_row_key(row) for row in source_data]
existing_records = self.get_tracking_records_batch(row_keys)  # 一次查询
existing_dict = {r['source_row_key']: r for r in existing_records}

for row in source_data:
    row_key = self._get_row_key(row)
    current_hash = self.compute_row_hash(row)
    existing = existing_dict.get(row_key)
    if existing and existing['source_hash'] == current_hash:
        continue  # 未变更
    # 同步...
```

### 2. 方向控制优化

#### 避免不必要的同步

```python
def should_sync(self, direction: str, source: str) -> bool:
    """判断是否需要同步"""
    if direction == 'bidirectional':
        return True
    elif direction == 'to_mysql_only':
        return source == 'tencent'
    elif direction == 'from_mysql_only':
        return source == 'mysql'
    return False
```

### 3. 错误重试优化

#### 使用指数退避

```python
import time
from tenacity import retry, wait_exponential, stop_after_attempt

class SyncEngine:
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),  # 指数退避
        stop=stop_after_attempt(5)  # 最多重试 5 次
    )
    def _call_api_with_retry(self, func, *args, **kwargs):
        """使用指数退避重试 API 调用"""
        return func(*args, **kwargs)
```

## API 性能优化

### 1. 使用异步路由

```python
from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/api/configs")
async def list_configs():
    """使用异步处理，避免阻塞"""
    # 在真正 I/O 操作前，释放事件循环
    await asyncio.sleep(0)
    configs = await get_configs_from_db()
    return configs
```

### 2. 响应压缩

```python
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 3. 使用缓存头

```python
from fastapi import Response
from datetime import datetime, timedelta

@app.get("/api/configs/{config_id}")
async def get_config(config_id: int, response: Response):
    """为 GET 请求添加缓存头"""
    config = await get_config_from_db(config_id)

    # 设置缓存时间（秒）
    response.headers["Cache-Control"] = "max-age=60"
    response.headers["Expires"] = (datetime.utcnow() + timedelta(seconds=60)).strftime('%a, %d %b %Y %H:%M:%S GMT')

    return config
```

### 4. 分页查询

```python
@app.get("/api/sync/logs")
async def get_sync_logs(page: int = 1, page_size: int = 20):
    """分页查询同步日志"""
    offset = (page - 1) * page_size
    logs = await get_logs_from_db(limit=page_size, offset=offset)
    total = await get_total_logs_count()
    return {
        "data": logs,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size
        }
    }
```

## 缓存策略

### 1. 使用 Redis 缓存

```bash
# 安装 Redis
sudo apt install redis-server

# 安装 Python Redis 客户端
pip install redis aioredis
```

```python
import aioredis
from functools import wraps

# 创建 Redis 连接池
redis = aioredis.from_url("redis://localhost", encoding="utf-8", decode_responses=True)

def cached(expire: int = 60):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存 key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # 尝试从缓存获取
            cached_value = await redis.get(cache_key)
            if cached_value:
                return json.loads(cached_value)

            # 缓存未命中，执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            await redis.set(cache_key, json.dumps(result), ex=expire)

            return result
        return wrapper
    return decorator

# 使用缓存
class MySQLService:
    @cached(expire=300)  # 缓存 5 分钟
    async def get_table_structure(self, table_name: str):
        return self.execute(f"DESC {table_name}")
```

### 2. 缓存策略选择

| 数据类型 | 缓存策略 | 过期时间 | 说明 |
|---------|---------|----------|------|
| 配置数据 | 写后失效 | 5 分钟 | 配置不频繁变更 |
| 表结构 | 写后失效 | 10 分钟 | 表结构很少变更 |
| 同步日志 | 不缓存 | - | 实时性要求高 |
| 统计数据 | 定时失效 | 1 分钟 | 可以接受短暂不一致 |

### 3. 缓存预热

```python
@app.on_event("startup")
async def warm_up_cache():
    """应用启动时预热缓存"""
    # 预热配置数据
    configs = await get_all_configs()
    for config in configs:
        cache_key = f"config:{config.id}"
        await redis.set(cache_key, json.dumps(config.dict()), ex=300)

    logger.info("Cache warm-up completed")
```

## 监控性能指标

### 1. 应用性能监控 (APM)

#### 使用 Prometheus 收集指标

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# 定义指标
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)
REQUEST_DURATION = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint']
)
ACTIVE_CONNECTIONS = Gauge(
    'mysql_connections_active',
    'Active MySQL connections'
)

# 在中间件中收集指标
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # 记录指标
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response
```

### 2. 性能分析

#### 使用 cProfile 分析性能瓶颈

```bash
# 运行性能分析
python -m cProfile -o output.prof app/main.py

# 查看分析结果
python -m pstats output.prof
```

#### 使用 py-spy 实时分析

```bash
# 安装 py-spy
pip install py-spy

# 查看实时性能火焰图
py-spy top --pid $(pgrep -f "uvicorn app.main:app")

# 生成火焰图
py-spy record -o profile.svg --pid $(pgrep -f "uvicorn app.main:app")
```

### 3. 数据库性能监控

```sql
-- 查看当前连接
SHOW PROCESSLIST;

-- 查看查询性能
SHOW STATUS LIKE 'Queries';
SHOW STATUS LIKE 'Threads_running';

-- 查看慢查询
SELECT * FROM information_schema.PROCESSLIST WHERE COMMAND != 'Sleep' AND TIME > 2;
```

## 性能测试

### 1. 压力测试

#### 使用 Apache Bench

```bash
# 1000 个请求，10 个并发
ab -n 1000 -c 10 http://localhost:8083/health

# 输出示例：
# Server Software:        uvicorn
# Server Hostname:        localhost
# Server Port:            8083
# Document Path:          /health
# Document Length:        45 bytes
# Concurrency Level:      10
# Time taken for tests:   2.345 seconds
# Complete requests:      1000
# Failed requests:        0
# Requests per second:    426.44 [#/sec] (mean)
# Time per request:       23.45 [ms] (mean)
# Time per request:       2.34 [ms] (mean, across all concurrent requests)
# Transfer rate:          78.23 [Kbytes/sec] received
```

#### 使用 wrk

```bash
# 4 个线程，100 个连接，持续 30 秒
wrk -t4 -c100 -d30s http://localhost:8083/health
```

### 2. 同步性能测试

```python
# tests/perf_test_sync.py
import pytest
import time
from app.services.sync_engine import SyncEngine

@pytest.mark.parametrize("row_count", [100, 1000, 10000])
def test_sync_performance(row_count):
    """测试不同数据量下的同步性能"""
    engine = SyncEngine(config_id=1)

    # 准备测试数据
    test_data = [{"id": i, "name": f"User {i}"} for i in range(row_count)]

    # 测试同步性能
    start_time = time.time()
    result = engine.sync_to_mysql(test_data)
    duration = time.time() - start_time

    # 断言性能要求
    assert result.success is True
    if row_count <= 1000:
        assert duration < 10  # 1000 行以内应在 10 秒内完成
    else:
        assert duration < 100  # 10000 行以内应在 100 秒内完成

    print(f"同步 {row_count} 行耗时：{duration:.2f} 秒")
```

### 3. 负载测试

```python
# tests/load_test.py
import asyncio
import aiohttp

async def make_request(session, url):
    """发送单个请求"""
    async with session.get(url) as response:
        return response.status

async def load_test(url: str, concurrent: int = 100, total: int = 1000):
    """负载测试"""
    connector = aiohttp.TCPConnector(limit=concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [make_request(session, url) for _ in range(total)]
        results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r == 200)
    print(f"总请求：{total}, 成功：{success}, 失败：{total - success}")

# 运行负载测试
asyncio.run(load_test("http://localhost:8083/health", concurrent=100, total=1000))
```

## 性能调优清单

### 系统级

- [ ] 操作系统参数已调优（`sysctl.conf`）
- [ ] 文件描述符限制已增加
- [ ] 磁盘 I/O 调度器已优化
- [ ] 使用 SSD 存储
- [ ] 内存足够（≥ 8GB）

### 数据库级

- [ ] `innodb_buffer_pool_size` 已设置为系统内存的 50-70%
- [ ] 已为频繁查询的字段添加索引
- [ ] 已启用慢查询日志
- [ ] 连接池大小已合理配置
- [ ] 已定期运行 `OPTIMIZE TABLE`

### 应用级

- [ ] 已启用多 worker（`--workers 4+`）
- [ ] 已使用异步 I/O（`async`/`await`）
- [ ] 已使用连接池
- [ ] 已启用响应压缩
- [ ] 已使用缓存（Redis）
- [ ] 批量大小已优化（`batch_size`）
- [ ] 已启用日志轮转

### 监控级

- [ ] 已配置 Prometheus 指标收集
- [ ] 已配置性能告警
- [ ] 已定期进行性能测试
- [ ] 已监控关键性能指标

---

**文档版本**：v1.0.0  
**最后更新**：2026-04-30  
**维护者**：性能优化团队
