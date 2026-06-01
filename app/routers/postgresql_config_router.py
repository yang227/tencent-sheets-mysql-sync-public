"""
PostgreSQL config management API endpoints.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.models.postgresql_config_models import (
    PostgreSQLConfigCreate,
    PostgreSQLConfigResponse,
    PostgreSQLConfigTestResult,
    PostgreSQLConfigUpdate,
)
from app.services.db_exception import handle_service_exception
from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.postgresql_config_service import (
    PostgreSQLConfigService,
    get_postgresql_config_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/postgresql-configs", tags=["PostgreSQL 配置管理"])


def get_db() -> MySQLService:
    return get_mysql_service()


def get_service(db: MySQLService = Depends(get_db)) -> PostgreSQLConfigService:
    return get_postgresql_config_service(db)


@router.get("", response_model=List[PostgreSQLConfigResponse])
async def list_configs(service: PostgreSQLConfigService = Depends(get_service)):
    """List all active PostgreSQL configs."""
    try:
        return service.list_configs()
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_service_exception(exc, "list_pg_configs")


@router.post("", response_model=PostgreSQLConfigResponse, status_code=201)
async def create_config(
    config: PostgreSQLConfigCreate,
    service: PostgreSQLConfigService = Depends(get_service),
):
    """Create a new PostgreSQL connection config."""
    try:
        return service.create_config(config)
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_service_exception(exc, "create_pg_config")


@router.get("/{config_id}", response_model=PostgreSQLConfigResponse)
async def get_config(
    config_id: int,
    service: PostgreSQLConfigService = Depends(get_service),
):
    """Get a PostgreSQL config by ID."""
    try:
        result = service.get_config(config_id)
        if not result:
            raise HTTPException(status_code=404, detail="PostgreSQL config not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_service_exception(exc, "get_pg_config")


@router.put("/{config_id}", response_model=PostgreSQLConfigResponse)
async def update_config(
    config_id: int,
    config: PostgreSQLConfigUpdate,
    service: PostgreSQLConfigService = Depends(get_service),
):
    """Update a PostgreSQL config."""
    try:
        result = service.update_config(config_id, config)
        if not result:
            raise HTTPException(status_code=404, detail="PostgreSQL config not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_service_exception(exc, "update_pg_config")


@router.delete("/{config_id}")
async def delete_config(
    config_id: int,
    service: PostgreSQLConfigService = Depends(get_service),
):
    """Soft-delete a PostgreSQL config."""
    try:
        success = service.delete_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="PostgreSQL config not found")
        return {"message": "Config deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_service_exception(exc, "delete_pg_config")


@router.post("/{config_id}/test", response_model=PostgreSQLConfigTestResult)
async def test_connection(
    config_id: int,
    service: PostgreSQLConfigService = Depends(get_service),
):
    """Test a PostgreSQL connection."""
    try:
        return service.test_connection(config_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_service_exception(exc, "test_pg_connection")