from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import asyncio
import hmac
import hashlib
import json
import logging

from app.services.mysql_service import get_mysql_service
from app.services.sync_engine import SyncEngine
from app.services.db_exception import DatabaseServiceError, handle_service_exception

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/tencent", tags=["Tencent Webhook"])


async def verify_tencent_signature(
    payload: bytes,
    signature: Optional[str],
    timestamp: Optional[str],
    token: str,
) -> bool:
    """Verify Tencent Document Webhook HMAC-SHA256 signature."""
    if not signature or not timestamp or not token:
        return False
    expected = hmac.new(
        token.encode("utf-8"),
        payload + timestamp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


async def _webhook_sync_task(
    config_id: int,
    event_type: str,
    changed_range: str,
    direction: str,
) -> None:
    """Background webhook sync task (scheduled via asyncio.create_task)."""
    try:
        engine = SyncEngine(config_id=config_id)
        if direction in ("to_mysql", "bidirectional"):
            await engine.handle_webhook(event_type, changed_range)
        logger.info("[Webhook background] Config %d sync completed", config_id)
    except DatabaseServiceError as exc:
        logger.error("[Webhook background] Config %d DB error: %s", config_id, exc)
    except Exception as exc:
        logger.exception("[Webhook background] Config %d sync error: %s", config_id, exc)


@router.post("/callback")
async def handle_tencent_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None),
    x_timestamp: Optional[str] = Header(None),
):
    """
    Handle Tencent Document change callback.
    Looks up config by spreadsheet_id and triggers incremental range sync.
    Returns immediately; actual sync runs in background.
    """
    try:
        body = await request.body()

        from app.config import get_settings
        config = get_settings()
        token = config.tencent.callback_token or ""
        if token:
            if not await verify_tencent_signature(body, x_signature, x_timestamp, token):
                raise HTTPException(status_code=403, detail="Signature verification failed")

        data = json.loads(body)
        event_type = data.get("event", "")
        spreadsheet_id = data.get("spreadsheetId", "")
        changed_range = data.get("changedRange", "")

        if not spreadsheet_id:
            raise HTTPException(status_code=400, detail="Missing spreadsheetId")

        db = get_mysql_service()
        result = db.execute(
            "SELECT * FROM sync_configs WHERE spreadsheet_id = %s AND is_active = 1",
            (spreadsheet_id,),
        )

        if not result:
            raise HTTPException(status_code=404, detail="No matching sync config found")

        config_data = result[0]
        direction = config_data.get("sync_direction", "bidirectional")

        asyncio.create_task(
            _webhook_sync_task(
                config_id=config_data["id"],
                event_type=event_type,
                changed_range=changed_range,
                direction=direction,
            )
        )
        return {"status": "ok", "message": "Received, processing in background"}

    except HTTPException:
        raise
    except DatabaseServiceError as exc:
        raise handle_service_exception(exc, "tencent_webhook")
    except json.JSONDecodeError as exc:
        logger.error("Webhook JSON parse error: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as exc:
        raise handle_service_exception(exc, "tencent_webhook")


@router.get("/health")
async def webhook_health():
    """Webhook endpoint health check."""
    return {"status": "ok"}