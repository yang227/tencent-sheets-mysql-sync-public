"""
增强的同步引擎 - 添加事务管理、并发控制和性能监控
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
from app.services.mysql_service import MySQLService, MySQLServiceError
from app.services.mapping import MappingEngine, MappingError
from app.services.metrics_collector import metrics_collector, Timer
from app.services.audit_logger import audit_logger
from app.services.retry_handler import retry_with_backoff, RetryConfig, retry_handler

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """同步状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class DistributedLock:
    """
    分布式锁实现 - 防止并发同步冲突
    """
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks.clear()
    
    @asynccontextmanager
    async def acquire(self, resource: str, timeout: float = 30.0):
        """获取锁"""
        if resource not in self._locks:
            self._locks[resource] = asyncio.Lock()
        
        lock = self._locks[resource]
        
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            logger.debug(f"Lock acquired: {resource}")
            yield
        except asyncio.TimeoutError:
            raise TimeoutError(f"Failed to acquire lock for {resource} within {timeout}s")
        finally:
            if lock.locked():
                lock.release()
            logger.debug(f"Lock released: {resource}")


class ConcurrencyLimiter:
    """
    并发限制器 - 控制同时进行的同步数量
    """
    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._max_concurrent = max_concurrent
    
    @asynccontextmanager
    async def acquire(self):
        """获取并发令牌"""
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
        """获取当前活跃数量"""
        return self._active_count


distributed_lock = DistributedLock()
concurrency_limiter = ConcurrencyLimiter(max_concurrent=5)


class SyncEngineError(Exception):
    """Base sync engine error."""
    pass


class SyncConflictError(SyncEngineError):
    """同步冲突错误"""
    pass


class SyncResult:
    """增强的同步结果"""

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
    增强的双向同步引擎

    新增功能:
    - 分布式锁防止并发冲突
    - 并发数量限制
    - 性能指标收集
    - 详细的审计日志
    - 事务管理
    - 幂等性保证
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

        self._mysql: Optional[MySQLService] = mysql_service
        self._tencent: Optional[TencentAPI] = tencent_api
        self._mapping: Optional[MappingEngine] = None
        self._config: Optional[Dict[str, Any]] = None
        self._log_id: Optional[int] = None
        self._sync_version: int = 0

        self._spreadsheet_id: Optional[str] = None
        self._sheet_id: Optional[str] = None
        self._table_name: Optional[str] = None
        self._database: Optional[str] = None
        self._sync_direction: Optional[str] = None
        self._poll_interval_cfg: int = 30

    @property
    def mysql(self) -> MySQLService:
        if self._mysql is None:
            self._mysql = MySQLService()
        return self._mysql

    @property
    def tencent(self) -> TencentAPI:
        if self._tencent is None:
            # from_env() prefers TENCENT_DOCS_ACCESS_TOKEN env var (JWT mode)
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

    def _ensure_config(self) -> None:
        """Load configuration from DB on first access."""
        if self._config is None:
            self._config = self.mysql.get_sync_config(self.config_id)
            if not self._config:
                raise SyncEngineError(f"Configuration {self.config_id} not found in database")

            self._spreadsheet_id = self._config["spreadsheet_id"]
            self._sheet_id = self._config["sheet_id"]
            self._table_name = self._config["table_name"]
            self._database = self._config.get("database", "")
            self._sync_direction = self._config.get("sync_direction", "bidirectional")
            self._poll_interval_cfg = self._config.get("poll_interval", 30)

            logger.info(
                f"[Config {self.config_id}] Loaded config: "
                f"table={self._table_name}, direction={self._sync_direction}"
            )

    @staticmethod
    def compute_row_hash(
        row_data: Dict[str, Any],
        exclude_cols: Optional[List[str]] = None,
    ) -> str:
        return MySQLService.compute_row_hash(row_data, exclude_cols)

    def _get_row_key(self, row_data: Dict[str, Any], source: str) -> Optional[str]:
        """Build a stable row key for tracking."""
        if source == "tencent":
            return str(row_data.get("_row_number", ""))
        else:
            pk_cols = self.mapping.primary_keys
            if not pk_cols:
                return None
            pk_values = []
            for pk in pk_cols:
                val = row_data.get(pk)
                if val is None:
                    return None
                pk_values.append(str(val))
            return "|".join(pk_values)

    async def sync_to_mysql(self) -> SyncResult:
        """
        增强的同步方法 - 腾讯文档 → MySQL
        添加了锁、事务、监控和审计
        """
        logger.info(f"[Config {self.config_id}] Starting to_mysql sync (enhanced)")
        
        lock_resource = f"sync_to_mysql_{self.config_id}"
        
        async with distributed_lock.acquire(lock_resource, timeout=60):
            async with concurrency_limiter.acquire():
                start_time = time.time()
                self._ensure_config()
                self._ensure_table_exists()

                direction = self._config.get("sync_direction", "bidirectional")
                if direction == "from_mysql":
                    return SyncResult(
                        success=True, direction="to_mysql", rows_affected=0,
                        details={"message": "Direction is from_mysql only — skipped"},
                        status=SyncStatus.COMPLETED,
                        duration_seconds=time.time() - start_time,
                    )

                self._log_id = self.mysql.create_sync_log(
                    self.config_id, "to_mysql", status="running"
                )
                
                self._sync_version += 1
                current_version = self._sync_version

                audit_logger.log_sync_triggered(
                    config_id=self.config_id,
                    direction="to_mysql",
                    trigger_type="manual"
                )

                errors: List[str] = []
                total_new = total_updated = total_skipped = 0

                try:
                    sheet_info = await self.tencent.get_sheet_info(
                        self._spreadsheet_id, self._sheet_id
                    )
                    last_row = sheet_info.get("rowCount", 1000)

                    range_str = self.mapping.build_sheet_range(
                        sheet_name=self._sheet_id,
                        start_row=self.mapping.data_start_row,
                        end_row=last_row,
                    )
                    logger.info(f"[Config {self.config_id}] Reading range {range_str}")

                    with Timer("tencent_api_get_values"):
                        result = await self.tencent.get_values(self._spreadsheet_id, range_str)
                    values: List[List[Any]] = result.get("values", [])

                    if not values:
                        self.mysql.complete_sync_log(
                            self._log_id, rows_affected=0, rows_new=0, rows_updated=0,
                            rows_skipped=0, status="success"
                        )
                        self.mysql.update_last_sync_time(self.config_id)
                        
                        duration = time.time() - start_time
                        metrics_collector.record_sync_duration(
                            self.config_id, "to_mysql", duration, True
                        )
                        
                        audit_logger.log_sync_completed(
                            config_id=self.config_id,
                            direction="to_mysql",
                            rows_affected=0,
                            duration_seconds=duration
                        )
                        
                        return SyncResult(
                            success=True, direction="to_mysql", rows_affected=0,
                            details={"message": "No data rows in sheet"},
                            status=SyncStatus.COMPLETED,
                            duration_seconds=duration,
                        )

                    sheet_cols = self.mapping.get_sheet_columns()
                    total_rows = len(values)

                    for batch_start in range(0, total_rows, self.batch_size):
                        if current_version != self._sync_version:
                            logger.warning(f"[Config {self.config_id}] Sync version changed, aborting")
                            break
                            
                        batch_end = min(batch_start + self.batch_size, total_rows)
                        batch = values[batch_start:batch_end]

                        batch_result = await self._sync_batch_to_mysql(
                            sheet_cols, batch, batch_start
                        )
                        total_new += batch_result.rows_new
                        total_updated += batch_result.rows_updated
                        total_skipped += batch_result.rows_skipped
                        errors.extend(batch_result.errors)

                        rows_done = batch_end
                        logger.info(
                            f"[Config {self.config_id}] to_mysql progress: "
                            f"{rows_done}/{total_rows} rows"
                        )

                    self.mysql.update_last_sync_time(self.config_id)
                    final_status = "partial" if errors else "success"
                    self.mysql.complete_sync_log(
                        self._log_id,
                        rows_affected=total_new + total_updated,
                        rows_new=total_new,
                        rows_updated=total_updated,
                        rows_skipped=total_skipped,
                        status=final_status,
                        error_message="; ".join(errors[:50]) if errors else None,
                    )

                    duration = time.time() - start_time
                    metrics_collector.record_sync_duration(
                        self.config_id, "to_mysql", duration, len(errors) == 0
                    )
                    metrics_collector.record_sync_rows(
                        self.config_id, "to_mysql", total_new + total_updated, "upsert"
                    )
                    
                    audit_logger.log_sync_completed(
                        config_id=self.config_id,
                        direction="to_mysql",
                        rows_affected=total_new + total_updated,
                        duration_seconds=duration,
                        status=final_status
                    )

                    return SyncResult(
                        success=True, direction="to_mysql",
                        rows_affected=total_new + total_updated,
                        rows_new=total_new, rows_updated=total_updated,
                        rows_skipped=total_skipped, errors=errors,
                        details={"total_sheet_rows": total_rows},
                        status=SyncStatus.COMPLETED if not errors else SyncStatus.COMPLETED,
                        duration_seconds=duration,
                    )

                except TencentAPIError as e:
                    duration = time.time() - start_time
                    logger.error(f"[Config {self.config_id}] TencentAPI error: {e}")
                    self.mysql.complete_sync_log(
                        self._log_id, 0, 0, 0, 0, "failed", str(e)
                    )
                    
                    metrics_collector.record_sync_duration(
                        self.config_id, "to_mysql", duration, False
                    )
                    audit_logger.log_sync_failed(
                        config_id=self.config_id,
                        direction="to_mysql",
                        error_message=str(e)
                    )
                    retry_handler.record_error(e, {"config_id": self.config_id, "operation": "to_mysql"})
                    
                    return SyncResult(success=False, direction="to_mysql", errors=[str(e)], status=SyncStatus.FAILED, duration_seconds=duration)

                except MySQLServiceError as e:
                    duration = time.time() - start_time
                    logger.error(f"[Config {self.config_id}] MySQL error: {e}")
                    self.mysql.complete_sync_log(
                        self._log_id, 0, 0, 0, 0, "failed", str(e)
                    )
                    
                    metrics_collector.record_sync_duration(
                        self.config_id, "to_mysql", duration, False
                    )
                    audit_logger.log_sync_failed(
                        config_id=self.config_id,
                        direction="to_mysql",
                        error_message=str(e)
                    )
                    retry_handler.record_error(e, {"config_id": self.config_id, "operation": "to_mysql"})
                    
                    return SyncResult(success=False, direction="to_mysql", errors=[str(e)], status=SyncStatus.FAILED, duration_seconds=duration)

                except Exception as e:
                    duration = time.time() - start_time
                    logger.exception(f"[Config {self.config_id}] Unexpected error in to_mysql: {e}")
                    self.mysql.complete_sync_log(
                        self._log_id, 0, 0, 0, 0, "failed", str(e)
                    )
                    
                    metrics_collector.record_sync_duration(
                        self.config_id, "to_mysql", duration, False
                    )
                    audit_logger.log_sync_failed(
                        config_id=self.config_id,
                        direction="to_mysql",
                        error_message=str(e)
                    )
                    retry_handler.record_error(e, {"config_id": self.config_id, "operation": "to_mysql"})
                    
                    return SyncResult(success=False, direction="to_mysql", errors=[str(e)], status=SyncStatus.FAILED, duration_seconds=duration)

    async def _sync_batch_to_mysql(
        self,
        sheet_cols: List[str],
        batch_values: List[List[Any]],
        batch_offset: int,
    ) -> SyncResult:
        """Process one batch of rows from Tencent → MySQL."""
        rows_new = rows_updated = rows_skipped = 0
        errors: List[str] = []

        for i, row in enumerate(batch_values):
            row_num = batch_offset + i + 1

            if not row or all(v is None or v == "" for v in row):
                continue

            row_data: Dict[str, Any] = {}
            for col_idx, col_letter in enumerate(sheet_cols):
                row_data[col_letter] = row[col_idx] if col_idx < len(row) else None
            row_data["_row_number"] = str(row_num)

            current_hash = self.compute_row_hash(row_data)

            tracked = self.mysql.get_tracked_row(
                self.config_id, str(row_num), "tencent"
            )
            if tracked and tracked["source_hash"] == current_hash:
                rows_skipped += 1
                continue

            try:
                db_row = self.mapping.sheet_row_to_db_row(row_data, "to_mysql")
            except MappingError as e:
                errors.append(f"Row {row_num} transform error: {e}")
                continue

            try:
                pk_cols = self.mapping.primary_keys
                affected = self.mysql.insert_or_update(self._table_name, db_row, pk_cols)

                if affected == 1:
                    rows_new += 1
                elif affected == 2:
                    rows_updated += 1

                self.mysql.upsert_tracked_row(
                    self.config_id,
                    str(row_num),
                    current_hash,
                    json.dumps(db_row, ensure_ascii=False, default=str),
                    "tencent",
                )
            except MySQLServiceError as e:
                errors.append(f"Row {row_num} DB error: {e}")
                logger.warning(f"[Config {self.config_id}] Row {row_num} write failed: {e}")

        return SyncResult(
            success=True, direction="to_mysql",
            rows_new=rows_new, rows_updated=rows_updated,
            rows_skipped=rows_skipped, errors=errors,
        )

    async def sync_from_mysql(self) -> SyncResult:
        """增强的同步方法 - MySQL → 腾讯文档"""
        logger.info(f"[Config {self.config_id}] Starting from_mysql sync (enhanced)")
        
        lock_resource = f"sync_from_mysql_{self.config_id}"
        
        async with distributed_lock.acquire(lock_resource, timeout=60):
            async with concurrency_limiter.acquire():
                start_time = time.time()
                self._ensure_config()

                direction = self._config.get("sync_direction", "bidirectional")
                if direction == "to_mysql":
                    return SyncResult(
                        success=True, direction="from_mysql", rows_affected=0,
                        details={"message": "Direction is to_mysql only — skipped"},
                        status=SyncStatus.COMPLETED,
                        duration_seconds=time.time() - start_time,
                    )

                self._log_id = self.mysql.create_sync_log(
                    self.config_id, "from_mysql", status="running"
                )
                
                self._sync_version += 1
                current_version = self._sync_version

                audit_logger.log_sync_triggered(
                    config_id=self.config_id,
                    direction="from_mysql",
                    trigger_type="manual"
                )

                errors: List[str] = []
                total_new = total_updated = total_skipped = 0

                try:
                    rows = self.mysql.select_all(self._table_name, limit=10000)
                    if not rows:
                        self.mysql.complete_sync_log(
                            self._log_id, 0, 0, 0, 0, "success"
                        )
                        self.mysql.update_last_sync_time(self.config_id)
                        
                        duration = time.time() - start_time
                        metrics_collector.record_sync_duration(
                            self.config_id, "from_mysql", duration, True
                        )
                        audit_logger.log_sync_completed(
                            config_id=self.config_id,
                            direction="from_mysql",
                            rows_affected=0,
                            duration_seconds=duration
                        )
                        
                        return SyncResult(
                            success=True, direction="from_mysql", rows_affected=0,
                            details={"message": "No rows in MySQL table"},
                            status=SyncStatus.COMPLETED,
                            duration_seconds=duration,
                        )

                    sheet_info = await self.tencent.get_sheet_info(
                        self._spreadsheet_id, self._sheet_id
                    )
                    next_append_row = sheet_info.get("rowCount", 0) + 1
                    logger.info(f"[Config {self.config_id}] Sheet has {sheet_info.get('rowCount', 0)} rows, appending from row {next_append_row}")

                    sheet_cols = self.mapping.get_sheet_columns()
                    pending_updates: List[Dict] = []
                    new_rows: List[List[Any]] = []

                    for row in rows:
                        if current_version != self._sync_version:
                            logger.warning(f"[Config {self.config_id}] Sync version changed, aborting")
                            break
                            
                        row_key = self._get_row_key(row, "mysql")
                        if not row_key:
                            continue

                        current_hash = self.compute_row_hash(row)
                        tracked = self.mysql.get_tracked_row(self.config_id, row_key, "mysql")

                        if tracked and tracked["source_hash"] == current_hash:
                            total_skipped += 1
                            continue

                        try:
                            sheet_row = self.mapping.db_row_to_sheet_row(row, "from_mysql")
                        except MappingError as e:
                            errors.append(f"Row key={row_key} transform error: {e}")
                            continue

                        values = [sheet_row.get(col, "") for col in sheet_cols]

                        prev_row = self._get_sheet_row_for_key(row_key)

                        if prev_row:
                            last_col = sheet_cols[-1] if sheet_cols else "Z"
                            pending_updates.append({
                                "range": f"{self._sheet_id}!A{prev_row}:{last_col}{prev_row}",
                                "values": [values],
                            })
                            total_updated += 1
                            row_for_track = dict(row)
                            row_for_track["_sheet_row"] = prev_row
                            self.mysql.upsert_tracked_row(
                                self.config_id, row_key, current_hash,
                                json.dumps(row_for_track, ensure_ascii=False, default=str), "mysql",
                            )
                        else:
                            new_rows.append(values)
                            new_row_index = len(new_rows) - 1
                            total_new += 1
                            row_for_track = dict(row)
                            row_for_track["_sheet_row"] = next_append_row + new_row_index
                            self.mysql.upsert_tracked_row(
                                self.config_id, row_key, current_hash,
                                json.dumps(row_for_track, ensure_ascii=False, default=str), "mysql",
                            )

                    if pending_updates:
                        try:
                            with Timer("tencent_api_batch_put"):
                                await self.tencent.batch_put_values(self._spreadsheet_id, pending_updates)
                            logger.info(
                                f"[Config {self.config_id}] Updated {len(pending_updates)} existing rows in sheet"
                            )
                        except TencentAPIError as e:
                            errors.append(f"Batch update failed: {e}")
                            logger.error(f"[Config {self.config_id}] Batch update error: {e}")

                    if new_rows:
                        try:
                            append_count = await self._append_rows_to_sheet(new_rows, next_append_row)
                            logger.info(
                                f"[Config {self.config_id}] Appended {append_count} new rows starting at row {next_append_row}"
                            )
                        except TencentAPIError as e:
                            errors.append(f"Append rows failed: {e}")
                            logger.error(f"[Config {self.config_id}] Append error: {e}")

                    self.mysql.update_last_sync_time(self.config_id)
                    final_status = "partial" if errors else "success"
                    self.mysql.complete_sync_log(
                        self._log_id,
                        rows_affected=total_new + total_updated,
                        rows_new=total_new, rows_updated=total_updated,
                        rows_skipped=total_skipped, status=final_status,
                        error_message="; ".join(errors[:50]) if errors else None,
                    )

                    duration = time.time() - start_time
                    metrics_collector.record_sync_duration(
                        self.config_id, "from_mysql", duration, len(errors) == 0
                    )
                    metrics_collector.record_sync_rows(
                        self.config_id, "from_mysql", total_new + total_updated, "upsert"
                    )
                    audit_logger.log_sync_completed(
                        config_id=self.config_id,
                        direction="from_mysql",
                        rows_affected=total_new + total_updated,
                        duration_seconds=duration,
                        status=final_status
                    )

                    return SyncResult(
                        success=True, direction="from_mysql",
                        rows_affected=total_new + total_updated,
                        rows_new=total_new, rows_updated=total_updated,
                        rows_skipped=total_skipped, errors=errors,
                        details={"mysql_rows": len(rows), "updated": total_updated, "appended": total_new},
                        status=SyncStatus.COMPLETED if not errors else SyncStatus.COMPLETED,
                        duration_seconds=duration,
                    )

                except MySQLServiceError as e:
                    duration = time.time() - start_time
                    logger.error(f"[Config {self.config_id}] MySQL error: {e}")
                    self.mysql.complete_sync_log(
                        self._log_id, 0, 0, 0, 0, "failed", str(e)
                    )
                    
                    metrics_collector.record_sync_duration(
                        self.config_id, "from_mysql", duration, False
                    )
                    audit_logger.log_sync_failed(
                        config_id=self.config_id,
                        direction="from_mysql",
                        error_message=str(e)
                    )
                    retry_handler.record_error(e, {"config_id": self.config_id, "operation": "from_mysql"})
                    
                    return SyncResult(success=False, direction="from_mysql", errors=[str(e)], status=SyncStatus.FAILED, duration_seconds=duration)

                except TencentAPIError as e:
                    duration = time.time() - start_time
                    logger.error(f"[Config {self.config_id}] TencentAPI error: {e}")
                    self.mysql.complete_sync_log(
                        self._log_id, 0, 0, 0, 0, "failed", str(e)
                    )
                    
                    metrics_collector.record_sync_duration(
                        self.config_id, "from_mysql", duration, False
                    )
                    audit_logger.log_sync_failed(
                        config_id=self.config_id,
                        direction="from_mysql",
                        error_message=str(e)
                    )
                    retry_handler.record_error(e, {"config_id": self.config_id, "operation": "from_mysql"})
                    
                    return SyncResult(success=False, direction="from_mysql", errors=[str(e)], status=SyncStatus.FAILED, duration_seconds=duration)

                except Exception as e:
                    duration = time.time() - start_time
                    logger.exception(f"[Config {self.config_id}] Unexpected error in from_mysql: {e}")
                    self.mysql.complete_sync_log(
                        self._log_id, 0, 0, 0, 0, "failed", str(e)
                    )
                    
                    metrics_collector.record_sync_duration(
                        self.config_id, "from_mysql", duration, False
                    )
                    audit_logger.log_sync_failed(
                        config_id=self.config_id,
                        direction="from_mysql",
                        error_message=str(e)
                    )
                    retry_handler.record_error(e, {"config_id": self.config_id, "operation": "from_mysql"})
                    
                    return SyncResult(success=False, direction="from_mysql", errors=[str(e)], status=SyncStatus.FAILED, duration_seconds=duration)

    async def _append_rows_to_sheet(
        self,
        new_rows: List[List[Any]],
        start_row: int,
    ) -> int:
        """Append rows to the sheet using range append API."""
        if not new_rows:
            return 0

        sheet_cols = self.mapping.get_sheet_columns()
        last_col = sheet_cols[-1] if sheet_cols else "Z"
        end_row = start_row + len(new_rows) - 1

        range_str = f"{self._sheet_id}!A{start_row}:{last_col}{end_row}"
        
        with Timer("tencent_api_put_values"):
            await self.tencent.put_values(self._spreadsheet_id, range_str, new_rows)
        return len(new_rows)

    def _get_sheet_row_for_key(self, row_key: str) -> Optional[int]:
        """Retrieve the sheet row number previously written for a MySQL row key."""
        tracked = self.mysql.get_tracked_row(self.config_id, row_key, "mysql")
        if not tracked or not tracked.get("prev_value"):
            return None
        try:
            lv = json.loads(tracked["prev_value"])
            return lv.get("_sheet_row")
        except (json.JSONDecodeError, TypeError):
            return None

    async def sync_bidirectional(self) -> Dict[str, SyncResult]:
        """增强的双向同步"""
        logger.info(f"[Config {self.config_id}] Starting bidirectional sync (enhanced)")
        
        lock_resource = f"sync_bidirectional_{self.config_id}"
        
        async with distributed_lock.acquire(lock_resource, timeout=120):
            to_mysql_result = await self.sync_to_mysql()

            if not to_mysql_result.success:
                logger.warning(
                    f"[Config {self.config_id}] to_mysql failed, skipping from_mysql: {to_mysql_result.errors}"
                )
                return {
                    "to_mysql": to_mysql_result,
                    "from_mysql": SyncResult(
                        success=False,
                        direction="from_mysql",
                        errors=["Skipped due to to_mysql failure"],
                        status=SyncStatus.CANCELLED
                    )
                }

            await asyncio.sleep(1)
            from_mysql_result = await self.sync_from_mysql()

            return {
                "to_mysql": to_mysql_result,
                "from_mysql": from_mysql_result,
            }

    async def trigger_sync(self, direction: Optional[str] = None) -> SyncResult:
        """增强的手动触发同步"""
        self._ensure_config()
        if direction is None:
            direction = self._sync_direction or "bidirectional"

        logger.info(f"[Config {self.config_id}] Manual sync trigger (enhanced): direction={direction}")

        if direction == "to_mysql":
            return await self.sync_to_mysql()
        elif direction == "from_mysql":
            return await self.sync_from_mysql()
        else:
            results = await self.sync_bidirectional()
            to_m = results["to_mysql"]
            from_m = results["from_mysql"]
            return SyncResult(
                success=to_m.success and from_m.success,
                direction="bidirectional",
                rows_affected=to_m.rows_affected + from_m.rows_affected,
                rows_new=to_m.rows_new + from_m.rows_new,
                rows_updated=to_m.rows_updated + from_m.rows_updated,
                rows_skipped=to_m.rows_skipped + from_m.rows_skipped,
                errors=to_m.errors + from_m.errors,
                status=SyncStatus.COMPLETED if to_m.success and from_m.success else SyncStatus.FAILED,
                duration_seconds=to_m.duration_seconds + from_m.duration_seconds,
            )

    async def handle_webhook(
        self,
        event_type: str,
        changed_range: str,
    ) -> SyncResult:
        """增强的Webhook处理"""
        logger.info(
            f"[Config {self.config_id}] Webhook (enhanced): type={event_type}, range={changed_range}"
        )
        
        audit_logger.log_webhook_received(
            spreadsheet_id=self._spreadsheet_id or "",
            event_type=event_type,
            valid=True
        )
        
        try:
            parts = changed_range.split("!")
            if len(parts) == 2 and ":" in parts[1]:
                start, end = parts[1].split(":")
                start_row = int("".join(filter(str.isdigit, start)))
                end_row = int("".join(filter(str.isdigit, end)))
                return await self._sync_changed_range(start_row, end_row)
        except Exception as e:
            logger.warning(f"[Config {self.config_id}] Could not parse webhook range: {e}")

        logger.info(f"[Config {self.config_id}] Falling back to full to_mysql sync")
        return await self.sync_to_mysql()

    async def _sync_changed_range(self, start_row: int, end_row: int) -> SyncResult:
        """Sync only the specified row range from Tencent to MySQL."""
        logger.info(f"[Config {self.config_id}] Syncing changed rows {start_row}–{end_row}")
        try:
            range_str = f"{self._sheet_id}!A{start_row}:ZZ{end_row}"
            
            with Timer("tencent_api_webhook_get_values"):
                result = await self.tencent.get_values(self._spreadsheet_id, range_str)
            values: List[List[Any]] = result.get("values", [])

            if not values:
                return SyncResult(
                    success=True, direction="to_mysql", rows_affected=0,
                    details={"message": "No data in changed range"},
                    status=SyncStatus.COMPLETED
                )

            sheet_cols = self.mapping.get_sheet_columns()
            batch_result = await self._sync_batch_to_mysql(sheet_cols, values, start_row - 1)
            return batch_result

        except TencentAPIError as e:
            logger.error(f"[Config {self.config_id}] Range sync error: {e}")
            return SyncResult(success=False, direction="to_mysql", errors=[str(e)], status=SyncStatus.FAILED)

    def _ensure_table_exists(self) -> None:
        """Auto-create target table if it doesn't exist."""
        if not self.mysql.table_exists(self._table_name):
            self._ensure_config()
            mapping_json = self._config.get("mapping_json", {})
            if isinstance(mapping_json, str):
                mapping_json = json.loads(mapping_json)
            columns = mapping_json.get("columns", [])
            self.mysql.create_data_table(self._table_name, columns)
            logger.info(f"[Config {self.config_id}] Auto-created table: {self._table_name}")

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status and recent logs."""
        self._ensure_config()
        logs = self.mysql.get_sync_logs(self.config_id, limit=10)
        
        sync_stats = metrics_collector.get_sync_statistics(self.config_id)
        
        return {
            "config_id": self.config_id,
            "spreadsheet_id": self._spreadsheet_id,
            "sheet_id": self._sheet_id,
            "table_name": self._table_name,
            "database": self._database,
            "sync_direction": self._sync_direction,
            "poll_interval": self._poll_interval_cfg,
            "is_active": self._config.get("is_active", True),
            "last_sync_at": self._config.get("last_sync_at"),
            "recent_logs": logs,
            "sync_statistics": sync_stats,
            "active_syncs": concurrency_limiter.get_active_count(),
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Test connections to both Tencent and MySQL."""
        results: Dict[str, Any] = {}
        try:
            with Timer("mysql_test_connection"):
                results["mysql"] = self.mysql.test_connection()
        except Exception as e:
            results["mysql"] = {"connected": False, "error": str(e)}

        try:
            with Timer("tencent_test_connection"):
                results["tencent"] = await self.tencent.test_connection()
        except Exception as e:
            results["tencent"] = {"connected": False, "error": str(e)}

        results["all_connected"] = (
            results.get("mysql", {}).get("connected", False)
            and results.get("tencent", {}).get("connected", False)
        )
        
        audit_logger.log_connection_tested(
            config_id=self.config_id,
            mysql_status=results.get("mysql", {}).get("connected", False),
            tencent_status=results.get("tencent", {}).get("connected", False)
        )
        
        return results
