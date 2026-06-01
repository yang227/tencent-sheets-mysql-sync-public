"""
PostgreSQL connection config service — mirrors MySQLConfigService.
"""
import logging
from typing import List, Optional

from fastapi import HTTPException

from app.models.postgresql_config_models import (
    PostgreSQLConfigCreate,
    PostgreSQLConfigResponse,
    PostgreSQLConfigTestResult,
    PostgreSQLConfigUpdate,
    TestStatus,
)
from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.postgresql_service import PostgreSQLService
from app.services.db_exception import (
    DatabaseConnectionError,
    DatabaseServiceError,
    handle_service_exception,
)
from app.utils.encryption import decrypt_password, encrypt_password

logger = logging.getLogger(__name__)


class PostgreSQLConfigService:
    """CRUD and runtime helpers for saved PostgreSQL configs."""

    def __init__(self, db: MySQLService):
        self.db = db
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        try:
            result = self.db.execute(
                "SELECT COUNT(*) AS cnt FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'postgresql_configs'"
            )
            if result and result[0]["cnt"] == 0:
                logger.warning(
                    "postgresql_configs table missing; run migrations/add_config_tables.sql"
                )
        except Exception as exc:
            logger.error("Failed to check postgresql_configs table: %s", exc)

    def create_config(self, config: PostgreSQLConfigCreate) -> PostgreSQLConfigResponse:
        try:
            encrypted_password = encrypt_password(config.password)
            self.db.execute(
                """INSERT INTO postgresql_configs
                   (name, host, port, username, password_encrypted,
                    database_name, schema_name, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    config.name, config.host, config.port, config.username,
                    encrypted_password, config.database_name,
                    config.schema_name, config.description,
                ),
            )
            return self.get_config_by_name(config.name)
        except DatabaseServiceError as exc:
            if "Duplicate" in str(exc):
                raise HTTPException(status_code=400, detail=f"Config name '{config.name}' already exists")
            raise handle_service_exception(exc, "create_pg_config")
        except Exception as exc:
            if "Duplicate" in str(exc):
                raise HTTPException(status_code=400, detail=f"Config name '{config.name}' already exists")
            raise handle_service_exception(exc, "create_pg_config")

    def get_config(self, config_id: int) -> Optional[PostgreSQLConfigResponse]:
        try:
            result = self.db.execute(
                "SELECT * FROM postgresql_configs WHERE id = %s AND is_active = 1",
                (config_id,),
            )
            return self._row_to_response(result[0]) if result else None
        except DatabaseServiceError as exc:
            raise handle_service_exception(exc, "get_pg_config")

    def get_config_by_name(self, name: str) -> Optional[PostgreSQLConfigResponse]:
        try:
            result = self.db.execute(
                "SELECT * FROM postgresql_configs WHERE name = %s AND is_active = 1",
                (name,),
            )
            return self._row_to_response(result[0]) if result else None
        except DatabaseServiceError as exc:
            raise handle_service_exception(exc, "get_pg_config_by_name")

    def list_configs(self, skip: int = 0, limit: int = 100) -> List[PostgreSQLConfigResponse]:
        try:
            result = self.db.execute(
                """SELECT * FROM postgresql_configs
                   WHERE is_active = 1 ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (limit, skip),
            )
            return [self._row_to_response(r) for r in (result or [])]
        except DatabaseServiceError as exc:
            raise handle_service_exception(exc, "list_pg_configs")

    def update_config(
        self, config_id: int, config: PostgreSQLConfigUpdate,
    ) -> Optional[PostgreSQLConfigResponse]:
        try:
            update_fields = []
            params = []

            for field_name, value in config.model_dump(exclude_unset=True).items():
                if value is None:
                    continue
                if field_name == "password":
                    update_fields.append("password_encrypted = %s")
                    params.append(encrypt_password(value))
                else:
                    update_fields.append(f"{field_name} = %s")
                    params.append(value)

            if not update_fields:
                return self.get_config(config_id)

            params.append(config_id)
            self.db.execute(
                f"UPDATE postgresql_configs SET {', '.join(update_fields)} WHERE id = %s",
                tuple(params),
            )
            return self.get_config(config_id)
        except DatabaseServiceError as exc:
            if "Duplicate" in str(exc):
                raise HTTPException(status_code=400, detail="Config name already exists")
            raise handle_service_exception(exc, "update_pg_config")

    def delete_config(self, config_id: int) -> bool:
        try:
            self.db.execute(
                "UPDATE postgresql_configs SET is_active = 0 WHERE id = %s AND is_active = 1",
                (config_id,),
            )
            return True
        except DatabaseServiceError as exc:
            raise handle_service_exception(exc, "delete_pg_config")

    def test_connection(self, config_id: int) -> PostgreSQLConfigTestResult:
        try:
            runtime_service = self.build_postgresql_service(config_id)
            result = runtime_service.test_connection()
            runtime_service.close()

            if result.get("connected"):
                self._update_test_status(config_id, TestStatus.success, "Connection successful")
                return PostgreSQLConfigTestResult(
                    success=True, message="PostgreSQL connection successful",
                    version=result.get("version"), database=result.get("database"),
                )

            error_msg = result.get("error", "Unknown connection error")
            self._update_test_status(config_id, TestStatus.failed, error_msg)
            return PostgreSQLConfigTestResult(
                success=False, message="Connection failed", error=error_msg,
            )
        except Exception as exc:
            self._update_test_status(config_id, TestStatus.failed, str(exc))
            return PostgreSQLConfigTestResult(
                success=False, message="Connection test error", error=str(exc),
            )

    def build_postgresql_service(
        self, config_id: int, config_row: Optional[dict] = None,
    ) -> PostgreSQLService:
        if config_row is None:
            result = self.db.execute(
                "SELECT * FROM postgresql_configs WHERE id = %s AND is_active = 1",
                (config_id,),
            )
            if not result:
                raise HTTPException(status_code=404, detail="PostgreSQL config not found")
            config_row = result[0]

        try:
            password = decrypt_password(config_row["password_encrypted"])
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Password decryption failed: {exc}"
            ) from exc

        return PostgreSQLService(
            host=config_row["host"],
            port=config_row["port"],
            user=config_row["username"],
            password=password,
            database=config_row["database_name"],
        )

    def _update_test_status(self, config_id: int, status: TestStatus, message: str) -> None:
        try:
            self.db.execute(
                """UPDATE postgresql_configs
                   SET test_status = %s, test_message = %s, last_tested_at = NOW()
                   WHERE id = %s""",
                (status.value, message, config_id),
            )
        except Exception as exc:
            logger.error("Failed to update PG config test status: %s", exc)

    def _row_to_response(self, row: dict) -> PostgreSQLConfigResponse:
        return PostgreSQLConfigResponse(
            id=row["id"],
            name=row["name"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            database_name=row["database_name"],
            schema_name=row.get("schema_name", "public"),
            description=row.get("description"),
            is_active=bool(row["is_active"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            last_tested_at=row.get("last_tested_at"),
            test_status=TestStatus(row.get("test_status", "untested")),
            test_message=row.get("test_message"),
        )


def get_postgresql_config_service(db: MySQLService = None) -> PostgreSQLConfigService:
    if db is None:
        db = get_mysql_service()
    return PostgreSQLConfigService(db)