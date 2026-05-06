"""
审计日志服务 - 记录所有关键操作
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """审计事件类型"""
    CONFIG_CREATED = "config_created"
    CONFIG_UPDATED = "config_updated"
    CONFIG_DELETED = "config_deleted"
    SYNC_TRIGGERED = "sync_triggered"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    CONNECTION_TESTED = "connection_tested"
    WEBHOOK_RECEIVED = "webhook_received"
    ERROR_OCCURRED = "error_occurred"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"


class AuditLogger:
    """
    审计日志记录器
    记录所有关键操作，用于合规审计和问题追溯
    """
    
    def __init__(self):
        self._events: List[Dict[str, Any]] = []
        self._max_events = 10000
    
    def log_event(
        self,
        event_type: Any,
        operator: str = "system",
        resource_type: str = "",
        resource_id: Any = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        记录审计事件
        
        Args:
            event_type: 事件类型 (AuditEventType枚举或字符串)
            operator: 操作者
            resource_type: 资源类型
            resource_id: 资源ID
            details: 详细信息
            status: 操作状态
            error_message: 错误信息
            ip_address: IP地址
            user_agent: 用户代理
        """
        event_type_value = event_type.value if hasattr(event_type, 'value') else str(event_type)
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type_value,
            "operator": operator,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id is not None else None,
            "details": details or {},
            "status": status,
            "error_message": error_message,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        
        self._events.append(event)
        
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        
        logger.info(
            f"AUDIT: {event_type_value} by {operator} on {resource_type}:{resource_id} - {status}"
        )
        
        if error_message:
            logger.error(f"AUDIT ERROR: {error_message}")
    
    def log_config_created(
        self,
        config_id: int,
        spreadsheet_id: str,
        table_name: str,
        operator: str = "system",
        **kwargs
    ) -> None:
        """记录配置创建"""
        self.log_event(
            event_type=AuditEventType.CONFIG_CREATED,
            operator=operator,
            resource_type="sync_config",
            resource_id=config_id,
            details={
                "spreadsheet_id": spreadsheet_id,
                "table_name": table_name,
                **kwargs
            }
        )
    
    def log_config_updated(
        self,
        config_id: int,
        changes: Dict[str, Any],
        operator: str = "system",
    ) -> None:
        """记录配置更新"""
        self.log_event(
            event_type=AuditEventType.CONFIG_UPDATED,
            operator=operator,
            resource_type="sync_config",
            resource_id=config_id,
            details={"changes": changes}
        )
    
    def log_config_deleted(
        self,
        config_id: int,
        operator: str = "system",
    ) -> None:
        """记录配置删除"""
        self.log_event(
            event_type=AuditEventType.CONFIG_DELETED,
            operator=operator,
            resource_type="sync_config",
            resource_id=config_id,
            details={"soft_delete": True}
        )
    
    def log_sync_triggered(
        self,
        config_id: int,
        direction: str,
        trigger_type: str = "manual",
        operator: str = "system",
    ) -> None:
        """记录同步触发"""
        self.log_event(
            event_type=AuditEventType.SYNC_TRIGGERED,
            operator=operator,
            resource_type="sync",
            resource_id=config_id,
            details={
                "direction": direction,
                "trigger_type": trigger_type
            }
        )
    
    def log_sync_completed(
        self,
        config_id: int,
        direction: str,
        rows_affected: int,
        duration_seconds: float,
        status: str = "success",
        **kwargs
    ) -> None:
        """记录同步完成"""
        self.log_event(
            event_type=AuditEventType.SYNC_COMPLETED,
            operator="system",
            resource_type="sync",
            resource_id=config_id,
            details={
                "direction": direction,
                "rows_affected": rows_affected,
                "duration_seconds": duration_seconds,
                **kwargs
            },
            status=status
        )
    
    def log_sync_failed(
        self,
        config_id: int,
        direction: str,
        error_message: str,
        **kwargs
    ) -> None:
        """记录同步失败"""
        self.log_event(
            event_type=AuditEventType.SYNC_FAILED,
            operator="system",
            resource_type="sync",
            resource_id=config_id,
            details={
                "direction": direction,
                **kwargs
            },
            status="failed",
            error_message=error_message
        )
    
    def log_connection_tested(
        self,
        config_id: int,
        mysql_status: str,
        tencent_status: str,
        operator: str = "system",
    ) -> None:
        """记录连接测试"""
        self.log_event(
            event_type=AuditEventType.CONNECTION_TESTED,
            operator=operator,
            resource_type="connection",
            resource_id=config_id,
            details={
                "mysql_status": mysql_status,
                "tencent_status": tencent_status
            },
            status="success" if mysql_status == "connected" and tencent_status == "connected" else "failed"
        )
    
    def log_webhook_received(
        self,
        spreadsheet_id: str,
        event_type: str,
        valid: bool = True,
    ) -> None:
        """记录Webhook接收"""
        self.log_event(
            event_type=AuditEventType.WEBHOOK_RECEIVED,
            operator="webhook",
            resource_type="webhook",
            resource_id=spreadsheet_id,
            details={
                "event_type": event_type,
                "valid": valid
            },
            status="success" if valid else "failed"
        )
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        operator: str = "system",
    ) -> None:
        """记录错误"""
        self.log_event(
            event_type=AuditEventType.ERROR_OCCURRED,
            operator=operator,
            resource_type="error",
            resource_id=error_type,
            details=context or {},
            status="failed",
            error_message=error_message
        )
    
    def get_events(
        self,
        event_type: Optional[Any] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        查询审计事件
        
        Args:
            event_type: 事件类型过滤 (AuditEventType枚举或字符串)
            resource_type: 资源类型过滤
            resource_id: 资源ID过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            审计事件列表
        """
        events = self._events.copy()
        
        if event_type:
            event_type_value = event_type.value if hasattr(event_type, 'value') else str(event_type)
            events = [e for e in events if e["event_type"] == event_type_value]
        
        if resource_type:
            events = [e for e in events if e["resource_type"] == resource_type]
        
        if resource_id is not None:
            events = [e for e in events if e["resource_id"] == str(resource_id)]
        
        if start_time:
            start_iso = start_time.isoformat()
            events = [e for e in events if e["timestamp"] >= start_iso]
        
        if end_time:
            end_iso = end_time.isoformat()
            events = [e for e in events if e["timestamp"] <= end_iso]
        
        return events[-limit:]
    
    def get_events_for_resource(
        self,
        resource_type: str,
        resource_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取特定资源的所有审计事件"""
        return self.get_events(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit
        )
    
    def export_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json",
    ) -> str:
        """
        导出审计事件
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            format: 导出格式 (json/csv)
            
        Returns:
            导出的事件数据
        """
        events = self.get_events(start_time=start_time, end_time=end_time, limit=100000)
        
        if format == "json":
            return json.dumps(events, ensure_ascii=False, indent=2)
        elif format == "csv":
            if not events:
                return ""
            
            headers = ["timestamp", "event_type", "operator", "resource_type", 
                      "resource_id", "status", "error_message"]
            
            csv_lines = [",".join(headers)]
            for event in events:
                row = [
                    event.get("timestamp", ""),
                    event.get("event_type", ""),
                    event.get("operator", ""),
                    event.get("resource_type", ""),
                    str(event.get("resource_id", "")),
                    event.get("status", ""),
                    event.get("error_message", "").replace(",", ";"),
                ]
                csv_lines.append(",".join(f'"{v}"' if ',' in str(v) else str(v) for v in row))
            
            return "\n".join(csv_lines)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取审计统计信息"""
        if not self._events:
            return {
                "total_events": 0,
                "event_types": {},
                "status_counts": {},
                "operators": {},
            }
        
        event_types = {}
        status_counts = {}
        operators = {}
        
        for event in self._events:
            event_type = event["event_type"]
            status = event["status"]
            operator = event["operator"]
            
            event_types[event_type] = event_types.get(event_type, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1
            operators[operator] = operators.get(operator, 0) + 1
        
        return {
            "total_events": len(self._events),
            "event_types": event_types,
            "status_counts": status_counts,
            "operators": operators,
            "oldest_event": self._events[0]["timestamp"] if self._events else None,
            "newest_event": self._events[-1]["timestamp"] if self._events else None,
        }
    
    def clear_old_events(self, before_date: datetime) -> int:
        """清理指定日期之前的审计事件"""
        before_iso = before_date.isoformat()
        original_count = len(self._events)
        self._events = [e for e in self._events if e["timestamp"] >= before_iso]
        removed = original_count - len(self._events)
        logger.info(f"Cleared {removed} audit events before {before_iso}")
        return removed


audit_logger = AuditLogger()
