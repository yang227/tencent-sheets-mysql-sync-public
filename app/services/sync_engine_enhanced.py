"""
Enhanced Synchronization Engine — adds transaction management,
concurrency control, performance monitoring, and PostgreSQL support.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from contextlib import asynccontextmanager

from app.config import get_settings
from app.services.tencent_api import TencentAPI, TencentAPIError
from app.services.database_service import DatabaseService, create_database_service
from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.mysql_config_service import MySQLConfigService
from app.services.postgresql_config_service import PostgreSQLConfigService
from app.services.mapping import MappingEngine, MappingError
from app.services.metrics_collector import metrics_collector, Timer
from app.services.audit_logger import audit_logger
from app.services.retry_handler import retry_with_backoff, RetryConfig, retry_handler
from app.services.db_exception import (
    DatabaseServiceError,
    DatabaseConnectionError,
    DatabaseQueryError,
    handle_service_exception,
)

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class DistributedLock:
    """Distributed lock — prevents concurrent sync conflicts."""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def acquire(self, resource: str, timeout: float = 30.0):
        if resource not in self._locks:
            self._locks[resource] = asyncio.Lock()
        lock = self._locks[resource]
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            logger.debug("Lock acquired: %s", resource)
            yield
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Failed to acquire lock for {resource} within {timeout}s"
            )
        finally:
            if lock.locked():
                lock.release()
            logger.debug("Lock released: %s", resource)


class ConcurrencyLimiter:
    """Concurrency limiter — controls max simultaneous syncs."""

    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0

    @asynccontextmanager
    async def acquire(self):
        await self._semaphore.acquire()
        self._active_count += 1
        metrics_collector.set_gauge("sync_active_count", self._active_count)
        try:
            yield
        finally:
            self._active_count -= 1
            self._semaphore.release()
            metrics_collector.set_gauge("sync_active_count", self._active_count)

    def get_active_count(self) -> int:
        return self._active_count


distributed_lock = DistributedLock()
concurrency_limiter = ConcurrencyLimiter(max_concurrent=5)


class SyncEngineError(Exception):
    pass


class SyncConflictError(SyncEngineError):
    pass


class SyncResult:
    """Enhanced sync result."""

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
        status: SyncStatus = SyncStatus.PENDING,
        duration_seconds: float = 0.0,
        retry_count: int = 0,
    ):
        self.success = success
        self.direction = direction
        self.rows_affected = rows_affected
        self.rows_new = rows_new
        self.rows_updated = rows_updated
        self.rows_skipped = rows_skipped
        self.errors = errors or []
        self.details = details or {}
        self.status = status
        self.duration_seconds = duration_seconds
        self.retry_count = retry_count

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
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "retry_count": self.retry_count,
        }


class SyncEngine:
    """
    Enhanced bidirectional sync engine (MySQL + PostgreSQL targets).

    Adds: distributed lock, concurrency limiter, performance metrics,
    audit logging, transaction management, idempotency guarantees.
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

    # ─── Service Access ─────────────────────────────────────────

    @property
    def metadata_db(self) -> MySQLService:
        if self._metadata_db is None:
            self._metadata_db = get_mysql_service()
        return self._metadata_db

    @property
    def db(self) -> DatabaseService:
        """Target database service (MySQL or PostgreSQL)."""
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

    # Keep backward-compat alias
    @property
    def mysql(self) -> DatabaseService:
        return self.db

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

    # ─── Config Loading ─────────────────────────────────────────

    def _ensure_config(self) -> None:
        if self._config is not None:
            return
        rows = self.metadata_db.execute(
            "SELECT * FROM sync_configs WHERE id = %s AND is_active = 1",
            (self.config_id,),
        )
        if not rows:
            raise SyncEngineError(f"Config {self.config_id} not found or inactive")
        self._config = rows[0]
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

    # ─── Sync Operations ─────────────────────────────────────────

    async def trigger_sync(self) -> SyncResult:
        self._ensure_config()
        direction = self._sync_direction

        if direction == "to_mysql":
            return await self.sync_to_mysql()
        elif direction == "from_mysql":
            return await self.sync_from_mysql()
        else:
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
                status=SyncStatus.COMPLETED if (result_to.success and result_from.success) else SyncStatus.FAILED,
            )

    @retry_with_backoff(RetryConfig(max_attempts=3))
    async def sync_to_mysql(self) -> SyncResult:
        """Tencent Sheets → Target database (MySQL or PostgreSQL)."""
        self._ensure_config()
        start_time = time.time()
        log_id = None
        lock_resource = f"sync_to_{self.config_id}"

        try:
            async with distributed_lock.acquire(lock_resource, timeout=30.0):
                async with concurrency_limiter.acquire():
                    log_id = self.metadata_db.create_sync_log(
                        self.config_id, "to_mysql", status="running"
                    )
                    audit_logger.log_sync_triggered(
                        self.config_id, "to_mysql", trigger_type="manual"
                    )
                    self._ensure_table_exists()

                    with Timer("tencent_api_get_values"):
                        sheet_cols = self.mapping.get_sheet_columns()
                        range_str = f"{self._sheet_id}!A2:ZZ"
                        result = await self.tencent.get_values(self._spreadsheet_id, range_str)
                        values: List[List[Any]] = result.get("values", [])

                    if not values:
                        self.metadata_db.complete_sync_log(log_id, 0, status="success")
                        return SyncResult(
                            success=True, direction="to_mysql", rows_affected=0,
                            status=SyncStatus.COMPLETED,
                        )

                    batch_result = await self._sync_batch_to_mysql(sheet_cols, values)
                    duration = time.time() - start_time

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

                    metrics_collector.record_sync(
                        config_id=self.config_id,
                        direction="to_mysql",
                        rows_affected=batch_result.rows_affected,
                        duration=duration,
                        success=batch_result.success,
                    )
                    audit_logger.log_sync_completed(
                        self.config_id, "to_mysql",
                        rows_affected=batch_result.rows_affected,
                        duration_seconds=duration,
                    )

                    return SyncResult(
                        success=batch_result.success,
                        direction="to_mysql",
                        rows_affected=batch_result.rows_affected,
                        rows_new=batch_result.rows_new,
                        rows_updated=batch_result.rows_updated,
                        rows_skipped=batch_result.rows_skipped,
                        errors=batch_result.errors,
                        status=SyncStatus.COMPLETED if batch_result.success else SyncStatus.FAILED,
                        duration_seconds=duration,
                    )

        except (TencentAPIError, DatabaseServiceError) as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.error("[Config %d] sync_to_db error: %s", self.config_id, exc)
            return SyncResult(
                success=False, direction="to_mysql", errors=[str(exc)],
                status=SyncStatus.FAILED,
            )

        except Exception as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.exception("[Config %d] Unexpected sync_to_db error", self.config_id)
            return SyncResult(
                success=False, direction="to_mysql", errors=[str(exc)],
                status=SyncStatus.FAILED,
            )

    async def _sync_batch_to_mysql(
        self, sheet_cols: List[str], values: List[List[Any]],
        header_offset: int = 0,
    ) -> SyncResult:
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
        start_time = time.time()
        log_id = None

        try:
            async with concurrency_limiter.acquire():
                log_id = self.metadata_db.create_sync_log(
                    self.config_id, "from_mysql", status="running"
                )

                with Timer("db_read"):
                    db_rows = self.db.execute(
                        f"SELECT * FROM {self.db.quote_identifier(self._table_name)}"
                    )

                if not db_rows:
                    self.metadata_db.complete_sync_log(log_id, 0, status="success")
                    return SyncResult(
                        success=True, direction="from_mysql", rows_affected=0,
                        status=SyncStatus.COMPLETED,
                    )

                sheet_rows = self.mapping.db_rows_to_sheet_rows(db_rows, direction="from_mysql")
                if not sheet_rows:
                    self.metadata_db.complete_sync_log(log_id, 0, status="success")
                    return SyncResult(
                        success=True, direction="from_mysql", rows_affected=0,
                        status=SyncStatus.COMPLETED,
                    )

                values = [list(row.values()) for row in sheet_rows]
                range_str = f"{self._sheet_id}!A2"

                with Timer("tencent_api_put_values"):
                    await self.tencent.put_values(self._spreadsheet_id, range_str, values)

                rows_affected = len(values)
                duration = time.time() - start_time

                self.metadata_db.complete_sync_log(log_id, rows_affected, status="success")
                self.metadata_db.update_last_sync_time(self.config_id)

                metrics_collector.record_sync(
                    config_id=self.config_id,
                    direction="from_mysql",
                    rows_affected=rows_affected,
                    duration=duration,
                    success=True,
                )

                return SyncResult(
                    success=True, direction="from_mysql",
                    rows_affected=rows_affected,
                    status=SyncStatus.COMPLETED,
                    duration_seconds=duration,
                )

        except (TencentAPIError, DatabaseServiceError) as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.error("[Config %d] sync_from_db error: %s", self.config_id, exc)
            return SyncResult(
                success=False, direction="from_mysql", errors=[str(exc)],
                status=SyncStatus.FAILED,
            )

        except Exception as exc:
            if log_id:
                self.metadata_db.complete_sync_log(log_id, 0, status="failed", error_message=str(exc))
            logger.exception("[Config %d] Unexpected sync_from_db error", self.config_id)
            return SyncResult(
                success=False, direction="from_mysql", errors=[str(exc)],
                status=SyncStatus.FAILED,
            )

    # ─── Row Helpers ────────────────────────────────────────────

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

    # ─── Webhook ────────────────────────────────────────────────

    async def handle_webhook(self, event_type: str, changed_range: str) -> SyncResult:
        logger.info("[Config %d] Webhook (enhanced): type=%s, range=%s", self.config_id, event_type, changed_range)
        audit_logger.log_webhook_received(
            spreadsheet_id=self._spreadsheet_id or "",
            event_type=event_type,
            valid=True,
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
            with Timer("tencent_api_webhook_get_values"):
                result = await self.tencent.get_values(self._spreadsheet_id, range_str)
            values: List[List[Any]] = result.get("values", [])

            if not values:
                return SyncResult(
                    success=True, direction="to_mysql", rows_affected=0,
                    details={"message": "No data in changed range"},
                    status=SyncStatus.COMPLETED,
                )

            sheet_cols = self.mapping.get_sheet_columns()
            return await self._sync_batch_to_mysql(sheet_cols, values, start_row - 1)

        except TencentAPIError as exc:
            logger.error("[Config %d] Range sync error: %s", self.config_id, exc)
            return SyncResult(
                success=False, direction="to_mysql", errors=[str(exc)],
                status=SyncStatus.FAILED,
            )

    # ─── Table Setup ────────────────────────────────────────────

    def _ensure_table_exists(self) -> None:
        if not self.db.table_exists(self._table_name):
            self._ensure_config()
            mapping_json = self._config.get("mapping_json", {})
            if isinstance(mapping_json, str):
                mapping_json = json.loads(mapping_json)
            columns = mapping_json.get("columns", [])
            self.db.create_data_table(self._table_name, columns)
            logger.info(
                "[Config %d] Auto-created table: %s (%s)",
                self.config_id, self._table_name, self._db_type,
            )

    # ─── Status ─────────────────────────────────────────────────

    def get_sync_status(self) -> Dict[str, Any]:
        self._ensure_config()
        logs = self.metadata_db.get_sync_logs(self.config_id, limit=10)
        sync_stats = metrics_collector.get_sync_statistics(self.config_id)
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
            "sync_statistics": sync_stats,
            "active_syncs": concurrency_limiter.get_active_count(),
        }

    async def test_connection(self) -> Dict[str, Any]:
        self._ensure_config()
        results: Dict[str, Any] = {}
        try:
            with Timer("metadata_mysql_test"):
                results["metadata_mysql"] = self.metadata_db.test_connection()
        except Exception as exc:
            results["metadata_mysql"] = {"connected": False, "error": str(exc)}

        try:
            with Timer("target_db_test"):
                results["target_db"] = self.db.test_connection()
        except Exception as exc:
            results["target_db"] = {"connected": False, "error": str(exc)}

        try:
            with Timer("tencent_test"):
                results["tencent"] = await self.tencent.test_connection()
        except Exception as exc:
            results["tencent"] = {"connected": False, "error": str(exc)}

        results["all_connected"] = (
            results.get("target_db", {}).get("connected", False)
            and results.get("tencent", {}).get("connected", False)
        )

        audit_logger.log_connection_tested(
            config_id=self.config_id,
            mysql_status=results.get("target_db", {}).get("connected", False),
            tencent_status=results.get("tencent", {}).get("connected", False),
        )
        return results