"""
集成测试 - 测试所有核心功能（pytest 兼容版）
通过 pytest tests/integration_test_pytest.py 运行
"""
import pytest
from datetime import datetime


class TestIntegrationSuite:
    """核心功能集成测试套件"""

    @pytest.mark.asyncio
    async def test_config_validation(self):
        """测试配置验证"""
        from app.services.config_validator import config_validator

        valid_config = {
            "spreadsheet_id": "abc123xxx",
            "sheet_id": "sheet001",
            "table_name": "test_table",
            "database": "test_db",
            "sync_direction": "bidirectional",
            "poll_interval": 30,
            "mapping_json": {
                "columns": [
                    {
                        "sheet_col": "A",
                        "sheet_header": "姓名",
                        "db_column": "name",
                        "db_type": "VARCHAR(64)",
                        "primary_key": True,
                    },
                    {
                        "sheet_col": "B",
                        "sheet_header": "年龄",
                        "db_column": "age",
                        "db_type": "INT",
                    }
                ],
                "sheet_header_row": 1,
                "data_start_row": 2
            }
        }

        is_valid, errors, warnings = config_validator.validate_config(valid_config)
        assert is_valid, f"配置验证失败: {[e.message for e in errors]}"

    @pytest.mark.asyncio
    async def test_audit_logger(self):
        """测试审计日志"""
        from app.services.audit_logger import audit_logger

        audit_logger.clear_old_events(datetime.now())

        audit_logger.log_config_created(
            config_id=1,
            spreadsheet_id="test123",
            table_name="test_table",
        )

        audit_logger.log_sync_triggered(
            config_id=1,
            direction="to_mysql",
            trigger_type="manual",
        )

        audit_logger.log_sync_completed(
            config_id=1,
            direction="to_mysql",
            rows_affected=10,
            duration_seconds=1.5,
        )

        stats = audit_logger.get_statistics()
        assert stats["total_events"] >= 3, f"审计日志记录不足: {stats['total_events']}"

    @pytest.mark.asyncio
    async def test_metrics_collector(self):
        """测试性能指标收集"""
        from app.services.metrics_collector import metrics_collector

        metrics_collector.reset_metrics()

        metrics_collector.increment_counter("test_counter", 5)
        metrics_collector.set_gauge("test_gauge", 42.5)
        metrics_collector.observe_histogram("test_histogram", 1.23)

        metrics_collector.record_sync_duration(
            config_id=1,
            direction="to_mysql",
            duration=2.5,
            success=True
        )

        metrics_collector.record_sync_rows(
            config_id=1,
            direction="to_mysql",
            rows=100,
            operation="upsert"
        )

        counter_value = metrics_collector.get_counter_value("test_counter")
        gauge_value = metrics_collector.get_gauge_value("test_gauge")
        histogram_stats = metrics_collector.get_histogram_stats("test_histogram")

        assert counter_value == 5, f"counter={counter_value}"
        assert gauge_value == 42.5, f"gauge={gauge_value}"
        assert histogram_stats["count"] == 1, f"histogram count={histogram_stats['count']}"

    @pytest.mark.asyncio
    async def test_error_handler(self):
        """测试错误处理"""
        from app.services.retry_handler import retry_handler, dead_letter_queue

        test_error = ValueError("Test error")
        is_retryable, error_type = retry_handler.classify_error(test_error)

        retry_handler.record_error(test_error, {"test": True})

        stats = retry_handler.get_error_statistics()
        assert stats["total_errors"] >= 1, f"错误统计不正确: {stats}"

    @pytest.mark.asyncio
    async def test_batch_optimizer(self):
        """测试批量操作优化"""
        from app.services.batch_optimizer import batch_optimizer

        rows = [
            {"id": 1, "name": "Test1", "value": 100},
            {"id": 2, "name": "Test2", "value": 200},
            {"id": 3, "name": "Test3", "value": 300},
        ]

        sql, params, columns = batch_optimizer.optimize_batch_insert(
            "test_table",
            rows,
            ["id"]
        )

        assert len(params) == 3, f"参数数量: {len(params)}"
        assert len(columns) == 3, f"列数量: {len(columns)}"

    @pytest.mark.asyncio
    async def test_data_validator(self):
        """测试数据验证"""
        from app.services.batch_optimizer import data_validator

        data_validator.clear()

        is_valid, int_val = data_validator.validate_value(42, "test_int", "INT")
        assert is_valid and int_val == 42

        is_valid, float_val = data_validator.validate_value(3.14, "test_float", "FLOAT")
        assert is_valid and float_val == 3.14

        is_valid, bool_val = data_validator.validate_value("true", "test_bool", "BOOL")
        assert is_valid and bool_val is True

        is_valid, str_val = data_validator.validate_value("  hello  ", "test_str", "VARCHAR(100)")
        assert is_valid and str_val == "hello"

    @pytest.mark.asyncio
    async def test_config_validator(self):
        """测试配置验证器（无效配置）"""
        from app.services.config_validator import ConfigValidator

        validator = ConfigValidator()

        invalid_config = {
            "spreadsheet_id": "",
            "table_name": "123invalid",
            "mapping_json": {"columns": []}
        }

        is_valid, errors, warnings = validator.validate_config(invalid_config)
        assert not is_valid, "应该检测到配置错误"
        assert len(errors) > 0, "应该有错误信息"
