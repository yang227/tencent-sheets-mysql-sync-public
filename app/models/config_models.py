"""
MySQL 连接配置和腾讯文档 API 配置的 Pydantic 模型
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TestStatus(str, Enum):
    UNTESTED = "untested"
    SUCCESS = "success"
    FAILED = "failed"


# ==================== MySQL 配置模型 ====================

class MySQLConfigBase(BaseModel):
    """MySQL 配置基础模型"""
    name: str = Field(..., min_length=1, max_length=128, description="配置名称（唯一标识）")
    host: str = Field(..., min_length=1, max_length=256, description="MySQL主机地址")
    port: int = Field(3306, ge=1, le=65535, description="MySQL端口")
    username: str = Field(..., min_length=1, max_length=128, description="用户名")
    password: str = Field(..., min_length=1, description="密码（明文，存储时加密）")
    database_name: str = Field(..., min_length=1, max_length=128, description="默认数据库名")
    charset: str = Field("utf8mb4", max_length=32, description="字符集")
    description: Optional[str] = Field(None, max_length=512, description="配置描述")
    is_active: bool = Field(True, description="是否启用")


class MySQLConfigCreate(MySQLConfigBase):
    """创建 MySQL 配置的请求模型"""
    pass


class MySQLConfigUpdate(BaseModel):
    """更新 MySQL 配置的请求模型（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    host: Optional[str] = Field(None, min_length=1, max_length=256)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=128)
    password: Optional[str] = Field(None, min_length=1, description="密码（明文，存储时加密）")
    database_name: Optional[str] = Field(None, min_length=1, max_length=128)
    charset: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=512)
    is_active: Optional[bool] = None


class MySQLConfigResponse(BaseModel):
    """MySQL 配置响应模型（不包含加密密码）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    host: str
    port: int
    username: str
    database_name: str
    charset: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_tested_at: Optional[datetime] = None
    test_status: TestStatus = TestStatus.UNTESTED
    test_message: Optional[str] = None


class MySQLConfigTestResult(BaseModel):
    """MySQL 连接测试结果"""
    success: bool = Field(..., description="连接是否成功")
    message: str = Field(..., description="结果消息")
    error: Optional[str] = Field(None, description="错误信息")


# ==================== 腾讯文档 API 配置模型 ====================

class TencentApiConfigBase(BaseModel):
    """腾讯文档 API 配置基础模型"""
    name: str = Field(..., min_length=1, max_length=128, description="配置名称（唯一标识）")
    app_id: str = Field(..., min_length=1, max_length=256, description="腾讯文档应用ID")
    open_id: str = Field(..., min_length=1, max_length=256, description="OpenID")
    access_token: str = Field(..., min_length=1, description="访问令牌（明文，存储时加密）")
    description: Optional[str] = Field(None, max_length=512, description="配置描述")
    is_active: bool = Field(True, description="是否启用")
    token_expires_at: Optional[datetime] = Field(None, description="Token过期时间")


class TencentApiConfigCreate(TencentApiConfigBase):
    """创建腾讯文档 API 配置的请求模型"""
    pass


class TencentApiConfigUpdate(BaseModel):
    """更新腾讯文档 API 配置的请求模型（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    app_id: Optional[str] = Field(None, min_length=1, max_length=256)
    open_id: Optional[str] = Field(None, min_length=1, max_length=256)
    access_token: Optional[str] = Field(None, min_length=1, description="访问令牌（明文，存储时加密）")
    description: Optional[str] = Field(None, max_length=512)
    is_active: Optional[bool] = None
    token_expires_at: Optional[datetime] = None


class TencentApiConfigResponse(BaseModel):
    """腾讯文档 API 配置响应模型（不包含加密的访问令牌）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    app_id: str
    open_id: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_tested_at: Optional[datetime] = None
    test_status: TestStatus = TestStatus.UNTESTED
    test_message: Optional[str] = None
    token_expires_at: Optional[datetime] = None


class TencentApiConfigTestResult(BaseModel):
    """腾讯文档 API 连接测试结果"""
    success: bool = Field(..., description="连接是否成功")
    message: str = Field(..., description="结果消息")
    error: Optional[str] = Field(None, description="错误信息")
