"""
MySQL Service for table operations and data manipulation.
Handles table creation, CRUD operations, and change tracking.
"""
import json
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
from mysql.connector import pooling, Error as MySQLError

from app.config import get_settings
from app.utils import parse_config_row

logger = logging.getLogger(__name__)

# Allowed identifier pattern: letters, digits, underscores, hyphens (for databases)
# Must start with letter or underscore
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_@$]*$')


def _validate_identifier(name: str, allow_hyphen: bool = False) -> str:
    """
    Validate a SQL identifier to prevent injection.
    Returns the validated name, or raises ValueError.
    """
    if not name:
        raise ValueError("Identifier cannot be empty")
    
    # Remove backticks if present
    if name.startswith('`') and name.endswith('`'):
        name = name[1:-1]
    
    # Check length (MySQL limit is 64 characters)
    if len(name) > 64:
        raise ValueError(f"Identifier too long: {name[:20]}...")
    
    # Pattern depends on whether hyphens are allowed (database names can have hyphens)
    if allow_hyphen:
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_@$-]*$'
        if not re.match(pattern, name):
            raise ValueError(f"Invalid identifier: {name}")
    else:
        if not VALID_IDENTIFIER_PATTERN.match(name):
            raise ValueError(f"Invalid identifier: {name}")
    
    return name


def _validate_sql_in_identifier_list(identifiers: List[str]) -> List[str]:
    """Validate a list of identifiers."""
    return [_validate_identifier(id) for id in identifiers]


# Whitelist of allowed MySQL data types to prevent type injection
ALLOWED_MYSQL_TYPES = {
    # Numeric types
    "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT",
    "FLOAT", "DOUBLE", "DECIMAL",
    # String types
    "VARCHAR", "CHAR", "TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
    # Binary types
    "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
    # Date and time types
    "DATE", "TIME", "DATETIME", "TIMESTAMP", "YEAR",
    # Other types
    "BOOLEAN", "BOOL", "JSON",
}


def _validate_mysql_type(type_str: str) -> str:
    """
    Validate a MySQL data type string.
    Allows types like VARCHAR(255), INT, DECIMAL(10,2), etc.
    Returns the validated type string.
    """
    if not type_str:
        raise ValueError("Data type cannot be empty")
    
    # Remove extra whitespace and convert to uppercase for checking
    type_upper = type_str.strip().upper()
    
    # Extract base type (before '(' if present)
    base_type = type_upper.split('(')[0].strip()
    
    # Check if base type is in whitelist
    if base_type not in ALLOWED_MYSQL_TYPES:
        raise ValueError(f"Invalid data type: {type_str}")
    
    # Additional check: ensure no semicolons or other dangerous characters
    if any(c in type_str for c in ';--/*'):
        raise ValueError(f"Invalid data type: {type_str}")
    
    return type_str


class MySQLServiceError(Exception):
    """MySQL service error."""
    pass


class MySQLService:
    """
    MySQL operations service with per-instance connection pooling.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        pool_size: int = 5,
        connect_timeout: int = 3,
    ):
        self.settings = get_settings()

        self.host = host or self.settings.database.host
        self.port = port or self.settings.database.port
        self.user = user or self.settings.database.user
        self.password = password or self.settings.database.password
        self.database = database or self.settings.database.name
        self.connect_timeout = connect_timeout

        self._pool_config = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "autocommit": False,
            "pool_name": f"sync_pool_{id(self)}",
            "pool_size": pool_size,
            "pool_reset_session": True,
            "charset": "utf8mb4",
            "connect_timeout": connect_timeout,
        }
        self._pool: Optional[pooling.MySQLConnectionPool] = None

    def _get_pool(self) -> pooling.MySQLConnectionPool:
        """Lazily create the connection pool."""
        if self._pool is None:
            try:
                self._pool = pooling.MySQLConnectionPool(**self._pool_config)
            except MySQLError as e:
                raise MySQLServiceError(f"MySQL error {e.errno}: {e.msg}") from e
        return self._pool

    def get_connection(self):
        """Get a connection from the pool."""
        try:
            pool = self._get_pool()
            conn = pool.get_connection()
            conn.autocommit = False
            return conn
        except MySQLServiceError:
            raise
        except MySQLError as e:
            raise MySQLServiceError(f"MySQL error {e.errno}: {e.msg}") from e

    def execute(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """
        Execute a query and return results as list of dicts.
        Automatically commits on success, rolls back on failure.
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            query_upper = query.strip().upper()

            if query_upper.startswith(("SELECT", "SHOW", "DESCRIBE")):
                result = cursor.fetchall()
                conn.commit()
                logger.debug(f"Query executed successfully, returned {len(result)} rows")
                return result
            else:
                conn.commit()
                logger.debug(f"Query executed successfully, affected {cursor.rowcount} rows")
                return [{"affected_rows": cursor.rowcount, "last_insert_id": cursor.lastrowid}]
        except MySQLError as e:
            conn.rollback()
            logger.error(f"MySQL error executing query: {e.errno}: {e.msg}")
            raise MySQLServiceError(f"MySQL error {e.errno}: {e.msg}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute a query multiple times with different parameters.
        Returns the total number of rows affected.
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except MySQLError as e:
            conn.rollback()
            raise MySQLServiceError(f"MySQL error {e.errno}: {e.msg}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ─── Browser APIs ───────────────────────────────────────────────

    def list_databases(self) -> List[str]:
        """List all databases accessible by the current user."""
        result = self.execute("SHOW DATABASES")
        return [row["Database"] for row in result]

    def list_tables(self, database: Optional[str] = None) -> List[str]:
        """List all tables in a database."""
        if database:
            # Validate database name to prevent SQL injection
            _validate_identifier(database, allow_hyphen=True)
            db_clause = f"FROM `{database}`"
        else:
            db_clause = "FROM DATABASE()"
        
        result = self.execute(f"SHOW TABLES {db_clause}")
        if not result:
            return []
        col = list(result[0].keys())[0]
        return [row[col] for row in result]

    def get_table_columns(self, table_name: str, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get column definitions for a table."""
        if database:
            _validate_identifier(database, allow_hyphen=True)
            db_clause = f"TABLE_SCHEMA = '{database}'"
        else:
            db_clause = "TABLE_SCHEMA = DATABASE()"
        
        query = f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA
            FROM information_schema.COLUMNS
            WHERE {db_clause} AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        return self.execute(query, (table_name,))

    def list_mysql_databases(self) -> List[Dict[str, str]]:
        """List user databases with names for frontend selection."""
        dbs = self.list_databases()
        system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}
        return [{"name": db, "label": db} for db in dbs if db not in system_dbs]

    def list_mysql_tables(self, database: str) -> List[Dict[str, str]]:
        """List tables in a specific database."""
        tables = self.list_tables(database)
        return [{"name": t, "label": t} for t in tables]

    # ─── System Tables ─────────────────────────────────────────────

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = """
            SELECT COUNT(*) as cnt
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """
        result = self.execute(query, (self.database, table_name))
        return bool(result and result[0]["cnt"] > 0)

    def create_sync_config_table(self) -> bool:
        """Create the sync_configs table."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS sync_configs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            spreadsheet_id VARCHAR(128) NOT NULL,
            sheet_id VARCHAR(64) NOT NULL,
            table_name VARCHAR(128) NOT NULL,
            `database` VARCHAR(128) NOT NULL DEFAULT '',
            mysql_config_id BIGINT DEFAULT NULL,
            tencent_config_id BIGINT DEFAULT NULL,
            mapping_json JSON NOT NULL,
            sync_direction ENUM('to_mysql','from_mysql','bidirectional') DEFAULT 'bidirectional',
            poll_interval INT DEFAULT 30,
            last_sync_at DATETIME DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_active TINYINT(1) DEFAULT 1,
            UNIQUE KEY uk_spreadsheet (spreadsheet_id),
            INDEX idx_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        self.execute(create_sql)
        return True

    def create_sync_logs_table(self) -> bool:
        """Create the sync_logs table."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS sync_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            config_id BIGINT NOT NULL,
            direction ENUM('to_mysql','from_mysql','bidirectional') NOT NULL,
            rows_affected INT DEFAULT 0,
            rows_new INT DEFAULT 0,
            rows_updated INT DEFAULT 0,
            rows_skipped INT DEFAULT 0,
            status ENUM('running','success','partial','failed') DEFAULT 'running',
            error_message TEXT,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_config_time (config_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        self.execute(create_sql)
        return True

    def create_change_tracking_table(self) -> bool:
        """Create the change_tracking table."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS change_tracking (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            config_id BIGINT NOT NULL,
            source_row_key VARCHAR(256) NOT NULL,
            source_hash VARCHAR(64) NOT NULL,
            prev_value TEXT,
            last_sync_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source ENUM('tencent','mysql') NOT NULL,
            INDEX idx_config_row (config_id, source_row_key),
            INDEX idx_last_sync (last_sync_at),
            UNIQUE KEY uk_config_row (config_id, source_row_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        self.execute(create_sql)
        return True

    def create_mysql_configs_table(self) -> bool:
        """Create the mysql_configs table."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS mysql_configs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(128) NOT NULL UNIQUE,
            host VARCHAR(256) NOT NULL,
            port INT NOT NULL DEFAULT 3306,
            username VARCHAR(128) NOT NULL,
            password_encrypted TEXT NOT NULL,
            database_name VARCHAR(128) NOT NULL,
            charset VARCHAR(32) DEFAULT 'utf8mb4',
            description VARCHAR(512) DEFAULT NULL,
            is_active TINYINT(1) DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            last_tested_at DATETIME DEFAULT NULL,
            test_status ENUM('untested', 'success', 'failed') DEFAULT 'untested',
            test_message TEXT DEFAULT NULL,
            INDEX idx_name (name),
            INDEX idx_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        self.execute(create_sql)
        self.execute(
            "ALTER TABLE sync_configs ADD COLUMN IF NOT EXISTS mysql_config_id BIGINT DEFAULT NULL AFTER `database`"
        )
        self.execute(
            "ALTER TABLE sync_configs ADD COLUMN IF NOT EXISTS tencent_config_id BIGINT DEFAULT NULL AFTER mysql_config_id"
        )
        self.execute(
            "ALTER TABLE sync_configs ADD INDEX IF NOT EXISTS idx_mysql_config_id (mysql_config_id)"
        )
        self.execute(
            "ALTER TABLE sync_configs ADD INDEX IF NOT EXISTS idx_tencent_config_id (tencent_config_id)"
        )
        return True

    def create_tencent_api_configs_table(self) -> bool:
        """Create the tencent_api_configs table."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS tencent_api_configs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(128) NOT NULL UNIQUE,
            app_id VARCHAR(256) NOT NULL,
            open_id VARCHAR(256) NOT NULL,
            access_token_encrypted TEXT NOT NULL,
            description VARCHAR(512) DEFAULT NULL,
            is_active TINYINT(1) DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            last_tested_at DATETIME DEFAULT NULL,
            test_status ENUM('untested', 'success', 'failed') DEFAULT 'untested',
            test_message TEXT DEFAULT NULL,
            token_expires_at DATETIME DEFAULT NULL,
            INDEX idx_name (name),
            INDEX idx_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        self.execute(create_sql)
        return True

    def init_system_tables(self) -> None:
        """Initialize all system tables."""
        self.create_sync_config_table()
        self.create_sync_logs_table()
        self.create_change_tracking_table()
        self.create_mysql_configs_table()
        self.create_tencent_api_configs_table()

    def create_data_table(
        self,
        table_name: str,
        mapping_columns: List[Dict[str, Any]],
    ) -> bool:
        """Create a data table based on column mapping."""
        # Validate table name to prevent SQL injection
        table_name = _validate_identifier(table_name)
        
        if self.table_exists(table_name):
            return False

        column_defs = []
        primary_keys = []

        for col in mapping_columns:
            db_col = col["db_column"]
            db_type = col.get("db_type", "VARCHAR(255)")
            is_primary = col.get("primary_key", False)
            
            # Validate column name and type
            db_col = _validate_identifier(db_col)
            db_type = _validate_mysql_type(db_type)

            col_def = f"`{db_col}` {db_type}"
            if is_primary:
                primary_keys.append(db_col)
                col_def += " NOT NULL"

            column_defs.append(col_def)

        column_defs.append("`created_at` DATETIME DEFAULT CURRENT_TIMESTAMP")
        column_defs.append("`updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        pk_clause = ""
        if primary_keys:
            pk_clause = f", PRIMARY KEY ({', '.join([f'`{pk}`' for pk in primary_keys])})"

        create_sql = f"""
        CREATE TABLE `{table_name}` (
            {', '.join(column_defs)}
            {pk_clause}
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """

        self.execute(create_sql)
        logger.info(f"Created table: {table_name}")
        return True

    # ─── Data Operations ────────────────────────────────────────────

    def insert_or_update(
        self,
        table_name: str,
        row_data: Dict[str, Any],
        primary_keys: List[str],
    ) -> int:
        """
        Insert a row or update if duplicate key exists.
        Returns: 0 = nothing changed, 1 = inserted, 2 = updated.
        Raises: MySQLServiceError on failure.
        """
        if not row_data:
            return 0

        # Validate table name and column names to prevent SQL injection
        table_name = _validate_identifier(table_name)
        columns = list(row_data.keys())
        values = list(row_data.values())
        
        # Validate all column names
        columns = [_validate_identifier(col) for col in columns]
        primary_keys = [_validate_identifier(pk) for pk in primary_keys]

        update_parts = [
            f"`{col}` = VALUES(`{col}`)"
            for col in columns
            if col not in primary_keys and col not in ("created_at", "updated_at")
        ]

        query = f"""
        INSERT INTO `{table_name}` ({', '.join([f'`{c}`' for c in columns])})
        VALUES ({', '.join(['%s'] * len(values))})
        {f'ON DUPLICATE KEY UPDATE {", ".join(update_parts)}' if update_parts else ''}
        """

        result = self.execute(query, tuple(values))
        if not result:
            return 0
        # mysql.connector returns affected_rows: 1 = inserted, 2 = updated (when ON DUPLICATE KEY UPDATE touches a row)
        return result[0].get("affected_rows", 0)

    def select_all(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        where: Optional[str] = None,
        params: Optional[Tuple] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Select rows from a table."""
        # Validate table name to prevent SQL injection
        table_name = _validate_identifier(table_name)
        
        # Validate column names if provided
        if columns:
            columns = [_validate_identifier(col) for col in columns]
            col_clause = ", ".join([f"`{c}`" for c in columns])
        else:
            col_clause = "*"
            
        query = f"SELECT {col_clause} FROM `{table_name}`"
        
        # WARNING: Dynamic WHERE clause is a SQL injection risk.
        # Users should use parameterized queries via the params argument.
        if where:
            logger.warning("Dynamic WHERE clause detected. Use parameterized queries with params argument instead.")
            # Basic sanity check: no comments or semicolons
            if any(c in where for c in ';--/*'):
                raise ValueError("Invalid characters in WHERE clause")
            query += f" WHERE {where}"
            
        query += f" LIMIT {limit}"
        return self.execute(query, params)

    # ─── Change Tracking ───────────────────────────────────────────

    @staticmethod
    def compute_row_hash(row_data: Dict[str, Any], exclude_cols: Optional[List[str]] = None) -> str:
        """Compute a SHA256 hash for a row."""
        exclude_cols = exclude_cols or ["updated_at", "last_sync_at", "created_at"]
        filtered = {k: v for k, v in row_data.items() if k not in exclude_cols and v is not None}
        stable_json = json.dumps(filtered, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()

    def get_tracked_row(
        self,
        config_id: int,
        source_row_key: str,
        source: str,
    ) -> Optional[Dict[str, Any]]:
        """Get tracked row info for change detection."""
        query = """
            SELECT source_hash, prev_value, last_sync_at
            FROM change_tracking
            WHERE config_id = %s AND source_row_key = %s AND source = %s
        """
        result = self.execute(query, (config_id, source_row_key, source))
        return result[0] if result else None

    def batch_get_tracked_rows(
        self,
        config_id: int,
        source_row_keys: List[str],
        source: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch tracked rows for multiple keys.
        Returns dict keyed by source_row_key for O(1) lookup.
        """
        if not source_row_keys:
            return {}
        
        # MySQL has a limit on IN clause, process in chunks
        result = {}
        chunk_size = 1000
        
        for i in range(0, len(source_row_keys), chunk_size):
            chunk = source_row_keys[i:i + chunk_size]
            placeholders = ", ".join(["%s"] * len(chunk))
            
            query = f"""
                SELECT source_row_key, source_hash, prev_value, last_sync_at
                FROM change_tracking
                WHERE config_id = %s AND source = %s AND source_row_key IN ({placeholders})
            """
            rows = self.execute(query, [config_id, source] + chunk)
            
            for row in rows:
                result[row["source_row_key"]] = {
                    "source_hash": row["source_hash"],
                    "prev_value": row["prev_value"],
                    "last_sync_at": row["last_sync_at"],
                }
        
        return result

        params_list = [
            (config_id, row_key, source_hash, prev_value, source)
            for row_key, source_hash, prev_value in rows
        ]
        
        self.execute_many(query, params_list)
        logger.debug(f"Batch upserted {len(rows)} tracked rows")
        
    def cleanup_old_tracking_data(
        self,
        config_id: Optional[int] = None,
        days_to_keep: int = 30,
    ) -> int:
        """
        Clean up old tracking data to prevent unlimited table growth.
        
        Args:
            config_id: If provided, only clean this config's data
            days_to_keep: Number of days of data to keep (default 30)
            
        Returns:
            Number of rows deleted
        """
        query = """
            DELETE FROM change_tracking
            WHERE last_sync_at < DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        params = [days_to_keep]
        
        if config_id is not None:
            query += " AND config_id = %s"
            params.append(config_id)
        
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"Cleaned up {deleted_count} old tracking records (older than {days_to_keep} days)")
            return deleted_count
        except MySQLError as e:
            conn.rollback()
            raise MySQLServiceError(f"MySQL error {e.errno}: {e.msg}") from e
        finally:
            if cursor:
                cursor.close()
            conn.close()



    def upsert_tracked_row(
        self,
        config_id: int,
        source_row_key: str,
        source_hash: str,
        prev_value: str,
        source: str,
    ) -> None:
        """Insert or update a change tracking record."""
        query = """
        INSERT INTO change_tracking
            (config_id, source_row_key, source_hash, prev_value, source, last_sync_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            source_hash = VALUES(source_hash),
            prev_value = VALUES(prev_value),
            last_sync_at = NOW()
        """
        self.execute(query, (config_id, source_row_key, source_hash, prev_value, source))

    def batch_upsert_tracked_rows(
        self,
        config_id: int,
        rows: List[Tuple[str, str, str]],
        source: str,
    ) -> None:
        """
        Batch upsert tracking rows for better performance.
        rows: List of (source_row_key, source_hash, prev_value) tuples
        """
        if not rows:
            return

        query = """
        INSERT INTO change_tracking
            (config_id, source_row_key, source_hash, prev_value, source, last_sync_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            source_hash = VALUES(source_hash),
            prev_value = VALUES(prev_value),
            last_sync_at = NOW()
        """

        params_list = [
            (config_id, row_key, source_hash, prev_value, source)
            for row_key, source_hash, prev_value in rows
        ]

        self.execute_many(query, params_list)
        logger.debug(f"Batch upserted {len(rows)} tracking rows for config {config_id}")

    # ─── Sync Config Operations ───────────────────────────────────

    def get_sync_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """Get a sync configuration by ID."""
        query = "SELECT * FROM sync_configs WHERE id = %s"
        result = self.execute(query, (config_id,))
        if not result:
            return None
        config = result[0]
        parse_config_row(config)
        return config

    def get_all_sync_configs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all sync configurations."""
        query = "SELECT * FROM sync_configs"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id"
        results = self.execute(query)
        for r in results:
            parse_config_row(r)
        return results

    def create_sync_config(
        self,
        spreadsheet_id: str,
        sheet_id: str,
        table_name: str,
        database: str,
        mysql_config_id: Optional[int],
        tencent_config_id: Optional[int],
        mapping_json: Dict[str, Any],
        sync_direction: str = "bidirectional",
        poll_interval: int = 30,
    ) -> int:
        """Create a new sync configuration."""
        query = """
        INSERT INTO sync_configs
            (spreadsheet_id, sheet_id, table_name, `database`, mysql_config_id, tencent_config_id,
             mapping_json, sync_direction, poll_interval)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.execute(query, (
            spreadsheet_id,
            sheet_id,
            table_name,
            database,
            mysql_config_id,
            tencent_config_id,
            json.dumps(mapping_json, ensure_ascii=False),
            sync_direction,
            poll_interval,
        ))
        result = self.execute("SELECT LAST_INSERT_ID() as id")
        return result[0]["id"]

    def update_sync_config(
        self,
        config_id: int,
        **kwargs,
    ) -> bool:
        """Update sync configuration fields."""
        allowed_fields = {
            "sheet_id", "table_name", "database", "mysql_config_id", "tencent_config_id",
            "mapping_json", "sync_direction",
            "poll_interval", "is_active", "last_sync_at"
        }
        updates = []
        params = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                # Validate key is a valid identifier (defense in depth)
                key = _validate_identifier(key)
                
                if key == "mapping_json":
                    updates.append("mapping_json = %s")
                    params.append(json.dumps(value, ensure_ascii=False))
                elif key == "last_sync_at":
                    updates.append("last_sync_at = %s")
                    params.append(value)
                else:
                    updates.append(f"`{key}` = %s")
                    params.append(value)
            else:
                logger.warning(f"Attempted to update non-allowed field: {key}")

        if not updates:
            return False

        params.append(config_id)
        query = f"UPDATE sync_configs SET {', '.join(updates)} WHERE id = %s"
        result = self.execute(query, tuple(params))
        return bool(result and result[0].get("affected_rows", 0) > 0)

    def delete_sync_config(self, config_id: int) -> bool:
        """Soft delete a sync configuration."""
        return self.update_sync_config(config_id, is_active=0)

    def update_last_sync_time(self, config_id: int) -> None:
        """Update the last_sync_at timestamp."""
        query = "UPDATE sync_configs SET last_sync_at = NOW() WHERE id = %s"
        self.execute(query, (config_id,))

    # ─── Sync Log Operations ──────────────────────────────────────

    def create_sync_log(
        self,
        config_id: int,
        direction: str,
        rows_affected: int = 0,
        rows_new: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> int:
        """Create a sync log entry and return its ID."""
        query = """
        INSERT INTO sync_logs
            (config_id, direction, rows_affected, rows_new, rows_updated, rows_skipped,
             status, error_message, started_at, completed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        self.execute(query, (
            config_id, direction, rows_affected, rows_new, rows_updated,
            rows_skipped, status, error_message,
        ))
        result = self.execute("SELECT LAST_INSERT_ID() as id")
        return result[0]["id"]

    def complete_sync_log(
        self,
        log_id: int,
        rows_affected: int,
        rows_new: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a sync log as complete with final stats."""
        query = """
        UPDATE sync_logs
        SET rows_affected = %s, rows_new = %s, rows_updated = %s, rows_skipped = %s,
            status = %s, error_message = %s, completed_at = NOW()
        WHERE id = %s
        """
        self.execute(query, (
            rows_affected, rows_new, rows_updated, rows_skipped,
            status, error_message, log_id,
        ))

    def get_sync_logs(
        self,
        config_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent sync logs for a config."""
        query = """
            SELECT * FROM sync_logs
            WHERE config_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self.execute(query, (config_id, limit))

    # ─── Connection Test ───────────────────────────────────────────

    def test_connection(self) -> Dict[str, Any]:
        """Test MySQL connection."""
        try:
            result = self.execute("SELECT VERSION() as version, DATABASE() as db")
            if result:
                return {
                    "connected": True,
                    "database": result[0].get("db"),
                    "version": result[0].get("version"),
                }
            return {"connected": False, "error": "No result returned"}
        except MySQLServiceError as e:
            return {"connected": False, "error": str(e)}


# Singleton accessor
_mysql_service: Optional[MySQLService] = None


def get_mysql_service() -> MySQLService:
    """Get or create the singleton MySQL service instance."""
    global _mysql_service
    if _mysql_service is None:
        _mysql_service = MySQLService()
    return _mysql_service


def reset_mysql_service() -> None:
    """Reset singleton (mainly for testing)."""
    global _mysql_service
    _mysql_service = None
