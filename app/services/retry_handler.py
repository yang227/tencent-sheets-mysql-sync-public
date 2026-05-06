"""
错误处理和重试机制服务
实现指数退避重试、错误分类和死信队列
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from enum import Enum
from dataclasses import dataclass, field
import functools

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorSeverity(Enum):
    """错误严重级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RetryableError(Enum):
    """可重试错误类型"""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    CONNECTION_ERROR = "connection_error"


@dataclass
class RetryConfig:
    """重试配置"""
    base_delay: float = 1.0
    max_delay: float = 60.0
    max_attempts: int = 5
    exponential_base: float = 2.0
    jitter: bool = True
    
    
@dataclass
class ErrorRecord:
    """错误记录"""
    timestamp: datetime
    error_type: str
    error_message: str
    context: Dict[str, Any]
    severity: ErrorSeverity
    retryable: bool
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class DeadLetterQueue:
    """
    死信队列 - 处理永久失败的请求
    """
    
    def __init__(self, max_size: int = 1000):
        self._queue: List[Dict[str, Any]] = []
        self._max_size = max_size
    
    def add(
        self,
        operation: str,
        payload: Any,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加失败项到死信队列"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "payload": str(payload)[:1000],
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "context": context or {},
            "retry_count": context.get("retry_count", 0) if context else 0,
        }
        
        self._queue.append(record)
        
        if len(self._queue) > self._max_size:
            self._queue = self._queue[-self._max_size:]
        
        logger.warning(
            f"DEAD_LETTER: {operation} failed permanently after retries. "
            f"Error: {error}"
        )
    
    def get_items(
        self,
        operation: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取死信队列项"""
        items = self._queue.copy()
        
        if operation:
            items = [i for i in items if i["operation"] == operation]
        
        if since:
            since_iso = since.isoformat()
            items = [i for i in items if i["timestamp"] >= since_iso]
        
        return items[-limit:]
    
    def retry_item(self, index: int) -> Optional[Dict[str, Any]]:
        """重新取出队列项进行重试"""
        if 0 <= index < len(self._queue):
            return self._queue.pop(index)
        return None
    
    def clear(self, before: Optional[datetime] = None) -> int:
        """清理死信队列"""
        original_count = len(self._queue)
        
        if before:
            before_iso = before.isoformat()
            self._queue = [i for i in self._queue if i["timestamp"] >= before_iso]
        else:
            self._queue.clear()
        
        removed = original_count - len(self._queue)
        logger.info(f"Cleared {removed} items from dead letter queue")
        return removed
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取死信队列统计"""
        if not self._queue:
            return {
                "total": 0,
                "by_operation": {},
                "recent_24h": 0,
            }
        
        by_operation: Dict[str, int] = {}
        recent_24h = 0
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        for item in self._queue:
            op = item["operation"]
            by_operation[op] = by_operation.get(op, 0) + 1
            
            if item["timestamp"] >= cutoff:
                recent_24h += 1
        
        return {
            "total": len(self._queue),
            "by_operation": by_operation,
            "recent_24h": recent_24h,
        }


class ErrorHandler:
    """
    统一错误处理器
    提供错误分类、严重性评估和重试策略
    """
    
    def __init__(self):
        self._error_history: List[ErrorRecord] = []
        self._max_history = 1000
        self._error_thresholds: Dict[str, int] = {
            "critical": 5,
            "high": 20,
            "medium": 50,
        }
    
    def classify_error(self, error: Exception) -> tuple[bool, RetryableError]:
        """
        分类错误，判断是否可重试
        
        Returns:
            (is_retryable, error_type)
        """
        error_str = str(error).lower()
        error_type_name = type(error).__name__
        
        if "timeout" in error_str or error_type_name == "TimeoutError":
            return True, RetryableError.TIMEOUT
        
        if "connection" in error_str or "connect" in error_str or error_type_name == "ConnectionError":
            return True, RetryableError.CONNECTION_ERROR
        
        if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
            return True, RetryableError.RATE_LIMIT
        
        if "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
            return True, RetryableError.SERVER_ERROR
        
        if "temporarily unavailable" in error_str or "service unavailable" in error_str:
            return True, RetryableError.TEMPORARY_UNAVAILABLE
        
        if "network" in error_str or "dns" in error_str or "socket" in error_str or error_type_name == "OSError":
            return True, RetryableError.NETWORK_ERROR
        
        return False, RetryableError.TIMEOUT
    
    def assess_severity(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> ErrorSeverity:
        """评估错误严重级别"""
        error_str = str(error).lower()
        
        if "authentication" in error_str or "authorization" in error_str:
            return ErrorSeverity.HIGH
        
        if "database" in error_str or "mysql" in error_str:
            return ErrorSeverity.HIGH
        
        if "data loss" in error_str or "corruption" in error_str:
            return ErrorSeverity.CRITICAL
        
        if context and context.get("retry_count", 0) >= 3:
            return ErrorSeverity.MEDIUM
        
        return ErrorSeverity.MEDIUM
    
    def record_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录错误到历史"""
        is_retryable, retry_error_type = self.classify_error(error)
        severity = self.assess_severity(error, context)
        
        # 记录原始异常类型，而不是可重试错误类型
        original_error_type = type(error).__name__
        
        record = ErrorRecord(
            timestamp=datetime.now(),
            error_type=original_error_type,  # 使用原始异常类型
            error_message=str(error),
            context=context or {},
            severity=severity,
            retryable=is_retryable,
        )
        
        self._error_history.append(record)
        
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history:]
        
        if severity == ErrorSeverity.CRITICAL or severity == ErrorSeverity.HIGH:
            logger.error(
                f"HIGH_SEVERITY_ERROR: {error_type.value} - {error}. "
                f"Context: {context}"
            )
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """
        计算重试延迟时间（线性增长）
        
        Args:
            attempt: 当前尝试次数（从1开始）
            config: 重试配置
            
        Returns:
            延迟秒数
        """
        # 线性增长：delay = base_delay * attempt
        delay = config.base_delay * attempt
        delay = min(delay, config.max_delay)
        
        if config.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay
    
    def should_retry(self, error: Exception, attempt: int, config: Optional[RetryConfig] = None) -> bool:
        """
        判断是否应该重试
        
        Args:
            error: 发生的异常
            attempt: 当前尝试次数（从0开始）
            config: 重试配置（可选，使用默认配置）
            
        Returns:
            是否应该重试
        """
        if config is None:
            config = RetryConfig()
        
        is_retryable, _ = self.classify_error(error)
        
        if not is_retryable:
            return False
        
        if attempt >= config.max_attempts - 1:
            return False
        
        return True
    
    def should_alert(self, error_type: str) -> bool:
        """判断是否需要告警"""
        recent_errors = [
            e for e in self._error_history
            if e.error_type == error_type
            and e.timestamp > datetime.now() - timedelta(minutes=5)
        ]
        
        threshold = self._error_thresholds.get(error_type, 10)
        return len(recent_errors) >= threshold
    
    def get_error_statistics(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取错误统计"""
        errors = self._error_history.copy()
        
        if since:
            errors = [e for e in errors if e.timestamp >= since]
        
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        retryable_count = 0
        
        for error in errors:
            by_type[error.error_type] = by_type.get(error.error_type, 0) + 1
            by_severity[error.severity.value] = by_severity.get(error.severity.value, 0) + 1
            if error.retryable:
                retryable_count += 1
        
        return {
            "total_errors": len(errors),
            "by_type": by_type,
            "by_severity": by_severity,
            "retryable_count": retryable_count,
            "non_retryable_count": len(errors) - retryable_count,
        }
    
    def get_error_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """
        获取错误摘要（简化版）
        
        Args:
            since: 可选，只统计此时间之后的错误
            
        Returns:
            包含错误摘要的字典
        """
        stats = self.get_error_statistics(since)
        
        # 简化版：返回总数、按类型分组和按严重级别分组
        return {
            "total": stats["total_errors"],
            "by_type": stats["by_type"],
            "by_severity": stats["by_severity"],
            "retryable": stats["retryable_count"],
        }


retry_handler = ErrorHandler()
dead_letter_queue = DeadLetterQueue()


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None,
    on_failure: Optional[Callable] = None,
):
    """
    装饰器：实现指数退避重试
    
    Args:
        config: 重试配置
        on_retry: 重试回调
        on_failure: 最终失败回调
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not retry_handler.should_retry(e, attempt, config):
                        retry_handler.record_error(
                            e,
                            {"function": func.__name__, "attempt": attempt + 1}
                        )
                        
                        dead_letter_queue.add(
                            operation=func.__name__,
                            payload={"args": str(args), "kwargs": str(kwargs)},
                            error=e,
                            context={"attempt": attempt + 1}
                        )
                        
                        if on_failure:
                            on_failure(e, attempt)
                        raise
                    
                    delay = retry_handler.calculate_delay(attempt, config)
                    
                    logger.warning(
                        f"RETRY: {func.__name__} failed (attempt {attempt + 1}/{config.max_attempts}). "
                        f"Retrying in {delay:.2f}s. Error: {e}"
                    )
                    
                    retry_handler.record_error(
                        e,
                        {"function": func.__name__, "attempt": attempt + 1, "delay": delay}
                    )
                    
                    if on_retry:
                        on_retry(e, attempt, delay)
                    
                    await asyncio.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not retry_handler.should_retry(e, attempt, config):
                        retry_handler.record_error(
                            e,
                            {"function": func.__name__, "attempt": attempt + 1}
                        )
                        
                        dead_letter_queue.add(
                            operation=func.__name__,
                            payload={"args": str(args), "kwargs": str(kwargs)},
                            error=e,
                            context={"attempt": attempt + 1}
                        )
                        
                        if on_failure:
                            on_failure(e, attempt)
                        raise
                    
                    delay = retry_handler.calculate_delay(attempt, config)
                    
                    logger.warning(
                        f"RETRY: {func.__name__} failed (attempt {attempt + 1}/{config.max_attempts}). "
                        f"Retrying in {delay:.2f}s. Error: {e}"
                    )
                    
                    retry_handler.record_error(
                        e,
                        {"function": func.__name__, "attempt": attempt + 1, "delay": delay}
                    )
                    
                    if on_retry:
                        on_retry(e, attempt, delay)
                    
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def get_error_context(error: Exception) -> Dict[str, Any]:
    """获取错误的详细上下文"""
    import traceback
    import sys
    
    exc_type, exc_value, exc_tb = sys.exc_info()
    
    return {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
        "module": getattr(error.__class__, '__module__', 'unknown'),
    }
