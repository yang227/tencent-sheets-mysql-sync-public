import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.sync_engine import SyncEngine, SyncResult, _config_cache, _config_cache_time


def test_sync_result_init():
    """Test SyncResult initialization."""
    result = SyncResult(
        success=True,
        direction="to_mysql",
        rows_affected=5,
        rows_new=3,
        rows_updated=2,
        rows_skipped=10,
        errors=[]
    )
    
    assert result.success is True
    assert result.direction == "to_mysql"
    assert result.rows_affected == 5
    assert result.rows_new == 3
    assert result.rows_updated == 2
    assert result.rows_skipped == 10
    assert len(result.errors) == 0


def test_sync_result_to_dict():
    """Test SyncResult serialization."""
    result = SyncResult(
        success=True,
        direction="bidirectional",
        rows_affected=10,
        rows_new=5,
        rows_updated=5,
        errors=["error1", "error2"]
    )
    
    data = result.to_dict()
    
    assert data["success"] is True
    assert data["direction"] == "bidirectional"
    assert data["rows_affected"] == 10
    assert len(data["errors"]) == 2


def test_compute_row_hash():
    """Test SHA256 hash computation."""
    row_data = {"name": "test", "value": 123}
    
    hash1 = SyncEngine.compute_row_hash(row_data)
    hash2 = SyncEngine.compute_row_hash(row_data)
    
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64 character hex string


def test_compute_row_hash_with_exclude():
    """Test hash computation with excluded columns."""
    row_data = {"name": "test", "value": 123, "updated_at": "2024-01-01"}
    
    hash1 = SyncEngine.compute_row_hash(row_data)
    hash2 = SyncEngine.compute_row_hash(row_data, exclude_cols=["updated_at"])
    
    assert hash1 == hash2


def test_sync_engine_init():
    """Test SyncEngine initialization."""
    engine = SyncEngine(config_id=1)
    
    assert engine.config_id == 1
    assert engine.poll_interval == 30
    assert engine.batch_size == 100
    assert engine.retry_times == 3


def test_sync_engine_with_custom_params():
    """Test SyncEngine with custom parameters."""
    engine = SyncEngine(
        config_id=2,
        poll_interval=60,
        batch_size=200,
        retry_times=5
    )
    
    assert engine.config_id == 2
    assert engine.poll_interval == 60
    assert engine.batch_size == 200
    assert engine.retry_times == 5


@pytest.mark.asyncio
async def test_trigger_sync_to_mysql():
    """Test trigger_sync with to_mysql direction."""
    engine = SyncEngine(config_id=1)
    engine._metadata_db = MagicMock()
    engine._metadata_db.get_sync_config.return_value = {
        "id": 1,
        "spreadsheet_id": "test_sheet",
        "sheet_id": "sheet1",
        "table_name": "test_table",
        "database": "",
        "sync_direction": "to_mysql",
        "mapping_json": {"columns": []}
    }
    
    # Mock the sync_to_mysql method
    with patch.object(engine, 'sync_to_mysql', new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = SyncResult(
            success=True,
            direction="to_mysql",
            rows_affected=5
        )
        
        result = await engine.trigger_sync(direction="to_mysql")
        
        assert result.success is True
        assert result.direction == "to_mysql"


def test_sync_engine_builds_target_mysql_from_saved_config():
    _config_cache.pop(101, None)
    _config_cache_time.pop(101, None)
    engine = SyncEngine(config_id=101)
    engine._metadata_db = MagicMock()
    engine._metadata_db.get_sync_config.return_value = {
        "spreadsheet_id": "sheet_1",
        "sheet_id": "Sheet1",
        "table_name": "target_table",
        "mapping_json": {"columns": []},
        "mysql_config_id": 11,
    }

    built_mysql = MagicMock()
    with patch("app.services.sync_engine.MySQLConfigService") as mock_service:
        mock_service.return_value.build_mysql_service.return_value = built_mysql
        assert engine.mysql is built_mysql
        mock_service.return_value.build_mysql_service.assert_called_once_with(11)


def test_sync_engine_builds_tencent_api_from_saved_config():
    _config_cache.pop(102, None)
    _config_cache_time.pop(102, None)
    engine = SyncEngine(config_id=102)
    engine._metadata_db = MagicMock()
    engine._metadata_db.get_sync_config.return_value = {
        "spreadsheet_id": "sheet_1",
        "sheet_id": "Sheet1",
        "table_name": "target_table",
        "mapping_json": {"columns": []},
        "tencent_config_id": 22,
    }

    built_api = MagicMock()
    with patch("app.services.sync_engine.TencentApiConfigService") as mock_service:
        mock_service.return_value.build_tencent_api.return_value = built_api
        assert engine.tencent is built_api
        mock_service.return_value.build_tencent_api.assert_called_once_with(22)


def test_sync_result_with_errors():
    """Test SyncResult handling errors."""
    result = SyncResult(
        success=False,
        direction="to_mysql",
        errors=["Connection timeout", "Invalid data"]
    )
    
    assert result.success is False
    assert len(result.errors) == 2
    assert result.rows_affected == 0


def test_sync_result_defaults():
    """Test SyncResult default values."""
    result = SyncResult(success=True, direction="to_mysql")
    
    assert result.rows_affected == 0
    assert result.rows_new == 0
    assert result.rows_updated == 0
    assert result.rows_skipped == 0
    assert result.errors == []
    assert result.details == {}
