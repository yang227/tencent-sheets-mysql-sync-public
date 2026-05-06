from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import asyncio
import hmac
import hashlib
import json
import logging

from app.services.mysql_service import get_mysql_service
from app.services.sync_engine import SyncEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/tencent", tags=["腾讯文档Webhook"])


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
    """后台执行的 webhook 同步任务（由 asyncio.create_task 调度）"""
    try:
        engine = SyncEngine(config_id=config_id)
        if direction in ("to_mysql", "bidirectional"):
            await engine.handle_webhook(event_type, changed_range)
        logger.info(f"[Webhook background] Config {config_id} sync completed")
    except Exception as e:
        logger.exception(f"[Webhook background] Config {config_id} sync error: {e}")


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

        # Verify signature if token is configured
        from app.config import get_settings
        config = get_settings()
        token = config.tencent.callback_token or ""
        if token:
            if not await verify_tencent_signature(body, x_signature, x_timestamp, token):
                raise HTTPException(status_code=403, detail="签名验证失败")

        data = json.loads(body)
        event_type = data.get("event", "")
        spreadsheet_id = data.get("spreadsheetId", "")
        changed_range = data.get("changedRange", "")

        if not spreadsheet_id:
            raise HTTPException(status_code=400, detail="缺少 spreadsheetId")

        db = get_mysql_service()
        result = db.execute(
            "SELECT * FROM sync_configs WHERE spreadsheet_id = %s AND is_active = 1",
            (spreadsheet_id,)
        )

        if not result:
            raise HTTPException(status_code=404, detail="未找到对应配置")

        config_data = result[0]
        direction = config_data.get("sync_direction", "bidirectional")

        # Fire-and-forget: 调度后台任务，立即返回 200
        asyncio.create_task(
            _webhook_sync_task(
                config_id=config_data["id"],
                event_type=event_type,
                changed_range=changed_range,
                direction=direction,
            )
        )
        return {"status": "ok", "message": "已接收，正在处理"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")


@router.get("/health")
async def webhook_health():
    """Webhook endpoint health check."""
    return {"status": "ok"}
