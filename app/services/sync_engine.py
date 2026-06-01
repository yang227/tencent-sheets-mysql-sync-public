"""
Synchronization Engine - Core bidirectional sync logic.

Supports both MySQL and PostgreSQL as sync targets via DatabaseService.
Handles change detection, hash comparison, and data synchronization.
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.services.tencent_api import (
    TencentAPI,
    TencentAPIError,
)
from app.services.database_service import DatabaseService, create_database_service
from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.mysql_config_service import MySQLConfigService
from app.services.postgresql_config_service import PostgreSQLConfigService
from app.services.mapping import MappingEngine, MappingError
from app.services.tencent_config_service import TencentApiConfigService
from app.services.db_exception import (
    DatabaseServiceError,
    DatabaseConnectionError,
    handle_service_exception,
)

logger = logging.getLogger(__name__)

# Global config cache
_config_cache: Dict[int, Dict[str, Any]] = {}
_config_cache_time: Dict[int, float] = {}
CONFIG_CACHE_TTL = 300  # 5 minutes


class SyncEngineError(Exception):
    """Base sync engine error."""
    pass


class SyncResult:
    """Result of a sync operation."""

    def __init__(
        self,
        success: bool,
        direction: str,
        rows_affected: int = 0,
        rows_new: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        errors: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.direction = direction
        self.rows_affected = rows_affected
        self.rows_new = rows_new
        self.rows_updated = rows_updated
        self.rows_skipped = rows_skipped
        self.errors = errors or []
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "direction": self.direction,
            "rows_affected": self.rows_affected,
            "rows_new": self.rows_new,
            "rows_updated": self.rows_updated,
            "rows_skipped": self.rows_skipped,
            "errors": self.errors,
            "details": self.details,
        }


class SyncEngine:
    """
    Bidirectional synchronization engine between Tencent Sheets and
    a target database (MySQL or PostgreSQL).

    Features:
    - Hash-based change detection (SHA256)
    - Batch processing with configurable batch size
    - Automatic retry on transient failures
    - Detailed per-row error collection
    - Progress logging during long syncs
    - Append detection for DB → Tencent inserts
    - Config caching to avoid repeated DB queries
    """

    def __init__(
        self,
        config_id: int,
        mysql_service: Optional[MySQLService] = None,
        tencent_api: Optional[TencentAPI] = None,
        poll_interval: int = 30,
        batch_size: int = 100,
        retry_times: int = 3,
    ):
        self.config_id = config_id
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.retry_times = retry_times

        self._metadata_db: Optional[MySQLService] = mysql_service
        self._target_db: Optional[DatabaseService] = None
        self._tencent: Optional[TencentAPI] = tencent_api
        self._mapping: Optional[MappingEngine] = None
        self._config: Optional[Dict[str, Any]] = None
        self._log_id: Optional[int] = None

        self._spreadsheet_id: Optional[str] = None
        self._sheet_id: Optional[str] = None
        self._table_name: Optional[str] = None
        self._database: Optional[str] = None
        self._db_type: str = "mysql"
        self._mysql_config_id: Optional[int] = None
        self._postgresql_config_id: Optional[int] = None
        self._tencent_config_id: Optional[int] = None
        self._sync_direction: Optional[str] = None
        self._poll_interval_cfg: int = 30

    # ─── Service Access ─────────────────────────────────────────────

    @property
    def metadata_db(self) -> MySQLService:
        if self._metadata_db is None:
            self._metadata_db = get_mysql_service()
        return self._metadata_db

    @property
    def db(self) -> DatabaseService:
        """Target database service (MySQL or PostgreSQL, selected by config)."""
        if self._target_db is None:
            self._ensure_config()
            if self._db_type == "postgresql":
                self._target_db = self._build_postgresql_service()
            elif self._mysql_config_id:
                self._target_db = MySQLConfigService(self.metadata_db).build_mysql_service(
                    self._mysql_config_id
                )
            else:
                self._target_db = self.metadata_db
        return self._target_db

    def _build_postgresql_service(self) -> DatabaseService:
        if self._postgresql_config_id:
            return PostgreSQLConfigService(self.metadata_db).build_postgresql_service(
                self._postgresql_config_id
            )
        raise SyncEngineError(
            f"Config {self.config_id} has db_type=postgresql but no postgresql_config_id"
        )

    @property
    def tencent(self) -> TencentAPI:
        if self._tencent is None:
            self._ensure_config()
            if self._tencent_config_id:
                self._tencent = TencentApiConfigService(self.metadata_db).build_tencent_api(
                    self._tencent_config_id
                )
            else:
                self._tencent = TencentAPI.from_env()
        return self._tencent

    @property
    def mapping(self) -> MappingEngine:
        if self._mapping is None:
            self._ensure_config()
            mapping_json = self._config.get("mapping_json", {})
            if isinstance(mapping_json, str):
                mapping_json = json.loads(mapping_json)
            self._mapping = MappingEngine(mapping_json)
        return self._mapping

    # ─── Config Loading ──────────────────────────────────────────────

    def _ensure_config(self) -> None:
        if self._config is not None:
            return
        now = time.time()
        if self.config_id in _config_cache:
            cached_at = _config_cache_time.get(self.config_id, 0)
            if now - cached_at < CONFIG_CACHE_TTL:
                self._config = _config_cache[self.config_id]
                self._apply_config()
                return

        rows = self.metadata_db.execute(
            "SELECT * FROM sync_configs WHERE id = %s AND is_active = 1",
            (self.config_id,),
        )
        if not rows:
            raise SyncEngineError(f"Sync config {self.config_id} not found or inactive")
        self._config = rows[0]
        _config_cache[self.config_id] = self._config
        _config_cache_time[self.config_id] = now
        self._apply_config()

    def _apply_config(self) -> None:
        cfg = self._config
        self._spreadsheet_id = cfg.get("spreadsheet_id", "")
        self._sheet_id = cfg.get("sheet_id", "")
        self._table_name = cfg.get("table_name", "")
        self._database = cfg.get("database", "")
        self._db_type = cfg.get("db_type", "mysql")
        self._mysql_config_id = cfg.get("mysql_config_id")
        self._postgresql_config_id = cfg.get("postgresql_config_id")
        self._tencent_config_id = cfg.get("tencent_config_id")
        self._sync_direction = cfg.get("sync_direction", "bidirectional")
        self._poll_interval_cfg = cfg.get("poll_interval", 30)

    # ─── Sync Operations ─────────────────────────────────────────────

    async def trigger_sync(self) -> SyncResult:
        """Execute sync in the configured direction."""
        self._ensure_config()
        direction = self._sync_direction

        if direction == "to_mysql":
            return await self.sync_to_mysql()
        elif direction == "from_mysql":
            return await self.sync_from_mysql()
        else:  # bidirectional
            result_to = await self.sync_to_mysql()
            result_from = await self.sync_from_mysql()
            return SyncResult(
                success=result_to.success and result_from.success,
                direction="bidirectional",
                rows_affected=result_to.rows_affected + result_from.rows_affected,
                rows_new=result_to.rows_new + result_from.rows_new,
                rows_updated=result_to.rows_updated + result_from.rows_updated,
                rows_skipped=result_to.rows_skipped + result_from.rows_skipped,
                errors=result_to.errors + result_from.errors,
                details={"to_db": result_to.to_dict(), "from_db": result_from.to_dict()},
            )

    async def sync_to_mysql(self) -> SyncResult:
        """Tencent Sheets → Target database (MySQL or PostgreSQL)."""
        self._ensure_config()
        log_id = None
        try:
            log_id = self.metadata_db.create_sync_log(
                self.config_id, "to_mysql", status="running"
            )
            self._ensure_table_exists()

            sheet_cols = self.mapping.get_sheet_columns()
            range_str = f"{self._sheet_id}!A2:ZZ"

            result = await self.tencent.get_values(self._spreadsheet_id, range_str)
            values: List[List[Any]] = result.get("values", [])

            if not values:
                self.metadata_db.complete_sync_log(log_id, 0, status="success")
                return SyncResult(success=True, direction="to_mysql", rows_affected=0)

            batch_result = await self._sync_batch_to_mysql(sheet_cols, values)

            self.metadata_db.complete_sync_log(
                log_id,
                rows_affected=batch_result.rows_affected,
                rows_new=batch_result.rows_new,
                rows_updated=batch_result.rows_updated,
                rows_skipped=batch_result.rows_skipped,
                status="success" if batch_result.success else "partial",
                error_message="; ".join(batch_result.errors) if batch_result.errors else None,
            )
            self.metadata_db.update_last_sync_time(self.config_id)
            return batch_result

        except TencentAPIError as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.error("[Config %d] Tencent API error in sync_to_db: %s", self.config_id, exc)
            return SyncResult(success=False, direction="to_mysql", errors=[str(exc)])

        except DatabaseServiceError as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.error("[Config %d] DB error in sync_to_db: %s", self.config_id, exc)
            return SyncResult(success=False, direction="to_mysql", errors=[str(exc)])

        except Exception as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.exception("[Config %d] Unexpected error in sync_to_db", self.config_id)
            return SyncResult(success=False, direction="to_mysql", errors=[str(exc)])

    async def _sync_batch_to_mysql(
        self,
        sheet_cols: List[str],
        values: List[List[Any]],
        header_offset: int = 0,
    ) -> SyncResult:
        """Process a batch of sheet rows into the target database."""
        total_new = 0
        total_updated = 0
        total_skipped = 0
        all_errors: List[str] = []

        db_rows = self.mapping.sheet_rows_to_db_rows(
            [dict(zip(sheet_cols, row)) for row in values if row],
            direction="to_mysql",
        )

        pk_cols = self.mapping.get_primary_key_columns()
        db_col_names = self.mapping.get_db_columns()

        for row_idx, row_data in enumerate(db_rows):
            if not row_data:
                continue
            try:
                row_key = self._build_row_key(row_data, pk_cols)
                row_values = [row_data.get(c) for c in db_col_names]
                current_hash = self.metadata_db.compute_row_hash(row_values)

                stored_hash = self.metadata_db.get_stored_hash(
                    self.config_id, row_key, source="tencent"
                )

                if stored_hash == current_hash:
                    total_skipped += 1
                    continue

                if stored_hash is None:
                    self._insert_row(db_col_names, row_data)
                    total_new += 1
                else:
                    self._update_row(db_col_names, row_data, pk_cols)
                    total_updated += 1

                self.metadata_db.upsert_change_record(
                    self.config_id, row_key, current_hash, source="tencent",
                    prev_value=json.dumps(row_values, ensure_ascii=False, default=str)[:4000],
                )

            except DatabaseServiceError as exc:
                all_errors.append(f"Row {header_offset + row_idx + 2}: {exc}")
                logger.warning("[Config %d] Row error: %s", self.config_id, exc)
            except Exception as exc:
                all_errors.append(f"Row {header_offset + row_idx + 2}: {exc}")
                logger.warning("[Config %d] Unexpected row error: %s", self.config_id, exc)

        return SyncResult(
            success=len(all_errors) == 0,
            direction="to_mysql",
            rows_affected=total_new + total_updated,
            rows_new=total_new,
            rows_updated=total_updated,
            rows_skipped=total_skipped,
            errors=all_errors,
        )

    async def sync_from_mysql(self) -> SyncResult:
        """Target database → Tencent Sheets."""
        self._ensure_config()
        log_id = None
        try:
            log_id = self.metadata_db.create_sync_log(
                self.config_id, "from_mysql", status="running"
            )

            db_rows = self.db.execute(f"SELECT * FROM {self.db.quote_identifier(self._table_name)}")
            if not db_rows:
                self.metadata_db.complete_sync_log(log_id, 0, status="success")
                return SyncResult(success=True, direction="from_mysql", rows_affected=0)

            sheet_rows = self.mapping.db_rows_to_sheet_rows(db_rows, direction="from_mysql")
            if not sheet_rows:
                self.metadata_db.complete_sync_log(log_id, 0, status="success")
                return SyncResult(success=True, direction="from_mysql", rows_affected=0)

            values = [list(row.values()) for row in sheet_rows]
            range_str = f"{self._sheet_id}!A2"

            await self.tencent.put_values(
                self._spreadsheet_id, range_str, values
            )

            rows_affected = len(values)
            self.metadata_db.complete_sync_log(log_id, rows_affected, status="success")
            self.metadata_db.update_last_sync_time(self.config_id)

            return SyncResult(
                success=True, direction="from_mysql", rows_affected=rows_affected,
            )

        except TencentAPIError as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.error("[Config %d] Tencent API error in sync_from_db: %s", self.config_id, exc)
            return SyncResult(success=False, direction="from_mysql", errors=[str(exc)])

        except DatabaseServiceError as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.error("[Config %d] DB error in sync_from_db: %s", self.config_id, exc)
            return SyncResult(success=False, direction="from_mysql", errors=[str(exc)])

        except Exception as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.exception("[Config %d] Unexpected error in sync_from_db", self.config_id)
            return SyncResult(success=False, direction="from_mysql", errors=[str(exc)])

    # ─── Row Helpers ────────────────────────────────────────────────

    def _build_row_key(self, row_data: Dict[str, Any], pk_cols: List[str]) -> str:
        pk_values = [str(row_data.get(c, "")) for c in pk_cols]
        return "||".join(pk_values) if pk_values else str(hash(tuple(row_data.items())))

    def _insert_row(self, columns: List[str], row_data: Dict[str, Any]) -> None:
        cols = ", ".join(self.db.quote_identifier(c) for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        values = tuple(row_data.get(c) for c in columns)
        self.db.execute(
            f"INSERT INTO {self.db.quote_identifier(self._table_name)} ({cols}) VALUES ({placeholders})",
            values,
        )

    def _update_row(self, columns: List[str], row_data: Dict[str, Any], pk_cols: List[str]) -> None:
        set_clause = ", ".join(
            f"{self.db.quote_identifier(c)} = %s" for c in columns
        )
        where_clause = " AND ".join(
            f"{self.db.quote_identifier(c)} = %s" for c in pk_cols
        )
        values = tuple(row_data.get(c) for c in columns) + tuple(
            row_data.get(c) for c in pk_cols
        )
        self.db.execute(
            f"UPDATE {self.db.quote_identifier(self._table_name)} SET {set_clause} WHERE {where_clause}",
            values,
        )

    # ─── Webhook ────────────────────────────────────────────────────

    async def handle_webhook(self, event_type: str, changed_range: str) -> SyncResult:
        logger.info(
            "[Config %d] Webhook: type=%s, range=%s",
            self.config_id, event_type, changed_range,
        )
        try:
            parts = changed_range.split("!")
            if len(parts) == 2 and ":" in parts[1]:
                start, end = parts[1].split(":")
                start_row = int("".join(filter(str.isdigit, start)))
                end_row = int("".join(filter(str.isdigit, end)))
                return await self._sync_changed_range(start_row, end_row)
        except Exception as exc:
            logger.warning("[Config %d] Could not parse webhook range: %s", self.config_id, exc)

        logger.info("[Config %d] Falling back to full to_db sync", self.config_id)
        return await self.sync_to_mysql()

    async def _sync_changed_range(self, start_row: int, end_row: int) -> SyncResult:
        logger.info("[Config %d] Syncing changed rows %d-%d", self.config_id, start_row, end_row)
        try:
            range_str = f"{self._sheet_id}!A{start_row}:ZZ{end_row}"
            result = await self.tencent.get_values(self._spreadsheet_id, range_str)
            values: List[List[Any]] = result.get("values", [])

            if not values:
                return SyncResult(
                    success=True, direction="to_mysql", rows_affected=0,
                    details={"message": "No data in changed range"},
                )

            sheet_cols = self.mapping.get_sheet_columns()
            return await self._sync_batch_to_mysql(sheet_cols, values, start_row - 1)

        except TencentAPIError as exc:
            logger.error("[Config %d] Range sync error: %s", self.config_id, exc)
            return SyncResult(success=False, direction="to_mysql", errors=[str(exc)])

    # ─── Table Setup ──────────────────────────────────────────────

    def _ensure_table_exists(self) -> None:
        """Auto-create target table if it doesn't exist."""
        if not self.db.table_exists(self._table_name):
            self._ensure_config()
            mapping_json = self._config.get("mapping_json", {})
            if isinstance(mapping_json, str):
                mapping_json = json.loads(mapping_json)
            columns = mapping_json.get("columns", [])
            self.db.create_data_table(self._table_name, columns)
            logger.info("[Config %d] Auto-created table: %s (%s)", self.config_id, self._table_name, self._db_type)

    # ─── Status ─────────────────────────────────────────────────

    def get_sync_status(self) -> Dict[str, Any]:
        self._ensure_config()
        logs = self.metadata_db.get_sync_logs(self.config_id, limit=10)
        return {
            "config_id": self.config_id,
            "spreadsheet_id": self._spreadsheet_id,
            "sheet_id": self._sheet_id,
            "table_name": self._table_name,
            "database": self._database,
            "db_type": self._db_type,
            "mysql_config_id": self._mysql_config_id,
            "postgresql_config_id": self._postgresql_config_id,
            "tencent_config_id": self._tencent_config_id,
            "sync_direction": self._sync_direction,
            "poll_interval": self._poll_interval_cfg,
            "is_active": self._config.get("is_active", True),
            "last_sync_at": self._config.get("last_sync_at"),
            "recent_logs": logs,
        }

    async def test_connection(self) -> Dict[str, Any]:
        self._ensure_config()
        results: Dict[str, Any] = {}
        try:
            results["metadata_mysql"] = self.metadata_db.test_connection()
        except Exception as exc:
            results["metadata_mysql"] = {"connected": False, "error": str(exc)}

        try:
            results["target_db"] = self.db.test_connection()
        except Exception as exc:
            results["target_db"] = {"connected": False, "error": str(exc)}

        try:
            if self._tencent_config_id:
                results["tencent"] = await TencentApiConfigService(
                    self.metadata_db
                ).validate_sheet_access_async(
                    self._tencent_config_id,
                    self._spreadsheet_id,
                    self._sheet_id,
                )
            else:
                sheet_info = await self.tencent.get_sheet_info(
                    self._spreadsheet_id, self._sheet_id,
                )
                results["tencent"] = {"connected": True, "details": sheet_info}
        except Exception as exc:
            results["tencent"] = {"connected": False, "error": str(exc)}

        results["all_connected"] = (
            results.get("target_db", {}).get("connected", False)
            and results.get("tencent", {}).get("connected", False)
        )
        return results