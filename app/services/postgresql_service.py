"""
PostgreSQL Service — concrete DatabaseService subclass.

Uses psycopg2 for connection pooling and async-compatible sync operations.
Shares all common logic from DatabaseService; overrides only
PostgreSQL-specific introspection, quoting, and connector behavior.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2 import pool, sql as pg_sql
    from psycopg2.extras import RealDictCursor
    from psycopg2.errors import (
        OperationalError,
        InterfaceError,
        ProgrammingError,
        IntegrityError as PgIntegrityError,
        QueryCanceledError,
    )
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False

from app.services.database_service import (
    DatabaseService,
    validate_identifier,
    validate_data_type,
)
from app.services.db_exception import (
    DatabaseConnectionError,
    DatabaseConfigurationError,
    DatabaseQueryError,
    DatabaseTimeoutError,
    DatabaseIntegrityError,
    DatabaseServiceError,
    DatabaseTypeValidationError,
)

logger = logging.getLogger(__name__)

# PostgreSQL-specific type whitelist
ALLOWED_PG_TYPES = {
    "SMALLINT", "INTEGER", "BIGINT", "SERIAL", "BIGSERIAL",
    "REAL", "DOUBLE PRECISION", "DECIMAL", "NUMERIC",
    "VARCHAR", "CHAR", "TEXT",
    "BYTEA",
    "DATE", "TIME", "TIMESTAMP", "TIMESTAMPTZ", "INTERVAL",
    "BOOLEAN", "JSON", "JSONB", "UUID",
}


def _validate_pg_type(type_str: str) -> str:
    """Validate a PostgreSQL column type against the whitelist."""
    if not type_str:
        raise DatabaseTypeValidationError("PostgreSQL data type cannot be empty")
    base = type_str.strip().upper()
    # Handle types like VARCHAR(255), NUMERIC(10,2)
    if "(" in base:
        base = base.split("(")[0].strip()
    # Handle "DOUBLE PRECISION" etc.
    if base not in ALLOWED_PG_TYPES:
        raise DatabaseTypeValidationError(f"Disallowed PostgreSQL type: {type_str}")
    if any(c in type_str for c in ";--/*"):
        raise DatabaseTypeValidationError(f"Invalid characters in type: {type_str}")
    return type_str


class PostgreSQLService(DatabaseService):
    """
    PostgreSQL operations service with connection pooling.
    """

    DB_TYPE: str = "postgresql"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "tencent_sheets_sync",
        pool_size: int = 5,
        connect_timeout: int = 3,
        **kwargs,
    ):
        if not _PSYCOPG2_AVAILABLE:
            raise DatabaseConfigurationError(
                "psycopg2 is not installed. Install it with: pip install psycopg2-binary",
                db_type="postgresql",
            )

        super().__init__(
            host=host, port=port, user=user, password=password,
            database=database, pool_size=pool_size, connect_timeout=connect_timeout,
        )
        self._pool = None

    def _get_pool(self):
        if self._pool is None or self._pool.closed:
            try:
                self._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=self.pool_size,
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    dbname=self.database,
                    connect_timeout=self.connect_timeout,
                    options="-c client_encoding=UTF8",
                )
            except OperationalError as exc:
                raise DatabaseConnectionError(
                    f"PostgreSQL pool creation failed: {exc}",
                    db_type="postgresql",
                    cause=exc,
                ) from exc
        return self._pool

    def close(self) -> None:
        if self._pool and not self._pool.closed:
            self._pool.closeall()
        self._pool = None
        logger.info("PostgreSQL connection pool closed.")

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
            conn = pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)

            if cursor.description:
                rows = [dict(r) for r in cursor.fetchall()]
                conn.commit()
                return rows

            conn.commit()
            return [{"affected_rows": cursor.rowcount}]

        except PgIntegrityError as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseIntegrityError(
                str(exc), db_type="postgresql", query=query, cause=exc,
            ) from exc

        except QueryCanceledError as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseTimeoutError(
                str(exc), db_type="postgresql", query=query, cause=exc,
            ) from exc

        except (OperationalError, InterfaceError) as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseConnectionError(
                str(exc), db_type="postgresql", query=query, cause=exc,
            ) from exc

        except ProgrammingError as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseQueryError(
                str(exc), db_type="postgresql", query=query, cause=exc,
            ) from exc

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseQueryError(
                f"Unexpected PostgreSQL error: {exc}",
                db_type="postgresql", query=query, cause=exc,
            ) from exc

        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    pool.putconn(conn)
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
            conn = pool.getconn()
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            affected = cursor.rowcount
            conn.commit()
            return affected

        except PgIntegrityError as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseIntegrityError(
                str(exc), db_type="postgresql", query=query, cause=exc,
            ) from exc

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise DatabaseQueryError(
                f"PostgreSQL executemany error: {exc}",
                db_type="postgresql", query=query, cause=exc,
            ) from exc

        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    pool.putconn(conn)
                except Exception:
                    pass

    # ─── Identifier quoting ────────────────────────────────────────

    def quote_identifier(self, name: str) -> str:
        return f'"{name}"'

    # ─── Introspection ─────────────────────────────────────────────

    def list_databases(self) -> List[str]:
        rows = self.execute(
            "SELECT datname FROM pg_database WHERE datistemplate = false "
            "ORDER BY datname"
        ) or []
        return [r["datname"] for r in rows]

    def list_tables(self, database: Optional[str] = None) -> List[str]:
        # PostgreSQL: list tables in current database (ignore database param
        # since each connection is to a specific database)
        rows = self.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ) or []
        return [r["table_name"] for r in rows]

    def get_table_columns(
        self, table_name: str, database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        safe_table = validate_identifier(table_name)
        rows = self.execute(
            "SELECT column_name, data_type, is_nullable, column_default, "
            "       character_maximum_length, numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (safe_table,),
        ) or []
        result = []
        for r in rows:
            dtype = r["data_type"]
            if r.get("character_maximum_length"):
                dtype = f"{dtype}({r['character_maximum_length']})"
            elif r.get("numeric_precision") and r.get("numeric_scale"):
                dtype = f"{dtype}({r['numeric_precision']},{r['numeric_scale']})"
            result.append({
                "COLUMN_NAME": r["column_name"],
                "DATA_TYPE": dtype,
                "IS_NULLABLE": r["is_nullable"],
                "COLUMN_KEY": "",
                "COLUMN_DEFAULT": r["column_default"],
                "EXTRA": "",
            })
        return result

    def table_exists(self, table_name: str) -> bool:
        safe_table = validate_identifier(table_name)
        rows = self.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s",
            (safe_table,),
        )
        return bool(rows and rows[0]["cnt"] > 0)

    # ─── DDL helpers ───────────────────────────────────────────────

    def create_data_table(
        self, table_name: str, columns: List[Dict[str, Any]],
    ) -> None:
        safe_name = validate_identifier(table_name)
        if not columns:
            raise DatabaseServiceError(
                "Cannot create table with no columns", db_type="postgresql"
            )

        col_defs = []
        for col in columns:
            db_col = validate_identifier(col.get("db_column", ""))
            raw_type = col.get("db_type", "TEXT")
            # Map MySQL types to PostgreSQL equivalents
            pg_type = _mysql_to_pg_type(raw_type)
            _validate_pg_type(pg_type)

            parts = [self.quote_identifier(db_col), pg_type]
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

        ddl = f'CREATE TABLE {self.quote_identifier(safe_name)} ({", ".join(col_defs)})'
        self.execute(ddl)
        logger.info("Created PostgreSQL table: %s", safe_name)

    # ─── Connection test ───────────────────────────────────────────

    def test_connection(self) -> Dict[str, Any]:
        try:
            result = self.execute("SELECT version() AS version, current_database() AS db")
            if result:
                return {
                    "connected": True,
                    "database": result[0].get("db"),
                    "version": result[0].get("version"),
                    "db_type": "postgresql",
                }
            return {"connected": False, "error": "No result returned", "db_type": "postgresql"}
        except DatabaseServiceError as exc:
            return {"connected": False, "error": str(exc), "db_type": "postgresql"}

    # ─── Override: init_system_tables is a no-op for PostgreSQL ────
    # (metadata DB remains MySQL; this service is only for sync targets)

    def init_system_tables(self) -> None:
        logger.info("PostgreSQL service: skipping system table init (metadata stays in MySQL).")


# ─── MySQL → PostgreSQL type mapping ──────────────────────────────

_MYSQL_TO_PG_MAP = {
    "INT": "INTEGER",
    "INTEGER": "INTEGER",
    "BIGINT": "BIGINT",
    "SMALLINT": "SMALLINT",
    "TINYINT": "SMALLINT",
    "MEDIUMINT": "INTEGER",
    "FLOAT": "REAL",
    "DOUBLE": "DOUBLE PRECISION",
    "DECIMAL": "NUMERIC",
    "VARCHAR": "VARCHAR",
    "CHAR": "CHAR",
    "TEXT": "TEXT",
    "TINYTEXT": "TEXT",
    "MEDIUMTEXT": "TEXT",
    "LONGTEXT": "TEXT",
    "BLOB": "BYTEA",
    "TINYBLOB": "BYTEA",
    "MEDIUMBLOB": "BYTEA",
    "LONGBLOB": "BYTEA",
    "DATE": "DATE",
    "TIME": "TIME",
    "DATETIME": "TIMESTAMP",
    "TIMESTAMP": "TIMESTAMPTZ",
    "YEAR": "SMALLINT",
    "BOOLEAN": "BOOLEAN",
    "BOOL": "BOOLEAN",
    "JSON": "JSONB",
}


def _mysql_to_pg_type(mysql_type: str) -> str:
    """Convert a MySQL type string to its PostgreSQL equivalent."""
    base = mysql_type.strip().upper().split("(")[0].strip()
    pg_base = _MYSQL_TO_PG_MAP.get(base, mysql_type)
    # Preserve length specifier for VARCHAR/CHAR/NUMERIC
    if "(" in mysql_type and pg_base in ("VARCHAR", "CHAR", "NUMERIC"):
        suffix = mysql_type[mysql_type.index("("):]
        return pg_base + suffix
    return pg_base