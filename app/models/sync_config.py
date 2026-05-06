from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class SyncDirection(str, Enum):
    TO_MYSQL = "to_mysql"
    FROM_MYSQL = "from_mysql"
    BIDIRECTIONAL = "bidirectional"


class ColumnMapping(BaseModel):
    sheet_col: str = Field(..., description="腾讯文档列标识，如 A, B, C")
    sheet_header: str = Field(..., description="表头名称")
    db_column: str = Field(..., description="MySQL字段名")
    db_type: str = Field(..., description="MySQL字段类型，如 VARCHAR(64), INT, DATETIME")
    direction: Literal["bidirectional", "to_mysql_only", "from_mysql_only"] = "bidirectional"
    primary_key: bool = False
    transform: Optional[str] = None


class MappingConfig(BaseModel):
    columns: List[ColumnMapping]
    sheet_header_row: int = 1
    data_start_row: int = 2


class SyncConfig(BaseModel):
    id: int
    spreadsheet_id: str
    sheet_id: str
    table_name: str
    database: str = ""
    mysql_config_id: Optional[int] = None
    tencent_config_id: Optional[int] = None
    mapping_json: MappingConfig
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    poll_interval: int = 30
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True


class SyncConfigCreate(BaseModel):
    spreadsheet_id: str
    sheet_id: str
    table_name: str
    database: str = ""
    mysql_config_id: Optional[int] = None
    tencent_config_id: Optional[int] = None
    mapping_json: MappingConfig
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    poll_interval: int = 30


class SyncConfigUpdate(BaseModel):
    sheet_id: Optional[str] = None
    table_name: Optional[str] = None
    database: Optional[str] = None
    mysql_config_id: Optional[int] = None
    tencent_config_id: Optional[int] = None
    mapping_json: Optional[MappingConfig] = None
    sync_direction: Optional[SyncDirection] = None
    poll_interval: Optional[int] = None
    is_active: Optional[bool] = None


class SyncStatus(BaseModel):
    config_id: int
    is_active: bool
    last_sync_at: Optional[datetime]
    recent_logs: List['SyncLog'] = []


from app.models.sync_log import SyncLog
SyncStatus.model_rebuild()
