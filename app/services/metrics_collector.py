"""
性能指标收集服务 - 监控系统性能和健康状态
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    性能指标收集器
    收集和聚合系统关键性能指标
    """
    
    def __init__(self):
        self._counters: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._max_points_per_metric = 10000
    
    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        增加计数器
        
        Args:
            name: 指标名称
            value: 增量值
            labels: 标签
        """
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        
        self._counters[name].append(point)
        
        if len(self._counters[name]) > self._max_points_per_metric:
            self._counters[name] = self._counters[name][-self._max_points_per_metric:]
        
        label_str = self._format_labels(labels)
        logger.debug(f"METRIC: {name}{label_str} +{value}")
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        设置仪表值
        
        Args:
            name: 指标名称
            value: 仪表值
            labels: 标签
        """
        key = self._make_key(name, labels)
        self._gauges[key] = value
        
        label_str = self._format_labels(labels)
        logger.debug(f"GAUGE: {name}{label_str} = {value}")
    
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        观察直方图值
        
        Args:
            name: 指标名称
            value: 观察值
            labels: 标签
        """
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        
        self._histograms[name].append(value)
        
        if len(self._histograms[name]) > self._max_points_per_metric:
            self._histograms[name] = self._histograms[name][-self._max_points_per_metric:]
        
        label_str = self._format_labels(labels)
        logger.debug(f"HISTOGRAM: {name}{label_str} {value}")
    
    def record_sync_duration(self, config_id: int, direction: str, duration: float, success: bool) -> None:
        """记录同步持续时间"""
        labels = {
            "config_id": str(config_id),
            "direction": direction,
            "status": "success" if success else "failure"
        }
        
        self.increment_counter("sync_total", 1, labels)
        self.observe_histogram("sync_duration_seconds", duration, labels)
        
        if success:
            self.increment_counter("sync_success_total", 1, labels)
        else:
            self.increment_counter("sync_failure_total", 1, labels)
    
    def record_sync_rows(self, config_id: int, direction: str, rows: int, operation: str) -> None:
        """记录同步行数"""
        labels = {
            "config_id": str(config_id),
            "direction": direction,
            "operation": operation
        }
        
        self.increment_counter("sync_rows_total", rows, labels)
    
    def record_api_call(
        self,
        api_name: str,
        duration: float,
        status_code: int,
        error: Optional[str] = None
    ) -> None:
        """记录API调用"""
        labels = {
            "api": api_name,
            "status": "success" if 200 <= status_code < 300 else "error"
        }
        
        self.increment_counter("api_calls_total", 1, labels)
        self.observe_histogram("api_latency_seconds", duration, labels)
        
        if error:
            self.increment_counter("api_errors_total", 1, {**labels, "error_type": error})
    
    def record_retry(self, operation: str, attempt: int, max_attempts: int) -> None:
        """记录重试"""
        self.increment_counter("retry_total", 1, {
            "operation": operation,
            "attempt": str(attempt),
            "max_attempts": str(max_attempts)
        })
    
    def record_batch_operation(self, operation: str, batch_size: int, duration: float) -> None:
        """记录批量操作"""
        self.increment_counter("batch_operations_total", 1, {"operation": operation})
        self.observe_histogram("batch_size", batch_size, {"operation": operation})
        self.observe_histogram("batch_duration_seconds", duration, {"operation": operation})
    
    def get_counter_value(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        since: Optional[float] = None,
    ) -> float:
        """获取计数器值"""
        points = self._counters.get(name, [])
        
        if labels:
            points = [p for p in points if all(p.labels.get(k) == v for k, v in labels.items())]
        
        if since:
            points = [p for p in points if p.timestamp >= since]
        
        return sum(p.value for p in points)
    
    def get_gauge_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """获取仪表值"""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0.0)
    
    def get_histogram_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        since: Optional[float] = None,
    ) -> Dict[str, float]:
        """获取直方图统计"""
        values = self._histograms.get(name, [])
        
        if since:
            points = [p for p in values if p >= since]
        else:
            points = values
        
        if not points:
            return {
                "count": 0,
                "sum": 0.0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }
        
        sorted_values = sorted(points)
        count = len(sorted_values)
        
        return {
            "count": count,
            "sum": sum(sorted_values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p90": sorted_values[int(count * 0.9)] if count >= 10 else sorted_values[-1],
            "p95": sorted_values[int(count * 0.95)] if count >= 20 else sorted_values[-1],
            "p99": sorted_values[int(count * 0.99)] if count >= 100 else sorted_values[-1],
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标摘要"""
        return {
            "timestamp": datetime.now().isoformat(),
            "counters": {
                name: {
                    "total": sum(p.value for p in points),
                    "points": len(points)
                }
                for name, points in self._counters.items()
            },
            "gauges": dict(self._gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self._histograms.keys()
            }
        }
    
    def get_sync_statistics(self, config_id: Optional[int] = None) -> Dict[str, Any]:
        """获取同步统计信息"""
        since = time.time() - 3600
        
        stats = {
            "period": "last_hour",
            "syncs_total": self.get_counter_value("sync_total", since=since),
            "syncs_success": self.get_counter_value("sync_success_total", since=since),
            "syncs_failed": self.get_counter_value("sync_failure_total", since=since),
            "rows_synced": self.get_counter_value("sync_rows_total", since=since),
            "duration_stats": self.get_histogram_stats("sync_duration_seconds", since=since),
        }
        
        if config_id:
            labels = {"config_id": str(config_id)}
            stats["config"] = {
                "syncs_total": self.get_counter_value("sync_total", labels, since=since),
                "syncs_success": self.get_counter_value("sync_success_total", labels, since=since),
                "rows_synced": self.get_counter_value("sync_rows_total", labels, since=since),
                "duration_stats": self.get_histogram_stats("sync_duration_seconds", labels, since=since),
            }
        
        if stats["syncs_total"] > 0:
            stats["success_rate"] = stats["syncs_success"] / stats["syncs_total"] * 100
        else:
            stats["success_rate"] = 0.0
        
        return stats
    
    def get_api_statistics(self) -> Dict[str, Any]:
        """获取API调用统计"""
        since = time.time() - 3600
        
        return {
            "period": "last_hour",
            "calls_total": self.get_counter_value("api_calls_total", since=since),
            "calls_success": self.get_counter_value("api_calls_total", {"status": "success"}, since=since),
            "calls_error": self.get_counter_value("api_calls_total", {"status": "error"}, since=since),
            "retries": self.get_counter_value("retry_total", since=since),
            "latency_stats": self.get_histogram_stats("api_latency_seconds", since=since),
        }
    
    def reset_metrics(self) -> None:
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        logger.info("Metrics reset")
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """生成唯一键"""
        if not labels:
            return name
        label_str = self._format_labels(labels)
        return f"{name}{label_str}"
    
    def _format_labels(self, labels: Optional[Dict[str, str]] = None) -> str:
        """格式化标签"""
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
    
    def export_prometheus_format(self) -> str:
        """导出Prometheus格式指标"""
        lines = []
        timestamp = int(time.time() * 1000)
        
        for name, points in self._counters.items():
            total = sum(p.value for p in points)
            lines.append(f"{name}_total {total} {timestamp}")
        
        for key, value in self._gauges.items():
            metric_name = key.split("{")[0] if "{" in key else key
            lines.append(f"{metric_name} {value} {timestamp}")
        
        for name, values in self._histograms.items():
            if values:
                stats = self.get_histogram_stats(name)
                for stat, value in stats.items():
                    if stat != "count":
                        lines.append(f"{name}_{stat} {value} {timestamp}")
        
        return "\n".join(lines)


metrics_collector = MetricsCollector()


class Timer:
    """上下文管理器，用于计时"""
    
    def __init__(self, name: str, labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.labels = labels or {}
        self.start_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time.time() - self.start_time
        metrics_collector.observe_histogram(self.name, self.duration, self.labels)
        return False
    
    def record(self, success: bool = True):
        """手动记录时长"""
        if self.duration is not None:
            metrics_collector.observe_histogram(
                f"{self.name}_duration",
                self.duration,
                {**self.labels, "success": str(success)}
            )
