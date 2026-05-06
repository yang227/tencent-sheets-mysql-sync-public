import os
import sys
import time
from pathlib import Path

import mysql.connector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_config


def wait_for_mysql(host: str, port: int, user: str, password: str, database: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        try:
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                connection_timeout=3,
            )
            conn.close()
            return
        except mysql.connector.Error as exc:
            last_error = exc
            time.sleep(2)

    raise RuntimeError(f"MySQL did not become ready in {timeout_seconds}s: {last_error}")


def apply_sql_file(connection, path: Path) -> None:
    cursor = connection.cursor()
    try:
        sql = path.read_text(encoding="utf-8")
        for _ in cursor.execute(sql, multi=True):
            pass
        connection.commit()
    finally:
        cursor.close()


def main() -> None:
    config = get_config()
    timeout_seconds = int(os.environ.get("METADATA_MYSQL_READY_TIMEOUT", "60"))

    wait_for_mysql(
        host=config.database.host,
        port=config.database.port,
        user=config.database.user,
        password=config.database.password,
        database=config.database.name,
        timeout_seconds=timeout_seconds,
    )

    conn = mysql.connector.connect(
        host=config.database.host,
        port=config.database.port,
        user=config.database.user,
        password=config.database.password,
        database=config.database.name,
    )
    try:
        apply_sql_file(conn, PROJECT_ROOT / "migrations" / "init.sql")
        apply_sql_file(conn, PROJECT_ROOT / "migrations" / "add_config_tables.sql")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
