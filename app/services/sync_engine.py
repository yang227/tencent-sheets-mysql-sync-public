"""
Synchronization Engine - Core bidirectional sync logic.
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
from app.services.mysql_config_service import MySQLConfigService
from app.services.mysql_service import MySQLService, MySQLServiceError, get_mysql_service
from app.services.mapping import MappingEngine, MappingError
from app.services.tencent_config_service import TencentApiConfigService

logger = logging.getLogger(__name__)

# Global config cache to avoid repeated DB queries
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
    Bidirectional synchronization engine between Tencent Sheets and MySQL.

    Features:
    - Hash-based change detection (SHA256)
    - Batch processing with configurable batch size
    - Automatic retry on transient failures
    - Detailed per-row error collection
    - Progress logging during long syncs
    - Append detection for MySQL→Tencent inserts
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
        self._mysql: Optional[MySQLService] = None
        self._tencent: Optional[TencentAPI] = tencent_api
        self._mapping: Optional[MappingEngine] = None
        self._config: Optional[Dict[str, Any]] = None
        self._log_id: Optional[int] = None

        # Short-lived fields loaded from config
        self._spreadsheet_id: Optional[str] = None
        self._sheet_id: Optional[str] = None
        self._table_name: Optional[str] = None
        self._database: Optional[str] = None
        self._mysql_config_id: Optional[int] = None
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
    def mysql(self) -> MySQLService:
        if self._mysql is None:
            self._ensure_config()
            if self._mysql_config_id:
                self._mysql = MySQLConfigService(self.metadata_db).build_mysql_service(
                    self._mysql_config_id
                )
            else:
                self._mysql = self.metadata_db
        return self._mysql

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

    # ─── Config Loading ─────────────────────────────────────────────

    def _ensure_config(self) -> None:
        """Load configuration from DB on first access (with caching)."""
        current_time = time.time()

        # Check cache first (TTL: 5 minutes)
        if self.config_id in _config_cache:
            cache_time = _config_cache_time.get(self.config_id, 0)
            if current_time - cache_time < CONFIG_CACHE_TTL:
                self._config = _config_cache[self.config_id]
                self._spreadsheet_id = self._config["spreadsheet_id"]
                self._sheet_id = self._config["sheet_id"]
                self._table_name = self._config["table_name"]
                self._database = self._config.get("database", "")
                self._mysql_config_id = self._config.get("mysql_config_id")
                self._tencent_config_id = self._config.get("tencent_config_id")
                self._sync_direction = self._config.get("sync_direction", "bidirectional")
                self._poll_interval_cfg = self._config.get("poll_interval", 30)
                return

        if self._config is None:
            self._config = self.metadata_db.get_sync_config(self.config_id)
            if not self._config:
                raise SyncEngineError(f"Configuration {self.config_id} not found in database")

            # Validate required fields
            required_fields = ["spreadsheet_id", "sheet_id", "table_name"]
            for field in required_fields:
                if field not in self._config or not self._config.get(field):
                    raise SyncEngineError(
                        f"Configuration {self.config_id} missing required field: {field}"
                    )

            self._spreadsheet_id = self._config["spreadsheet_id"]
            self._sheet_id = self._config["sheet_id"]
            self._table_name = self._config["table_name"]
            self._database = self._config.get("database", "")
            self._mysql_config_id = self._config.get("mysql_config_id")
            self._tencent_config_id = self._config.get("tencent_config_id")
            self._sync_direction = self._config.get("sync_direction", "bidirectional")
            self._poll_interval_cfg = self._config.get("poll_interval", 30)

            # Update cache
            _config_cache[self.config_id] = self._config
            _config_cache_time[self.config_id] = current_time

            logger.info(
                f"[Config {self.config_id}] Loaded config: "
                f"table={self._table_name}, direction={self._sync_direction}"
            )

    # ─── Change Detection (Batch Optimized) ─────────────────────

    async def _batch_get_tracked_rows(
        self,
        config_id: int,
        source_row_keys: List[str],
        source: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch tracked rows to avoid N+1 queries.
        Returns dict keyed by source_row_key.
        """
        if not source_row_keys:
            return {}

        # MySQL has a limit on IN clause, batch the keys
        tracked = {}
        batch_size = 1000
        for i in range(0, len(source_row_keys), batch_size):
            batch_keys = source_row_keys[i:i + batch_size]
            placeholders = ",".join(["%s"] * len(batch_keys))
            query = f"""
                SELECT source_row_key, source_hash, prev_value, last_sync_at
                FROM change_tracking
                WHERE config_id = %s AND source = %s AND source_row_key IN ({placeholders})
            """
            results = self.metadata_db.execute(query, [config_id, source] + batch_keys)
            for row in results:
                tracked[row["source_row_key"]] = row

        return tracked

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

    # ─── Tencent → MySQL ──────────────────────────────────────────

    async def sync_to_mysql(self) -> SyncResult:
        """
        Sync data from Tencent Sheets to MySQL.
        Detects unchanged rows via SHA256 hash — only writes changed rows.
        """
        logger.info(f"[Config {self.config_id}] Starting to_mysql sync")
        self._ensure_config()
        self._ensure_table_exists()

        direction = self._config.get("sync_direction", "bidirectional")
        if direction == "from_mysql":
            return SyncResult(
                success=True, direction="to_mysql", rows_affected=0,
                details={"message": "Direction is from_mysql only — skipped"}
            )

        self._log_id = self.metadata_db.create_sync_log(
            self.config_id, "to_mysql", status="running"
        )

        errors: List[str] = []
        total_new = total_updated = total_skipped = 0

        try:
            # ── Step 1: Read sheet range ──────────────────────────
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

            result = await self.tencent.get_values(self._spreadsheet_id, range_str)
            values: List[List[Any]] = result.get("values", [])

            if not values:
                self.metadata_db.complete_sync_log(
                    self._log_id, rows_affected=0, rows_new=0, rows_updated=0,
                    rows_skipped=0, status="success"
                )
                self.metadata_db.update_last_sync_time(self.config_id)
                return SyncResult(
                    success=True, direction="to_mysql", rows_affected=0,
                    details={"message": "No data rows in sheet"}
                )

            sheet_cols = self.mapping.get_sheet_columns()
            total_rows = len(values)

            # ── Step 2: Process in batches ────────────────────────
            for batch_start in range(0, total_rows, self.batch_size):
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
                    f"{rows_done}/{total_rows} rows, "
                    f"+{batch_result.rows_new} new, +{batch_result.rows_updated} updated"
                )

            self.metadata_db.update_last_sync_time(self.config_id)
            final_status = "partial" if errors else "success"
            self.metadata_db.complete_sync_log(
                self._log_id,
                rows_affected=total_new + total_updated,
                rows_new=total_new,
                rows_updated=total_updated,
                rows_skipped=total_skipped,
                status=final_status,
                error_message="; ".join(errors[:50]) if errors else None,
            )

            return SyncResult(
                success=True, direction="to_mysql",
                rows_affected=total_new + total_updated,
                rows_new=total_new, rows_updated=total_updated,
                rows_skipped=total_skipped, errors=errors,
                details={"total_sheet_rows": total_rows},
            )

        except TencentAPIError as e:
            logger.error(f"[Config {self.config_id}] TencentAPI error: {e}")
            self.metadata_db.complete_sync_log(
                self._log_id, 0, 0, 0, 0, "failed", str(e)
            )
            return SyncResult(success=False, direction="to_mysql", errors=[str(e)])

        except MySQLServiceError as e:
            logger.error(f"[Config {self.config_id}] MySQL error: {e}")
            self.metadata_db.complete_sync_log(
                self._log_id, 0, 0, 0, 0, "failed", str(e)
            )
            return SyncResult(success=False, direction="to_mysql", errors=[str(e)])

        except Exception as e:
            logger.exception(f"[Config {self.config_id}] Unexpected error in to_mysql: {e}")
            self.metadata_db.complete_sync_log(
                self._log_id, 0, 0, 0, 0, "failed", str(e)
            )
            return SyncResult(success=False, direction="to_mysql", errors=[str(e)])

    async def _sync_batch_to_mysql(
        self,
        sheet_cols: List[str],
        batch_values: List[List[Any]],
        batch_offset: int,
    ) -> SyncResult:
        """Process one batch of rows from Tencent → MySQL."""
        rows_new = rows_updated = rows_skipped = 0
        errors: List[str] = []
        
        # Batch fetch tracked rows to avoid N+1 queries
        batch_row_keys = []
        row_data_list = []
        
        for i, row in enumerate(batch_values):
            row_num = batch_offset + i + 1
            
            # Skip completely empty rows
            if not row or all(v is None or v == "" for v in row):
                continue
            
            # Build sheet row dict keyed by column letter
            row_data: Dict[str, Any] = {}
            for col_idx, col_letter in enumerate(sheet_cols):
                row_data[col_letter] = row[col_idx] if col_idx < len(row) else None
            row_data["_row_number"] = str(row_num)
            
            batch_row_keys.append(str(row_num))
            row_data_list.append((row_num, row_data))
        
        # Batch fetch all tracked rows for this batch
        tracked_rows = self.metadata_db.batch_get_tracked_rows(
            self.config_id, batch_row_keys, "tencent"
        )
        
        # Process rows with cached tracking data
        db_rows_to_upsert = []
        tracking_to_upsert = []
        
        for row_num, row_data in row_data_list:
            current_hash = self.compute_row_hash(row_data)
            
            # Check if unchanged using cached tracking data
            tracked = tracked_rows.get(str(row_num))
            if tracked and tracked["source_hash"] == current_hash:
                rows_skipped += 1
                continue
            
            # Transform
            try:
                db_row = self.mapping.sheet_row_to_db_row(row_data, "to_mysql")
            except MappingError as e:
                errors.append(f"Row {row_num} transform error: {e}")
                continue
            
            db_rows_to_upsert.append((db_row, row_num, current_hash))
        
        # Batch upsert into MySQL
        if db_rows_to_upsert:
            for db_row, row_num, current_hash in db_rows_to_upsert:
                try:
                    pk_cols = self.mapping.primary_keys
                    affected = self.mysql.insert_or_update(self._table_name, db_row, pk_cols)
                    
                    if affected == 1:
                        rows_new += 1
                    elif affected == 2:
                        rows_updated += 1
                    
                    # Track for next sync
                    tracking_to_upsert.append((
                        str(row_num),
                        current_hash,
                        json.dumps(db_row, ensure_ascii=False, default=str),
                    ))
                except MySQLServiceError as e:
                    errors.append(f"Row {row_num} DB error: {e}")
                    logger.warning(f"[Config {self.config_id}] Row {row_num} write failed: {e}")
        
        # Batch upsert tracking data
        if tracking_to_upsert:
            self.metadata_db.batch_upsert_tracked_rows(
                self.config_id, tracking_to_upsert, "tencent"
            )
        
        return SyncResult(
            success=True, direction="to_mysql",
            rows_new=rows_new, rows_updated=rows_updated,
            rows_skipped=rows_skipped, errors=errors,
        )

    # ─── MySQL → Tencent ─────────────────────────────────────────

    async def sync_from_mysql(self) -> SyncResult:
        """
        Sync data from MySQL to Tencent Sheets.
        Detects changed rows via SHA256 hash. New rows are appended at the end.
        """
        logger.info(f"[Config {self.config_id}] Starting from_mysql sync")
        self._ensure_config()

        direction = self._config.get("sync_direction", "bidirectional")
        if direction == "to_mysql":
            return SyncResult(
                success=True, direction="from_mysql", rows_affected=0,
                details={"message": "Direction is to_mysql only — skipped"}
            )

        self._log_id = self.metadata_db.create_sync_log(
            self.config_id, "from_mysql", status="running"
        )

        errors: List[str] = []
        total_new = total_updated = total_skipped = 0

        try:
            # ── Step 1: Read MySQL rows ─────────────────────────
            rows = self.mysql.select_all(self._table_name, limit=10000)
            if not rows:
                self.metadata_db.complete_sync_log(
                    self._log_id, 0, 0, 0, 0, "success"
                )
                self.metadata_db.update_last_sync_time(self.config_id)
                return SyncResult(
                    success=True, direction="from_mysql", rows_affected=0,
                    details={"message": "No rows in MySQL table"}
                )

            # ── Step 2: Fetch current sheet row count for append ──
            sheet_info = await self.tencent.get_sheet_info(
                self._spreadsheet_id, self._sheet_id
            )
            next_append_row = sheet_info.get("rowCount", 0) + 1
            logger.info(f"[Config {self.config_id}] Sheet has {sheet_info.get('rowCount', 0)} rows, appending from row {next_append_row}")

            sheet_cols = self.mapping.get_sheet_columns()
            pending_updates: List[Dict] = []  # {range, values}
            new_rows: List[List[Any]] = []

            # ── Step 3: Compute changes (Batch Optimized) ───────────────────
            # Batch fetch all tracked rows to avoid N+1 queries
            row_keys = [self._get_row_key(row, "mysql") for row in rows if self._get_row_key(row, "mysql")]
            tracked_rows = await self._batch_get_tracked_rows(
                self.config_id, row_keys, "mysql"
            )

            tracking_to_upsert = []

            for row in rows:
                row_key = self._get_row_key(row, "mysql")
                if not row_key:
                    continue

                current_hash = self.compute_row_hash(row)
                tracked = tracked_rows.get(row_key)

                if tracked and tracked["source_hash"] == current_hash:
                    total_skipped += 1
                    continue

                # Build sheet row (only mapped from_mysql/bidirectional columns)
                try:
                    sheet_row = self.mapping.db_row_to_sheet_row(row, "from_mysql")
                except MappingError as e:
                    errors.append(f"Row key={row_key} transform error: {e}")
                    continue

                values = [sheet_row.get(col, "") for col in sheet_cols]

                # Check if this key was previously written to a sheet row
                prev_row = None
                if tracked and tracked.get("prev_value"):
                    try:
                        prev_data = json.loads(tracked["prev_value"])
                        prev_row = prev_data.get("_sheet_row")
                    except (json.JSONDecodeError, AttributeError):
                        pass

                if prev_row:
                    # Update in-place
                    last_col = sheet_cols[-1] if sheet_cols else "Z"
                    pending_updates.append({
                        "range": f"{self._sheet_id}!A{prev_row}:{last_col}{prev_row}",
                        "values": [values],
                    })
                    total_updated += 1
                    # Track with the row number where it currently lives
                    row_for_track = dict(row)
                    row_for_track["_sheet_row"] = prev_row
                    tracking_to_upsert.append((
                        row_key, current_hash,
                        json.dumps(row_for_track, ensure_ascii=False, default=str),
                    ))
                else:
                    # Append new row — store its position in new_rows list for later mapping
                    new_rows.append(values)
                    new_row_index = len(new_rows) - 1  # 0-based index within new_rows
                    total_new += 1
                    # Track with a placeholder _sheet_row; will be updated after append
                    row_for_track = dict(row)
                    row_for_track["_sheet_row"] = next_append_row + new_row_index
                    tracking_to_upsert.append((
                        row_key, current_hash,
                        json.dumps(row_for_track, ensure_ascii=False, default=str),
                    ))

            # ── Step 4: Batch write updates ──────────────────────
            if pending_updates:
                try:
                    await self.tencent.batch_put_values(self._spreadsheet_id, pending_updates)
                    logger.info(
                        f"[Config {self.config_id}] Updated {len(pending_updates)} existing rows in sheet"
                    )
                except TencentAPIError as e:
                    errors.append(f"Batch update failed: {e}")
                    logger.error(f"[Config {self.config_id}] Batch update error: {e}")

            # ── Step 5: Append new rows ──────────────────────────
            if new_rows:
                try:
                    append_count = await self._append_rows_to_sheet(new_rows, next_append_row)
                    logger.info(
                        f"[Config {self.config_id}] Appended {append_count} new rows starting at row {next_append_row}"
                    )
                except TencentAPIError as e:
                    errors.append(f"Append rows failed: {e}")
                    logger.error(f"[Config {self.config_id}] Append error: {e}")

            # Batch upsert tracking data
            if tracking_to_upsert:
                self.metadata_db.batch_upsert_tracked_rows(
                    self.config_id, tracking_to_upsert, "mysql"
                )

            self.metadata_db.update_last_sync_time(self.config_id)
            final_status = "partial" if errors else "success"
            self.metadata_db.complete_sync_log(
                self._log_id,
                rows_affected=total_new + total_updated,
                rows_new=total_new, rows_updated=total_updated,
                rows_skipped=total_skipped, status=final_status,
                error_message="; ".join(errors[:50]) if errors else None,
            )

            return SyncResult(
                success=True, direction="from_mysql",
                rows_affected=total_new + total_updated,
                rows_new=total_new, rows_updated=total_updated,
                rows_skipped=total_skipped, errors=errors,
                details={"mysql_rows": len(rows), "updated": total_updated, "appended": total_new},
            )

        except MySQLServiceError as e:
            logger.error(f"[Config {self.config_id}] MySQL error: {e}")
            self.metadata_db.complete_sync_log(
                self._log_id, 0, 0, 0, 0, "failed", str(e)
            )
            return SyncResult(success=False, direction="from_mysql", errors=[str(e)])

        except TencentAPIError as e:
            logger.error(f"[Config {self.config_id}] TencentAPI error: {e}")
            self.metadata_db.complete_sync_log(
                self._log_id, 0, 0, 0, 0, "failed", str(e)
            )
            return SyncResult(success=False, direction="from_mysql", errors=[str(e)])

        except Exception as e:
            logger.exception(f"[Config {self.config_id}] Unexpected error in from_mysql: {e}")
            self.metadata_db.complete_sync_log(
                self._log_id, 0, 0, 0, 0, "failed", str(e)
            )
            return SyncResult(success=False, direction="from_mysql", errors=[str(e)])

    async def _append_rows_to_sheet(
        self,
        new_rows: List[List[Any]],
        start_row: int,
    ) -> int:
        """
        Append rows to the sheet using range append API.
        Returns the number of rows actually appended.
        """
        if not new_rows:
            return 0

        sheet_cols = self.mapping.get_sheet_columns()
        last_col = sheet_cols[-1] if sheet_cols else "Z"
        end_row = start_row + len(new_rows) - 1

        range_str = f"{self._sheet_id}!A{start_row}:{last_col}{end_row}"
        await self.tencent.put_values(self._spreadsheet_id, range_str, new_rows)
        return len(new_rows)

    def _get_sheet_row_for_key_from_cache(self, tracked: Optional[Dict[str, Any]]) -> Optional[int]:
        """
        Extract the sheet row number from a tracked row dict (from the tracked_rows cache).
        Stored in tracked["prev_value"]["_sheet_row"].
        """
        if not tracked or not tracked.get("prev_value"):
            return None
        try:
            lv = json.loads(tracked["prev_value"])
            return lv.get("_sheet_row")
        except (json.JSONDecodeError, TypeError):
            return None

    def _get_sheet_row_for_key(self, row_key: str) -> Optional[int]:
        """
        Retrieve the sheet row number previously written for a MySQL row key.
        Stored in the change_tracking.prev_value._sheet_row field.
        """
        tracked = self.metadata_db.get_tracked_row(self.config_id, row_key, "mysql")
        if not tracked or not tracked.get("prev_value"):
            return None
        try:
            lv = json.loads(tracked["prev_value"])
            return lv.get("_sheet_row")
        except (json.JSONDecodeError, TypeError):
            return None

    def _get_sheet_row_for_key_from_cache(self, tracked: Optional[Dict]) -> Optional[int]:
        """
        Retrieve the sheet row number from cached tracked data.
        """
        if not tracked or not tracked.get("prev_value"):
            return None
        try:
            lv = json.loads(tracked["prev_value"])
            return lv.get("_sheet_row")
        except (json.JSONDecodeError, TypeError):
            return None

    # ─── Bidirectional ────────────────────────────────────────────

    async def sync_bidirectional(self) -> Dict[str, SyncResult]:
        """
        Perform bidirectional sync: Tencent→MySQL first, then MySQL→Tencent.
        Adding a 1s delay between directions to avoid thundering herd.
        """
        logger.info(f"[Config {self.config_id}] Starting bidirectional sync")
        to_mysql_result = await self.sync_to_mysql()

        if not to_mysql_result.success:
            logger.warning(
                f"[Config {self.config_id}] to_mysql failed, skipping from_mysql: {to_mysql_result.errors}"
            )
            return {"to_mysql": to_mysql_result, "from_mysql": SyncResult(success=False, direction="from_mysql", errors=["Skipped due to to_mysql failure"])}

        await asyncio.sleep(1)  # Prevent write-write race condition
        from_mysql_result = await self.sync_from_mysql()

        return {
            "to_mysql": to_mysql_result,
            "from_mysql": from_mysql_result,
        }

    # ─── Public Trigger ───────────────────────────────────────────

    async def trigger_sync(self, direction: Optional[str] = None) -> SyncResult:
        """
        Manually trigger a sync. Uses config direction if not specified.
        """
        self._ensure_config()
        if direction is None:
            direction = self._sync_direction or "bidirectional"

        logger.info(f"[Config {self.config_id}] Manual sync trigger: direction={direction}")

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
            )

    # ─── Webhook Handler ──────────────────────────────────────────

    async def handle_webhook(
        self,
        event_type: str,
        changed_range: str,
    ) -> SyncResult:
        """
        Handle Tencent Document webhook: sync only the changed range.
        Falls back to full sync on parse failure.
        """
        logger.info(
            f"[Config {self.config_id}] Webhook: type={event_type}, range={changed_range}"
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
            result = await self.tencent.get_values(self._spreadsheet_id, range_str)
            values: List[List[Any]] = result.get("values", [])

            if not values:
                return SyncResult(
                    success=True, direction="to_mysql", rows_affected=0,
                    details={"message": "No data in changed range"}
                )

            sheet_cols = self.mapping.get_sheet_columns()
            batch_result = await self._sync_batch_to_mysql(sheet_cols, values, start_row - 1)
            return batch_result

        except TencentAPIError as e:
            logger.error(f"[Config {self.config_id}] Range sync error: {e}")
            return SyncResult(success=False, direction="to_mysql", errors=[str(e)])

    # ─── Table Setup ──────────────────────────────────────────────

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

    # ─── Status ─────────────────────────────────────────────────

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status and recent logs."""
        self._ensure_config()
        logs = self.metadata_db.get_sync_logs(self.config_id, limit=10)
        return {
            "config_id": self.config_id,
            "spreadsheet_id": self._spreadsheet_id,
            "sheet_id": self._sheet_id,
            "table_name": self._table_name,
            "database": self._database,
            "mysql_config_id": self._mysql_config_id,
            "tencent_config_id": self._tencent_config_id,
            "sync_direction": self._sync_direction,
            "poll_interval": self._poll_interval_cfg,
            "is_active": self._config.get("is_active", True),
            "last_sync_at": self._config.get("last_sync_at"),
            "recent_logs": logs,
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Test metadata DB, target MySQL, and real Tencent sheet access."""
        self._ensure_config()
        results: Dict[str, Any] = {}
        try:
            results["metadata_mysql"] = self.metadata_db.test_connection()
        except Exception as e:
            results["metadata_mysql"] = {"connected": False, "error": str(e)}

        try:
            results["mysql"] = self.mysql.test_connection()
        except Exception as e:
            results["mysql"] = {"connected": False, "error": str(e)}

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
                    self._spreadsheet_id,
                    self._sheet_id,
                )
                results["tencent"] = {"connected": True, "details": sheet_info}
        except Exception as e:
            results["tencent"] = {"connected": False, "error": str(e)}

        results["all_connected"] = (
            results.get("mysql", {}).get("connected", False)
            and results.get("tencent", {}).get("connected", False)
        )
        return results
