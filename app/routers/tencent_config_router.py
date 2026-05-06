from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.models.config_models import (
    TencentApiConfigCreate,
    TencentApiConfigResponse,
    TencentApiConfigTestResult,
    TencentApiConfigUpdate,
)
from app.services.mysql_service import get_mysql_service
from app.services.tencent_config_service import (
    TencentApiConfigService,
    get_tencent_config_service,
)

router = APIRouter(prefix="/api/tencent-configs", tags=["tencent-configs"])


def get_service() -> TencentApiConfigService:
    return get_tencent_config_service(get_mysql_service())


def _storage_unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=f"Platform metadata storage unavailable: {detail}",
    )


@router.get("", response_model=List[TencentApiConfigResponse])
async def list_tencent_configs(
    skip: int = 0,
    limit: int = 100,
    service: TencentApiConfigService = Depends(get_service),
):
    try:
        return service.list_configs(skip=skip, limit=limit)
    except Exception:
        return []


@router.post("", response_model=TencentApiConfigResponse)
async def create_tencent_config(
    config: TencentApiConfigCreate,
    service: TencentApiConfigService = Depends(get_service),
):
    try:
        return service.create_config(config)
    except HTTPException:
        raise
    except Exception as exc:
        raise _storage_unavailable(str(exc)) from exc


@router.get("/{config_id}", response_model=TencentApiConfigResponse)
async def get_tencent_config(
    config_id: int,
    service: TencentApiConfigService = Depends(get_service),
):
    try:
        config = service.get_config(config_id)
        if config is None:
            raise HTTPException(status_code=404, detail="Config not found")
        return config
    except HTTPException:
        raise
    except Exception as exc:
        raise _storage_unavailable(str(exc)) from exc


@router.put("/{config_id}", response_model=TencentApiConfigResponse)
async def update_tencent_config(
    config_id: int,
    config: TencentApiConfigUpdate,
    service: TencentApiConfigService = Depends(get_service),
):
    try:
        updated = service.update_config(config_id, config)
        if updated is None:
            raise HTTPException(status_code=404, detail="Config not found")
        return updated
    except HTTPException:
        raise
    except Exception as exc:
        raise _storage_unavailable(str(exc)) from exc


@router.delete("/{config_id}")
async def delete_tencent_config(
    config_id: int,
    service: TencentApiConfigService = Depends(get_service),
):
    try:
        success = service.delete_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Config not found")
        return {"message": "Config deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        raise _storage_unavailable(str(exc)) from exc


@router.post("/{config_id}/test", response_model=TencentApiConfigTestResult)
async def test_tencent_api_connection(
    config_id: int,
    service: TencentApiConfigService = Depends(get_service),
):
    try:
        return service.test_connection(config_id)
    except Exception as exc:
        raise _storage_unavailable(str(exc)) from exc
