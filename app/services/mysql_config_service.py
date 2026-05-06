"""
MySQL connection config service.
"""
import logging
from typing import List, Optional

from fastapi import HTTPException

from app.models.config_models import (
    MySQLConfigCreate,
    MySQLConfigResponse,
    MySQLConfigTestResult,
    MySQLConfigUpdate,
    TestStatus,
)
from app.services.mysql_service import MySQLService, get_mysql_service
from app.utils.encryption import decrypt_password, encrypt_password

logger = logging.getLogger(__name__)


class MySQLConfigService:
    """CRUD and runtime helpers for saved MySQL configs."""

    def __init__(self, db: MySQLService):
        self.db = db
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        try:
            result = self.db.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'mysql_configs'"
            )
            if result and result[0]["cnt"] == 0:
                logger.warning(
                    "mysql_configs table is missing; run migrations/add_config_tables.sql"
                )
        except Exception as exc:
            logger.error("Failed to check mysql_configs table: %s", exc)

    def create_config(self, config: MySQLConfigCreate) -> MySQLConfigResponse:
        try:
            encrypted_password = encrypt_password(config.password)
            insert_sql = """
                INSERT INTO mysql_configs
                (name, host, port, username, password_encrypted, database_name, charset, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.execute(
                insert_sql,
                (
                    config.name,
                    config.host,
                    config.port,
                    config.username,
                    encrypted_password,
                    config.database_name,
                    config.charset,
                    config.description,
                ),
            )
            return self.get_config_by_name(config.name)
        except Exception as exc:
            logger.error("Failed to create MySQL config: %s", exc)
            if "Duplicate entry" in str(exc):
                raise HTTPException(status_code=400, detail=f"配置名称 '{config.name}' 已存在")
            raise HTTPException(status_code=500, detail=f"创建配置失败: {exc}") from exc

    def get_config(self, config_id: int) -> Optional[MySQLConfigResponse]:
        try:
            sql = "SELECT * FROM mysql_configs WHERE id = %s AND is_active = 1"
            result = self.db.execute(sql, (config_id,))
            if not result:
                return None
            return self._row_to_response(result[0])
        except Exception as exc:
            logger.error("Failed to get MySQL config: %s", exc)
            raise HTTPException(status_code=500, detail=f"获取配置失败: {exc}") from exc

    def get_config_by_name(self, name: str) -> Optional[MySQLConfigResponse]:
        try:
            sql = "SELECT * FROM mysql_configs WHERE name = %s AND is_active = 1"
            result = self.db.execute(sql, (name,))
            if not result:
                return None
            return self._row_to_response(result[0])
        except Exception as exc:
            logger.error("Failed to get MySQL config by name: %s", exc)
            raise HTTPException(status_code=500, detail=f"获取配置失败: {exc}") from exc

    def list_configs(self, skip: int = 0, limit: int = 100) -> List[MySQLConfigResponse]:
        try:
            sql = """
                SELECT * FROM mysql_configs
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            result = self.db.execute(sql, (limit, skip))
            return [self._row_to_response(row) for row in result]
        except Exception as exc:
            logger.error("Failed to list MySQL configs: %s", exc)
            raise HTTPException(status_code=500, detail=f"列出配置失败: {exc}") from exc

    def update_config(
        self,
        config_id: int,
        config: MySQLConfigUpdate,
    ) -> Optional[MySQLConfigResponse]:
        try:
            update_fields = []
            params = []

            if config.name is not None:
                update_fields.append("name = %s")
                params.append(config.name)
            if config.host is not None:
                update_fields.append("host = %s")
                params.append(config.host)
            if config.port is not None:
                update_fields.append("port = %s")
                params.append(config.port)
            if config.username is not None:
                update_fields.append("username = %s")
                params.append(config.username)
            if config.password is not None:
                update_fields.append("password_encrypted = %s")
                params.append(encrypt_password(config.password))
            if config.database_name is not None:
                update_fields.append("database_name = %s")
                params.append(config.database_name)
            if config.charset is not None:
                update_fields.append("charset = %s")
                params.append(config.charset)
            if config.description is not None:
                update_fields.append("description = %s")
                params.append(config.description)
            if config.is_active is not None:
                update_fields.append("is_active = %s")
                params.append(1 if config.is_active else 0)

            if not update_fields:
                raise HTTPException(status_code=400, detail="没有需要更新的字段")

            params.append(config_id)
            update_sql = (
                f"UPDATE mysql_configs SET {', '.join(update_fields)} "
                "WHERE id = %s AND is_active = 1"
            )
            self.db.execute(update_sql, tuple(params))
            return self.get_config(config_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to update MySQL config: %s", exc)
            if "Duplicate entry" in str(exc):
                raise HTTPException(status_code=400, detail="配置名称已存在")
            raise HTTPException(status_code=500, detail=f"更新配置失败: {exc}") from exc

    def delete_config(self, config_id: int) -> bool:
        try:
            sql = "UPDATE mysql_configs SET is_active = 0 WHERE id = %s AND is_active = 1"
            self.db.execute(sql, (config_id,))
            return True
        except Exception as exc:
            logger.error("Failed to delete MySQL config: %s", exc)
            raise HTTPException(status_code=500, detail=f"删除配置失败: {exc}") from exc

    def test_connection(self, config_id: int) -> MySQLConfigTestResult:
        try:
            runtime_service = self.build_mysql_service(config_id)
            result = runtime_service.test_connection()
            if result.get("connected"):
                self._update_test_status(config_id, TestStatus.SUCCESS, "连接成功")
                return MySQLConfigTestResult(success=True, message="数据库连接成功")

            error_msg = result.get("error", "Unknown connection error")
            self._update_test_status(config_id, TestStatus.FAILED, error_msg)
            return MySQLConfigTestResult(
                success=False,
                message="数据库连接失败",
                error=error_msg,
            )
        except HTTPException as exc:
            self._update_test_status(config_id, TestStatus.FAILED, str(exc.detail))
            return MySQLConfigTestResult(
                success=False,
                message="数据库连接失败",
                error=str(exc.detail),
            )
        except Exception as exc:
            logger.error("Failed to test MySQL config connection: %s", exc)
            self._update_test_status(config_id, TestStatus.FAILED, str(exc))
            return MySQLConfigTestResult(
                success=False,
                message="测试连接时发生错误",
                error=str(exc),
            )

    def _update_test_status(self, config_id: int, status: TestStatus, message: str) -> None:
        try:
            sql = """
                UPDATE mysql_configs
                SET test_status = %s, test_message = %s, last_tested_at = NOW()
                WHERE id = %s
            """
            self.db.execute(sql, (status.value, message, config_id))
        except Exception as exc:
            logger.error("Failed to update MySQL config test status: %s", exc)

    def _row_to_response(self, row: dict) -> MySQLConfigResponse:
        return MySQLConfigResponse(
            id=row["id"],
            name=row["name"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            database_name=row["database_name"],
            charset=row["charset"],
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_tested_at=row.get("last_tested_at"),
            test_status=TestStatus(row.get("test_status", "untested")),
            test_message=row.get("test_message"),
        )

    def get_decrypted_password(self, config_id: int) -> Optional[str]:
        try:
            sql = "SELECT password_encrypted FROM mysql_configs WHERE id = %s AND is_active = 1"
            result = self.db.execute(sql, (config_id,))
            if not result:
                return None
            return decrypt_password(result[0]["password_encrypted"])
        except Exception as exc:
            logger.error("Failed to decrypt MySQL password: %s", exc)
            return None

    def build_mysql_service(
        self,
        config_id: int,
        config_row: Optional[dict] = None,
    ) -> MySQLService:
        if config_row is None:
            sql = "SELECT * FROM mysql_configs WHERE id = %s AND is_active = 1"
            result = self.db.execute(sql, (config_id,))
            if not result:
                raise HTTPException(status_code=404, detail="Config not found")
            config_row = result[0]

        try:
            password = decrypt_password(config_row["password_encrypted"])
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"密码解密失败: {exc}") from exc

        return MySQLService(
            host=config_row["host"],
            port=config_row["port"],
            user=config_row["username"],
            password=password,
            database=config_row["database_name"],
        )


def get_mysql_config_service(db: MySQLService = None) -> MySQLConfigService:
    if db is None:
        db = get_mysql_service()
    return MySQLConfigService(db)
