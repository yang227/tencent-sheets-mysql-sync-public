from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.models.sync_log import SyncLog
from app.services.mysql_service import get_mysql_service, MySQLService
from app.services.sync_engine import SyncEngine, SyncEngineError
from app.utils import parse_config_row

router = APIRouter(prefix="/api/sync", tags=["同步操作"])


def get_db() -> MySQLService:
    return get_mysql_service()


def load_config(db: MySQLService, config_id: int) -> dict:
    """Load and parse a sync config, raising 404 if missing."""
    result = db.execute(
        "SELECT * FROM sync_configs WHERE id = %s AND is_active = 1",
        (config_id,)
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"配置 {config_id} 不存在或已停用")
    config = result[0]
    parse_config_row(config)
    return config


@router.post("/{config_id}/trigger")
async def trigger_sync(config_id: int, db: MySQLService = Depends(get_db)):
    """
    手动触发一次完整同步。
    同步方向由配置决定：bidirectional / to_mysql / from_mysql。
    """
    try:
        config = load_config(db, config_id)

        engine = SyncEngine(
            config_id=config["id"],
            mysql_service=db,
            poll_interval=config.get("poll_interval", 30),
        )

        result = await engine.trigger_sync()

        return {
            "message": "同步完成",
            "success": result.success,
            "direction": result.direction,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "errors": result.errors,
            "details": result.details,
        }

    except SyncEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")


@router.post("/{config_id}/to-mysql")
async def sync_to_mysql(config_id: int, db: MySQLService = Depends(get_db)):
    """仅同步：腾讯文档 → MySQL"""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        result = await engine.sync_to_mysql()
        return {
            "message": "腾讯文档 → MySQL 同步完成",
            "success": result.success,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "errors": result.errors,
        }
    except SyncEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")


@router.post("/{config_id}/from-mysql")
async def sync_from_mysql(config_id: int, db: MySQLService = Depends(get_db)):
    """仅同步：MySQL → 腾讯文档"""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        result = await engine.sync_from_mysql()
        return {
            "message": "MySQL → 腾讯文档 同步完成",
            "success": result.success,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "errors": result.errors,
        }
    except SyncEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")


@router.get("/{config_id}/status")
async def get_sync_status(config_id: int, db: MySQLService = Depends(get_db)):
    """查看同步配置状态和最近日志"""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        return engine.get_sync_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/test")
async def test_connections(config_id: int, db: MySQLService = Depends(get_db)):
    """测试 MySQL 和腾讯文档连接状态"""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        return await engine.test_connection()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
