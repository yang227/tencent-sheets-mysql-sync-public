"""
Tencent API config service.
"""
import logging
from typing import List, Optional

from fastapi import HTTPException

from app.models.config_models import (
    TencentApiConfigCreate,
    TencentApiConfigResponse,
    TencentApiConfigTestResult,
    TencentApiConfigUpdate,
    TestStatus,
)
from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.tencent_api import TencentAPI, TencentAPIError
from app.utils.encryption import decrypt_password, encrypt_password

logger = logging.getLogger(__name__)


class TencentApiConfigService:
    """CRUD and runtime helpers for saved Tencent configs."""

    def __init__(self, db: MySQLService):
        self.db = db
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        try:
            result = self.db.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'tencent_api_configs'"
            )
            if result and result[0]["cnt"] == 0:
                logger.warning(
                    "tencent_api_configs table is missing; run migrations/add_config_tables.sql"
                )
        except Exception as exc:
            logger.error("Failed to check tencent_api_configs table: %s", exc)

    def create_config(self, config: TencentApiConfigCreate) -> TencentApiConfigResponse:
        try:
            encrypted_token = encrypt_password(config.access_token)
            insert_sql = """
                INSERT INTO tencent_api_configs
                (name, app_id, open_id, access_token_encrypted, description, token_expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.execute(
                insert_sql,
                (
                    config.name,
                    config.app_id,
                    config.open_id,
                    encrypted_token,
                    config.description,
                    config.token_expires_at,
                ),
            )
            return self.get_config_by_name(config.name)
        except Exception as exc:
            logger.error("Failed to create Tencent config: %s", exc)
            if "Duplicate entry" in str(exc):
                raise HTTPException(status_code=400, detail=f"配置名称 '{config.name}' 已存在")
            raise HTTPException(status_code=500, detail=f"创建配置失败: {exc}") from exc

    def get_config(self, config_id: int) -> Optional[TencentApiConfigResponse]:
        try:
            sql = "SELECT * FROM tencent_api_configs WHERE id = %s AND is_active = 1"
            result = self.db.execute(sql, (config_id,))
            if not result:
                return None
            return self._row_to_response(result[0])
        except Exception as exc:
            logger.error("Failed to get Tencent config: %s", exc)
            raise HTTPException(status_code=500, detail=f"获取配置失败: {exc}") from exc

    def get_config_by_name(self, name: str) -> Optional[TencentApiConfigResponse]:
        try:
            sql = "SELECT * FROM tencent_api_configs WHERE name = %s AND is_active = 1"
            result = self.db.execute(sql, (name,))
            if not result:
                return None
            return self._row_to_response(result[0])
        except Exception as exc:
            logger.error("Failed to get Tencent config by name: %s", exc)
            raise HTTPException(status_code=500, detail=f"获取配置失败: {exc}") from exc

    def list_configs(self, skip: int = 0, limit: int = 100) -> List[TencentApiConfigResponse]:
        try:
            sql = """
                SELECT * FROM tencent_api_configs
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            result = self.db.execute(sql, (limit, skip))
            return [self._row_to_response(row) for row in result]
        except Exception as exc:
            logger.error("Failed to list Tencent configs: %s", exc)
            raise HTTPException(status_code=500, detail=f"列出配置失败: {exc}") from exc

    def update_config(
        self,
        config_id: int,
        config: TencentApiConfigUpdate,
    ) -> Optional[TencentApiConfigResponse]:
        try:
            update_fields = []
            params = []

            if config.name is not None:
                update_fields.append("name = %s")
                params.append(config.name)
            if config.app_id is not None:
                update_fields.append("app_id = %s")
                params.append(config.app_id)
            if config.open_id is not None:
                update_fields.append("open_id = %s")
                params.append(config.open_id)
            if config.access_token is not None:
                update_fields.append("access_token_encrypted = %s")
                params.append(encrypt_password(config.access_token))
            if config.description is not None:
                update_fields.append("description = %s")
                params.append(config.description)
            if config.is_active is not None:
                update_fields.append("is_active = %s")
                params.append(1 if config.is_active else 0)
            if config.token_expires_at is not None:
                update_fields.append("token_expires_at = %s")
                params.append(config.token_expires_at)

            if not update_fields:
                raise HTTPException(status_code=400, detail="没有需要更新的字段")

            params.append(config_id)
            update_sql = (
                f"UPDATE tencent_api_configs SET {', '.join(update_fields)} "
                "WHERE id = %s AND is_active = 1"
            )
            self.db.execute(update_sql, tuple(params))
            return self.get_config(config_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to update Tencent config: %s", exc)
            if "Duplicate entry" in str(exc):
                raise HTTPException(status_code=400, detail="配置名称已存在")
            raise HTTPException(status_code=500, detail=f"更新配置失败: {exc}") from exc

    def delete_config(self, config_id: int) -> bool:
        try:
            sql = "UPDATE tencent_api_configs SET is_active = 0 WHERE id = %s AND is_active = 1"
            self.db.execute(sql, (config_id,))
            return True
        except Exception as exc:
            logger.error("Failed to delete Tencent config: %s", exc)
            raise HTTPException(status_code=500, detail=f"删除配置失败: {exc}") from exc

    def test_connection(self, config_id: int) -> TencentApiConfigTestResult:
        try:
            api = self.build_tencent_api(config_id)
            if api.access_token and api.app_id and api.open_id:
                self._update_test_status(config_id, TestStatus.SUCCESS, "Token 校验成功")
                return TencentApiConfigTestResult(success=True, message="腾讯配置可用")

            error_msg = "Missing required Tencent runtime fields"
            self._update_test_status(config_id, TestStatus.FAILED, error_msg)
            return TencentApiConfigTestResult(success=False, message="腾讯配置不可用", error=error_msg)
        except HTTPException as exc:
            self._update_test_status(config_id, TestStatus.FAILED, str(exc.detail))
            return TencentApiConfigTestResult(
                success=False,
                message="腾讯配置不可用",
                error=str(exc.detail),
            )
        except Exception as exc:
            logger.error("Failed to test Tencent config connection: %s", exc)
            self._update_test_status(config_id, TestStatus.FAILED, str(exc))
            return TencentApiConfigTestResult(
                success=False,
                message="测试连接时发生错误",
                error=str(exc),
            )

    def _update_test_status(self, config_id: int, status: TestStatus, message: str) -> None:
        try:
            sql = """
                UPDATE tencent_api_configs
                SET test_status = %s, test_message = %s, last_tested_at = NOW()
                WHERE id = %s
            """
            self.db.execute(sql, (status.value, message, config_id))
        except Exception as exc:
            logger.error("Failed to update Tencent config test status: %s", exc)

    def _row_to_response(self, row: dict) -> TencentApiConfigResponse:
        return TencentApiConfigResponse(
            id=row["id"],
            name=row["name"],
            app_id=row["app_id"],
            open_id=row["open_id"],
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_tested_at=row.get("last_tested_at"),
            test_status=TestStatus(row.get("test_status", "untested")),
            test_message=row.get("test_message"),
            token_expires_at=row.get("token_expires_at"),
        )

    def get_decrypted_token(self, config_id: int) -> Optional[str]:
        try:
            sql = "SELECT access_token_encrypted FROM tencent_api_configs WHERE id = %s AND is_active = 1"
            result = self.db.execute(sql, (config_id,))
            if not result:
                return None
            return decrypt_password(result[0]["access_token_encrypted"])
        except Exception as exc:
            logger.error("Failed to decrypt Tencent token: %s", exc)
            return None

    def build_tencent_api(
        self,
        config_id: int,
        config_row: Optional[dict] = None,
    ) -> TencentAPI:
        if config_row is None:
            sql = "SELECT * FROM tencent_api_configs WHERE id = %s AND is_active = 1"
            result = self.db.execute(sql, (config_id,))
            if not result:
                raise HTTPException(status_code=404, detail="Config not found")
            config_row = result[0]

        try:
            access_token = decrypt_password(config_row["access_token_encrypted"])
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"访问令牌解密失败: {exc}") from exc

        return TencentAPI(
            app_id=config_row["app_id"],
            access_token=access_token,
            open_id=config_row["open_id"],
        )

    async def validate_sheet_access_async(
        self,
        config_id: int,
        spreadsheet_id: str,
        sheet_id: Optional[str] = None,
    ) -> dict:
        api = self.build_tencent_api(config_id)
        try:
            if sheet_id:
                result = await api.get_sheet_info(spreadsheet_id, sheet_id)
            else:
                result = await api.get_spreadsheet_info(spreadsheet_id)
            self._update_test_status(config_id, TestStatus.SUCCESS, "Sheet access verified")
            return {"connected": True, "details": result}
        except TencentAPIError as exc:
            self._update_test_status(config_id, TestStatus.FAILED, str(exc))
            return {"connected": False, "error": str(exc)}
        except Exception as exc:
            self._update_test_status(config_id, TestStatus.FAILED, str(exc))
            return {"connected": False, "error": str(exc)}


def get_tencent_config_service(db: MySQLService = None) -> TencentApiConfigService:
    if db is None:
        db = get_mysql_service()
    return TencentApiConfigService(db)
