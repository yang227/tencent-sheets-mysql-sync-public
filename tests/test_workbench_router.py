from fastapi.testclient import TestClient

from app.main import app
from app.routers.workbench_router import get_db


class FakeDB:
    def execute(self, query, params=()):
        if "FROM sync_logs l" in query:
            return [
                {
                    "id": 8,
                    "config_id": 3,
                    "table_name": "orders",
                    "database": "biz",
                    "direction": "bidirectional",
                    "status": "success",
                    "rows_affected": 12,
                    "rows_new": 7,
                    "rows_updated": 5,
                    "rows_skipped": 0,
                    "started_at": "2026-04-30 15:00:00",
                    "completed_at": "2026-04-30 15:00:08",
                    "error_message": None,
                }
            ]
        if "FROM sync_configs WHERE is_active = 1" in query:
            return [{"value": 4}]
        if "FROM mysql_configs WHERE is_active = 1" in query:
            return [{"value": 2}]
        if "FROM tencent_api_configs WHERE is_active = 1" in query:
            return [{"value": 2}]
        if "FROM sync_logs WHERE status = 'success'" in query:
            return [{"value": 9}]
        if "FROM sync_logs WHERE status = 'failed'" in query:
            return [{"value": 1}]
        if "FROM sync_logs" in query:
            return [{"value": 10}]
        return []

    def test_connection(self):
        return {"connected": True, "message": "ok"}

    def list_mysql_databases(self):
        return [{"database": "biz"}, {"database": "warehouse"}]


def test_workbench_summary():
    app.dependency_overrides[get_db] = lambda: FakeDB()
    client = TestClient(app)

    response = client.get("/api/workbench/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["sync_configs"] == 4
    assert payload["counts"]["sync_runs"] == 10
    assert payload["mysql_connection"]["connected"] is True
    assert payload["recent_runs"][0]["table_name"] == "orders"

    app.dependency_overrides.clear()


def test_workbench_catalog():
    app.dependency_overrides[get_db] = lambda: FakeDB()
    client = TestClient(app)

    response = client.get("/api/workbench/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["databases"]) == 2
    assert payload["directions"][2]["value"] == "bidirectional"

    app.dependency_overrides.clear()
