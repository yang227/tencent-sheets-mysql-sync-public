from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.services.mysql_service import get_mysql_service, MySQLService
from app.services.sync_engine import SyncEngine, SyncEngineError
from app.services.db_exception import DatabaseServiceError, handle_service_exception
from app.utils import parse_config_row

router = APIRouter(prefix="/api/sync", tags=["Sync Operations"])


def get_db() -> MySQLService:
    return get_mysql_service()


def load_config(db: MySQLService, config_id: int) -> dict:
    result = db.execute(
        "SELECT * FROM sync_configs WHERE id = %s AND is_active = 1",
        (config_id,),
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Config {config_id} not found or inactive")
    config = result[0]
    parse_config_row(config)
    return config


@router.post("/{config_id}/trigger")
async def trigger_sync(config_id: int, db: MySQLService = Depends(get_db)):
    """Trigger a full sync. Direction is determined by config."""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(
            config_id=config["id"], mysql_service=db,
            poll_interval=config.get("poll_interval", 30),
        )
        result = await engine.trigger_sync()
        return {
            "message": "Sync completed",
            "success": result.success,
            "direction": result.direction,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "errors": result.errors,
            "details": result.details,
        }
    except HTTPException:
        raise
    except DatabaseServiceError as exc:
        raise handle_service_exception(exc, "trigger_sync")
    except Exception as exc:
        raise handle_service_exception(exc, "trigger_sync")


@router.post("/{config_id}/to-mysql")
async def sync_to_mysql(config_id: int, db: MySQLService = Depends(get_db)):
    """Sync: Tencent Sheets → Target database."""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        result = await engine.sync_to_mysql()
        return {
            "message": "Tencent Sheets → DB sync completed",
            "success": result.success,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "errors": result.errors,
        }
    except HTTPException:
        raise
    except DatabaseServiceError as exc:
        raise handle_service_exception(exc, "sync_to_mysql")
    except Exception as exc:
        raise handle_service_exception(exc, "sync_to_mysql")


@router.post("/{config_id}/from-mysql")
async def sync_from_mysql(config_id: int, db: MySQLService = Depends(get_db)):
    """Sync: Target database → Tencent Sheets."""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        result = await engine.sync_from_mysql()
        return {
            "message": "DB → Tencent Sheets sync completed",
            "success": result.success,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "errors": result.errors,
        }
    except HTTPException:
        raise
    except DatabaseServiceError as exc:
        raise handle_service_exception(exc, "sync_from_mysql")
    except Exception as exc:
        raise handle_service_exception(exc, "sync_from_mysql")


@router.get("/{config_id}/status")
async def get_sync_status(config_id: int, db: MySQLService = Depends(get_db)):
    """Get sync config status and recent logs."""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        return engine.get_sync_status()
    except HTTPException:
        raise
    except DatabaseServiceError as exc:
        raise handle_service_exception(exc, "get_sync_status")
    except Exception as exc:
        raise handle_service_exception(exc, "get_sync_status")


@router.post("/{config_id}/test")
async def test_connections(config_id: int, db: MySQLService = Depends(get_db)):
    """Test database and Tencent Sheets connection status."""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        return await engine.test_connection()
    except HTTPException:
        raise
    except DatabaseServiceError as exc:
        raise handle_service_exception(exc, "test_connections")
    except Exception as exc:
        raise handle_service_exception(exc, "test_connections")