from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class SyncStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SyncDirection(str, Enum):
    TO_MYSQL = "to_mysql"
    FROM_MYSQL = "from_mysql"


class SyncLog(BaseModel):
    id: int
    config_id: int
    direction: SyncDirection
    rows_affected: int = 0
    status: SyncStatus = SyncStatus.SUCCESS
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
