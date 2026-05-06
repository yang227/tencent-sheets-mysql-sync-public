"""
集成测试套件 - 测试所有核心功能
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationTestRunner:
    """
    集成测试运行器
    自动化测试所有核心功能
    """
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        self.start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("开始集成测试")
        logger.info("=" * 80)
        
        test_methods = [
            ("test_config_validation", self.test_config_validation),
            ("test_audit_logger", self.test_audit_logger),
            ("test_metrics_collector", self.test_metrics_collector),
            ("test_error_handler", self.test_error_handler),
            ("test_batch_optimizer", self.test_batch_optimizer),
            ("test_data_validator", self.test_data_validator),
            ("test_config_validator", self.test_config_validator),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in test_methods:
            logger.info(f"\n执行测试: {test_name}")
            try:
                result = await test_func()
                if result["success"]:
                    passed += 1
                    logger.info(f"✅ {test_name} 通过")
                else:
                    failed += 1
                    logger.error(f"❌ {test_name} 失败: {result.get('error')}")
            except Exception as e:
                failed += 1
                logger.error(f"❌ {test_name} 异常: {e}")
        
        self.end_time = datetime.now()
        
        summary = {
            "total": passed + failed,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0,
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "timestamp": self.start_time.isoformat(),
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("测试完成")
        logger.info(f"总计: {summary['total']}")
        logger.info(f"通过: {summary['passed']}")
        logger.info(f"失败: {summary['failed']}")
        logger.info(f"成功率: {summary['success_rate']:.2f}%")
        logger.info(f"耗时: {summary['duration_seconds']:.2f}秒")
        logger.info("=" * 80)
        
        return summary
    
    async def test_config_validation(self) -> Dict[str, Any]:
        """测试配置验证"""
        try:
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
            
            if is_valid:
                return {"success": True, "message": "配置验证正常"}
            else:
                return {
                    "success": False,
                    "error": f"配置验证失败: {[e.message for e in errors]}"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_audit_logger(self) -> Dict[str, Any]:
        """测试审计日志"""
        try:
            from app.services.audit_logger import audit_logger, AuditEventType
            
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
            
            events = audit_logger.get_events(resource_type="sync_config", limit=10)
            
            stats = audit_logger.get_statistics()
            
            if stats["total_events"] >= 3:
                return {"success": True, "message": f"审计日志正常，记录了{stats['total_events']}条"}
            else:
                return {"success": False, "error": "审计日志记录不完整"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_metrics_collector(self) -> Dict[str, Any]:
        """测试性能指标收集"""
        try:
            from app.services.metrics_collector import metrics_collector, metrics_collector as mc
            
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
            
            all_metrics = metrics_collector.get_all_metrics()
            
            if counter_value == 5 and gauge_value == 42.5 and histogram_stats["count"] == 1:
                return {"success": True, "message": "性能指标收集正常"}
            else:
                return {
                    "success": False,
                    "error": f"指标值不正确: counter={counter_value}, gauge={gauge_value}"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_error_handler(self) -> Dict[str, Any]:
        """测试错误处理"""
        try:
            from app.services.retry_handler import (
                retry_handler, dead_letter_queue, ErrorSeverity, RetryableError
            )
            
            test_error = ValueError("Test error")
            is_retryable, error_type = retry_handler.classify_error(test_error)
            
            retry_handler.record_error(test_error, {"test": True})
            
            stats = retry_handler.get_error_statistics()
            
            dlq_stats = dead_letter_queue.get_statistics()
            
            if stats["total_errors"] >= 1:
                return {"success": True, "message": "错误处理正常"}
            else:
                return {"success": False, "error": "错误统计不正确"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_batch_optimizer(self) -> Dict[str, Any]:
        """测试批量操作优化"""
        try:
            from app.services.batch_optimizer import batch_optimizer, data_validator
            
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
            
            if len(params) == 3 and len(columns) == 3:
                return {"success": True, "message": "批量操作优化正常"}
            else:
                return {"success": False, "error": "批量操作结果不正确"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_data_validator(self) -> Dict[str, Any]:
        """测试数据验证"""
        try:
            from app.services.batch_optimizer import data_validator
            
            data_validator.clear()
            
            is_valid, int_val = data_validator.validate_value(42, "test_int", "INT")
            assert is_valid and int_val == 42, "整数验证失败"
            
            is_valid, float_val = data_validator.validate_value(3.14, "test_float", "FLOAT")
            assert is_valid and float_val == 3.14, "浮点数验证失败"
            
            is_valid, bool_val = data_validator.validate_value("true", "test_bool", "BOOL")
            assert is_valid and bool_val is True, "布尔验证失败"
            
            is_valid, str_val = data_validator.validate_value("  hello  ", "test_str", "VARCHAR(100)")
            assert is_valid and str_val == "hello", "字符串验证失败"
            
            return {"success": True, "message": "数据验证正常"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_config_validator(self) -> Dict[str, Any]:
        """测试配置验证器"""
        try:
            from app.services.config_validator import ConfigValidator
            
            validator = ConfigValidator()
            
            invalid_config = {
                "spreadsheet_id": "",
                "table_name": "123invalid",
                "mapping_json": {
                    "columns": []
                }
            }
            
            is_valid, errors, warnings = validator.validate_config(invalid_config)
            
            if not is_valid and len(errors) > 0:
                return {"success": True, "message": f"配置验证器正常，检测到{len(errors)}个错误"}
            else:
                return {"success": False, "error": "应该检测到配置错误"}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def main():
    """主函数"""
    runner = IntegrationTestRunner()
    summary = await runner.run_all_tests()
    
    if summary["failed"] == 0:
        logger.info("\n🎉 所有测试通过！")
        return 0
    else:
        logger.warning(f"\n⚠️  {summary['failed']} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
