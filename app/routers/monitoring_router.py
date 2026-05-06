"""
监控Dashboard API - 提供实时监控数据
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

from app.services.audit_logger import audit_logger
from app.services.metrics_collector import metrics_collector
from app.services.retry_handler import retry_handler, dead_letter_queue

router = APIRouter(prefix="/api/dashboard", tags=["监控Dashboard"])


@router.get("/overview")
async def get_overview() -> Dict[str, Any]:
    """
    获取系统总览
    包含所有关键指标的摘要
    """
    try:
        sync_stats = metrics_collector.get_sync_statistics()
        api_stats = metrics_collector.get_api_statistics()
        audit_stats = audit_logger.get_statistics()
        error_stats = retry_handler.get_error_statistics()
        dlq_stats = dead_letter_queue.get_statistics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": {
                "status": "healthy",
                "uptime_seconds": (datetime.now() - datetime.now()).total_seconds(),
            },
            "sync_overview": {
                "total_syncs": sync_stats.get("syncs_total", 0),
                "successful_syncs": sync_stats.get("syncs_success", 0),
                "failed_syncs": sync_stats.get("syncs_failed", 0),
                "success_rate": sync_stats.get("success_rate", 0),
                "rows_synced": sync_stats.get("rows_synced", 0),
                "avg_duration": sync_stats.get("duration_stats", {}).get("avg", 0),
            },
            "api_overview": {
                "total_calls": api_stats.get("calls_total", 0),
                "successful_calls": api_stats.get("calls_success", 0),
                "failed_calls": api_stats.get("calls_error", 0),
                "avg_latency": api_stats.get("latency_stats", {}).get("avg", 0),
                "p95_latency": api_stats.get("latency_stats", {}).get("p95", 0),
            },
            "audit_overview": {
                "total_events": audit_stats.get("total_events", 0),
                "event_types": audit_stats.get("event_types", {}),
            },
            "error_overview": {
                "total_errors": error_stats.get("total_errors", 0),
                "retryable_errors": error_stats.get("retryable_count", 0),
                "non_retryable_errors": error_stats.get("non_retryable_count", 0),
                "critical_errors": error_stats.get("by_severity", {}).get("critical", 0),
            },
            "dead_letter_queue": {
                "total_items": dlq_stats.get("total", 0),
                "items_24h": dlq_stats.get("recent_24h", 0),
                "by_operation": dlq_stats.get("by_operation", {}),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/statistics")
async def get_sync_statistics(
    config_id: Optional[int] = None,
    period: str = "1h",
) -> Dict[str, Any]:
    """
    获取同步统计信息
    
    Args:
        config_id: 可选，特定配置ID
        period: 时间周期 (1h, 6h, 24h, 7d)
    """
    try:
        if period == "1h":
            since_hours = 1
        elif period == "6h":
            since_hours = 6
        elif period == "24h":
            since_hours = 24
        elif period == "7d":
            since_hours = 168
        else:
            since_hours = 1
        
        stats = metrics_collector.get_sync_statistics(config_id)
        
        return {
            "period": period,
            "config_id": config_id,
            "statistics": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/statistics")
async def get_api_statistics() -> Dict[str, Any]:
    """获取API调用统计"""
    try:
        return metrics_collector.get_api_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/histograms")
async def get_performance_histograms() -> Dict[str, Any]:
    """获取性能直方图数据"""
    try:
        all_metrics = metrics_collector.get_all_metrics()
        
        return {
            "histograms": all_metrics.get("histograms", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors/statistics")
async def get_error_statistics(
    period: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取错误统计
    
    Args:
        period: 可选的时间周期
    """
    try:
        since = None
        if period:
            hours = int(period.rstrip('h').rstrip('d'))
            if period.endswith('d'):
                hours *= 24
            since = datetime.now() - timedelta(hours=hours)
        
        stats = retry_handler.get_error_statistics(since)
        
        return {
            "period": period,
            "statistics": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dead-letter-queue")
async def get_dead_letter_queue(
    operation: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    获取死信队列
    
    Args:
        operation: 可选的操作类型过滤
        limit: 返回数量限制
    """
    try:
        items = dead_letter_queue.get_items(operation=operation, limit=limit)
        stats = dead_letter_queue.get_statistics()
        
        return {
            "items": items,
            "total": len(items),
            "statistics": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dead-letter-queue/{index}/retry")
async def retry_dead_letter_item(index: int) -> Dict[str, Any]:
    """
    重试死信队列中的项目
    
    Args:
        index: 项目索引
    """
    try:
        item = dead_letter_queue.retry_item(index)
        
        if item:
            return {
                "success": True,
                "message": "项目已取出，准备重试",
                "item": item,
            }
        else:
            return {
                "success": False,
                "message": "项目不存在或索引无效",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/statistics")
async def get_audit_statistics() -> Dict[str, Any]:
    """获取审计统计"""
    try:
        return audit_logger.get_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/recent")
async def get_recent_audit_events(
    event_type: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    获取最近的审计事件
    
    Args:
        event_type: 可选的事件类型过滤
        limit: 返回数量限制
    """
    try:
        from app.services.audit_logger import AuditEventType
        
        event_enum = None
        if event_type:
            try:
                event_enum = AuditEventType(event_type)
            except ValueError:
                pass
        
        events = audit_logger.get_events(
            event_type=event_enum,
            limit=limit,
        )
        
        return {
            "events": events,
            "total": len(events),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/by-resource/{resource_type}/{resource_id}")
async def get_audit_by_resource(
    resource_type: str,
    resource_id: int,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    获取特定资源的所有审计事件
    
    Args:
        resource_type: 资源类型
        resource_id: 资源ID
        limit: 返回数量限制
    """
    try:
        events = audit_logger.get_events_for_resource(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "events": events,
            "total": len(events),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """获取指标摘要"""
    try:
        all_metrics = metrics_collector.get_all_metrics()
        
        return {
            "counters": {
                name: {
                    "total": data["total"],
                    "recent_1h": metrics_collector.get_counter_value(
                        name, since=datetime.now().timestamp() - 3600
                    ),
                }
                for name, data in all_metrics.get("counters", {}).items()
            },
            "gauges": all_metrics.get("gauges", {}),
            "histogram_count": len(all_metrics.get("histograms", {})),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_health_status() -> Dict[str, Any]:
    """获取系统健康状态"""
    try:
        error_stats = retry_handler.get_error_statistics()
        dlq_stats = dead_letter_queue.get_statistics()
        
        health_score = 100
        
        critical_errors = error_stats.get("by_severity", {}).get("critical", 0)
        if critical_errors > 0:
            health_score -= min(critical_errors * 10, 30)
        
        dlq_items = dlq_stats.get("total", 0)
        if dlq_items > 100:
            health_score -= min((dlq_items - 100) * 0.5, 20)
        
        recent_errors = sum(
            1 for e in retry_handler._error_history
            if e.timestamp > datetime.now() - timedelta(minutes=5)
        )
        if recent_errors > 10:
            health_score -= min((recent_errors - 10) * 2, 20)
        
        health_score = max(0, health_score)
        
        if health_score >= 90:
            status = "healthy"
        elif health_score >= 70:
            status = "degraded"
        elif health_score >= 50:
            status = "unhealthy"
        else:
            status = "critical"
        
        return {
            "status": status,
            "health_score": health_score,
            "checks": {
                "critical_errors": {
                    "value": critical_errors,
                    "status": "ok" if critical_errors == 0 else "warning",
                },
                "dead_letter_queue": {
                    "value": dlq_items,
                    "status": "ok" if dlq_items < 100 else "warning",
                },
                "recent_errors": {
                    "value": recent_errors,
                    "status": "ok" if recent_errors < 10 else "warning",
                },
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prometheus")
async def get_prometheus_metrics() -> str:
    """获取Prometheus格式的指标"""
    try:
        return metrics_collector.export_prometheus_format()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
