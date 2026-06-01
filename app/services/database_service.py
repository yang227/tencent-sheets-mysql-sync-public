"""
Abstract DatabaseService — shared logic for MySQL and PostgreSQL.

Concrete subclasses must override the abstract methods for:
  - Connection pool creation / acquisition
  - Identifier quoting style
  - Database / table introspection
  - DDL helpers (create_data_table, table_exists)
"""
import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.db_exception import (
    DatabaseConnectionError,
    DatabaseConfigurationError,
    DatabaseIntegrityError,
    DatabaseQueryError,
    DatabaseServiceError,
    DatabaseTimeoutError,
    IdentifierValidationError,
    DatabaseTypeValidationError,
)

logger = logging.getLogger(__name__)

# ─── Identifier validation (shared) ────────────────────────────────

VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_@$]*$")


def validate_identifier(name: str, allow_hyphen: bool = False) -> str:
    """Validate a SQL identifier to prevent injection."""
    if not name:
        raise IdentifierValidationError("Identifier cannot be empty")
    if name.startswith("`") and name.endswith("`"):
        name = name[1:-1]
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    if len(name) > 63:
        raise IdentifierValidationError(f"Identifier too long: {name[:20]}...")
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_@$-]*$" if allow_hyphen else r"^[a-zA-Z_][a-zA-Z0-9_@$]*$"
    if not re.match(pattern, name):
        raise IdentifierValidationError(f"Invalid identifier: {name}")
    return name


def validate_identifier_list(identifiers: List[str]) -> List[str]:
    return [validate_identifier(i) for i in identifiers]


# ─── Type whitelist (shared) ───────────────────────────────────────

ALLOWED_DATA_TYPES = {
    "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT",
    "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "SERIAL", "BIGSERIAL",
    "VARCHAR", "CHAR", "TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
    "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB", "BYTEA",
    "DATE", "TIME", "DATETIME", "TIMESTAMP", "YEAR",
    "BOOLEAN", "BOOL", "JSON", "JSONB", "UUID",
}


def validate_data_type(type_str: str) -> str:
    """Validate a column data type against the whitelist."""
    if not type_str:
        raise DatabaseTypeValidationError("Data type cannot be empty")
    base = type_str.strip().upper().split("(")[0].strip()
    if base not in ALLOWED_DATA_TYPES:
        raise DatabaseTypeValidationError(f"Disallowed data type: {type_str}")
    if any(c in type_str for c in ";--/*"):
        raise DatabaseTypeValidationError(f"Invalid characters in type: {type_str}")
    return type_str


class DatabaseService(ABC):
    """
    Abstract database service.

    Provides shared CRUD, sync-config management, change-tracking,
    sync-log management, and connection-test helpers.

    Subclasses implement the abstract methods for vendor-specific behavior.
    """

    DB_TYPE: str = "abstract"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "",
        pool_size: int = 5,
        connect_timeout: int = 3,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool_size = pool_size
        self.connect_timeout = connect_timeout

    # ─── Abstract: connection lifecycle ────────────────────────────

    @abstractmethod
    def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a single SQL statement. Returns rows (SELECT) or affected-row metadata."""
        ...

    @abstractmethod
    def execute_many(
        self,
        query: str,
        params_list: List[tuple],
    ) -> int:
        """Execute a statement with many parameter sets. Returns total affected rows."""
        ...

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Return {"connected": bool, "version": str, "database": str, ...}."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close connection pool / release resources."""
        ...

    # ─── Abstract: introspection ──────────────────────────────────

    @abstractmethod
    def list_databases(self) -> List[str]:
        ...

    @abstractmethod
    def list_tables(self, database: Optional[str] = None) -> List[str]:
        ...

    @abstractmethod
    def get_table_columns(
        self, table_name: str, database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        ...

    @abstractmethod
    def create_data_table(
        self, table_name: str, columns: List[Dict[str, Any]],
    ) -> None:
        ...

    @abstractmethod
    def quote_identifier(self, name: str) -> str:
        """Return the identifier wrapped in the vendor's quoting (backtick / double-quote)."""
        ...

    # ─── Shared: system table init ─────────────────────────────────

    def init_system_tables(self) -> None:
        """Create sync_configs, sync_logs, change_tracking if missing."""
        self.execute("""
            CREATE TABLE IF NOT EXISTS sync_configs (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                spreadsheet_id VARCHAR(128) NOT NULL,
                sheet_id VARCHAR(64) NOT NULL,
                table_name VARCHAR(128) NOT NULL,
                `database` VARCHAR(128) NOT NULL DEFAULT '',
                db_type VARCHAR(16) NOT NULL DEFAULT 'mysql',
                mysql_config_id BIGINT DEFAULT NULL,
                postgresql_config_id BIGINT DEFAULT NULL,
                tencent_config_id BIGINT DEFAULT NULL,
                mapping_json JSON NOT NULL,
                sync_direction ENUM('to_mysql','from_mysql','bidirectional') DEFAULT 'bidirectional',
                poll_interval INT DEFAULT 30,
                last_sync_at DATETIME DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_active TINYINT(1) DEFAULT 1,
                UNIQUE KEY uk_spreadsheet_sheet (spreadsheet_id, sheet_id),
                INDEX idx_active (is_active)
            )
        """)
        self.execute("""
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
            )
        """)
        self.execute("""
            CREATE TABLE IF NOT EXISTS change_tracking (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                config_id BIGINT NOT NULL,
                source_row_key VARCHAR(256) NOT NULL,
                source_hash VARCHAR(64) NOT NULL,
                prev_value TEXT,
                last_sync_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                source ENUM('tencent','mysql') NOT NULL,
                INDEX idx_config_row (config_id, source_row_key),
                UNIQUE KEY uk_config_row (config_id, source_row_key)
            )
        """)
        logger.info("System tables ensured.")

    # ─── Shared: sync config CRUD ──────────────────────────────────

    def get_sync_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        rows = self.execute(
            "SELECT * FROM sync_configs WHERE id = %s AND is_active = 1",
            (config_id,),
        )
        return rows[0] if rows else None

    def list_sync_configs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.execute(
            "SELECT * FROM sync_configs WHERE is_active = 1 ORDER BY id DESC LIMIT %s",
            (limit,),
        ) or []

    def update_sync_config(self, config_id: int, **kwargs) -> bool:
        allowed = {
            "spreadsheet_id", "sheet_id", "table_name", "database",
            "mapping_json", "sync_direction", "poll_interval",
            "is_active", "last_sync_at", "db_type",
            "mysql_config_id", "postgresql_config_id", "tencent_config_id",
        }
        updates = []
        params = []
        for key, value in kwargs.items():
            if key not in allowed:
                continue
            safe_key = validate_identifier(key)
            if key == "mapping_json":
                updates.append("mapping_json = %s")
                params.append(json.dumps(value, ensure_ascii=False))
            elif key == "last_sync_at":
                updates.append("last_sync_at = %s")
                params.append(value)
            else:
                updates.append(f"{self.quote_identifier(safe_key)} = %s")
                params.append(value)

        if not updates:
            return False
        params.append(config_id)
        result = self.execute(
            f"UPDATE sync_configs SET {', '.join(updates)} WHERE id = %s",
            tuple(params),
        )
        return bool(result and result[0].get("affected_rows", 0) > 0)

    def delete_sync_config(self, config_id: int) -> bool:
        return self.update_sync_config(config_id, is_active=0)

    def update_last_sync_time(self, config_id: int) -> None:
        self.execute(
            "UPDATE sync_configs SET last_sync_at = NOW() WHERE id = %s",
            (config_id,),
        )

    # ─── Shared: sync log CRUD ─────────────────────────────────────

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
        self.execute("""
            INSERT INTO sync_logs
                (config_id, direction, rows_affected, rows_new, rows_updated, rows_skipped,
                 status, error_message, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (config_id, direction, rows_affected, rows_new, rows_updated,
              rows_skipped, status, error_message))
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
        self.execute("""
            UPDATE sync_logs
            SET rows_affected=%s, rows_new=%s, rows_updated=%s, rows_skipped=%s,
                status=%s, error_message=%s, completed_at=NOW()
            WHERE id=%s
        """, (rows_affected, rows_new, rows_updated, rows_skipped,
              status, error_message, log_id))

    def get_sync_logs(self, config_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return self.execute("""
            SELECT * FROM sync_logs WHERE config_id = %s
            ORDER BY created_at DESC LIMIT %s
        """, (config_id, limit)) or []

    # ─── Shared: change tracking ───────────────────────────────────

    @staticmethod
    def compute_row_hash(values: List[Any]) -> str:
        """SHA-256 hash of a row's values for incremental change detection."""
        serialized = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_stored_hash(
        self, config_id: int, row_key: str, source: str = "tencent",
    ) -> Optional[str]:
        rows = self.execute(
            "SELECT source_hash FROM change_tracking "
            "WHERE config_id = %s AND source_row_key = %s AND source = %s",
            (config_id, row_key, source),
        )
        return rows[0]["source_hash"] if rows else None

    def upsert_change_record(
        self,
        config_id: int,
        row_key: str,
        source_hash: str,
        source: str = "tencent",
        prev_value: Optional[str] = None,
    ) -> None:
        existing = self.execute(
            "SELECT id FROM change_tracking "
            "WHERE config_id=%s AND source_row_key=%s AND source=%s",
            (config_id, row_key, source),
        )
        if existing:
            self.execute("""
                UPDATE change_tracking
                SET source_hash=%s, prev_value=%s, last_sync_at=NOW()
                WHERE id=%s
            """, (source_hash, prev_value, existing[0]["id"]))
        else:
            self.execute("""
                INSERT INTO change_tracking
                    (config_id, source_row_key, source_hash, prev_value, last_sync_at, source)
                VALUES (%s, %s, %s, %s, NOW(), %s)
            """, (config_id, row_key, source_hash, prev_value, source))

    def cleanup_change_tracking(self, config_id: int, keep_days: int = 90) -> int:
        result = self.execute(
            "DELETE FROM change_tracking WHERE config_id = %s "
            "AND last_sync_at < DATE_SUB(NOW(), INTERVAL %s DAY)",
            (config_id, keep_days),
        )
        return result[0].get("affected_rows", 0) if result else 0


# ─── Factory ───────────────────────────────────────────────────────

def create_database_service(db_type: str, **kwargs) -> DatabaseService:
    """
    Factory: instantiate the correct DatabaseService subclass.

    Args:
        db_type: "mysql" or "postgresql"
        **kwargs: passed to the concrete constructor

    Returns:
        A DatabaseService instance.
    """
    db_type = (db_type or "mysql").lower().strip()
    if db_type == "mysql":
        from app.services.mysql_service import MySQLService
        return MySQLService(**kwargs)
    if db_type in ("postgresql", "postgres", "pg"):
        from app.services.postgresql_service import PostgreSQLService
        return PostgreSQLService(**kwargs)
    raise DatabaseConfigurationError(
        f"Unsupported db_type: {db_type!r}. Use 'mysql' or 'postgresql'."
    )