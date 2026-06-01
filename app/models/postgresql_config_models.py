"""
Pydantic models for PostgreSQL config CRUD.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class TestStatus(str, Enum):
    untested = "untested"
    success = "success"
    failed = "failed"


class PostgreSQLConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    host: str = Field(..., min_length=1)
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    database_name: str = Field(..., min_length=1)
    schema_name: str = Field(default="public")
    description: Optional[str] = None


class PostgreSQLConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None
    schema_name: Optional[str] = None
    description: Optional[str] = None


class PostgreSQLConfigResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    username: str
    database_name: str
    schema_name: str
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_tested_at: Optional[datetime] = None
    test_status: TestStatus = TestStatus.untested
    test_message: Optional[str] = None


class PostgreSQLConfigTestResult(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None
    version: Optional[str] = None
    database: Optional[str] = None