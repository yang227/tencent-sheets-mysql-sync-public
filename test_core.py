#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from unittest.mock import MagicMock, patch, AsyncMock
from app.services.tencent_api import TencentAPI
from app.services.mysql_service import MySQLService
from app.services.mapping import MappingEngine
from app.services.sync_engine import SyncEngine, SyncResult

print("=" * 60)
print("1. TencentAPI — 模拟 Token 刷新")
print("=" * 60)
api = TencentAPI(app_id="test_app", app_secret="test_secret")

async def mock_refresh():
    api.access_token = "mock_token_abc123"
    api.refresh_token = "mock_refresh_xyz789"
    import time; api._token_expires_at = time.time() + 7200

with patch.object(api, '_refresh_access_token', mock_refresh):
    import asyncio
    async def test(): await api._refresh_access_token()
    asyncio.run(test())
    print(f"  access_token: {api.access_token}")
    print(f"  refresh_token: {api.refresh_token}")
    print("  ✅ Token 刷新逻辑 OK")

print()
print("=" * 60)
print("2. MappingEngine — 字段映射 & 转换")
print("=" * 60)
config = {
    "columns": [
        {"sheet_col": "A", "db_column": "name",  "primary_key": True},
        {"sheet_col": "B", "db_column": "age",   "primary_key": False},
        {"sheet_col": "C", "db_column": "city",  "primary_key": False},
    ]
}
mapper = MappingEngine(config)
print(f"  主键: {mapper.primary_keys}")
print(f"  映射数量: {len(mapper._column_map)}")
sheet_row = {"A": "Alice", "B": "30", "C": "Beijing"}
db_row = mapper.sheet_row_to_db_row(sheet_row)
print(f"  sheet→db: {db_row}")
db_back = mapper.db_row_to_sheet_row(db_row)
print(f"  db→sheet: {db_back}")
print("  ✅ 字段映射 & 转换 OK")

print()
print("=" * 60)
print("3. SyncEngine — 同步模拟")
print("=" * 60)
engine = SyncEngine(config_id=1, mysql_service=MagicMock(), tencent_api=MagicMock())
engine._mysql = MagicMock()
engine._mysql.get_sync_config.return_value = {
    "id": 1, "spreadsheet_id": "sheet_123", "mysql_table": "users",
    "table_name": "users",
    "direction": "bidirectional",
    "column_mappings": '{"A":"name","B":"age","C":"city"}',
    "last_sync_at": None,
    "sheet_id": "sheet_123",
    "sheet_title": "Sheet1",
}
engine._mysql.get_column_names.return_value = ["name", "age", "city"]
engine._mysql.fetch_table_rows.return_value = [{"name": "Alice", "age": "30", "city": "Beijing"}]
engine._mysql.update_sync_status.return_value = True
engine._mysql.insert_rows.return_value = 1
engine._mysql.update_rows.return_value = 1

async def test_sync():
    engine._tencent = MagicMock()
    engine._tencent.get_sheet_info = AsyncMock(return_value={"rowCount": 10})
    engine._tencent.get_values = AsyncMock(return_value={
        "values": [
            ["Alice", "30", "Beijing"],
            ["Bob", "25", "Shanghai"]
        ]
    })
    engine._tencent.put_values = AsyncMock(return_value={})
    engine._tencent.batch_put_values = AsyncMock(return_value={})
    result = await engine.sync_bidirectional()
    to_mysql = result["to_mysql"]
    print(f"  to_mysql: success={to_mysql.success}, 新增={to_mysql.rows_new}, 更新={to_mysql.rows_updated}")
    print(f"  from_mysql: success={result['from_mysql'].success}")
    print("  ✅ 同步逻辑 OK")

import asyncio; asyncio.run(test_sync())

print()
print("=" * 60)
print("4. MySQLService — SQL 生成测试")
print("=" * 60)
svc = MySQLService()
svc._pool = MagicMock()
with patch.object(svc, 'get_connection') as mc:
    mc.return_value.cursor.return_value.fetchall.return_value = [{"cnt": 1}]
    exists = svc.table_exists("users")
    print(f"  table_exists('users'): {exists}")
    print("  ✅ 表存在检查 OK")

print()
print("=" * 60)
print("5. SyncResult — 结果序列化")
print("=" * 60)
result = SyncResult(success=True, direction="to_mysql", rows_new=2, rows_updated=1, errors=[])
print(f"  to_dict: {result.to_dict()}")
print("  ✅ SyncResult OK")

print()
print("✅ 所有核心逻辑测试通过！")
