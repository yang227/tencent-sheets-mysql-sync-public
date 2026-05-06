"""
Comprehensive tests for SyncEngine - targeting 90%+ coverage.
Tests all core sync logic, edge cases, and error handling.
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.sync_engine import (
    SyncEngine, SyncResult, SyncEngineError, _config_cache, _config_cache_time
)
from app.services.tencent_api import TencentAPIError, DocumentNotFoundError, PermissionDeniedError, DocumentTypeMismatchError
from app.services.mysql_service import MySQLServiceError


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Clear the global config cache before each test to ensure isolation."""
    _config_cache.clear()
    _config_cache_time.clear()
    yield


def _make_config(config_id=1, direction="bidirectional"):
    return {
        "id": config_id,
        "spreadsheet_id": "testsheet123",
        "sheet_id": "sheet1",
        "table_name": "test_table",
        "database": "test_db",
        "sync_direction": direction,
        "poll_interval": 30,
        "mapping_json": {
            "columns": [
                {"sheet_col": "A", "db_column": "id", "primary_key": True},
                {"sheet_col": "B", "db_column": "name"},
            ],
            "sheet_header_row": 1,
            "data_start_row": 2,
        },
    }


def _make_engine(config_id=1):
    engine = SyncEngine(config_id=config_id)
    engine._mysql = MagicMock()
    engine._tencent = AsyncMock()
    engine._config = _make_config(config_id)
    engine._spreadsheet_id = engine._config["spreadsheet_id"]
    engine._sheet_id = engine._config["sheet_id"]
    engine._table_name = engine._config["table_name"]
    engine._database = engine._config["database"]
    engine._sync_direction = engine._config["sync_direction"]
    engine._poll_interval_cfg = engine._config["poll_interval"]
    engine._mapping = None
    return engine


class TestSyncResult:
    def test_init_all_fields(self):
        r = SyncResult(success=True, direction="to_mysql",
                       rows_affected=10, rows_new=3, rows_updated=5, rows_skipped=2,
                       errors=["e1"], details={"note": "ok"})
        assert r.success is True
        assert r.rows_affected == 10
        assert r.rows_skipped == 2

    def test_to_dict(self):
        r = SyncResult(success=False, direction="from_mysql", errors=["fail"])
        d = r.to_dict()
        assert d["success"] is False
        assert d["errors"] == ["fail"]

    def test_defaults(self):
        r = SyncResult(success=True, direction="to_mysql")
        assert r.rows_affected == 0
        assert r.errors == []
        assert r.details == {}


class TestSyncEngineInit:
    def test_init_defaults(self):
        e = SyncEngine(config_id=5)
        assert e.config_id == 5
        assert e.poll_interval == 30
        assert e.batch_size == 100

    def test_init_custom(self):
        e = SyncEngine(config_id=2, poll_interval=60, batch_size=50, retry_times=5)
        assert e.poll_interval == 60
        assert e.batch_size == 50

    def test_property_mysql_lazy(self):
        e = SyncEngine(config_id=1)
        mock_mysql = MagicMock()
        e._mysql = mock_mysql
        assert e.mysql is mock_mysql

    def test_property_tencent_lazy(self):
        e = SyncEngine(config_id=1)
        mock_tencent = AsyncMock()
        e._tencent = mock_tencent
        assert e.tencent is mock_tencent


class TestEnsureConfig:
    def test_loads_config(self):
        e = SyncEngine(config_id=42)
        e._mysql = MagicMock()
        e._mysql.get_sync_config.return_value = _make_config(42)
        e._ensure_config()
        assert e._config is not None
        assert e._spreadsheet_id == "testsheet123"

    def test_config_not_found(self):
        e = SyncEngine(config_id=999)
        e._mysql = MagicMock()
        e._mysql.get_sync_config.return_value = None
        with pytest.raises(SyncEngineError, match="not found"):
            e._ensure_config()


class TestComputeRowHash:
    def test_basic(self):
        row = {"a": 1, "b": "hello"}
        h1 = SyncEngine.compute_row_hash(row)
        h2 = SyncEngine.compute_row_hash(row)
        assert h1 == h2
        assert len(h1) == 64

    def test_exclude_cols(self):
        row = {"a": 1, "updated_at": "2024-01-01"}
        h1 = SyncEngine.compute_row_hash(row)
        h2 = SyncEngine.compute_row_hash(row, exclude_cols=["updated_at"])
        assert h1 == h2

    def test_none_values_excluded(self):
        row = {"a": 1, "b": None}
        h = SyncEngine.compute_row_hash(row)
        assert h is not None


class TestGetRowKey:
    def test_tencent_source(self):
        e = _make_engine()
        row = {"_row_number": "5"}
        assert e._get_row_key(row, "tencent") == "5"

    def test_mysql_source_with_pk(self):
        e = _make_engine()
        row = {"id": 42, "name": "test"}
        assert e._get_row_key(row, "mysql") == "42"

    def test_mysql_source_no_pk(self):
        cfg = _make_config()
        cfg["mapping_json"]["columns"] = [{"sheet_col": "A", "db_column": "name"}]
        e = _make_engine()
        e._config = cfg
        e._mapping = None
        row = {"name": "test"}
        assert e._get_row_key(row, "mysql") is None


class TestSyncToMysql:
    @pytest.mark.asyncio
    async def test_direction_from_mysql_only_skips(self):
        e = _make_engine()
        e._config["sync_direction"] = "from_mysql"
        result = await e.sync_to_mysql()
        assert result.success is True
        assert result.rows_affected == 0

    @pytest.mark.asyncio
    async def test_empty_sheet_data(self):
        e = _make_engine()
        e._mysql.table_exists.return_value = True
        e._mysql.create_sync_log.return_value = 1
        e._tencent.get_sheet_info.return_value = {"rowCount": 10}
        e._tencent.get_values.return_value = {"values": []}
        result = await e.sync_to_mysql()
        assert result.success is True
        assert result.rows_affected == 0

    @pytest.mark.asyncio
    async def test_with_data_rows(self):
        e = _make_engine()
        e._mysql.table_exists.return_value = True
        e._mysql.create_sync_log.return_value = 1
        e._mysql.get_tracked_row.return_value = None
        e._mysql.insert_or_update.return_value = 1
        e._tencent.get_sheet_info.return_value = {"rowCount": 5}
        e._tencent.get_values.return_value = {"values": [["1", "Alice"], ["2", "Bob"]]}
        result = await e.sync_to_mysql()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_tencent_api_error(self):
        e = _make_engine()
        e._mysql.create_sync_log.return_value = 1
        e._tencent.get_sheet_info.side_effect = TencentAPIError(500, "Server error")
        result = await e.sync_to_mysql()
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_mysql_error_during_batch(self):
        e = _make_engine()
        e._mysql.table_exists.return_value = True
        e._mysql.create_sync_log.return_value = 1
        e._tencent.get_sheet_info.return_value = {"rowCount": 2}
        e._tencent.get_values.return_value = {"values": [["1", "Alice"]]}
        e._mysql.insert_or_update.side_effect = MySQLServiceError("DB error")
        result = await e.sync_to_mysql()
        assert result.success is True
        assert len(result.errors) > 0


class TestSyncFromMysql:
    @pytest.mark.asyncio
    async def test_direction_to_mysql_only_skips(self):
        e = _make_engine()
        e._config["sync_direction"] = "to_mysql"
        result = await e.sync_from_mysql()
        assert result.success is True
        assert result.rows_affected == 0

    @pytest.mark.asyncio
    async def test_empty_mysql_table(self):
        e = _make_engine()
        e._mysql.create_sync_log.return_value = 1
        e._mysql.select_all.return_value = []
        result = await e.sync_from_mysql()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_with_mysql_data(self):
        e = _make_engine()
        e._mysql.create_sync_log.return_value = 1
        e._mysql.select_all.return_value = [{"id": 1, "name": "Alice"}]
        e._mysql.get_tracked_row.return_value = None
        e._tencent.get_sheet_info.return_value = {"rowCount": 5}
        e._mysql.batch_upsert_tracked_rows = MagicMock()
        result = await e.sync_from_mysql()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_mysql_service_error(self):
        e = _make_engine()
        e._mysql.create_sync_log.return_value = 1
        e._mysql.select_all.side_effect = MySQLServiceError("Connection lost")
        result = await e.sync_from_mysql()
        assert result.success is False


class TestSyncBidirectional:
    @pytest.mark.asyncio
    async def test_both_directions_success(self):
        e = _make_engine()
        e.sync_to_mysql = AsyncMock(return_value=SyncResult(success=True, direction="to_mysql", rows_affected=2))
        e.sync_from_mysql = AsyncMock(return_value=SyncResult(success=True, direction="from_mysql", rows_affected=3))
        results = await e.sync_bidirectional()
        assert results["to_mysql"].success is True
        assert results["from_mysql"].success is True

    @pytest.mark.asyncio
    async def test_to_mysql_failure_skips_from_mysql(self):
        e = _make_engine()
        e.sync_to_mysql = AsyncMock(return_value=SyncResult(success=False, direction="to_mysql", errors=["fail"]))
        e.sync_from_mysql = AsyncMock()
        results = await e.sync_bidirectional()
        assert results["to_mysql"].success is False
        assert results["from_mysql"].success is False
        e.sync_from_mysql.assert_not_called()


class TestTriggerSync:
    @pytest.mark.asyncio
    async def test_trigger_to_mysql(self):
        e = _make_engine()
        e.sync_to_mysql = AsyncMock(return_value=SyncResult(success=True, direction="to_mysql"))
        result = await e.trigger_sync(direction="to_mysql")
        assert result.direction == "to_mysql"

    @pytest.mark.asyncio
    async def test_trigger_from_mysql(self):
        e = _make_engine()
        e.sync_from_mysql = AsyncMock(return_value=SyncResult(success=True, direction="from_mysql"))
        result = await e.trigger_sync(direction="from_mysql")
        assert result.direction == "from_mysql"

    @pytest.mark.asyncio
    async def test_trigger_none_uses_config(self):
        e = _make_engine()
        e._sync_direction = "to_mysql"
        e.sync_to_mysql = AsyncMock(return_value=SyncResult(success=True, direction="to_mysql"))
        result = await e.trigger_sync(direction=None)
        assert result.direction == "to_mysql"


class TestHandleWebhook:
    @pytest.mark.asyncio
    async def test_valid_range(self):
        e = _make_engine()
        e._sync_changed_range = AsyncMock(return_value=SyncResult(success=True, direction="to_mysql"))
        result = await e.handle_webhook("edit", "Sheet1!A2:C10")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_range_falls_back(self):
        e = _make_engine()
        e.sync_to_mysql = AsyncMock(return_value=SyncResult(success=True, direction="to_mysql"))
        result = await e.handle_webhook("edit", "invalid_range")
        assert result.success is True


class TestGetSyncStatus:
    def test_status(self):
        e = _make_engine()
        e._mysql.get_sync_logs.return_value = [{"id": 1, "status": "success"}]
        status = e.get_sync_status()
        assert status["config_id"] == 1
        assert "recent_logs" in status


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_both_connected(self):
        e = _make_engine()
        e._mysql.test_connection.return_value = {"connected": True}
        e._tencent.test_connection = AsyncMock(return_value={"connected": True})
        result = await e.test_connection()
        assert result["all_connected"] is True

    @pytest.mark.asyncio
    async def test_mysql_disconnected(self):
        e = _make_engine()
        e._mysql.test_connection.return_value = {"connected": False, "error": "refused"}
        e._tencent.test_connection = AsyncMock(return_value={"connected": True})
        result = await e.test_connection()
        assert result["all_connected"] is False
