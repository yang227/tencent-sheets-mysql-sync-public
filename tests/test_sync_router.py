"""
Tests for sync router API endpoints.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.mysql_service import MySQLService
from app.services.sync_engine import SyncResult, SyncEngineError

from app.routers.sync_router import router as sync_router, get_db, load_config
app = FastAPI()
app.include_router(sync_router)


@pytest.fixture
def client():
    mock_db = MagicMock(spec=MySQLService)
    app.dependency_overrides[get_db] = lambda: mock_db
    test_client = TestClient(app)
    yield test_client, mock_db
    app.dependency_overrides.clear()


# ── Line 12: get_db() ────────────────────────────────

def test_get_db():
    """Cover get_db() -> get_mysql_service() (line 12)."""
    with patch("app.routers.sync_router.get_mysql_service") as mock_get:
        mock_get.return_value = MagicMock(spec=MySQLService)
        result = get_db()
        assert result is not None
        mock_get.assert_called_once()


# ── Helpers ─────────────────────────────────────────────

def _mock_config():
    """Return a config dict that satisfies load_config + SyncConfig."""
    return {
        "id": 1,
        "spreadsheet_id": "s1",
        "sheet_id": "sh1",
        "table_name": "t1",
        "database": "db1",
        "mapping_json": '{"columns": [{"sheet_col": "A", "db_column": "id", "db_type": "INT", "primary_key": true}]}',
        "sync_direction": "bidirectional",
        "poll_interval": 30,
        "last_sync_at": None,
        "is_active": 1,
    }


def _mock_engine_for_success():
    """Patch SyncEngine to return a successful SyncResult."""
    mock_engine = MagicMock()
    mock_engine.trigger_sync = AsyncMock(return_value=SyncResult(
        success=True, direction="bidirectional",
        rows_affected=5, rows_new=2, rows_updated=3, rows_skipped=0,
    ))
    mock_engine.sync_to_mysql = AsyncMock(return_value=SyncResult(
        success=True, direction="to_mysql",
        rows_affected=3, rows_new=1, rows_updated=2, rows_skipped=0,
    ))
    mock_engine.sync_from_mysql = AsyncMock(return_value=SyncResult(
        success=True, direction="from_mysql",
        rows_affected=2, rows_new=1, rows_updated=1, rows_skipped=0,
    ))
    mock_engine.get_sync_status.return_value = {
        "config_id": 1, "spreadsheet_id": "s1",
        "last_sync": None, "recent_logs": [],
    }
    mock_engine.test_connection = AsyncMock(return_value={
        "mysql": {"connected": True},
        "tencent": {"connected": True},
        "all_connected": True,
    })
    return mock_engine


# ── POST /{config_id}/trigger ─────────────────────────

class TestTriggerSync:
    def test_success(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            MockEngine.return_value = _mock_engine_for_success()
            response = test_client.post("/api/sync/1/trigger")
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_not_found(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = []
        response = test_client.post("/api/sync/999/trigger")
        assert response.status_code == 404

    def test_sync_engine_error(self, client):
        """Cover lines 57-62: SyncEngineError / generic exception."""
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.trigger_sync = AsyncMock(
                side_effect=SyncEngineError("engine failure")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/trigger")
            assert response.status_code == 500

    def test_generic_exception(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.trigger_sync = AsyncMock(
                side_effect=Exception("unexpected")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/trigger")
            assert response.status_code == 500


# ── POST /{config_id}/to-mysql ────────────────────────

class TestSyncToMysql:
    def test_success(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            MockEngine.return_value = _mock_engine_for_success()
            response = test_client.post("/api/sync/1/to-mysql")
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_not_found(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = []
        response = test_client.post("/api/sync/999/to-mysql")
        assert response.status_code == 404

    def test_sync_engine_error(self, client):
        """Cover line 82: SyncEngineError in sync_to_mysql."""
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.sync_to_mysql = AsyncMock(
                side_effect=SyncEngineError("boom")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/to-mysql")
            assert response.status_code == 500

    def test_generic_exception(self, client):
        """Cover lines 85-86: generic exception in sync_to_mysql."""
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.sync_to_mysql = AsyncMock(
                side_effect=Exception("unexpected")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/to-mysql")
            assert response.status_code == 500


# ── POST /{config_id}/from-mysql ─────────────────────

class TestSyncFromMysql:
    def test_success(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            MockEngine.return_value = _mock_engine_for_success()
            response = test_client.post("/api/sync/1/from-mysql")
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_not_found(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = []
        response = test_client.post("/api/sync/999/from-mysql")
        assert response.status_code == 404

    def test_sync_engine_error(self, client):
        """Cover line 106: SyncEngineError in sync_from_mysql."""
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.sync_from_mysql = AsyncMock(
                side_effect=SyncEngineError("engine boom")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/from-mysql")
            assert response.status_code == 500

    def test_generic_exception(self, client):
        """Cover lines 109-110: generic exception in sync_from_mysql."""
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.sync_from_mysql = AsyncMock(
                side_effect=Exception("unexpected")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/from-mysql")
            assert response.status_code == 500


# ── GET /{config_id}/status ───────────────────────────

class TestGetSyncStatus:
    def test_success(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            MockEngine.return_value = _mock_engine_for_success()
            response = test_client.get("/api/sync/1/status")
            assert response.status_code == 200
            assert "config_id" in response.json()

    def test_not_found(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = []
        response = test_client.get("/api/sync/999/status")
        assert response.status_code == 404

    def test_exception(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.get_sync_status.side_effect = Exception("boom")
            MockEngine.return_value = mock_engine
            response = test_client.get("/api/sync/1/status")
            assert response.status_code == 500


# ── POST /{config_id}/test ─────────────────────────────

class TestTestConnections:
    def test_success(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            MockEngine.return_value = _mock_engine_for_success()
            response = test_client.post("/api/sync/1/test")
            assert response.status_code == 200
            data = response.json()
            assert "all_connected" in data

    def test_not_found(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = []
        response = test_client.post("/api/sync/999/test")
        assert response.status_code == 404

    def test_exception(self, client):
        test_client, mock_db = client
        mock_db.execute.return_value = [_mock_config()]
        with patch("app.routers.sync_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.test_connection = AsyncMock(
                side_effect=Exception("conn failed")
            )
            MockEngine.return_value = mock_engine
            response = test_client.post("/api/sync/1/test")
            assert response.status_code == 500
