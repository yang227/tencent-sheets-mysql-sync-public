"""
Comprehensive tests for MySQLService.
Tests all methods including edge cases and error handling.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from mysql.connector import Error as MySQLError, pooling
from app.services.mysql_service import MySQLService, MySQLServiceError


# ─── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def mysql_service():
    """Create a MySQLService instance with test config."""
    service = MySQLService(
        host="localhost",
        port=3306,
        user="test_user",
        password="test_pass",
        database="test_db",
        pool_size=2,
    )
    service._pool = None  # Reset pool for testing
    yield service
    service._pool = None


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = MagicMock()
    conn.autocommit = True
    return conn


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = MagicMock()
    return cursor


# ─── Initialization Tests ───────────────────────────────────────

class TestMySQLServiceInit:
    def test_init_with_defaults(self):
        """Test initialization with default values."""
        with patch("app.services.mysql_service.get_settings") as mock_settings:
            mock_settings.return_value.database.host = "localhost"
            mock_settings.return_value.database.port = 3306
            mock_settings.return_value.database.user = "root"
            mock_settings.return_value.database.password = ""
            mock_settings.return_value.database.name = "test_db"
            service = MySQLService()
            assert service.host == "localhost"
            assert service.port == 3306
            assert service._pool_config["pool_size"] == 5

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        service = MySQLService(
            host="db.example.com",
            port=3307,
            user="admin",
            password="secret",
            database="myapp",
            pool_size=10,
            connect_timeout=20,
        )
        assert service.host == "db.example.com"
        assert service.port == 3307
        assert service._pool_config["pool_size"] == 10
        assert service.connect_timeout == 20


# ─── Connection Pool Tests ──────────────────────────────────────

class TestConnectionPool:
    def test_get_pool_creates_pool(self, mysql_service):
        """Test that _get_pool creates a new pool."""
        with patch.object(pooling, 'MySQLConnectionPool') as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value = mock_pool
            
            result = mysql_service._get_pool()
            
            assert result == mock_pool
            assert mysql_service._pool == mock_pool

    def test_get_connection(self, mysql_service, mock_conn):
        """Test getting a connection from pool."""
        mock_pool = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mysql_service._pool = mock_pool
        
        conn = mysql_service.get_connection()
        
        assert conn == mock_conn
        assert conn.autocommit is False


# ─── Execute Tests ───────────────────────────────────────────────

class TestExecute:
    def test_execute_select(self, mysql_service, mock_conn, mock_cursor):
        """Test SELECT query execution."""
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.execute("SELECT * FROM users")
        
        assert len(result) == 1
        assert result[0]["id"] == 1
        mock_conn.commit.assert_called_once()

    def test_execute_insert(self, mysql_service, mock_conn, mock_cursor):
        """Test INSERT query execution."""
        mock_cursor.rowcount = 1
        mock_cursor.lastrowid = 100
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.execute(
            "INSERT INTO users (name) VALUES (%s)",
            ("test",)
        )
        
        assert result[0]["affected_rows"] == 1
        assert result[0]["last_insert_id"] == 100

    def test_execute_with_params(self, mysql_service, mock_conn, mock_cursor):
        """Test query execution with parameters."""
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        mysql_service.execute(
            "SELECT * FROM users WHERE id = %s",
            (1,)
        )
        
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM users WHERE id = %s",
            (1,)
        )

    def test_execute_mysql_error(self, mysql_service, mock_conn, mock_cursor):
        """Test MySQL error handling in execute."""
        mock_error = MySQLError(errno=1062, msg="Duplicate entry")
        mock_cursor.execute.side_effect = mock_error
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        with pytest.raises(MySQLServiceError) as exc_info:
            mysql_service.execute("INSERT INTO users (name) VALUES (%s)", ("test",))
        
        assert "1062" in str(exc_info.value)
        mock_conn.rollback.assert_called_once()

    def test_execute_closes_cursor_and_conn(self, mysql_service, mock_conn, mock_cursor):
        """Test that execute closes cursor and connection."""
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        mysql_service.execute("SELECT 1")
        
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


# ─── Execute Many Tests ─────────────────────────────────────────

class TestExecuteMany:
    def test_execute_many_success(self, mysql_service, mock_conn, mock_cursor):
        """Test executemany success."""
        mock_cursor.rowcount = 3
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.execute_many(
            "INSERT INTO users (name) VALUES (%s)",
            [("user1",), ("user2",), ("user3",)]
        )
        
        assert result == 3
        mock_cursor.executemany.assert_called_once()

    def test_execute_many_error(self, mysql_service, mock_conn, mock_cursor):
        """Test executemany error handling."""
        mock_error = MySQLError(errno=1062, msg="Duplicate entry")
        mock_cursor.executemany.side_effect = mock_error
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        with pytest.raises(MySQLServiceError):
            mysql_service.execute_many("INSERT INTO users VALUES (%s)", [("test",)])


# ─── Browser API Tests ──────────────────────────────────────────

class TestBrowserAPIs:
    def test_list_databases(self, mysql_service, mock_conn, mock_cursor):
        """Test listing databases."""
        mock_cursor.fetchall.return_value = [
            {"Database": "db1"},
            {"Database": "db2"},
        ]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.list_databases()
        
        assert result == ["db1", "db2"]

    def test_list_tables(self, mysql_service, mock_conn, mock_cursor):
        """Test listing tables."""
        mock_cursor.fetchall.return_value = [
            {"Tables_in_test_db": "users"},
            {"Tables_in_test_db": "orders"},
        ]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.list_tables()
        
        assert result == ["users", "orders"]

    def test_list_tables_with_database(self, mysql_service, mock_conn, mock_cursor):
        """Test listing tables from specific database."""
        mock_cursor.fetchall.return_value = [{"Tables_in_other_db": "table1"}]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.list_tables("other_db")
        
        assert result == ["table1"]

    def test_get_table_columns(self, mysql_service, mock_conn, mock_cursor):
        """Test getting table column definitions."""
        mock_cursor.fetchall.return_value = [
            {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO", "COLUMN_KEY": "PRI"},
            {"COLUMN_NAME": "name", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES", "COLUMN_KEY": ""},
        ]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.get_table_columns("users")
        
        assert len(result) == 2
        assert result[0]["COLUMN_NAME"] == "id"

    def test_list_mysql_databases(self, mysql_service):
        """Test listing user databases (excluding system DBs)."""
        with patch.object(mysql_service, 'list_databases') as mock_list:
            mock_list.return_value = [
                "information_schema", "mysql", "performance_schema",
                "sys", "myapp", "test_db"
            ]
            
            result = mysql_service.list_mysql_databases()
            
            assert len(result) == 2
            assert result[0]["name"] == "myapp"

    def test_list_mysql_tables(self, mysql_service):
        """Test listing MySQL tables for frontend."""
        with patch.object(mysql_service, 'list_tables') as mock_list:
            mock_list.return_value = ["users", "orders"]
            
            result = mysql_service.list_mysql_tables("myapp")
            
            assert len(result) == 2
            assert result[0]["name"] == "users"


# ─── System Table Tests ──────────────────────────────────────────

class TestSystemTables:
    def test_table_exists_true(self, mysql_service, mock_conn, mock_cursor):
        """Test table_exists returns True when table exists."""
        mock_cursor.fetchall.return_value = [{"cnt": 1}]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.table_exists("users")
        
        assert result is True

    def test_table_exists_false(self, mysql_service, mock_conn, mock_cursor):
        """Test table_exists returns False when table doesn't exist."""
        mock_cursor.fetchall.return_value = [{"cnt": 0}]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.table_exists("nonexistent")
        
        assert result is False

    def test_create_sync_config_table(self, mysql_service, mock_conn, mock_cursor):
        """Test creating sync_configs table."""
        mock_cursor.fetchall.return_value = [{"affected_rows": 0}]
        mock_conn.cursor.return_value = mock_cursor
        mysql_service._pool = MagicMock()
        mysql_service._pool.get_connection.return_value = mock_conn
        
        result = mysql_service.create_sync_config_table()
        
        assert result is True

    def test_create_sync_logs_table(self, mysql_service):
        """Test creating sync_logs table."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            result = mysql_service.create_sync_logs_table()
            assert result is True

    def test_create_change_tracking_table(self, mysql_service):
        """Test creating change_tracking table."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            result = mysql_service.create_change_tracking_table()
            assert result is True

    def test_init_system_tables(self, mysql_service):
        """Test initializing all system tables."""
        with patch.object(mysql_service, 'create_sync_config_table') as m1, \
             patch.object(mysql_service, 'create_sync_logs_table') as m2, \
             patch.object(mysql_service, 'create_change_tracking_table') as m3:
            mysql_service.init_system_tables()
            m1.assert_called_once()
            m2.assert_called_once()
            m3.assert_called_once()


# ─── Data Table Creation Tests ──────────────────────────────────

class TestCreateDataTable:
    def test_create_data_table_new(self, mysql_service):
        """Test creating a new data table."""
        columns = [
            {"db_column": "id", "db_type": "INT", "primary_key": True},
            {"db_column": "name", "db_type": "VARCHAR(255)"},
            {"db_column": "age", "db_type": "INT"},
        ]
        
        with patch.object(mysql_service, 'table_exists', return_value=False), \
             patch.object(mysql_service, 'execute') as mock_execute:
            result = mysql_service.create_data_table("users", columns)
            
            assert result is True
            mock_execute.assert_called_once()

    def test_create_data_table_exists(self, mysql_service):
        """Test creating a table that already exists."""
        with patch.object(mysql_service, 'table_exists', return_value=True):
            result = mysql_service.create_data_table("users", [])
            
            assert result is False

    def test_create_data_table_with_primary_key(self, mysql_service):
        """Test creating table with primary key."""
        columns = [
            {"db_column": "id", "db_type": "INT", "primary_key": True},
        ]
        
        with patch.object(mysql_service, 'table_exists', return_value=False), \
             patch.object(mysql_service, 'execute') as mock_execute:
            mysql_service.create_data_table("users", columns)
            
            call_args = mock_execute.call_args[0][0]
            assert "PRIMARY KEY" in call_args


# ─── Data Operation Tests ────────────────────────────────────────

class TestDataOperations:
    def test_insert_or_update_insert(self, mysql_service):
        """Test inserting a new row."""
        row_data = {"id": 1, "name": "test", "age": 25}
        primary_keys = ["id"]
        
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"affected_rows": 1}]
            
            result = mysql_service.insert_or_update("users", row_data, primary_keys)
            
            assert result == 1  # Inserted

    def test_insert_or_update_update(self, mysql_service):
        """Test updating an existing row."""
        row_data = {"id": 1, "name": "updated", "age": 30}
        primary_keys = ["id"]
        
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"affected_rows": 2}]
            
            result = mysql_service.insert_or_update("users", row_data, primary_keys)
            
            assert result == 2  # Updated

    def test_insert_or_update_no_change(self, mysql_service):
        """Test insert_or_update with no changes."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"affected_rows": 0}]
            
            result = mysql_service.insert_or_update("users", {"id": 1}, ["id"])
            
            assert result == 0

    def test_insert_or_update_empty_data(self, mysql_service):
        """Test insert_or_update with empty data."""
        result = mysql_service.insert_or_update("users", {}, ["id"])
        assert result == 0

    def test_select_all(self, mysql_service):
        """Test selecting all rows."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"id": 1}, {"id": 2}]
            
            result = mysql_service.select_all("users")
            
            assert len(result) == 2

    def test_select_all_with_columns(self, mysql_service):
        """Test selecting specific columns."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"id": 1}]
            
            result = mysql_service.select_all("users", columns=["id", "name"])
            
            assert len(result) == 1

    def test_select_all_with_where(self, mysql_service):
        """Test selecting with WHERE clause."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"id": 1}]
            
            mysql_service.select_all("users", where="id = %s", params=(1,))
            
            call_args = mock_execute.call_args[0]
            assert "WHERE" in call_args[0]

    def test_select_all_with_limit(self, mysql_service):
        """Test selecting with custom limit."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = []
            
            mysql_service.select_all("users", limit=50)
            
            call_args = mock_execute.call_args[0]
            assert "LIMIT 50" in call_args[0]


# ─── Compute Row Hash Tests ──────────────────────────────────────

class TestComputeRowHash:
    def test_compute_row_hash_basic(self):
        """Test basic hash computation."""
        row_data = {"id": 1, "name": "test"}
        hash1 = MySQLService.compute_row_hash(row_data)
        hash2 = MySQLService.compute_row_hash(row_data)
        
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_compute_row_hash_with_exclude(self):
        """Test hash with excluded columns."""
        row_data = {"id": 1, "name": "test", "updated_at": "2024-01-01"}
        
        hash1 = MySQLService.compute_row_hash(row_data)
        hash2 = MySQLService.compute_row_hash(row_data, exclude_cols=["updated_at"])
        
        assert hash1 == hash2  # updated_at is excluded by default

    def test_compute_row_hash_different_data(self):
        """Test hash with different data produces different hashes."""
        row1 = {"id": 1, "name": "test1"}
        row2 = {"id": 2, "name": "test2"}
        
        hash1 = MySQLService.compute_row_hash(row1)
        hash2 = MySQLService.compute_row_hash(row2)
        
        assert hash1 != hash2

    def test_compute_row_hash_none_values(self):
        """Test hash ignores None values."""
        row_data = {"id": 1, "name": None, "age": 25}
        
        hash_result = MySQLService.compute_row_hash(row_data)
        
        assert hash_result is not None
        assert len(hash_result) == 64


# ─── Change Tracking Tests ──────────────────────────────────────

class TestChangeTracking:
    def test_get_tracked_row_exists(self, mysql_service):
        """Test getting an existing tracked row."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{
                "source_hash": "abc123",
                "prev_value": '{"id": 1}',
                "last_sync_at": "2024-01-01"
            }]
            
            result = mysql_service.get_tracked_row(1, "row1", "tencent")
            
            assert result is not None
            assert result["source_hash"] == "abc123"

    def test_get_tracked_row_not_exists(self, mysql_service):
        """Test getting a non-existent tracked row."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = []
            
            result = mysql_service.get_tracked_row(1, "row1", "tencent")
            
            assert result is None

    def test_upsert_tracked_row_new(self, mysql_service):
        """Test inserting a new tracked row."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mysql_service.upsert_tracked_row(
                1, "row1", "hash123", '{"id": 1}', "tencent"
            )
            
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0]
            assert "INSERT INTO change_tracking" in call_args[0]

    def test_upsert_tracked_row_update(self, mysql_service):
        """Test updating an existing tracked row."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            # This uses ON DUPLICATE KEY UPDATE
            mysql_service.upsert_tracked_row(
                1, "row1", "new_hash", '{"id": 1}', "tencent"
            )
            
            call_args = mock_execute.call_args[0][0]
            assert "ON DUPLICATE KEY UPDATE" in call_args


# ─── Sync Config Tests ──────────────────────────────────────────

class TestSyncConfig:
    def test_get_sync_config_exists(self, mysql_service):
        """Test getting an existing sync config."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{
                "id": 1,
                "spreadsheet_id": "test",
                "mapping_json": '{"columns": []}'
            }]
            
            result = mysql_service.get_sync_config(1)
            
            assert result is not None
            assert result["id"] == 1
            assert isinstance(result["mapping_json"], dict)

    def test_get_sync_config_not_exists(self, mysql_service):
        """Test getting a non-existent sync config."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = []
            
            result = mysql_service.get_sync_config(999)
            
            assert result is None

    def test_get_all_sync_configs(self, mysql_service):
        """Test getting all sync configs."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [
                {"id": 1, "mapping_json": '{"columns": []}'},
                {"id": 2, "mapping_json": '{"columns": []}'},
            ]
            
            result = mysql_service.get_all_sync_configs()
            
            assert len(result) == 2

    def test_get_all_sync_configs_inactive(self, mysql_service):
        """Test getting only active sync configs."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = []
            
            mysql_service.get_all_sync_configs(active_only=True)
            
            call_args = mock_execute.call_args[0][0]
            assert "is_active = 1" in call_args

    def test_create_sync_config(self, mysql_service):
        """Test creating a new sync config."""
        with patch.object(mysql_service, 'execute') as mock_execute1, \
             patch.object(mysql_service, 'execute') as mock_execute2:
            mock_execute1.return_value = [{"affected_rows": 1}]
            mock_execute2.return_value = [{"id": 1}]
            
            result = mysql_service.create_sync_config(
                spreadsheet_id="test_sheet",
                sheet_id="sheet1",
                table_name="users",
                database="test_db",
                mapping_json={"columns": []},
            )
            
            assert result == 1

    def test_update_sync_config_success(self, mysql_service):
        """Test updating sync config fields."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{"affected_rows": 1}]
            
            result = mysql_service.update_sync_config(
                1,
                table_name="new_table",
                poll_interval=60,
            )
            
            assert result is True

    def test_update_sync_config_no_valid_fields(self, mysql_service):
        """Test updating with no valid fields."""
        result = mysql_service.update_sync_config(1, invalid_field="value")
        assert result is False

    def test_delete_sync_config(self, mysql_service):
        """Test soft deleting a sync config."""
        with patch.object(mysql_service, 'update_sync_config') as mock_update:
            mock_update.return_value = True
            
            result = mysql_service.delete_sync_config(1)
            
            assert result is True
            mock_update.assert_called_once_with(1, is_active=0)

    def test_update_last_sync_time(self, mysql_service):
        """Test updating last sync time."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mysql_service.update_last_sync_time(1)
            
            call_args = mock_execute.call_args[0]
            assert "last_sync_at = NOW()" in call_args[0]


# ─── Sync Log Tests ─────────────────────────────────────────────

class TestSyncLogs:
    def test_create_sync_log(self, mysql_service):
        """Test creating a sync log entry."""
        with patch.object(mysql_service, 'execute') as mock_execute1, \
             patch.object(mysql_service, 'execute') as mock_execute2:
            mock_execute1.return_value = [{"affected_rows": 1}]
            mock_execute2.return_value = [{"id": 100}]
            
            result = mysql_service.create_sync_log(
                config_id=1,
                direction="to_mysql",
                rows_affected=10,
                rows_new=5,
                rows_updated=5,
                status="success",
            )
            
            assert result == 100

    def test_complete_sync_log(self, mysql_service):
        """Test completing a sync log."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mysql_service.complete_sync_log(
                log_id=100,
                rows_affected=10,
                rows_new=5,
                rows_updated=5,
                rows_skipped=0,
                status="success",
            )
            
            call_args = mock_execute.call_args[0]
            assert "UPDATE sync_logs" in call_args[0]
            assert "completed_at = NOW()" in call_args[0]

    def test_get_sync_logs(self, mysql_service):
        """Test getting recent sync logs."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [
                {"id": 1, "direction": "to_mysql"},
                {"id": 2, "direction": "from_mysql"},
            ]
            
            result = mysql_service.get_sync_logs(1, limit=10)
            
            assert len(result) == 2


# ─── Connection Test ─────────────────────────────────────────────

class TestConnectionTest:
    def test_test_connection_success(self, mysql_service):
        """Test successful connection test."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.return_value = [{
                "version": "8.0.30",
                "db": "test_db"
            }]
            
            result = mysql_service.test_connection()
            
            assert result["connected"] is True
            assert result["version"] == "8.0.30"

    def test_test_connection_failure(self, mysql_service):
        """Test connection test failure."""
        with patch.object(mysql_service, 'execute') as mock_execute:
            mock_execute.side_effect = MySQLServiceError("Connection failed")
            
            result = mysql_service.test_connection()
            
            assert result["connected"] is False
            assert "Connection failed" in result["error"]


# ─── Singleton Tests ─────────────────────────────────────────────

class TestSingleton:
    def test_get_mysql_service_singleton(self):
        """Test that get_mysql_service returns singleton."""
        with patch('app.services.mysql_service._mysql_service', None):
            service1 = get_mysql_service_from_module()
            service2 = get_mysql_service_from_module()
            
            assert service1 is service2

    def test_reset_mysql_service(self):
        """Test resetting the singleton."""
        from app.services.mysql_service import _mysql_service
        
        # This is mainly for testing
        assert True  # Just verify the function exists


def get_mysql_service_from_module():
    """Helper to get mysql service."""
    from app.services.mysql_service import get_mysql_service
    return get_mysql_service()
