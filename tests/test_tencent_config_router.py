"""Tests for tencent_config_router.py"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.models.config_models import TencentApiConfigResponse, TestStatus

# Create a minimal FastAPI app for testing
app = FastAPI()
from app.routers.tencent_config_router import router as tencent_router
app.include_router(tencent_router)


@pytest.fixture
def client():
    """Create test client with mocked service"""
    with patch('app.routers.tencent_config_router.TencentApiConfigService') as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        
        # Also mock the get_service dependency
        from app.routers.tencent_config_router import get_service
        app.dependency_overrides[get_service] = lambda: mock_instance
        
        client = TestClient(app)
        yield client, mock_instance
        app.dependency_overrides.clear()


class TestListTencentConfigs:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.list_configs.return_value = [
            TencentApiConfigResponse(
                id=1, name="test", app_id="app1", open_id="open1",
                description=None, is_active=True,
                created_at=datetime.now(), updated_at=datetime.now()
            )
        ]
        resp = c.get("/api/tencent-configs")
        assert resp.status_code == 200

    def test_empty(self, client):
        c, mock_svc = client
        mock_svc.list_configs.return_value = []
        resp = c.get("/api/tencent-configs")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateTencentConfig:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.create_config.return_value = TencentApiConfigResponse(
            id=1, name="new", app_id="app1", open_id="open1",
            description=None, is_active=True,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        resp = c.post("/api/tencent-configs", json={
            "name": "new", "app_id": "app1", "open_id": "open1",
            "access_token": "token"
        })
        assert resp.status_code == 200


class TestGetTencentConfig:
    def test_found(self, client):
        c, mock_svc = client
        mock_svc.get_config.return_value = TencentApiConfigResponse(
            id=1, name="test", app_id="app1", open_id="open1",
            description=None, is_active=True,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        resp = c.get("/api/tencent-configs/1")
        assert resp.status_code == 200

    def test_not_found(self, client):
        c, mock_svc = client
        mock_svc.get_config.return_value = None
        resp = c.get("/api/tencent-configs/999")
        assert resp.status_code == 404


class TestUpdateTencentConfig:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.update_config.return_value = TencentApiConfigResponse(
            id=1, name="updated", app_id="app1", open_id="open1",
            description=None, is_active=True,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        resp = c.put("/api/tencent-configs/1", json={"name": "updated"})
        assert resp.status_code == 200


class TestDeleteTencentConfig:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.delete_config.return_value = True
        resp = c.delete("/api/tencent-configs/1")
        assert resp.status_code == 200


class TestTestTencentConnection:
    def test_success(self, client):
        c, mock_svc = client
        mock_svc.test_connection.return_value = {"success": True, "message": "OK"}
        resp = c.post("/api/tencent-configs/1/test")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
