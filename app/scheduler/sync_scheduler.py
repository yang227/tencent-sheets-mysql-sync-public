"""
Sync scheduler — runs periodic sync jobs for all active configurations.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Dict, Optional
import asyncio
import logging
import time

from app.services.mysql_service import get_mysql_service
from app.services.sync_engine import SyncEngine
from app.services.metrics_collector import metrics_collector
from app.services.audit_logger import audit_logger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


class SyncScheduler:
    """
    Manages periodic sync jobs for all active configurations.
    Each config gets its own APScheduler job identified by sync_{config_id}.
    """

    _jobs: Dict[int, str] = {}  # config_id → job_id string

    @classmethod
    def init(cls) -> None:
        """Load all active configs and schedule their sync jobs."""
        db = get_mysql_service()

        try:
            configs = db.get_all_sync_configs(active_only=True)
            logger.info(f"Scheduling {len(configs)} active sync configs")
        except Exception as e:
            logger.error(f"Failed to load sync configs: {e}")
            return

        for cfg in configs:
            try:
                cls.add_sync_job(
                    job_id=cfg["id"],
                    config_id=cfg["id"],
                    interval_seconds=cfg.get("poll_interval", 30),
                )
            except Exception as e:
                logger.error(f"Failed to schedule config {cfg['id']}: {e}")

        if not scheduler.running:
            scheduler.start()
            logger.info("Sync scheduler started")

    @classmethod
    def add_sync_job(
        cls,
        *,
        job_id: int,
        config_id: int,
        interval_seconds: int = 30,
    ) -> None:
        """
        Add or replace a periodic sync job.
        Uses `config_id` as APScheduler job id so replacing works correctly.
        """
        job_id_str = f"sync_{job_id}"

        if job_id_str in cls._jobs:
            cls.remove_sync_job(job_id)

        async def sync_task() -> None:
            await cls._run_sync(config_id)

        scheduler.add_job(
            func=sync_task,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id_str,
            replace_existing=True,
            max_instances=1,
            coalesce=True,  # Collapse missed runs into one
        )
        cls._jobs[job_id] = job_id_str
        logger.info(f"Scheduled sync job: {job_id_str} every {interval_seconds}s")

    @classmethod
    async def _run_sync(cls, config_id: int) -> None:
        """Execute a single sync run for one config."""
        logger.info(f"[Config {config_id}] Scheduled sync starting")
        engine: Optional[SyncEngine] = None
        try:
            engine = SyncEngine(config_id=config_id)
            engine._ensure_config()
            direction = engine._sync_direction
        except Exception as e:
            logger.exception(f"[Config {config_id}] Failed to init engine: {e}")
            return

        # 每个方向独立 try，避免 one direction 失败影响另一个
        if direction in ("to_mysql", "bidirectional"):
            start = time.monotonic()
            try:
                result = engine.sync_to_mysql()
                if asyncio.iscoroutine(result):
                    result = await result
                duration = time.monotonic() - start
                success = result.success
                if success and result.rows_affected > 0:
                    logger.info(
                        f"[Config {config_id}] to_mysql done: "
                        f"+{result.rows_new} new, +{result.rows_updated} updated, "
                        f"~{result.rows_skipped} skipped"
                    )
                elif not success:
                    logger.warning(
                        f"[Config {config_id}] to_mysql completed with errors: {result.errors}"
                    )
                # 记录 metrics + audit
                metrics_collector.record_sync_duration(config_id, "to_mysql", duration, success)
                if result.rows_affected > 0:
                    metrics_collector.record_sync_rows(config_id, "to_mysql", result.rows_affected, "upsert")
                if success:
                    audit_logger.log_sync_completed(
                        config_id=config_id, direction="to_mysql",
                        rows_affected=result.rows_affected, duration_seconds=duration,
                        rows_new=result.rows_new, rows_updated=result.rows_updated,
                    )
                else:
                    audit_logger.log_sync_failed(
                        config_id=config_id, direction="to_mysql",
                        error_message="; ".join(result.errors) if result.errors else "Unknown error",
                    )
            except Exception as e:
                duration = time.monotonic() - start
                logger.exception(f"[Config {config_id}] to_mysql failed: {e}")
                metrics_collector.record_sync_duration(config_id, "to_mysql", duration, False)
                audit_logger.log_sync_failed(config_id=config_id, direction="to_mysql", error_message=str(e))

        if direction in ("from_mysql", "bidirectional"):
            start = time.monotonic()
            try:
                result = engine.sync_from_mysql()
                if asyncio.iscoroutine(result):
                    result = await result
                duration = time.monotonic() - start
                success = result.success
                if success and result.rows_affected > 0:
                    logger.info(
                        f"[Config {config_id}] from_mysql done: "
                        f"+{result.rows_new} new, +{result.rows_updated} updated"
                    )
                elif not success:
                    logger.warning(
                        f"[Config {config_id}] from_mysql completed with errors: {result.errors}"
                    )
                # 记录 metrics + audit
                metrics_collector.record_sync_duration(config_id, "from_mysql", duration, success)
                if result.rows_affected > 0:
                    metrics_collector.record_sync_rows(config_id, "from_mysql", result.rows_affected, "upsert")
                if success:
                    audit_logger.log_sync_completed(
                        config_id=config_id, direction="from_mysql",
                        rows_affected=result.rows_affected, duration_seconds=duration,
                        rows_new=result.rows_new, rows_updated=result.rows_updated,
                    )
                else:
                    audit_logger.log_sync_failed(
                        config_id=config_id, direction="from_mysql",
                        error_message="; ".join(result.errors) if result.errors else "Unknown error",
                    )
            except Exception as e:
                duration = time.monotonic() - start
                logger.exception(f"[Config {config_id}] from_mysql failed: {e}")
                metrics_collector.record_sync_duration(config_id, "from_mysql", duration, False)
                audit_logger.log_sync_failed(config_id=config_id, direction="from_mysql", error_message=str(e))

        logger.info(f"[Config {config_id}] Scheduled sync run completed")

    @classmethod
    def remove_sync_job(cls, job_id: int) -> None:
        """Remove a sync job."""
        job_id_str = f"sync_{job_id}"
        if job_id_str in cls._jobs:
            try:
                scheduler.remove_job(job_id_str)
            except Exception as e:
                logger.warning(f"Error removing job {job_id_str}: {e}")
            del cls._jobs[job_id]
            logger.info(f"Removed sync job: {job_id_str}")

    @classmethod
    def pause_job(cls, job_id: int) -> None:
        """Pause a job (won't run until resumed)."""
        job_id_str = f"sync_{job_id}"
        if job_id_str in cls._jobs:
            scheduler.pause_job(job_id_str)
            logger.info(f"Paused job: {job_id_str}")

    @classmethod
    def resume_job(cls, job_id: int) -> None:
        """Resume a paused job."""
        job_id_str = f"sync_{job_id}"
        if job_id_str in cls._jobs:
            scheduler.resume_job(job_id_str)
            logger.info(f"Resumed job: {job_id_str}")

    @classmethod
    def shutdown(cls) -> None:
        """Shutdown the scheduler."""
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Sync scheduler shutdown")
