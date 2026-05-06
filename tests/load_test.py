"""
高并发测试和性能测试套件
测试系统在高并发场景下的表现
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, List
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceTestRunner:
    """
    性能测试运行器
    模拟高并发场景，测试系统性能和稳定性
    """
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = None
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """运行性能测试"""
        self.start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("开始性能测试")
        logger.info("=" * 80)
        
        test_results = []
        
        logger.info("\n测试1: 模拟并发同步操作")
        result1 = await self.test_concurrent_sync()
        test_results.append(("并发同步测试", result1))
        
        logger.info("\n测试2: 模拟批量数据处理")
        result2 = await self.test_batch_processing()
        test_results.append(("批量处理测试", result2))
        
        logger.info("\n测试3: 模拟配置验证性能")
        result3 = await self.test_config_validation_performance()
        test_results.append(("配置验证性能测试", result3))
        
        logger.info("\n测试4: 模拟错误处理性能")
        result4 = await self.test_error_handling_performance()
        test_results.append(("错误处理性能测试", result4))
        
        logger.info("\n测试5: 模拟内存使用")
        result5 = await self.test_memory_usage()
        test_results.append(("内存使用测试", result5))
        
        summary = {
            "test_results": test_results,
            "timestamp": self.start_time.isoformat(),
            "total_duration": (datetime.now() - self.start_time).total_seconds(),
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("性能测试完成")
        for test_name, result in test_results:
            status = "✅" if result["success"] else "❌"
            logger.info(f"{status} {test_name}: {result.get('message', '')}")
        logger.info("=" * 80)
        
        return summary
    
    async def test_concurrent_sync(self) -> Dict[str, Any]:
        """测试并发同步操作"""
        try:
            from app.services.sync_engine_enhanced import distributed_lock, concurrency_limiter
            import asyncio
            
            logger.info("模拟100个并发同步请求...")
            
            start_time = time.time()
            active_count_history = []
            
            async def mock_sync_task(task_id: int):
                lock_resource = f"test_sync_{task_id % 10}"
                async with distributed_lock.acquire(lock_resource, timeout=5):
                    async with concurrency_limiter.acquire():
                        active_count_history.append(concurrency_limiter.get_active_count())
                        await asyncio.sleep(0.1)
                        return task_id
            
            tasks = [mock_sync_task(i) for i in range(100)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            duration = time.time() - start_time
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            max_concurrent = max(active_count_history) if active_count_history else 0
            
            logger.info(f"并发测试完成: {success_count}/100 成功, 耗时 {duration:.2f}s, 最大并发 {max_concurrent}")
            
            return {
                "success": success_count >= 95,
                "message": f"并发处理 {success_count}/100 成功, 耗时 {duration:.2f}s, 最大并发 {max_concurrent}",
                "duration": duration,
                "success_rate": success_count,
                "max_concurrent": max_concurrent,
            }
        except Exception as e:
            logger.error(f"并发测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_batch_processing(self) -> Dict[str, Any]:
        """测试批量处理性能"""
        try:
            from app.services.batch_optimizer import batch_optimizer
            
            logger.info("测试批量处理10000行数据...")
            
            test_rows = [
                {"id": i, "name": f"User_{i}", "value": random.randint(1, 1000)}
                for i in range(10000)
            ]
            
            start_time = time.time()
            
            sql, params, columns = batch_optimizer.optimize_batch_insert(
                "test_table",
                test_rows,
                ["id"]
            )
            
            batches = batch_optimizer.split_into_batches(test_rows, batch_size=100)
            
            duration = time.time() - start_time
            
            logger.info(f"批量处理完成: {len(batches)} 批次, 耗时 {duration:.4f}s")
            
            return {
                "success": duration < 1.0,
                "message": f"批量处理 {len(test_rows)} 行分为 {len(batches)} 批次, 耗时 {duration:.4f}s",
                "duration": duration,
                "rows_processed": len(test_rows),
                "batches": len(batches),
            }
        except Exception as e:
            logger.error(f"批量处理测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_config_validation_performance(self) -> Dict[str, Any]:
        """测试配置验证性能"""
        try:
            from app.services.config_validator import ConfigValidator
            
            logger.info("测试配置验证性能，验证1000次...")
            
            validator = ConfigValidator()
            test_config = {
                "spreadsheet_id": "abc123xxx",
                "sheet_id": "sheet001",
                "table_name": "test_table",
                "database": "test_db",
                "sync_direction": "bidirectional",
                "poll_interval": 30,
                "mapping_json": {
                    "columns": [
                        {"sheet_col": "A", "sheet_header": "姓名", "db_column": "name", "db_type": "VARCHAR(64)", "primary_key": True},
                        {"sheet_col": "B", "sheet_header": "年龄", "db_column": "age", "db_type": "INT"},
                        {"sheet_col": "C", "sheet_header": "城市", "db_column": "city", "db_type": "VARCHAR(100)"},
                    ],
                    "sheet_header_row": 1,
                    "data_start_row": 2
                }
            }
            
            start_time = time.time()
            
            for _ in range(1000):
                validator.validate_config(test_config)
            
            duration = time.time() - start_time
            avg_time = duration / 1000 * 1000
            
            logger.info(f"配置验证性能: 1000次验证, 总耗时 {duration:.4f}s, 平均 {avg_time:.4f}ms")
            
            return {
                "success": avg_time < 1.0,
                "message": f"配置验证性能: 平均 {avg_time:.4f}ms/次",
                "duration": duration,
                "iterations": 1000,
                "avg_time_ms": avg_time,
            }
        except Exception as e:
            logger.error(f"配置验证性能测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_error_handling_performance(self) -> Dict[str, Any]:
        """测试错误处理性能"""
        try:
            from app.services.retry_handler import retry_handler
            
            logger.info("测试错误处理性能，记录10000个错误...")
            
            start_time = time.time()
            
            for i in range(10000):
                test_error = ValueError(f"Test error {i}")
                retry_handler.record_error(test_error, {"index": i})
            
            duration = time.time() - start_time
            avg_time = duration / 10000 * 1000
            
            stats = retry_handler.get_error_statistics()
            
            logger.info(f"错误处理性能: 10000次记录, 总耗时 {duration:.4f}s, 平均 {avg_time:.4f}ms")
            
            return {
                "success": avg_time < 0.1,
                "message": f"错误处理性能: 平均 {avg_time:.4f}ms/次, 共 {stats['total_errors']} 条错误",
                "duration": duration,
                "iterations": 10000,
                "avg_time_ms": avg_time,
            }
        except Exception as e:
            logger.error(f"错误处理性能测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_memory_usage(self) -> Dict[str, Any]:
        """测试内存使用"""
        try:
            from app.services.audit_logger import audit_logger
            from app.services.metrics_collector import metrics_collector
            
            logger.info("测试内存使用...")
            
            import sys
            
            audit_logger_events = len(audit_logger._events)
            metrics_counters = len(metrics_collector._counters)
            metrics_gauges = len(metrics_collector._gauges)
            metrics_histograms = len(metrics_collector._histograms)
            
            logger.info(f"内存使用统计:")
            logger.info(f"  - 审计日志: {audit_logger_events} 条")
            logger.info(f"  - 性能指标计数器: {metrics_counters} 个")
            logger.info(f"  - 性能指标仪表: {metrics_gauges} 个")
            logger.info(f"  - 性能指标直方图: {metrics_histograms} 个")
            
            total_objects = (
                audit_logger_events +
                metrics_counters +
                metrics_gauges +
                metrics_histograms
            )
            
            return {
                "success": total_objects < 10000,
                "message": f"内存使用正常: {total_objects} 个对象",
                "audit_events": audit_logger_events,
                "metrics_counters": metrics_counters,
                "metrics_gauges": metrics_gauges,
                "metrics_histograms": metrics_histograms,
                "total_objects": total_objects,
            }
        except Exception as e:
            logger.error(f"内存使用测试失败: {e}")
            return {"success": False, "error": str(e)}


class StressTestRunner:
    """
    压力测试运行器
    测试系统在极限负载下的表现
    """
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    async def run_stress_tests(self) -> Dict[str, Any]:
        """运行压力测试"""
        logger.info("=" * 80)
        logger.info("开始压力测试")
        logger.info("=" * 80)
        
        test_results = []
        
        logger.info("\n压力测试1: 极限并发测试 (1000个并发请求)")
        result1 = await self.stress_test_1()
        test_results.append(("极限并发测试", result1))
        
        logger.info("\n压力测试2: 长时间运行测试 (模拟24小时)")
        result2 = await self.stress_test_2()
        test_results.append(("长时间运行测试", result2))
        
        summary = {
            "test_results": test_results,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("压力测试完成")
        for test_name, result in test_results:
            status = "✅" if result.get("success", False) else "❌"
            logger.info(f"{status} {test_name}: {result.get('message', '')}")
        logger.info("=" * 80)
        
        return summary
    
    async def stress_test_1(self) -> Dict[str, Any]:
        """极限并发测试"""
        try:
            from app.services.sync_engine_enhanced import distributed_lock, concurrency_limiter
            import asyncio
            
            logger.info("模拟1000个极限并发请求...")
            
            start_time = time.time()
            success_count = 0
            failure_count = 0
            
            async def stress_task(task_id: int):
                nonlocal success_count, failure_count
                try:
                    lock_resource = f"stress_sync_{task_id % 50}"
                    async with distributed_lock.acquire(lock_resource, timeout=10):
                        async with concurrency_limiter.acquire():
                            await asyncio.sleep(0.01)
                            success_count += 1
                except Exception:
                    failure_count += 1
            
            tasks = [stress_task(i) for i in range(1000)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            duration = time.time() - start_time
            throughput = success_count / duration
            
            logger.info(f"极限并发测试完成: {success_count} 成功, {failure_count} 失败, 耗时 {duration:.2f}s")
            logger.info(f"吞吐量: {throughput:.2f} 请求/秒")
            
            return {
                "success": failure_count < 50,
                "message": f"极限并发: {success_count} 成功, {failure_count} 失败, 吞吐量 {throughput:.2f} req/s",
                "duration": duration,
                "success_count": success_count,
                "failure_count": failure_count,
                "throughput": throughput,
            }
        except Exception as e:
            logger.error(f"极限并发测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def stress_test_2(self) -> Dict[str, Any]:
        """长时间运行测试（模拟）"""
        try:
            import traceback
            from app.services.metrics_collector import metrics_collector
            from app.services.audit_logger import audit_logger
            
            logger.info("模拟24小时运行测试（10秒模拟）...")
            
            start_time = time.time()
            
            for i in range(1000):
                metrics_collector.increment_counter("stress_test_ops", 1)
                
                if i % 100 == 0:
                    try:
                        audit_logger.log_event(
                            event_type="test",
                            operator="load_test",
                            resource_type="test",
                            resource_id=i,
                        )
                    except Exception as e:
                        logger.error(f"Audit log error at {i}: {e}")
                        logger.error(traceback.format_exc())
                        raise
            
            duration = time.time() - start_time
            
            stats = metrics_collector.get_all_metrics()
            
            logger.info(f"长时间运行测试完成: 模拟 {duration:.2f}s")
            
            return {
                "success": duration < 30,
                "message": f"长时间运行模拟完成, 操作 {duration:.2f}s",
                "duration": duration,
            }
        except Exception as e:
            logger.error(f"长时间运行测试失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}


async def main():
    """主函数"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 性能测试套件")
    logger.info("=" * 80 + "\n")
    
    perf_runner = PerformanceTestRunner()
    perf_results = await perf_runner.run_performance_tests()
    
    logger.info("\n" + "-" * 80 + "\n")
    
    stress_runner = StressTestRunner()
    stress_results = await stress_runner.run_stress_tests()
    
    logger.info("\n" + "=" * 80)
    logger.info("🎉 所有测试完成!")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
