"""
压力测试 - 测试高并发和性能（pytest 兼容版）
通过 pytest tests/load_test_pytest.py 运行
"""
import pytest
import asyncio
import time


class TestLoadSuite:
    """高并发压力测试套件"""

    @pytest.mark.asyncio
    async def test_concurrent_sync_simulation(self):
        """测试并发同步模拟（100个并发）"""
        import random
        from app.services.batch_optimizer import batch_optimizer

        async def simulate_sync(task_id: int) -> dict:
            await asyncio.sleep(0.001)
            rows = [{"id": i, "val": random.random()} for i in range(100)]
            sql, params, cols = batch_optimizer.optimize_batch_insert("t", rows, ["id"])
            return {"id": task_id, "rows": len(params), "success": True}

        tasks = [simulate_sync(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        successes = sum(1 for r in results if r["success"])
        assert successes == 100, f"并发成功率: {successes}/100"

    @pytest.mark.asyncio
    async def test_batch_processing_performance(self):
        """测试批量处理性能（10000行）"""
        from app.services.batch_optimizer import batch_optimizer

        rows = [{"id": i, "name": f"user_{i}", "value": i * 10} for i in range(10000)]

        start = time.perf_counter()
        sql, params, columns = batch_optimizer.optimize_batch_insert("users", rows, ["id"])
        elapsed = time.perf_counter() - start

        assert len(params) == 10000, f"处理行数: {len(params)}"
        assert elapsed < 1.0, f"耗时过长: {elapsed:.3f}s"
        assert len(columns) == 3, f"列数: {len(columns)}"

    @pytest.mark.asyncio
    async def test_config_validation_performance(self):
        """测试配置验证性能（1000次）"""
        from app.services.config_validator import config_validator

        config = {
            "spreadsheet_id": "abc123",
            "sheet_id": "sheet1",
            "table_name": "test_table",
            "database": "test_db",
            "sync_direction": "bidirectional",
            "poll_interval": 30,
            "mapping_json": {
                "columns": [
                    {"sheet_col": "A", "sheet_header": "姓名", "db_column": "name", "db_type": "VARCHAR(64)", "primary_key": True},
                    {"sheet_col": "B", "sheet_header": "年龄", "db_column": "age", "db_type": "INT"},
                ],
                "sheet_header_row": 1,
                "data_start_row": 2
            }
        }

        start = time.perf_counter()
        for _ in range(1000):
            config_validator.validate_config(config)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000

        assert avg_ms < 10, f"平均耗时过长: {avg_ms:.3f}ms/次"

    @pytest.mark.asyncio
    async def test_error_handling_performance(self):
        """测试错误处理性能（10000个错误）"""
        from app.services.retry_handler import retry_handler

        errors = [ValueError(f"err_{i}") for i in range(10000)]

        start = time.perf_counter()
        for e in errors:
            retry_handler.classify_error(e)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 10000) * 1000

        assert avg_ms < 1, f"平均耗时过长: {avg_ms:.4f}ms/次"

    @pytest.mark.asyncio
    async def test_extreme_concurrency(self):
        """测试极限并发（1000个任务）"""
        async def trivial_task(i: int) -> int:
            await asyncio.sleep(0.0001)
            return i * 2

        tasks = [trivial_task(i) for i in range(1000)]
        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        throughput = 1000 / elapsed

        assert len(results) == 1000, f"结果数量: {len(results)}"
        assert throughput > 100, f"吞吐量过低: {throughput:.1f} req/s"

    @pytest.mark.asyncio
    async def test_metrics_stability(self):
        """测试指标收集器稳定性"""
        from app.services.metrics_collector import metrics_collector

        initial_counters = len(metrics_collector._counters)

        for i in range(100):
            metrics_collector.increment_counter(f"mem_test_{i % 10}", 1)
            metrics_collector.set_gauge(f"mem_gauge_{i % 10}", float(i))
            metrics_collector.observe_histogram(f"mem_hist_{i % 10}", float(i))

        final_counters = len(metrics_collector._counters)
        assert final_counters >= initial_counters, "计数器未正常增长"
