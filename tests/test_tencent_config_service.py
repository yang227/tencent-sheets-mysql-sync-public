"""
Test suite for Tencent API config service
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.models.config_models import (
    TencentApiConfigCreate, TencentApiConfigUpdate,
    TencentApiConfigResponse, TestStatus, TencentApiConfigTestResult
)
from app.services.tencent_config_service import TencentApiConfigService


@pytest.fixture
def mock_db():
    """Create a mock database service"""
    db = MagicMock()
    db.execute.return_value = []
    return db


@pytest.fixture
def service(mock_db):
    """Create TencentApiConfigService instance with mock db"""
    with patch.object(TencentApiConfigService, '_ensure_table_exists', return_value=None):
        s = TencentApiConfigService(mock_db)
    return s


@pytest.fixture
def sample_tencent_config_create():
    """Sample TencentApiConfigCreate object"""
    return TencentApiConfigCreate(
        name="test-tencent-api",
        app_id="wx1234567890abcdef",
        open_id="user_open_id_123",
        access_token="test_access_token_123",
        description="Test Tencent API config",
        is_active=True,
        token_expires_at=datetime(2026, 12, 31, 23, 59, 59)
    )


@pytest.fixture
def sample_tencent_config_response():
    """Sample TencentApiConfigResponse object"""
    return TencentApiConfigResponse(
        id=1,
        name="test-tencent-api",
        app_id="wx1234567890abcdef",
        open_id="user_open_id_123",
        description="Test Tencent API config",
        is_active=True,
        created_at=datetime(2026, 4, 30, 12, 0, 0),
        updated_at=datetime(2026, 4, 30, 12, 0, 0),
        last_tested_at=None,
        test_status=TestStatus.UNTESTED,
        test_message=None,
        token_expires_at=datetime(2026, 12, 31, 23, 59, 59)
    )


class TestTencentConfigServiceInit:
    """Test TencentApiConfigService initialization"""

    def test_init(self, mock_db):
        """Test service initialization"""
        with patch.object(TencentApiConfigService, '_ensure_table_exists') as mock_ensure:
            service = TencentApiConfigService(mock_db)
            assert service.db == mock_db
            mock_ensure.assert_called_once()


class TestCreateTencentConfig:
    """Test create_config method"""

    @patch('app.services.tencent_config_service.encrypt_password')
    def test_create_config_success(self, mock_encrypt, service, mock_db, sample_tencent_config_create, sample_tencent_config_response):
        """Test successful config creation"""
        mock_encrypt.return_value = "encrypted_token_123"
        mock_db.execute.return_value = None
        mock_db.execute.side_effect = [
            None,  # INSERT
            [{"name": "test-tencent-api", "id": 1}],  # SELECT for get_config_by_name
        ]

        with patch.object(service, 'get_config_by_name') as mock_get:
            mock_get.return_value = sample_tencent_config_response
            result = service.create_config(sample_tencent_config_create)

            assert result.name == "test-tencent-api"
            mock_encrypt.assert_called_once_with("test_access_token_123")
            mock_db.execute.assert_called()

    @patch('app.services.tencent_config_service.encrypt_password')
    def test_create_config_duplicate_name(self, mock_encrypt, service, mock_db, sample_tencent_config_create):
        """Test create config with duplicate name"""
        mock_encrypt.return_value = "encrypted_token_123"
        mock_db.execute.side_effect = Exception("Duplicate entry 'test-tencent-api' for key 'name'")

        with pytest.raises(Exception):
            service.create_config(sample_tencent_config_create)


class TestGetTencentConfig:
    """Test get_config method"""

    def test_get_config_found(self, service, mock_db, sample_tencent_config_response):
        """Test get existing config"""
        row = {
            "id": 1,
            "name": "test-tencent-api",
            "app_id": "wx1234567890abcdef",
            "open_id": "user_open_id_123",
            "access_token_encrypted": "encrypted",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime(2026, 4, 30),
            "updated_at": datetime(2026, 4, 30),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": datetime(2026, 12, 31)
        }
        mock_db.execute.return_value = [row]

        with patch.object(service, '_row_to_response') as mock_convert:
            mock_convert.return_value = sample_tencent_config_response
            result = service.get_config(1)

            assert result is not None
            mock_db.execute.assert_called_once()

    def test_get_config_not_found(self, service, mock_db):
        """Test get non-existent config"""
        mock_db.execute.return_value = []
        result = service.get_config(999)
        assert result is None


class TestListTencentConfigs:
    """Test list_configs method"""

    def test_list_configs(self, service, mock_db):
        """Test listing configs"""
        rows = [
            {"id": 1, "name": "config1", "app_id": "app1"},
            {"id": 2, "name": "config2", "app_id": "app2"},
        ]
        mock_db.execute.return_value = rows

        with patch.object(service, '_row_to_response') as mock_convert:
            mock_convert.side_effect = [
                TencentApiConfigResponse(
                    id=1, name="config1", app_id="app1", open_id="open1",
                    description=None, is_active=True,
                    created_at=datetime(2026, 4, 30),
                    updated_at=datetime(2026, 4, 30)
                ),
                TencentApiConfigResponse(
                    id=2, name="config2", app_id="app2", open_id="open2",
                    description=None, is_active=True,
                    created_at=datetime(2026, 4, 30),
                    updated_at=datetime(2026, 4, 30)
                ),
            ]
            results = service.list_configs()

            assert len(results) == 2
            assert results[0].name == "config1"
            assert results[1].name == "config2"


class TestUpdateTencentConfig:
    """Test update_config method"""

    def test_update_config_success(self, service, mock_db):
        """Test successful config update"""
        update_data = TencentApiConfigUpdate(name="updated-tencent-name", app_id="new_app_id")

        mock_db.execute.return_value = None
        mock_db.execute.side_effect = [
            None,  # UPDATE
            [{"id": 1}],  # SELECT
        ]

        with patch.object(service, 'get_config') as mock_get:
            mock_get.return_value = TencentApiConfigResponse(
                id=1, name="updated-tencent-name", app_id="new_app_id",
                open_id="open1", description=None, is_active=True,
                created_at=datetime(2026, 4, 30),
                updated_at=datetime(2026, 4, 30)
            )
            result = service.update_config(1, update_data)

            assert result.name == "updated-tencent-name"
            assert result.app_id == "new_app_id"

    def test_update_config_no_fields(self, service):
        """Test update with no fields"""
        update_data = TencentApiConfigUpdate()

        with pytest.raises(Exception) as exc_info:
            service.update_config(1, update_data)

        assert "没有需要更新的字段" in str(exc_info.value)

    @patch('app.services.tencent_config_service.encrypt_password')
    def test_update_config_with_token(self, mock_encrypt, service, mock_db):
        """Test update config with access token change"""
        mock_encrypt.return_value = "new_encrypted_token"
        update_data = TencentApiConfigUpdate(access_token="NewToken456!")

        mock_db.execute.return_value = None
        mock_db.execute.side_effect = [
            None,  # UPDATE
            [{"id": 1}],  # SELECT
        ]

        with patch.object(service, 'get_config') as mock_get:
            mock_get.return_value = TencentApiConfigResponse(
                id=1, name="test", app_id="app1", open_id="open1",
                description=None, is_active=True,
                created_at=datetime(2026, 4, 30),
                updated_at=datetime(2026, 4, 30)
            )
            result = service.update_config(1, update_data)

            mock_encrypt.assert_called_once_with("NewToken456!")


class TestDeleteTencentConfig:
    """Test delete_config method"""

    def test_delete_config_success(self, service, mock_db):
        """Test successful delete"""
        mock_db.execute.return_value = None

        result = service.delete_config(1)

        assert result is True
        mock_db.execute.assert_called_once()


class TestRuntimeBuilder:
    @patch("app.services.tencent_config_service.decrypt_password")
    def test_build_tencent_api(self, mock_decrypt, service, mock_db):
        mock_decrypt.return_value = "plain_token"
        mock_db.execute.return_value = [{
            "id": 1,
            "app_id": "app_123",
            "open_id": "open_456",
            "access_token_encrypted": "encrypted",
        }]

        api = service.build_tencent_api(1)

        assert api.app_id == "app_123"
        assert api.open_id == "open_456"
        assert api.access_token == "plain_token"


class TestRowToResponseTencent:
    """Test _row_to_response method"""

    def test_row_to_response(self, service):
        """Test converting row to response model"""
        row = {
            "id": 1,
            "name": "test-tencent-api",
            "app_id": "wx1234567890abcdef",
            "open_id": "user_open_id_123",
            "access_token_encrypted": "encrypted",
            "description": "Test config",
            "is_active": 1,
            "created_at": datetime(2026, 4, 30, 12, 0, 0),
            "updated_at": datetime(2026, 4, 30, 12, 0, 0),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": datetime(2026, 12, 31, 23, 59, 59)
        }

        result = service._row_to_response(row)

        assert isinstance(result, TencentApiConfigResponse)
        assert result.id == 1
        assert result.name == "test-tencent-api"
        assert result.is_active is True
        assert result.test_status == TestStatus.UNTESTED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
