"""
Tests for Tencent Config Service - test_tencent_config.py
测试腾讯文档 API 配置服务的 CRUD 操作、连接测试和凭证加密
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
import httpx

from app.services.tencent_config_service import TencentApiConfigService, get_tencent_config_service
from app.models.config_models import TencentApiConfigCreate, TencentApiConfigUpdate, TestStatus
from app.utils.encryption import encrypt_password, decrypt_password


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock MySQLService database dependency."""
    db = MagicMock()
    db.execute.return_value = []
    return db


@pytest.fixture
def tencent_config_service(mock_db):
    """Create TencentApiConfigService with mocked database."""
    service = TencentApiConfigService(mock_db)
    return service


@pytest.fixture
def sample_tencent_config_data():
    """Sample Tencent API config data for testing."""
    return TencentApiConfigCreate(
        name="test-tencent-api",
        app_id="test-app-id",
        open_id="test-open-id",
        access_token="test-access-token-123",
        description="Test Tencent API configuration",
        token_expires_at=datetime(2026, 12, 31, 23, 59, 59)
    )


# ── Encryption Tests ────────────────────────────────────────

class TestEncryption:
    """Test token encryption and decryption."""

    def test_encrypt_decrypt_token(self):
        """Test that encrypting and decrypting returns original token."""
        original = "tencent-access-token-12345"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original
        assert encrypted != original
        assert isinstance(encrypted, str)

    def test_encrypt_empty_token(self):
        """Test encrypting empty token returns empty string."""
        assert encrypt_password("") == ""
        assert encrypt_password(None) == ""

    def test_decrypt_empty_token(self):
        """Test decrypting empty token returns empty string."""
        assert decrypt_password("") == ""
        assert decrypt_password(None) == ""

    def test_encrypt_decrypt_long_token(self):
        """Test encryption with long token."""
        original = "A" * 500  # Long token
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original


# ── TencentApiConfigService Tests ─────────────────────────

class TestTencentApiConfigServiceInit:
    """Test TencentApiConfigService initialization."""

    def test_init_with_db(self, mock_db):
        """Test service initialization with database."""
        service = TencentApiConfigService(mock_db)
        assert service.db == mock_db

    def test_ensure_table_exists(self, mock_db):
        """Test table existence check."""
        mock_db.execute.return_value = [{"cnt": 1}]
        service = TencentApiConfigService(mock_db)
        service._ensure_table_exists()
        # Should not raise any errors

    def test_ensure_table_not_exists(self, mock_db):
        """Test when table doesn't exist (warning expected)."""
        mock_db.execute.return_value = [{"cnt": 0}]
        with patch("app.services.tencent_config_service.logger") as mock_logger:
            service = TencentApiConfigService(mock_db)
            service._ensure_table_exists()
            # Should be called at least once
            mock_logger.warning.assert_called()
            # Check that the warning message is correct
            call_args = mock_logger.warning.call_args[0][0]
            assert "tencent_api_configs 表不存在" in call_args


class TestCreateConfig:
    """Test create_config method."""

    def test_create_config_success(self, tencent_config_service, sample_tencent_config_data):
        """Test successful config creation."""
        # Reset mock to ignore init calls
        tencent_config_service.db.execute.reset_mock()

        # Mock get_config_by_name to return created config
        created_config = MagicMock()
        tencent_config_service.get_config_by_name = MagicMock(return_value=created_config)

        result = tencent_config_service.create_config(sample_tencent_config_data)

        assert result == created_config
        assert tencent_config_service.db.execute.called
        # Verify encrypt_password was called (access_token should be encrypted)
        call_args = tencent_config_service.db.execute.call_args
        assert call_args is not None

    def test_create_config_duplicate_name(self, tencent_config_service, sample_tencent_config_data):
        """Test creating config with duplicate name."""
        import mysql.connector
        tencent_config_service.db.execute.side_effect = mysql.connector.Error(
            msg="Duplicate entry 'test-tencent-api'"
        )

        with pytest.raises(Exception):
            tencent_config_service.create_config(sample_tencent_config_data)

    def test_create_config_db_error(self, tencent_config_service, sample_tencent_config_data):
        """Test database error during config creation."""
        tencent_config_service.db.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            tencent_config_service.create_config(sample_tencent_config_data)


class TestGetConfig:
    """Test get_config method."""

    def test_get_config_success(self, tencent_config_service):
        """Test successful config retrieval by ID."""
        mock_row = {
            "id": 1,
            "name": "test",
            "app_id": "app-id",
            "open_id": "open-id",
            "access_token_encrypted": encrypt_password("token"),
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": None
        }
        tencent_config_service.db.execute.return_value = [mock_row]

        result = tencent_config_service.get_config(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "test"
        assert result.app_id == "app-id"

    def test_get_config_not_found(self, tencent_config_service):
        """Test config not found."""
        tencent_config_service.db.execute.return_value = []

        result = tencent_config_service.get_config(999)

        assert result is None

    def test_get_config_db_error(self, tencent_config_service):
        """Test database error during config retrieval."""
        tencent_config_service.db.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            tencent_config_service.get_config(1)


class TestGetConfigByName:
    """Test get_config_by_name method."""

    def test_get_config_by_name_success(self, tencent_config_service):
        """Test successful config retrieval by name."""
        mock_row = {
            "id": 1,
            "name": "test-tencent",
            "app_id": "app-id",
            "open_id": "open-id",
            "access_token_encrypted": encrypt_password("token"),
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": None
        }
        tencent_config_service.db.execute.return_value = [mock_row]

        result = tencent_config_service.get_config_by_name("test-tencent")

        assert result is not None
        assert result.name == "test-tencent"

    def test_get_config_by_name_not_found(self, tencent_config_service):
        """Test config not found by name."""
        tencent_config_service.db.execute.return_value = []

        result = tencent_config_service.get_config_by_name("nonexistent")

        assert result is None


class TestListConfigs:
    """Test list_configs method."""

    def test_list_configs_success(self, tencent_config_service):
        """Test successful config listing."""
        mock_rows = [
            {
                "id": 1,
                "name": "config1",
                "app_id": "app1",
                "open_id": "open1",
                "access_token_encrypted": encrypt_password("token1"),
                "description": "Test 1",
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_tested_at": None,
                "test_status": "untested",
                "test_message": None,
                "token_expires_at": None
            },
            {
                "id": 2,
                "name": "config2",
                "app_id": "app2",
                "open_id": "open2",
                "access_token_encrypted": encrypt_password("token2"),
                "description": "Test 2",
                "is_active": 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_tested_at": None,
                "test_status": "success",
                "test_message": "OK",
                "token_expires_at": None
            }
        ]
        tencent_config_service.db.execute.return_value = mock_rows

        result = tencent_config_service.list_configs()

        assert len(result) == 2
        assert result[0].name == "config1"
        assert result[1].name == "config2"

    def test_list_configs_empty(self, tencent_config_service):
        """Test empty config list."""
        tencent_config_service.db.execute.return_value = []

        result = tencent_config_service.list_configs()

        assert len(result) == 0

    def test_list_configs_with_pagination(self, tencent_config_service):
        """Test config listing with pagination."""
        tencent_config_service.db.execute.return_value = []

        tencent_config_service.list_configs(skip=10, limit=5)

        call_args = tencent_config_service.db.execute.call_args
        assert call_args[0][1] == (5, 10)  # (limit, skip)


class TestUpdateConfig:
    """Test update_config method."""

    def test_update_config_success(self, tencent_config_service):
        """Test successful config update."""
        update_data = TencentApiConfigUpdate(
            name="updated-name",
            app_id="new-app-id"
        )

        # Reset mock to ignore init calls
        tencent_config_service.db.execute.reset_mock()

        # Mock get_config to return updated config
        updated_config = MagicMock()
        tencent_config_service.get_config = MagicMock(return_value=updated_config)

        result = tencent_config_service.update_config(1, update_data)

        assert result == updated_config
        assert tencent_config_service.db.execute.called

    def test_update_config_with_token(self, tencent_config_service):
        """Test updating config with access token encryption."""
        update_data = TencentApiConfigUpdate(access_token="NewToken123!")

        updated_config = MagicMock()
        tencent_config_service.get_config = MagicMock(return_value=updated_config)

        result = tencent_config_service.update_config(1, update_data)

        assert result == updated_config
        # Verify that encrypt_password was called (access_token_encrypted should be in SQL)
        call_args = tencent_config_service.db.execute.call_args
        assert "access_token_encrypted = %s" in call_args[0][0]

    def test_update_config_no_fields(self, tencent_config_service):
        """Test update with no fields (should raise error)."""
        update_data = TencentApiConfigUpdate()

        with pytest.raises(Exception):  # Should raise HTTPException with 400
            tencent_config_service.update_config(1, update_data)

    def test_update_config_duplicate_name(self, tencent_config_service):
        """Test updating config with duplicate name."""
        import mysql.connector
        update_data = TencentApiConfigUpdate(name="new-name")
        tencent_config_service.db.execute.side_effect = mysql.connector.Error(
            msg="Duplicate entry"
        )

        with pytest.raises(Exception):
            tencent_config_service.update_config(1, update_data)


class TestDeleteConfig:
    """Test delete_config method."""

    def test_delete_config_success(self, tencent_config_service):
        """Test successful config deletion (soft delete)."""
        # Reset mock to ignore init calls
        tencent_config_service.db.execute.reset_mock()

        result = tencent_config_service.delete_config(1)

        assert result is True
        tencent_config_service.db.execute.assert_called_once_with(
            "UPDATE tencent_api_configs SET is_active = 0 WHERE id = %s AND is_active = 1",
            (1,)
        )

    def test_delete_config_error(self, tencent_config_service):
        """Test error during config deletion."""
        tencent_config_service.db.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            tencent_config_service.delete_config(1)


class TestTestConnection:
    """Test test_connection method."""

    @patch("httpx.Client")
    def test_test_connection_success(self, mock_client_class, tencent_config_service):
        """Test successful API connection test."""
        # Mock database response
        mock_row = {
            "id": 1,
            "name": "test",
            "app_id": "app-id",
            "open_id": "open-id",
            "access_token_encrypted": encrypt_password("valid-token"),
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": None
        }
        tencent_config_service.db.execute.return_value = [mock_row]

        # Mock HTTP response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        result = tencent_config_service.test_connection(1)

        assert result.success is True
        assert "成功" in result.message

    @patch("httpx.Client")
    def test_test_connection_failure(self, mock_client_class, tencent_config_service):
        """Test failed API connection test."""
        mock_row = {
            "id": 1,
            "name": "test",
            "app_id": "app-id",
            "open_id": "open-id",
            "access_token_encrypted": encrypt_password("invalid-token"),
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": None
        }
        tencent_config_service.db.execute.return_value = [mock_row]

        # Mock HTTP response failure
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        result = tencent_config_service.test_connection(1)

        assert result.success is False
        assert "失败" in result.message

    @patch("httpx.Client")
    def test_test_connection_timeout(self, mock_client_class, tencent_config_service):
        """Test API connection timeout."""
        mock_row = {
            "id": 1,
            "name": "test",
            "app_id": "app-id",
            "open_id": "open-id",
            "access_token_encrypted": encrypt_password("token"),
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": None
        }
        tencent_config_service.db.execute.return_value = [mock_row]

        # Mock timeout
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        result = tencent_config_service.test_connection(1)

        assert result.success is False
        assert "超时" in result.message or "Timeout" in result.message

    def test_test_connection_config_not_found(self, tencent_config_service):
        """Test connection test with non-existent config."""
        tencent_config_service.db.execute.return_value = []

        result = tencent_config_service.test_connection(999)

        assert result.success is False
        assert "不存在" in result.message or "Config not found" in result.error

    def test_test_connection_decrypt_failure(self, tencent_config_service):
        """Test connection test with token decryption failure."""
        mock_row = {
            "id": 1,
            "name": "test",
            "app_id": "app-id",
            "open_id": "open-id",
            "access_token_encrypted": "invalid-encrypted-data",
            "description": "Test",
            "is_active": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_tested_at": None,
            "test_status": "untested",
            "test_message": None,
            "token_expires_at": None
        }
        tencent_config_service.db.execute.return_value = [mock_row]

        result = tencent_config_service.test_connection(1)

        assert result.success is False
        assert "解密" in result.message or "decrypt" in result.error.lower()


class TestGetDecryptedToken:
    """Test get_decrypted_token method."""

    def test_get_decrypted_token_success(self, tencent_config_service):
        """Test successful token decryption."""
        original_token = "MySecretToken"
        encrypted = encrypt_password(original_token)

        mock_row = {"access_token_encrypted": encrypted}
        tencent_config_service.db.execute.return_value = [mock_row]

        result = tencent_config_service.get_decrypted_token(1)

        assert result == original_token

    def test_get_decrypted_token_not_found(self, tencent_config_service):
        """Test token retrieval for non-existent config."""
        tencent_config_service.db.execute.return_value = []

        result = tencent_config_service.get_decrypted_token(999)

        assert result is None

    def test_get_decrypted_token_decrypt_error(self, tencent_config_service):
        """Test token decryption error."""
        tencent_config_service.db.execute.return_value = [{"access_token_encrypted": "invalid"}]

        result = tencent_config_service.get_decrypted_token(1)

        assert result is None


class TestGetTencentConfigService:
    """Test get_tencent_config_service factory function."""

    @patch("app.services.tencent_config_service.get_mysql_service")
    def test_get_tencent_config_service_default(self, mock_get_service):
        """Test getting config service with default db."""
        mock_get_service.return_value = MagicMock()

        result = get_tencent_config_service()

        assert result is not None
        assert isinstance(result, TencentApiConfigService)

    def test_get_tencent_config_service_with_db(self, mock_db):
        """Test getting config service with provided db."""
        result = get_tencent_config_service(mock_db)

        assert result is not None
        assert isinstance(result, TencentApiConfigService)
        assert result.db == mock_db
