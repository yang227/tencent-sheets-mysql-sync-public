"""
增强的同步路由器 - 集成审计、日志和监控
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timedelta
import json

from app.models.sync_config import SyncConfig, SyncConfigCreate, SyncConfigUpdate
from app.models.sync_log import SyncLog
from app.services.mysql_service import get_mysql_service, MySQLService
from app.services.sync_engine_enhanced import SyncEngine, SyncStatus, SyncEngineError
from app.services.audit_logger import audit_logger
from app.services.metrics_collector import metrics_collector

router = APIRouter(prefix="/api/sync", tags=["增强同步操作"])


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
    if isinstance(config.get("mapping_json"), str):
        config["mapping_json"] = json.loads(config["mapping_json"])
    return config


def get_client_info(request: Request) -> dict:
    """获取客户端信息"""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.post("/{config_id}/trigger")
async def trigger_sync(
    config_id: int,
    direction: Optional[str] = None,
    db: MySQLService = Depends(get_db),
    request: Request = None,
):
    """
    增强的同步触发接口
    添加了审计日志和性能监控
    """
    try:
        config = load_config(db, config_id)
        client_info = get_client_info(request) if request else {}

        audit_logger.log_event(
            event_type="sync_triggered",
            operator=client_info.get("ip_address", "unknown"),
            resource_type="sync",
            resource_id=config_id,
            details={
                "direction": direction or "auto",
                "trigger_type": "manual",
                "client_ip": client_info.get("ip_address"),
            }
        )

        engine = SyncEngine(
            config_id=config["id"],
            mysql_service=db,
            poll_interval=config.get("poll_interval", 30),
        )

        result = await engine.trigger_sync(direction=direction)

        # 记录同步完成审计日志
        if result.success:
            audit_logger.log_sync_completed(
                config_id=config_id,
                direction=result.direction,
                rows_affected=result.rows_affected,
                duration_seconds=result.duration_seconds,
                rows_new=result.rows_new,
                rows_updated=result.rows_updated,
            )
        else:
            audit_logger.log_sync_failed(
                config_id=config_id,
                direction=result.direction,
                error_message="; ".join(result.errors) if result.errors else "未知错误",
            )

        return {
            "message": "同步完成",
            "success": result.success,
            "direction": result.direction,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "status": result.status.value,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "details": result.details,
        }

    except SyncEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_sync_failed(
            config_id=config_id,
            direction=direction or "auto",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")


@router.post("/{config_id}/to-mysql")
async def sync_to_mysql(
    config_id: int,
    db: MySQLService = Depends(get_db),
    request: Request = None,
):
    """增强的腾讯文档 → MySQL 同步"""
    try:
        config = load_config(db, config_id)
        client_info = get_client_info(request) if request else {}

        audit_logger.log_sync_triggered(
            config_id=config_id,
            direction="to_mysql",
            trigger_type="manual",
            operator=client_info.get("ip_address", "unknown")
        )

        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        result = await engine.sync_to_mysql()

        if result.success:
            audit_logger.log_sync_completed(
                config_id=config_id,
                direction="to_mysql",
                rows_affected=result.rows_affected,
                duration_seconds=result.duration_seconds,
                rows_new=result.rows_new,
                rows_updated=result.rows_updated,
            )
        else:
            audit_logger.log_sync_failed(
                config_id=config_id,
                direction="to_mysql",
                error_message="; ".join(result.errors) if result.errors else "未知错误",
            )
        
        return {
            "message": "腾讯文档 → MySQL 同步完成",
            "success": result.success,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "status": result.status.value,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
        }
    except SyncEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_sync_failed(config_id=config_id, direction="to_mysql", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")


@router.post("/{config_id}/from-mysql")
async def sync_from_mysql(
    config_id: int,
    db: MySQLService = Depends(get_db),
    request: Request = None,
):
    """增强的 MySQL → 腾讯文档 同步"""
    try:
        config = load_config(db, config_id)
        client_info = get_client_info(request) if request else {}

        audit_logger.log_sync_triggered(
            config_id=config_id,
            direction="from_mysql",
            trigger_type="manual",
            operator=client_info.get("ip_address", "unknown")
        )

        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        result = await engine.sync_from_mysql()

        if result.success:
            audit_logger.log_sync_completed(
                config_id=config_id,
                direction="from_mysql",
                rows_affected=result.rows_affected,
                duration_seconds=result.duration_seconds,
                rows_new=result.rows_new,
                rows_updated=result.rows_updated,
            )
        else:
            audit_logger.log_sync_failed(
                config_id=config_id,
                direction="from_mysql",
                error_message="; ".join(result.errors) if result.errors else "未知错误",
            )
        
        return {
            "message": "MySQL → 腾讯文档 同步完成",
            "success": result.success,
            "rows_affected": result.rows_affected,
            "rows_new": result.rows_new,
            "rows_updated": result.rows_updated,
            "rows_skipped": result.rows_skipped,
            "status": result.status.value,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
        }
    except SyncEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_sync_failed(config_id=config_id, direction="from_mysql", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")


@router.get("/{config_id}/status")
async def get_sync_status(config_id: int, db: MySQLService = Depends(get_db)):
    """获取增强的同步状态，包含统计信息"""
    try:
        config = load_config(db, config_id)
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        return engine.get_sync_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}/statistics")
async def get_sync_statistics(config_id: int, db: MySQLService = Depends(get_db)):
    """获取同步统计信息"""
    try:
        config = load_config(db, config_id)
        
        stats = metrics_collector.get_sync_statistics(config_id)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/test")
async def test_connections(
    config_id: int,
    db: MySQLService = Depends(get_db),
    request: Request = None,
):
    """增强的连接测试"""
    try:
        config = load_config(db, config_id)
        client_info = get_client_info(request) if request else {}

        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        results = await engine.test_connection()
        
        audit_logger.log_connection_tested(
            config_id=config_id,
            mysql_status=results.get("mysql", {}).get("connected", False),
            tencent_status=results.get("tencent", {}).get("connected", False),
            operator=client_info.get("ip_address", "unknown")
        )
        
        return results
    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_error(
            error_type="connection_test_error",
            error_message=str(e),
            context={"config_id": config_id}
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/logs")
async def get_audit_logs(
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    since: Optional[str] = None,
    limit: int = 100,
):
    """获取审计日志"""
    try:
        start_time = None
        if since:
            start_time = datetime.fromisoformat(since)
        
        events = audit_logger.get_events(
            resource_type=resource_type,
            resource_id=resource_id,
            start_time=start_time,
            limit=limit,
        )
        
        return {
            "events": events,
            "total": len(events),
            "statistics": audit_logger.get_statistics(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/export")
async def export_audit_logs(
    since: Optional[str] = None,
    until: Optional[str] = None,
    format: str = "json",
):
    """导出审计日志"""
    try:
        start_time = None
        end_time = None
        
        if since:
            start_time = datetime.fromisoformat(since)
        if until:
            end_time = datetime.fromisoformat(until)
        
        if format == "csv":
            content = audit_logger.export_events(start_time, end_time, "csv")
            return {
                "format": "csv",
                "content": content,
            }
        else:
            content = audit_logger.export_events(start_time, end_time, "json")
            return {
                "format": "json",
                "content": content,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics():
    """获取系统指标"""
    try:
        return metrics_collector.get_all_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/prometheus")
async def get_metrics_prometheus():
    """获取Prometheus格式指标"""
    try:
        from fastapi.responses import PlainTextResponse
        content = metrics_collector.export_prometheus_format()
        return PlainTextResponse(content=content, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/sync")
async def get_sync_metrics():
    """获取同步相关指标"""
    try:
        return {
            "sync_statistics": metrics_collector.get_sync_statistics(),
            "api_statistics": metrics_collector.get_api_statistics(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/reset")
async def reset_metrics():
    """重置所有指标"""
    try:
        metrics_collector.reset_metrics()
        return {"message": "指标已重置"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
