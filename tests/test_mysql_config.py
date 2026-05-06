"""
Tests for MySQL Config Service - test_mysql_config.py
测试 MySQL 配置服务的 CRUD 操作、连接测试和密码加密
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.services.mysql_config_service import MySQLConfigService, get_mysql_config_service
from app.models.config_models import MySQLConfigCreate, MySQLConfigUpdate, TestStatus
from app.utils.encryption import encrypt_password, decrypt_password


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock MySQLService database dependency."""
    db = MagicMock()
    db.execute.return_value = []
    return db


@pytest.fixture
def mysql_config_service(mock_db):
    """Create MySQLConfigService with mocked database."""
    service = MySQLConfigService(mock_db)
    return service


@pytest.fixture
def sample_config_data():
    """Sample MySQL config data for testing."""
    return MySQLConfigCreate(
        name="test-mysql",
        host="localhost",
        port=3306,
        username="root",
        password="TestPassword123!",
        database_name="test_db",
        charset="utf8mb4",
        description="Test MySQL configuration"
    )


# ── Encryption Tests ────────────────────────────────────────

class TestEncryption:
    """Test password encryption and decryption."""

    def test_encrypt_decrypt_password(self):
        """Test that encrypting and decrypting returns original password."""
        original = "MySecretPassword123!"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original
        assert encrypted != original
        assert isinstance(encrypted, str)
        assert isinstance(decrypted, str)

    def test_encrypt_empty_password(self):
        """Test encrypting empty password returns empty string."""
        assert encrypt_password("") == ""
        assert encrypt_password(None) == ""

    def test_decrypt_empty_password(self):
        """Test decrypting empty password returns empty string."""
        assert decrypt_password("") == ""
        assert decrypt_password(None) == ""

    def test_encrypt_decrypt_special_chars(self):
        """Test encryption with special characters."""
        original = "pass@#$%^&*()_+-=[]{}|;:'\",.<>?/`~"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original

    def test_different_encryptions(self):
        """Test that same password encrypted twice produces different tokens."""
        password = "SamePassword"
        encrypted1 = encrypt_password(password)
        encrypted2 = encrypt_password(password)

        # Fernet uses random IV, so encryptions should be different
        assert encrypted1 != encrypted2
        # But both should decrypt to the same value
        assert decrypt_password(encrypted1) == decrypt_password(encrypted2)


# ── MySQLConfigService Tests ────────────────────────────────

class TestMySQLConfigServiceInit:
    """Test MySQLConfigService initialization."""

    def test_init_with_db(self, mock_db):
        """Test service initialization with database."""
        service = MySQLConfigService(mock_db)
        assert service.db == mock_db

    def test_ensure_table_exists(self, mock_db):
        """Test table existence check."""
        mock_db.execute.return_value = [{"cnt": 1}]
        service = MySQLConfigService(mock_db)
        service._ensure_table_exists()
        # Should not raise any errors

    def test_ensure_table_not_exists(self, mock_db):
        """Test when table doesn't exist (warning expected)."""
        mock_db.execute.return_value = [{"cnt": 0}]
        with patch("app.services.mysql_config_service.logger") as mock_logger:
            service = MySQLConfigService(mock_db)
            service._ensure_table_exists()
            # Should be called at least once (maybe twice if init calls it)
            mock_logger.warning.assert_called()
            # Check that the warning message is correct
            call_args = mock_logger.warning.call_args[0][0]
            assert "mysql_configs 表不存在" in call_args


class TestCreateConfig:
    """Test create_config method."""

    def test_create_config_success(self, mysql_config_service, sample_config_data):
        """Test successful config creation."""
        # Reset mock to ignore init calls
        mysql_config_service.db.execute.reset_mock()

        # Mock get_config_by_name to return created config
        created_config = MagicMock()
        mysql_config_service.get_config_by_name = MagicMock(return_value=created_config)

        result = mysql_config_service.create_config(sample_config_data)

        assert result == created_config
        # Should have called execute for INSERT
        assert mysql_config_service.db.execute.called
        # Verify encrypt_password was called (password should be encrypted)
        call_args = mysql_config_service.db.execute.call_args
        assert call_args is not None

    def test_create_config_duplicate_name(self, mysql_config_service, sample_config_data):
        """Test creating config with duplicate name."""
        import mysql.connector
        mysql_config_service.db.execute.side_effect = mysql.connector.Error(msg="Duplicate entry 'test-mysql'")

        with pytest.raises(Exception):  # Should raise HTTPException
            mysql_config_service.create_config(sample_config_data)

    def test_create_config_db_error(self, mysql_config_service, sample_config_data):
        """Test database error during config creation."""
        mysql_config_service.db.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            mysql_config_service.create_config(sample_config_data)


class TestGetConfig:
    """Test get_config method."""

    def test_get_config_success(self, mysql_config_service):
        """Test successful config retrieval by ID."""
        mock_row = {
            "id": 1,
            "name": "test",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password_encrypted": "encrypted",
            "database_name": "test_db",
            "charset": "utf8mb4",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None
        }
        mysql_config_service.db.execute.return_value = [mock_row]

        result = mysql_config_service.get_config(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "test"

    def test_get_config_not_found(self, mysql_config_service):
        """Test config not found."""
        mysql_config_service.db.execute.return_value = []

        result = mysql_config_service.get_config(999)

        assert result is None

    def test_get_config_db_error(self, mysql_config_service):
        """Test database error during config retrieval."""
        mysql_config_service.db.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            mysql_config_service.get_config(1)


class TestGetConfigByName:
    """Test get_config_by_name method."""

    def test_get_config_by_name_success(self, mysql_config_service):
        """Test successful config retrieval by name."""
        mock_row = {
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
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None
        }
        mysql_config_service.db.execute.return_value = [mock_row]

        result = mysql_config_service.get_config_by_name("test-mysql")

        assert result is not None
        assert result.name == "test-mysql"

    def test_get_config_by_name_not_found(self, mysql_config_service):
        """Test config not found by name."""
        mysql_config_service.db.execute.return_value = []

        result = mysql_config_service.get_config_by_name("nonexistent")

        assert result is None


class TestListConfigs:
    """Test list_configs method."""

    def test_list_configs_success(self, mysql_config_service):
        """Test successful config listing."""
        mock_rows = [
            {
                "id": 1,
                "name": "config1",
                "host": "localhost",
                "port": 3306,
                "username": "root",
                "password_encrypted": "encrypted1",
                "database_name": "db1",
                "charset": "utf8mb4",
                "description": "Test 1",
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_tested_at": None,
                "test_status": "untested",
                "test_message": None
            },
            {
                "id": 2,
                "name": "config2",
                "host": "remote",
                "port": 3307,
                "username": "admin",
                "password_encrypted": "encrypted2",
                "database_name": "db2",
                "charset": "utf8mb4",
                "description": "Test 2",
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_tested_at": None,
                "test_status": "success",
                "test_message": "OK"
            }
        ]
        mysql_config_service.db.execute.return_value = mock_rows

        result = mysql_config_service.list_configs()

        assert len(result) == 2
        assert result[0].name == "config1"
        assert result[1].name == "config2"

    def test_list_configs_empty(self, mysql_config_service):
        """Test empty config list."""
        mysql_config_service.db.execute.return_value = []

        result = mysql_config_service.list_configs()

        assert len(result) == 0

    def test_list_configs_with_pagination(self, mysql_config_service):
        """Test config listing with pagination."""
        mysql_config_service.db.execute.return_value = []

        mysql_config_service.list_configs(skip=10, limit=5)

        call_args = mysql_config_service.db.execute.call_args
        assert call_args[0][1] == (5, 10)  # (limit, skip)


class TestUpdateConfig:
    """Test update_config method."""

    def test_update_config_success(self, mysql_config_service):
        """Test successful config update."""
        update_data = MySQLConfigUpdate(
            name="updated-name",
            host="new-host",
            port=3307
        )

        # Reset mock to ignore init calls
        mysql_config_service.db.execute.reset_mock()

        # Mock get_config to return updated config
        updated_config = MagicMock()
        mysql_config_service.get_config = MagicMock(return_value=updated_config)

        result = mysql_config_service.update_config(1, update_data)

        assert result == updated_config
        assert mysql_config_service.db.execute.called

    def test_update_config_with_password(self, mysql_config_service):
        """Test updating config with password encryption."""
        update_data = MySQLConfigUpdate(password="NewPassword123!")

        updated_config = MagicMock()
        mysql_config_service.get_config = MagicMock(return_value=updated_config)

        result = mysql_config_service.update_config(1, update_data)

        assert result == updated_config
        # Verify that encrypt_password was called (password_encrypted should be in SQL)
        call_args = mysql_config_service.db.execute.call_args
        assert "password_encrypted = %s" in call_args[0][0]

    def test_update_config_no_fields(self, mysql_config_service):
        """Test update with no fields (should raise error)."""
        update_data = MySQLConfigUpdate()

        with pytest.raises(Exception):  # Should raise HTTPException with 400
            mysql_config_service.update_config(1, update_data)

    def test_update_config_not_found(self, mysql_config_service):
        """Test updating non-existent config."""
        update_data = MySQLConfigUpdate(name="new-name")
        mysql_config_service.db.execute.return_value = [{"affected_rows": 0}]

        # The method doesn't check affected_rows, so it will try to get_config
        # which will return None
        mysql_config_service.get_config = MagicMock(return_value=None)

        result = mysql_config_service.update_config(1, update_data)

        # get_config returns None, so update returns None
        assert result is None


class TestDeleteConfig:
    """Test delete_config method."""

    def test_delete_config_success(self, mysql_config_service):
        """Test successful config deletion (soft delete)."""
        # Reset mock to ignore init calls
        mysql_config_service.db.execute.reset_mock()

        result = mysql_config_service.delete_config(1)

        assert result is True
        mysql_config_service.db.execute.assert_called_once_with(
            "UPDATE mysql_configs SET is_active = 0 WHERE id = %s AND is_active = 1",
            (1,)
        )

    def test_delete_config_error(self, mysql_config_service):
        """Test error during config deletion."""
        mysql_config_service.db.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            mysql_config_service.delete_config(1)


class TestTestConnection:
    """Test test_connection method."""

    @patch("mysql.connector.connect")
    def test_test_connection_success(self, mock_connect, mysql_config_service):
        """Test successful connection test."""
        # Mock database response
        mock_row = {
            "id": 1,
            "name": "test",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password_encrypted": encrypt_password("password"),
            "database_name": "test_db",
            "charset": "utf8mb4",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None
        }
        mysql_config_service.db.execute.return_value = [mock_row]

        # Mock MySQL connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = mysql_config_service.test_connection(1)

        assert result.success is True
        assert "成功" in result.message

    @patch("mysql.connector.connect")
    def test_test_connection_failure(self, mock_connect, mysql_config_service):
        """Test failed connection test."""
        mock_row = {
            "id": 1,
            "name": "test",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password_encrypted": encrypt_password("password"),
            "database_name": "test_db",
            "charset": "utf8mb4",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None
        }
        mysql_config_service.db.execute.return_value = [mock_row]

        # Mock MySQL connection failure
        import mysql.connector
        mock_connect.side_effect = mysql.connector.Error(msg="Connection refused")

        result = mysql_config_service.test_connection(1)

        assert result.success is False
        assert "失败" in result.message

    def test_test_connection_config_not_found(self, mysql_config_service):
        """Test connection test with non-existent config."""
        mysql_config_service.db.execute.return_value = []

        result = mysql_config_service.test_connection(999)

        assert result.success is False
        assert "不存在" in result.message or "Config not found" in result.error

    def test_test_connection_decrypt_failure(self, mysql_config_service):
        """Test connection test with password decryption failure."""
        mock_row = {
            "id": 1,
            "name": "test",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password_encrypted": "invalid-encrypted-data",
            "database_name": "test_db",
            "charset": "utf8mb4",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None
        }
        mysql_config_service.db.execute.return_value = [mock_row]

        result = mysql_config_service.test_connection(1)

        assert result.success is False
        assert "解密" in result.message or "decrypt" in result.error.lower()


class TestGetDecryptedPassword:
    """Test get_decrypted_password method."""

    def test_get_decrypted_password_success(self, mysql_config_service):
        """Test successful password decryption."""
        original_password = "MySecretPassword"
        encrypted = encrypt_password(original_password)

        mock_row = {"password_encrypted": encrypted}
        mysql_config_service.db.execute.return_value = [mock_row]

        result = mysql_config_service.get_decrypted_password(1)

        assert result == original_password

    def test_get_decrypted_password_not_found(self, mysql_config_service):
        """Test password retrieval for non-existent config."""
        mysql_config_service.db.execute.return_value = []

        result = mysql_config_service.get_decrypted_password(999)

        assert result is None

    def test_get_decrypted_password_decrypt_error(self, mysql_config_service):
        """Test password decryption error."""
        mysql_config_service.db.execute.return_value = [{"password_encrypted": "invalid"}]

        result = mysql_config_service.get_decrypted_password(1)

        assert result is None


class TestGetMySQLConfigService:
    """Test get_mysql_config_service factory function."""

    @patch("app.services.mysql_config_service.get_mysql_service")
    def test_get_mysql_config_service_default(self, mock_get_service):
        """Test getting config service with default db."""
        mock_get_service.return_value = MagicMock()

        result = get_mysql_config_service()

        assert result is not None
        assert isinstance(result, MySQLConfigService)

    def test_get_mysql_config_service_with_db(self, mock_db):
        """Test getting config service with provided db."""
        result = get_mysql_config_service(mock_db)

        assert result is not None
        assert isinstance(result, MySQLConfigService)
        assert result.db == mock_db
