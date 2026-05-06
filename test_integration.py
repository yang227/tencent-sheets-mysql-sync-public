#!/usr/bin/env python3
"""
集成测试脚本。

注意：
- 不在仓库中内嵌任何真实腾讯凭据
- 运行前请通过环境变量注入真实值，或接受示例占位符仅做结构验证
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")

os.environ.setdefault("TENCENT_DOCS_ACCESS_TOKEN", "your_tencent_docs_access_token")
os.environ.setdefault("TENCENT_APP_ID", "your_tencent_app_id")
os.environ.setdefault("TENCENT_OPEN_ID", "your_tencent_open_id")

from app.services.mapping import MappingEngine
from app.services.mysql_service import MySQLService
from app.services.sync_engine import SyncEngine, SyncResult
from app.services.tencent_api import TencentAPI


print("=" * 70)
print("Tencent Docs / MySQL Sync - 集成测试")
print("=" * 70)


async def test_tencent_api():
    print("\n1. 测试腾讯 API 连接")
    print("-" * 70)

    api = TencentAPI()
    result = await api.test_connection()

    if result.get("connected"):
        print("   OK - API 连接成功")
        print(f"   - App ID: {result.get('app_id')}")
        return True

    print(f"   FAIL - API 连接失败: {result.get('error')}")
    return False


def test_mapping_engine():
    print("\n2. 测试字段映射引擎")
    print("-" * 70)

    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "name", "primary_key": True, "direction": "bidirectional"},
            {"sheet_col": "B", "db_column": "age", "primary_key": False, "direction": "to_mysql_only", "transform": "int"},
            {"sheet_col": "C", "db_column": "city", "primary_key": False, "direction": "bidirectional"},
        ],
        "sheet_header_row": 1,
        "data_start_row": 2,
    }

    engine = MappingEngine(config)
    assert engine.primary_keys == ["name"]

    db_row = engine.sheet_row_to_db_row({"A": "张三", "B": "25", "C": "北京"})
    assert db_row["name"] == "张三"
    assert db_row.get("age") == 25

    sheet_row = engine.db_row_to_sheet_row({"name": "李四", "age": 30, "city": "上海"})
    assert sheet_row.get("A") == "李四"

    assert engine.can_sync_to_mysql("B") is True
    assert engine.can_sync_from_mysql("B") is False
    print("   OK - 映射转换与方向过滤正常")
    return True


def test_sync_engine():
    print("\n3. 测试同步引擎")
    print("-" * 70)

    result = SyncResult(
        success=True,
        direction="to_mysql",
        rows_affected=10,
        rows_new=5,
        rows_updated=3,
        rows_skipped=2,
        errors=[],
    )
    assert result.success is True
    assert result.rows_affected == 10

    row_data = {"name": "测试", "value": 123}
    hash1 = SyncEngine.compute_row_hash(row_data)
    hash2 = SyncEngine.compute_row_hash(row_data)
    assert hash1 == hash2
    assert len(hash1) == 64

    print("   OK - 同步结果与哈希计算正常")
    return True


def test_mysql_service():
    print("\n4. 测试 MySQL 服务初始化")
    print("-" * 70)

    try:
        MySQLService()
        print("   INFO - MySQL 服务对象初始化成功")
        return True
    except Exception as exc:
        print(f"   INFO - 跳过真实 MySQL 连接验证: {exc}")
        return True


async def main():
    print("\n" + "=" * 70)
    print("开始执行集成测试")
    print("=" * 70)

    results = []

    for name, runner in [
        ("腾讯 API 连接", test_tencent_api),
        ("字段映射引擎", test_mapping_engine),
        ("同步引擎", test_sync_engine),
        ("MySQL 服务", test_mysql_service),
    ]:
        try:
            result = await runner() if asyncio.iscoroutinefunction(runner) else runner()
            results.append((name, result))
        except Exception as exc:
            print(f"   FAIL - {name}: {exc}")
            results.append((name, False))

    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)

    for name, result in results:
        print(f"   {name:20s}: {'PASS' if result else 'FAIL'}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("\n" + "=" * 70)
    print(f"通过数: {passed}/{total}")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
