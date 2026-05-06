"""Tests for mysql_config_router.py"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.models.config_models import MySQLConfigResponse, TestStatus, MySQLConfigTestResult

# Create a minimal FastAPI app for testing
app = FastAPI()
from app.routers.mysql_config_router import router as mysql_router
app.include_router(mysql_router)


@pytest.fixture
def client():
    """Create test client with mocked service"""
    with patch('app.routers.mysql_config_router.MySQLConfigService') as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        
        # Also mock the get_service dependency
        from app.routers.mysql_config_router import get_service
        app.dependency_overrides[get_service] = lambda: mock_instance
        
        client = TestClient(app)
        yield client, mock_instance
        app.dependency_overrides.clear()


class TestListMySQLConfigs:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.list_configs.return_value = [
            MySQLConfigResponse(
                id=1, name="test", host="localhost", port=3306,
                username="root", database_name="db", charset="utf8mb4",
                description=None, is_active=True,
                created_at=datetime.now(), updated_at=datetime.now()
            )
        ]
        resp = c.get("/api/mysql-configs")
        assert resp.status_code == 200

    def test_empty(self, client):
        c, mock_svc = client
        mock_svc.list_configs.return_value = []
        resp = c.get("/api/mysql-configs")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateMySQLConfig:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.create_config.return_value = MySQLConfigResponse(
            id=1, name="new", host="localhost", port=3306,
            username="root", database_name="db", charset="utf8mb4",
            description=None, is_active=True,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        resp = c.post("/api/mysql-configs", json={
            "name": "new", "host": "localhost", "username": "root",
            "password": "pass", "database_name": "db"
        })
        assert resp.status_code == 200


class TestGetMySQLConfig:
    def test_found(self, client):
        c, mock_svc = client
        mock_svc.get_config.return_value = MySQLConfigResponse(
            id=1, name="test", host="localhost", port=3306,
            username="root", database_name="db", charset="utf8mb4",
            description=None, is_active=True,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        resp = c.get("/api/mysql-configs/1")
        assert resp.status_code == 200

    def test_not_found(self, client):
        c, mock_svc = client
        mock_svc.get_config.return_value = None
        resp = c.get("/api/mysql-configs/999")
        assert resp.status_code == 404


class TestUpdateMySQLConfig:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.update_config.return_value = MySQLConfigResponse(
            id=1, name="updated", host="localhost", port=3306,
            username="root", database_name="db", charset="utf8mb4",
            description=None, is_active=True,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        resp = c.put("/api/mysql-configs/1", json={"name": "updated"})
        assert resp.status_code == 200

    def test_not_found(self, client):
        c, mock_svc = client
        mock_svc.update_config.return_value = None
        resp = c.put("/api/mysql-configs/999", json={"name": "updated"})
        assert resp.status_code == 404


class TestDeleteMySQLConfig:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.delete_config.return_value = True
        resp = c.delete("/api/mysql-configs/1")
        assert resp.status_code == 200


class TestTestMySQLConnection:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.test_connection.return_value = {"success": True, "message": "OK"}
        resp = c.post("/api/mysql-configs/1/test")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
