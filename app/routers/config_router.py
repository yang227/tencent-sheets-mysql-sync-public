from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.models.sync_config import SyncConfig, SyncConfigCreate, SyncConfigUpdate
from app.services.mysql_service import MySQLService, MySQLServiceError, get_mysql_service
from app.services.sync_engine import SyncEngine
from app.utils import parse_config_row

router = APIRouter(prefix="/api/configs", tags=["sync-configs"])


def get_db() -> MySQLService:
    return get_mysql_service()


def _storage_unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=f"Platform metadata storage unavailable: {detail}",
    )


@router.get("", response_model=List[SyncConfig])
async def list_configs(db: MySQLService = Depends(get_db)):
    try:
        rows = db.execute(
            "SELECT * FROM sync_configs WHERE is_active = 1 ORDER BY created_at DESC"
        )
        configs = []
        for row in rows:
            parse_config_row(row)
            configs.append(SyncConfig.model_validate(row))
        return configs
    except Exception:
        return []


@router.post("", response_model=SyncConfig)
async def create_config(config: SyncConfigCreate, db: MySQLService = Depends(get_db)):
    try:
        mapping_dict = config.mapping_json.model_dump()
        db.create_sync_config(
            spreadsheet_id=config.spreadsheet_id,
            sheet_id=config.sheet_id,
            table_name=config.table_name,
            database=config.database,
            mysql_config_id=config.mysql_config_id,
            tencent_config_id=config.tencent_config_id,
            mapping_json=mapping_dict,
            sync_direction=config.sync_direction.value,
            poll_interval=config.poll_interval,
        )
        result = db.execute(
            "SELECT * FROM sync_configs WHERE spreadsheet_id = %s ORDER BY id DESC LIMIT 1",
            (config.spreadsheet_id,),
        )
        if not result:
            raise HTTPException(status_code=500, detail="Config created but could not be reloaded")
        row = result[0]
        parse_config_row(row)
        return SyncConfig.model_validate(row)
    except MySQLServiceError as exc:
        raise _storage_unavailable(str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{config_id}", response_model=SyncConfig)
async def get_config(config_id: int, db: MySQLService = Depends(get_db)):
    try:
        result = db.execute("SELECT * FROM sync_configs WHERE id = %s", (config_id,))
        if not result:
            raise HTTPException(status_code=404, detail="Config not found")
        row = result[0]
        parse_config_row(row)
        return SyncConfig.model_validate(row)
    except MySQLServiceError as exc:
        raise _storage_unavailable(str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{config_id}", response_model=SyncConfig)
async def update_config(
    config_id: int,
    config: SyncConfigUpdate,
    db: MySQLService = Depends(get_db),
):
    kwargs = {}
    if config.sheet_id is not None:
        kwargs["sheet_id"] = config.sheet_id
    if config.table_name is not None:
        kwargs["table_name"] = config.table_name
    if config.database is not None:
        kwargs["database"] = config.database
    if config.mysql_config_id is not None:
        kwargs["mysql_config_id"] = config.mysql_config_id
    if config.tencent_config_id is not None:
        kwargs["tencent_config_id"] = config.tencent_config_id
    if config.mapping_json is not None:
        kwargs["mapping_json"] = config.mapping_json.model_dump()
    if config.sync_direction is not None:
        kwargs["sync_direction"] = config.sync_direction.value
    if config.poll_interval is not None:
        kwargs["poll_interval"] = config.poll_interval
    if config.is_active is not None:
        kwargs["is_active"] = config.is_active

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        success = db.update_sync_config(config_id, **kwargs)
        if not success:
            raise HTTPException(status_code=404, detail="Config not found or unchanged")

        try:
            from app.scheduler.sync_scheduler import SyncScheduler

            if config.is_active is not None and not config.is_active:
                SyncScheduler.remove_sync_job(config_id)
            else:
                current = db.execute(
                    "SELECT poll_interval FROM sync_configs WHERE id = %s",
                    (config_id,),
                )
                interval = (current[0]["poll_interval"] if current else 30) or 30
                SyncScheduler.add_sync_job(
                    job_id=config_id,
                    config_id=config_id,
                    interval_seconds=interval,
                )
        except Exception:
            pass

        result = db.execute("SELECT * FROM sync_configs WHERE id = %s", (config_id,))
        if not result:
            raise HTTPException(status_code=404, detail="Config not found")
        row = result[0]
        parse_config_row(row)
        return SyncConfig.model_validate(row)
    except MySQLServiceError as exc:
        raise _storage_unavailable(str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{config_id}")
async def delete_config(config_id: int, db: MySQLService = Depends(get_db)):
    try:
        db.delete_sync_config(config_id)
        try:
            from app.scheduler.sync_scheduler import SyncScheduler

            SyncScheduler.remove_sync_job(config_id)
        except Exception:
            pass
        return {"message": "Config deleted"}
    except MySQLServiceError as exc:
        raise _storage_unavailable(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{config_id}/test")
async def test_connection(config_id: int, db: MySQLService = Depends(get_db)):
    try:
        result = db.execute("SELECT * FROM sync_configs WHERE id = %s", (config_id,))
        if not result:
            raise HTTPException(status_code=404, detail="Config not found")

        config = result[0]
        engine = SyncEngine(config_id=config["id"], mysql_service=db)
        return await engine.test_connection()
    except MySQLServiceError as exc:
        raise _storage_unavailable(str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
