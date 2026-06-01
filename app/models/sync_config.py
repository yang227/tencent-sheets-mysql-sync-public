from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class SyncDirection(str, Enum):
    TO_MYSQL = "to_mysql"
    FROM_MYSQL = "from_mysql"
    BIDIRECTIONAL = "bidirectional"


class ColumnMapping(BaseModel):
    sheet_col: str = Field(..., description="Tencent sheet column, e.g. A, B, C")
    sheet_header: str = Field(..., description="Header name")
    db_column: str = Field(..., description="Database column name")
    db_type: str = Field(..., description="Database column type, e.g. VARCHAR(64), INT, TIMESTAMP")
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
    db_type: str = "mysql"
    mysql_config_id: Optional[int] = None
    postgresql_config_id: Optional[int] = None
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
    db_type: str = "mysql"
    mysql_config_id: Optional[int] = None
    postgresql_config_id: Optional[int] = None
    tencent_config_id: Optional[int] = None
    mapping_json: MappingConfig
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    poll_interval: int = 30


class SyncConfigUpdate(BaseModel):
    sheet_id: Optional[str] = None
    table_name: Optional[str] = None
    database: Optional[str] = None
    db_type: Optional[str] = None
    mysql_config_id: Optional[int] = None
    postgresql_config_id: Optional[int] = None
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