"""
Test suite for MySQL config service
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime
from app.models.config_models import (
    MySQLConfigCreate, MySQLConfigUpdate, 
    MySQLConfigResponse, TestStatus, MySQLConfigTestResult
)
from app.services.mysql_config_service import MySQLConfigService


@pytest.fixture
def mock_db():
    """Create a mock database service"""
    db = MagicMock()
    db.execute.return_value = []
    return db


@pytest.fixture
def service(mock_db):
    """Create MySQLConfigService instance with mock db"""
    with patch.object(MySQLConfigService, '_ensure_table_exists', return_value=None):
        s = MySQLConfigService(mock_db)
    return s


@pytest.fixture
def sample_config_create():
    """Sample MySQLConfigCreate object"""
    return MySQLConfigCreate(
        name="test-mysql",
        host="localhost",
        port=3306,
        username="root",
        password="TestPass123!",
        database_name="test_db",
        charset="utf8mb4",
        description="Test MySQL config",
        is_active=True
    )


@pytest.fixture
def sample_config_response():
    """Sample MySQLConfigResponse object"""
    return MySQLConfigResponse(
        id=1,
        name="test-mysql",
        host="localhost",
        port=3306,
        username="root",
        database_name="test_db",
        charset="utf8mb4",
        description="Test MySQL config",
        is_active=True,
        created_at=datetime(2026, 4, 30, 12, 0, 0),
        updated_at=datetime(2026, 4, 30, 12, 0, 0),
        last_tested_at=None,
        test_status=TestStatus.UNTESTED,
        test_message=None
    )


class TestMySQLConfigServiceInit:
    """Test MySQLConfigService initialization"""

    def test_init(self, mock_db):
        """Test service initialization"""
        with patch.object(MySQLConfigService, '_ensure_table_exists') as mock_ensure:
            service = MySQLConfigService(mock_db)
            assert service.db == mock_db
            mock_ensure.assert_called_once()


class TestCreateConfig:
    """Test create_config method"""

    @patch('app.services.mysql_config_service.encrypt_password')
    def test_create_config_success(self, mock_encrypt, service, mock_db, sample_config_create, sample_config_response):
        """Test successful config creation"""
        mock_encrypt.return_value = "encrypted_password_123"
        mock_db.execute.return_value = None
        mock_db.execute.side_effect = [
            None,  # INSERT
            [{"name": "test-mysql", "id": 1}],  # SELECT for get_config_by_name
        ]

        with patch.object(service, 'get_config_by_name') as mock_get:
            mock_get.return_value = sample_config_response
            result = service.create_config(sample_config_create)

            assert result.name == "test-mysql"
            mock_encrypt.assert_called_once_with("TestPass123!")
            mock_db.execute.assert_called()

    @patch('app.services.mysql_config_service.encrypt_password')
    def test_create_config_duplicate_name(self, mock_encrypt, service, mock_db, sample_config_create):
        """Test create config with duplicate name"""
        mock_encrypt.return_value = "encrypted_password_123"
        mock_db.execute.side_effect = Exception("Duplicate entry 'test-mysql' for key 'name'")

        with pytest.raises(Exception):
            service.create_config(sample_config_create)


class TestGetConfig:
    """Test get_config method"""

    def test_get_config_found(self, service, mock_db, sample_config_response):
        """Test get existing config"""
        row = {
            "id": 1,
            "name": "test-mysql",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password_encrypted": "encrypted",
            "database_name": "test_db",
            "charset": "utf8mb4",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime(2026, 4, 30),
            "updated_at": datetime(2026, 4, 30),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None
        }
        mock_db.execute.return_value = [row]

        with patch.object(service, '_row_to_response') as mock_convert:
            mock_convert.return_value = sample_config_response
            result = service.get_config(1)

            assert result is not None
            mock_db.execute.assert_called_once()

    def test_get_config_not_found(self, service, mock_db):
        """Test get non-existent config"""
        mock_db.execute.return_value = []
        result = service.get_config(999)
        assert result is None


class TestListConfigs:
    """Test list_configs method"""

    def test_list_configs(self, service, mock_db):
        """Test listing configs"""
        rows = [
            {"id": 1, "name": "config1", "host": "localhost"},
            {"id": 2, "name": "config2", "host": "192.168.1.1"},
        ]
        mock_db.execute.return_value = rows

        with patch.object(service, '_row_to_response') as mock_convert:
            mock_convert.side_effect = [
                MySQLConfigResponse(
                    id=1, name="config1", host="localhost", port=3306,
                    username="root", database_name="db1", charset="utf8mb4",
                    description=None, is_active=True,
                    created_at=datetime(2026, 4, 30),
                    updated_at=datetime(2026, 4, 30)
                ),
                MySQLConfigResponse(
                    id=2, name="config2", host="192.168.1.1", port=3306,
                    username="root", database_name="db2", charset="utf8mb4",
                    description=None, is_active=True,
                    created_at=datetime(2026, 4, 30),
                    updated_at=datetime(2026, 4, 30)
                ),
            ]
            results = service.list_configs()

            assert len(results) == 2
            assert results[0].name == "config1"
            assert results[1].name == "config2"


class TestUpdateConfig:
    """Test update_config method"""

    def test_update_config_success(self, service, mock_db):
        """Test successful config update"""
        update_data = MySQLConfigUpdate(name="updated-name", port=3307)

        mock_db.execute.return_value = None
        mock_db.execute.side_effect = [
            None,  # UPDATE
            [{"id": 1}],  # SELECT for get_config
        ]

        with patch.object(service, 'get_config') as mock_get:
            mock_get.return_value = MySQLConfigResponse(
                id=1, name="updated-name", host="localhost", port=3307,
                username="root", database_name="test_db", charset="utf8mb4",
                description=None, is_active=True,
                created_at=datetime(2026, 4, 30),
                updated_at=datetime(2026, 4, 30)
            )
            result = service.update_config(1, update_data)

            assert result.name == "updated-name"
            assert result.port == 3307

    def test_update_config_no_fields(self, service):
        """Test update with no fields"""
        update_data = MySQLConfigUpdate()

        with pytest.raises(Exception) as exc_info:
            service.update_config(1, update_data)

        assert "没有需要更新的字段" in str(exc_info.value)

    @patch('app.services.mysql_config_service.encrypt_password')
    def test_update_config_with_password(self, mock_encrypt, service, mock_db):
        """Test update config with password change"""
        mock_encrypt.return_value = "new_encrypted_password"
        update_data = MySQLConfigUpdate(password="NewPass456!")

        mock_db.execute.return_value = None
        mock_db.execute.side_effect = [
            None,  # UPDATE
            [{"id": 1}],  # SELECT
        ]

        with patch.object(service, 'get_config') as mock_get:
            mock_get.return_value = MySQLConfigResponse(
                id=1, name="test", host="localhost", port=3306,
                username="root", database_name="test_db", charset="utf8mb4",
                description=None, is_active=True,
                created_at=datetime(2026, 4, 30),
                updated_at=datetime(2026, 4, 30)
            )
            result = service.update_config(1, update_data)

            mock_encrypt.assert_called_once_with("NewPass456!")


class TestDeleteConfig:
    """Test delete_config method"""

    def test_delete_config_success(self, service, mock_db):
        """Test successful delete"""
        mock_db.execute.return_value = None

        result = service.delete_config(1)

        assert result is True
        mock_db.execute.assert_called_once()


class TestRuntimeBuilder:
    @patch("app.services.mysql_config_service.decrypt_password")
    def test_build_mysql_service(self, mock_decrypt, service, mock_db):
        mock_decrypt.return_value = "plain_password"
        mock_db.execute.return_value = [{
            "id": 1,
            "host": "127.0.0.1",
            "port": 3306,
            "username": "root",
            "password_encrypted": "encrypted",
            "database_name": "biz_db",
        }]

        runtime = service.build_mysql_service(1)

        assert runtime.host == "127.0.0.1"
        assert runtime.user == "root"
        assert runtime.password == "plain_password"
        assert runtime.database == "biz_db"


class TestRowToResponse:
    """Test _row_to_response method"""

    def test_row_to_response(self, service):
        """Test converting row to response model"""
        row = {
            "id": 1,
            "name": "test-mysql",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password_encrypted": "encrypted",
            "database_name": "test_db",
            "charset": "utf8mb4",
            "description": "Test config",
            "is_active": 1,
            "created_at": datetime(2026, 4, 30, 12, 0, 0),
            "updated_at": datetime(2026, 4, 30, 12, 0, 0),
            "last_tested_at": datetime(2026, 4, 30, 13, 0, 0),
            "test_status": "success",
            "test_message": "Connection successful"
        }

        result = service._row_to_response(row)

        assert isinstance(result, MySQLConfigResponse)
        assert result.id == 1
        assert result.name == "test-mysql"
        assert result.is_active is True
        assert result.test_status == TestStatus.SUCCESS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
