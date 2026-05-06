"""Tests for config_router.py — push coverage to 80%+."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.mysql_service import MySQLService
from app.routers.config_router import router as config_router, get_db

app = FastAPI()
app.include_router(config_router)


# ── fixture ─────────────────────────────────────────────────────

@pytest.fixture
def client():
    mock_db = MagicMock(spec=MySQLService)
    app.dependency_overrides[get_db] = lambda: mock_db
    c = TestClient(app)
    yield c, mock_db
    app.dependency_overrides.clear()


# ── helpers ───────────────────────────────────────────────────────

def _make_row(**overrides):
    """Build a config row with mapping_json as a proper JSON string."""
    cols = [{"sheet_col": "A", "sheet_header": "ID",
             "db_column": "id", "db_type": "INT", "primary_key": True}]
    row = {
        "id": 1,
        "spreadsheet_id": "s1",
        "sheet_id": "sh1",
        "table_name": "t1",
        "database": "db1",
        "mapping_json": json.dumps({"columns": cols}),
        "sync_direction": "bidirectional",
        "poll_interval": 30,
        "last_sync_at": None,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
        "is_active": 1,
    }
    row.update(overrides)
    return row


def _cols():
    return [{"sheet_col": "A", "sheet_header": "ID",
            "db_column": "id", "db_type": "INT", "primary_key": True}]


# ── get_db (line 16) ───────────────────────────────────────────

def test_get_db():
    with patch("app.routers.config_router.get_mysql_service") as mock_get:
        mock_get.return_value = MagicMock(spec=MySQLService)
        result = get_db()
        assert result is not None


# ── GET /api/configs ─────────────────────────────────────────

class TestListConfigs:
    def test_success(self, client):
        c, mock_db = client
        mock_db.execute.return_value = [_make_row()]
        resp = c.get("/api/configs")
        assert resp.status_code == 200

    def test_error(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = Exception("db boom")
        resp = c.get("/api/configs")
        assert resp.status_code == 500


# ── POST /api/configs ────────────────────────────────────────

class TestCreateConfig:
    BODY = {
        "spreadsheet_id": "s_new",
        "sheet_id": "sh_new",
        "table_name": "t_new",
        "database": "db_new",
        "mapping_json": {"columns": _cols(), "sheet_header_row": 1, "data_start_row": 2},
        "sync_direction": "bidirectional",
        "poll_interval": 60,
    }

    def test_success(self, client):
        c, mock_db = client
        mock_db.create_sync_config.return_value = 42
        mock_db.execute.return_value = [_make_row(id=42)]
        resp = c.post("/api/configs", json=self.BODY)
        assert resp.status_code == 200

    def test_error(self, client):
        c, mock_db = client
        mock_db.create_sync_config.side_effect = Exception("create boom")
        resp = c.post("/api/configs", json=self.BODY)
        assert resp.status_code == 500

    def test_empty_result_after_create(self, client):
        """Cover line 58."""
        c, mock_db = client
        mock_db.create_sync_config.return_value = 42
        mock_db.execute.return_value = []
        resp = c.post("/api/configs", json=self.BODY)
        assert resp.status_code == 500


# ── GET /api/configs/{config_id} ─────────────────────────────

class TestGetConfig:
    def test_success(self, client):
        c, mock_db = client
        mock_db.execute.return_value = [_make_row()]
        resp = c.get("/api/configs/1")
        assert resp.status_code == 200

    def test_not_found(self, client):
        c, mock_db = client
        mock_db.execute.return_value = []
        resp = c.get("/api/configs/999")
        assert resp.status_code == 404

    def test_error(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = Exception("db boom")
        resp = c.get("/api/configs/1")
        assert resp.status_code == 500


# ── PUT /api/configs/{config_id} ─────────────────────────────

class TestUpdateConfig:
    def test_success(self, client):
        c, mock_db = client
        mock_db.update_sync_config.return_value = True
        mock_db.execute.side_effect = [
            [{"poll_interval": 30}],
            [_make_row()],
        ]
        with patch("app.scheduler.sync_scheduler.SyncScheduler") as MockSched:
            MockSched.return_value = MagicMock()
            resp = c.put(
                "/api/configs/1",
                json={"poll_interval": 120, "is_active": True}
            )
            assert resp.status_code == 200

    def test_no_fields(self, client):
        """Cover line 113: 400 if no update fields."""
        c, mock_db = client
        resp = c.put(
            "/api/configs/1",
            json={"poll_interval": None, "sheet_id": None, "table_name": None,
                 "database": None, "mapping_json": None, "sync_direction": None,
                 "is_active": None}
        )
        assert resp.status_code == 400

    def test_not_found(self, client):
        c, mock_db = client
        mock_db.update_sync_config.return_value = False
        resp = c.put("/api/configs/999", json={"poll_interval": 60})
        assert resp.status_code == 404

    def test_deactivate_removes_job(self, client):
        """Cover lines 124-126."""
        c, mock_db = client
        mock_db.update_sync_config.return_value = True
        # 只会被调用一次：SELECT * FROM sync_configs WHERE id = %s
        mock_db.execute.side_effect = [
            [_make_row(is_active=0)],
        ]
        with patch("app.scheduler.sync_scheduler.SyncScheduler") as MockSched:
            resp = c.put(
                "/api/configs/1",
                json={"is_active": False}
            )
            assert resp.status_code == 200
            MockSched.remove_sync_job.assert_called_once_with(1)

    def test_error(self, client):
        c, mock_db = client
        mock_db.update_sync_config.side_effect = Exception("update boom")
        resp = c.put("/api/configs/1", json={"poll_interval": 60})
        assert resp.status_code == 500


# ── DELETE /api/configs/{config_id} ─────────────────────────

class TestDeleteConfig:
    def test_success(self, client):
        c, mock_db = client
        mock_db.delete_sync_config.return_value = True
        with patch("app.scheduler.sync_scheduler.SyncScheduler") as MockSched:
            resp = c.delete("/api/configs/1")
            assert resp.status_code == 200
            mock_db.delete_sync_config.assert_called_once_with(1)
            MockSched.remove_sync_job.assert_called_once_with(1)

    def test_error(self, client):
        c, mock_db = client
        mock_db.delete_sync_config.side_effect = Exception("delete boom")
        resp = c.delete("/api/configs/1")
        assert resp.status_code == 500


# ── POST /api/configs/{config_id}/test ──────────────────────

class TestTestConnection:
    def test_success(self, client):
        c, mock_db = client
        mock_db.execute.return_value = [_make_row()]
        mock_db.test_connection.return_value = {"connected": True}
        with patch("app.routers.config_router.SyncEngine") as MockEngine:
            mock_engine = MagicMock()
            # 使用 AsyncMock 模拟异步方法
            mock_engine.tencent.test_connection = AsyncMock(
                return_value={"connected": True}
            )
            MockEngine.return_value = mock_engine
            resp = c.post("/api/configs/1/test")
            assert resp.status_code == 200

    def test_not_found(self, client):
        c, mock_db = client
        mock_db.execute.return_value = []
        resp = c.post("/api/configs/999/test")
        assert resp.status_code == 404

    def test_error(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = Exception("db boom")
        resp = c.post("/api/configs/1/test")
        assert resp.status_code == 500
