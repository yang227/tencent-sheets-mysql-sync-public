"""
Tests for mysql_browser router API endpoints.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.services.mysql_service import MySQLService

from app.routers.mysql_browser import router as mysql_router, get_db
app = FastAPI()
app.include_router(mysql_router)


@pytest.fixture
def client():
    mock_db = MagicMock(spec=MySQLService)
    app.dependency_overrides[get_db] = lambda: mock_db
    test_client = TestClient(app)
    yield test_client, mock_db
    app.dependency_overrides.clear()


class TestMysqlBrowserRouter:
    # ── Line 9: get_db() ────────────────────────────────
    def test_get_db(self):
        """Cover get_db() -> get_mysql_service() (line 9)."""
        with patch("app.routers.mysql_browser.get_mysql_service") as mock_get:
            mock_get.return_value = MagicMock(spec=MySQLService)
            result = get_db()
            assert result is not None
            mock_get.assert_called_once()

    # ── GET /databases ───────────────────────────────────
    def test_list_databases_success(self, client):
        test_client, mock_db = client
        mock_db.list_mysql_databases.return_value = [{"name": "db1", "label": "db1"}]
        response = test_client.get("/api/mysql/databases")
        assert response.status_code == 200

    def test_list_databases_error(self, client):
        test_client, mock_db = client
        mock_db.list_mysql_databases.side_effect = Exception("DB error")
        response = test_client.get("/api/mysql/databases")
        assert response.status_code == 500

    # ── GET /databases/{database}/tables ─────────────────
    def test_list_tables_success(self, client):
        test_client, mock_db = client
        mock_db.list_mysql_tables.return_value = [{"name": "t1", "label": "t1"}]
        response = test_client.get("/api/mysql/databases/mydb/tables")
        assert response.status_code == 200

    def test_list_tables_error(self, client):
        test_client, mock_db = client
        mock_db.list_mysql_tables.side_effect = Exception("DB error")
        response = test_client.get("/api/mysql/databases/mydb/tables")
        assert response.status_code == 500

    # ── GET /tables/{table_name}/columns ────────────────
    def test_get_columns_success(self, client):
        test_client, mock_db = client
        mock_db.get_table_columns.return_value = [
            {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO",
             "COLUMN_KEY": "PRI", "COLUMN_DEFAULT": None, "EXTRA": ""}
        ]
        response = test_client.get("/api/mysql/tables/mytable/columns")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["name"] == "id"

    def test_get_columns_with_database_param(self, client):
        test_client, mock_db = client
        mock_db.get_table_columns.return_value = []
        response = test_client.get("/api/mysql/tables/mytable/columns?database=mydb")
        assert response.status_code == 200
        mock_db.get_table_columns.assert_called_once_with("mytable", "mydb")

    def test_get_columns_error(self, client):
        test_client, mock_db = client
        mock_db.get_table_columns.side_effect = Exception("DB error")
        response = test_client.get("/api/mysql/tables/mytable/columns")
        assert response.status_code == 500
