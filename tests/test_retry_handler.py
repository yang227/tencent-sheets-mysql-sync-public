"""
Tests for retry_handler service.
"""
import pytest
from datetime import datetime, timedelta
from app.services.retry_handler import (
    ErrorSeverity, RetryableError, RetryConfig, ErrorRecord,
    DeadLetterQueue, ErrorHandler,
)


class TestErrorSeverity:
    def test_enum_values(self):
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestRetryableError:
    def test_enum_values(self):
        assert RetryableError.NETWORK_ERROR.value == "network_error"
        assert RetryableError.TIMEOUT.value == "timeout"


class TestDeadLetterQueue:
    def test_init(self):
        q = DeadLetterQueue(max_size=10)
        assert q._max_size == 10
        assert q._queue == []

    def test_add(self):
        q = DeadLetterQueue(max_size=10)
        q.add("test_op", {"data": 1}, ValueError("bad data"), {"retry_count": 2})
        assert len(q._queue) == 1
        item = q._queue[0]
        assert item["operation"] == "test_op"
        assert item["error_type"] == "ValueError"
        assert item["retry_count"] == 2

    def test_add_truncates(self):
        q = DeadLetterQueue(max_size=10)
        q.add("op", "x" * 2000, Exception("e" * 1000), None)
        item = q._queue[0]
        assert len(item["payload"]) == 1000
        assert len(item["error_message"]) == 500

    def test_add_max_size(self):
        q = DeadLetterQueue(max_size=3)
        for i in range(5):
            q.add(f"op{i}", f"p{i}", Exception("e"))
        assert len(q._queue) == 3
        assert q._queue[0]["operation"] == "op2"  # kept last 3

    def test_get_items_all(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        q.add("op2", "p2", Exception("e"))
        items = q.get_items()
        assert len(items) == 2

    def test_get_items_filter_operation(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        q.add("op2", "p2", Exception("e"))
        items = q.get_items(operation="op1")
        assert len(items) == 1
        assert items[0]["operation"] == "op1"

    def test_get_items_filter_since(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        cutoff = datetime.now() - timedelta(hours=12)
        items = q.get_items(since=cutoff)
        assert len(items) == 1

    def test_retry_item_valid(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        item = q.retry_item(0)
        assert item is not None
        assert item["operation"] == "op1"
        assert len(q._queue) == 0

    def test_retry_item_invalid_index(self):
        q = DeadLetterQueue()
        item = q.retry_item(5)
        assert item is None

    def test_clear_all(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        removed = q.clear()
        assert removed == 1
        assert len(q._queue) == 0

    def test_clear_before(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        before = datetime.now() + timedelta(hours=1)
        removed = q.clear(before=before)
        assert removed == 1

    def test_get_statistics_empty(self):
        q = DeadLetterQueue()
        stats = q.get_statistics()
        assert stats["total"] == 0
        assert stats["by_operation"] == {}
        assert stats["recent_24h"] == 0

    def test_get_statistics(self):
        q = DeadLetterQueue()
        q.add("op1", "p1", Exception("e"))
        q.add("op1", "p2", Exception("e"))
        q.add("op2", "p3", Exception("e"))
        stats = q.get_statistics()
        assert stats["total"] == 3
        assert stats["by_operation"]["op1"] == 2
        assert stats["by_operation"]["op2"] == 1


class TestErrorHandler:
    def test_init(self):
        h = ErrorHandler()
        assert h._max_history == 1000
        assert h._error_thresholds["critical"] == 5

    def test_classify_error_timeout(self):
        h = ErrorHandler()
        retryable, error_type = h.classify_error(TimeoutError("timeout"))
        assert retryable is True
        assert error_type == RetryableError.TIMEOUT

    def test_classify_error_connection(self):
        h = ErrorHandler()
        retryable, error_type = h.classify_error(ConnectionError("connection refused"))
        assert retryable is True
        assert error_type == RetryableError.CONNECTION_ERROR

    def test_classify_error_rate_limit(self):
        h = ErrorHandler()
        retryable, error_type = h.classify_error(Exception("rate limit exceeded"))
        assert retryable is True
        assert error_type == RetryableError.RATE_LIMIT

    def test_classify_error_server(self):
        h = ErrorHandler()
        retryable, error_type = h.classify_error(Exception("500 internal error"))
        assert retryable is True
        assert error_type == RetryableError.SERVER_ERROR

    def test_classify_error_non_retryable(self):
        h = ErrorHandler()
        retryable, error_type = h.classify_error(ValueError("bad value"))
        assert retryable is False

    def test_assess_severity_auth(self):
        h = ErrorHandler()
        severity = h.assess_severity(Exception("authentication failed"))
        assert severity == ErrorSeverity.HIGH

    def test_assess_severity_database(self):
        h = ErrorHandler()
        severity = h.assess_severity(Exception("database connection failed"))
        assert severity == ErrorSeverity.HIGH

    def test_assess_severity_data_loss(self):
        h = ErrorHandler()
        severity = h.assess_severity(Exception("data corruption detected"))
        assert severity == ErrorSeverity.CRITICAL

    def test_assess_severity_retry_count(self):
        h = ErrorHandler()
        severity = h.assess_severity(Exception("oops"), context={"retry_count": 5})
        assert severity == ErrorSeverity.MEDIUM

    def test_assess_severity_low(self):
        h = ErrorHandler()
        severity = h.assess_severity(Exception("minor issue"))
        assert severity == ErrorSeverity.MEDIUM

    def test_record_error(self):
        h = ErrorHandler()
        h.record_error(ValueError("bad"), {"op": "test"})
        assert len(h._error_history) == 1
        assert h._error_history[0].error_type == "ValueError"

    def test_record_error_max_history(self):
        h = ErrorHandler()
        h._max_history = 3
        for i in range(5):
            h.record_error(ValueError(f"e{i}"), None)
        assert len(h._error_history) == 3

    def test_get_error_summary_empty(self):
        h = ErrorHandler()
        summary = h.get_error_summary()
        assert summary["total"] == 0

    def test_get_error_summary(self):
        h = ErrorHandler()
        h.record_error(ValueError("bad"), None)
        h.record_error(ConnectionError("conn"), None)
        h.record_error(ValueError("bad2"), None)
        summary = h.get_error_summary()
        assert summary["total"] == 3
        assert summary["by_type"]["ValueError"] == 2
        assert summary["by_severity"]["medium"] == 3

    def test_should_retry(self):
        h = ErrorHandler()
        assert h.should_retry(ConnectionError("conn"), attempt=1) is True
        assert h.should_retry(ValueError("bad"), attempt=1) is False

    def test_calculate_delay(self):
        h = ErrorHandler()
        config = RetryConfig(base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=False)
        delay1 = h.calculate_delay(1, config)
        delay2 = h.calculate_delay(2, config)
        assert delay1 == 1.0
        assert delay2 == 2.0
