"""
MySQL Service — concrete DatabaseService subclass.

All shared logic lives in DatabaseService; this module overrides only
MySQL-specific behavior (connector, quoting, introspection queries).
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import mysql.connector
from mysql.connector import pooling, Error as MySQLError

from app.config import get_settings
from app.services.database_service import (
    DatabaseService,
    validate_identifier,
    validate_identifier_list,
    validate_data_type,
)
from app.services.db_exception import (
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseTimeoutError,
    DatabaseIntegrityError,
    DatabaseServiceError,
    IdentifierValidationError,
    DatabaseTypeValidationError,
)

logger = logging.getLogger(__name__)


# ─── MySQL-specific identifier validation ──────────────────────────

VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_@$]*$")

# Whitelist of allowed MySQL data types
ALLOWED_MYSQL_TYPES = {
    "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT",
    "FLOAT", "DOUBLE", "DECIMAL",
    "VARCHAR", "CHAR", "TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
    "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
    "DATE", "TIME", "DATETIME", "TIMESTAMP", "YEAR",
    "BOOLEAN", "BOOL", "JSON",
}


class MySQLService(DatabaseService):
    """
    MySQL operations service with per-instance connection pooling.
    """

    DB_TYPE: str = "mysql"

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
        settings = get_settings()
        _host = host or settings.database.host
        _port = port or settings.database.port
        _user = user or settings.database.user
        _password = password or settings.database.password
        _database = database or settings.database.name

        super().__init__(
            host=_host, port=_port, user=_user, password=_password,
            database=_database, pool_size=pool_size, connect_timeout=connect_timeout,
        )

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

    # ─── Pool lifecycle ────────────────────────────────────────────

    def _get_pool(self) -> pooling.MySQLConnectionPool:
        if self._pool is None:
            try:
                self._pool = pooling.MySQLConnectionPool(**self._pool_config)
            except MySQLError as exc:
                raise DatabaseConnectionError(
                    f"MySQL pool creation failed: {exc.msg}",
                    db_type="mysql",
                    cause=exc,
                ) from exc
        return self._pool

    def close(self) -> None:
        self._pool = None
        logger.info("MySQL connection pool closed.")

    # ─── Execute ───────────────────────────────────────────────────

    def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        pool = self._get_pool()
        conn = None
        cursor = None
        try:
            conn = pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)

            if cursor.with_rows:
                rows = cursor.fetchall()
                conn.commit()
                return rows

            conn.commit()
            return [{"affected_rows": cursor.rowcount}]

        except MySQLError as exc:
            if conn:
                try:
                    conn.rollback()
                except MySQLError:
                    pass
            msg = exc.msg if hasattr(exc, "msg") else str(exc)

            # Classify
            errno = getattr(exc, "errno", 0)
            if errno in (1045, 2003, 2005):
                raise DatabaseConnectionError(
                    msg, db_type="mysql", query=query, cause=exc,
                ) from exc
            if errno in (1062, 1451, 1452, 1048):
                raise DatabaseIntegrityError(
                    msg, db_type="mysql", query=query, cause=exc,
                ) from exc
            if errno in (1205, 1213, 2006, 2013):
                raise DatabaseTimeoutError(
                    msg, db_type="mysql", query=query, cause=exc,
                ) from exc
            raise DatabaseQueryError(
                msg, db_type="mysql", query=query, cause=exc,
            ) from exc

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseQueryError(
                f"Unexpected MySQL error: {exc}",
                db_type="mysql", query=query, cause=exc,
            ) from exc

        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def execute_many(
        self,
        query: str,
        params_list: List[tuple],
    ) -> int:
        if not params_list:
            return 0
        pool = self._get_pool()
        conn = None
        cursor = None
        try:
            conn = pool.get_connection()
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            affected = cursor.rowcount
            conn.commit()
            return affected

        except MySQLError as exc:
            if conn:
                try:
                    conn.rollback()
                except MySQLError:
                    pass
            errno = getattr(exc, "errno", 0)
            msg = exc.msg if hasattr(exc, "msg") else str(exc)
            if errno in (1062, 1451, 1452, 1048):
                raise DatabaseIntegrityError(
                    msg, db_type="mysql", query=query, cause=exc,
                ) from exc
            raise DatabaseQueryError(
                msg, db_type="mysql", query=query, cause=exc,
            ) from exc

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseQueryError(
                f"Unexpected MySQL executemany error: {exc}",
                db_type="mysql", query=query, cause=exc,
            ) from exc

        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ─── Identifier quoting ────────────────────────────────────────

    def quote_identifier(self, name: str) -> str:
        return f"`{name}`"

    # ─── Introspection ─────────────────────────────────────────────

    def list_databases(self) -> List[str]:
        rows = self.execute("SHOW DATABASES") or []
        return [
            r[list(r.keys())[0]]
            for r in rows
            if r[list(r.keys())[0]] not in ("information_schema", "mysql", "performance_schema", "sys")
        ]

    def list_tables(self, database: Optional[str] = None) -> List[str]:
        if database:
            safe_db = validate_identifier(database, allow_hyphen=True)
            rows = self.execute(f"SHOW TABLES FROM {self.quote_identifier(safe_db)}") or []
        else:
            rows = self.execute("SHOW TABLES") or []
        return [r[list(r.keys())[0]] for r in rows]

    def get_table_columns(
        self, table_name: str, database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        safe_table = validate_identifier(table_name)
        if database:
            safe_db = validate_identifier(database, allow_hyphen=True)
            table_expr = f"{self.quote_identifier(safe_db)}.{self.quote_identifier(safe_table)}"
        else:
            table_expr = self.quote_identifier(safe_table)
        return self.execute(f"SHOW COLUMNS FROM {table_expr}") or []

    def table_exists(self, table_name: str) -> bool:
        safe_table = validate_identifier(table_name)
        rows = self.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            (safe_table,),
        )
        return bool(rows and rows[0]["cnt"] > 0)

    # ─── DDL helpers ───────────────────────────────────────────────

    def create_data_table(
        self, table_name: str, columns: List[Dict[str, Any]],
    ) -> None:
        safe_name = validate_identifier(table_name)
        if not columns:
            raise DatabaseServiceError("Cannot create table with no columns", db_type="mysql")

        col_defs = []
        for col in columns:
            db_col = validate_identifier(col.get("db_column", ""))
            dtype = col.get("db_type", "TEXT")
            _validate_mysql_type(dtype)

            parts = [self.quote_identifier(db_col), dtype]
            if col.get("primary_key"):
                parts.append("NOT NULL")
            else:
                parts.append("DEFAULT NULL")
            col_defs.append(" ".join(parts))

        pk_cols = [
            self.quote_identifier(validate_identifier(c["db_column"]))
            for c in columns if c.get("primary_key")
        ]
        if pk_cols:
            col_defs.append(f"PRIMARY KEY ({', '.join(pk_cols)})")

        ddl = f"CREATE TABLE {self.quote_identifier(safe_name)} ({', '.join(col_defs)})"
        self.execute(ddl)
        logger.info("Created MySQL table: %s", safe_name)

    # ─── MySQL-specific: list_mysql_* (backward compat) ───────────

    def list_mysql_databases(self) -> List[str]:
        return self.list_databases()

    def list_mysql_tables(self, database: str) -> List[str]:
        return self.list_tables(database)

    # ─── Connection test ───────────────────────────────────────────

    def test_connection(self) -> Dict[str, Any]:
        try:
            result = self.execute("SELECT VERSION() AS version, DATABASE() AS db")
            if result:
                return {
                    "connected": True,
                    "database": result[0].get("db"),
                    "version": result[0].get("version"),
                    "db_type": "mysql",
                }
            return {"connected": False, "error": "No result returned", "db_type": "mysql"}
        except DatabaseServiceError as exc:
            return {"connected": False, "error": str(exc), "db_type": "mysql"}


def _validate_identifier(name: str, allow_hyphen: bool = False) -> str:
    """Backward-compatible module-level alias."""
    return validate_identifier(name, allow_hyphen=allow_hyphen)


def _validate_identifier_list(identifiers: List[str]) -> List[str]:
    return validate_identifier_list(identifiers)


def _validate_mysql_type(type_str: str) -> str:
    """Validate a MySQL data type string."""
    if not type_str:
        raise DatabaseTypeValidationError("Data type cannot be empty")
    base = type_str.strip().upper().split("(")[0].strip()
    if base not in ALLOWED_MYSQL_TYPES:
        raise DatabaseTypeValidationError(f"Invalid MySQL data type: {type_str}")
    if any(c in type_str for c in ";--/*"):
        raise DatabaseTypeValidationError(f"Invalid characters in type: {type_str}")
    return type_str


def _validate_sql_in_identifier_list(identifiers: List[str]) -> List[str]:
    return validate_identifier_list(identifiers)


# ─── Legacy aliases for backward compatibility ─────────────────────

class MySQLServiceError(DatabaseServiceError):
    """Backward-compatible alias."""
    pass


# ─── Singleton accessor ────────────────────────────────────────────

_mysql_service: Optional[MySQLService] = None


def get_mysql_service() -> MySQLService:
    global _mysql_service
    if _mysql_service is None:
        _mysql_service = MySQLService()
    return _mysql_service


def reset_mysql_service() -> None:
    global _mysql_service
    _mysql_service = None