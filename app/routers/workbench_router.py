from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.services.mysql_service import MySQLService, get_mysql_service

router = APIRouter(prefix="/api/workbench", tags=["workbench"])


def get_db() -> MySQLService:
    return get_mysql_service()


def _safe_rows(db: MySQLService, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        return db.execute(query, params)
    except Exception:
        return []


def _safe_scalar(
    db: MySQLService,
    query: str,
    key: str,
    default: Any,
    params: tuple = (),
) -> Any:
    rows = _safe_rows(db, query, params)
    if not rows:
        return default
    return rows[0].get(key, default)


@router.get("/summary")
async def get_workbench_summary(db: MySQLService = Depends(get_db)) -> Dict[str, Any]:
    recent_runs = _safe_rows(
        db,
        """
        SELECT
            l.id,
            l.config_id,
            c.table_name,
            c.database,
            l.direction,
            l.status,
            l.rows_affected,
            l.rows_new,
            l.rows_updated,
            l.rows_skipped,
            l.started_at,
            l.completed_at,
            l.error_message
        FROM sync_logs l
        LEFT JOIN sync_configs c ON c.id = l.config_id
        ORDER BY l.started_at DESC
        LIMIT 8
        """,
    )

    try:
        connection_status = db.test_connection()
    except Exception as exc:
        connection_status = {
            "connected": False,
            "error": str(exc),
        }

    return {
        "generated_at": datetime.now().isoformat(),
        "counts": {
            "sync_configs": _safe_scalar(
                db,
                "SELECT COUNT(*) AS value FROM sync_configs WHERE is_active = 1",
                "value",
                0,
            ),
            "mysql_configs": _safe_scalar(
                db,
                "SELECT COUNT(*) AS value FROM mysql_configs WHERE is_active = 1",
                "value",
                0,
            ),
            "tencent_configs": _safe_scalar(
                db,
                "SELECT COUNT(*) AS value FROM tencent_api_configs WHERE is_active = 1",
                "value",
                0,
            ),
            "sync_runs": _safe_scalar(
                db,
                "SELECT COUNT(*) AS value FROM sync_logs",
                "value",
                0,
            ),
            "success_runs": _safe_scalar(
                db,
                "SELECT COUNT(*) AS value FROM sync_logs WHERE status = 'success'",
                "value",
                0,
            ),
            "failed_runs": _safe_scalar(
                db,
                "SELECT COUNT(*) AS value FROM sync_logs WHERE status = 'failed'",
                "value",
                0,
            ),
        },
        "mysql_connection": connection_status,
        "recent_runs": recent_runs,
    }


@router.get("/catalog")
async def get_catalog(db: MySQLService = Depends(get_db)) -> Dict[str, Any]:
    databases = []
    try:
        databases = db.list_mysql_databases()
    except Exception:
        databases = []

    return {
        "generated_at": datetime.now().isoformat(),
        "databases": databases,
        "directions": [
            {"label": "腾讯表格 -> MySQL", "value": "to_mysql"},
            {"label": "MySQL -> 腾讯表格", "value": "from_mysql"},
            {"label": "双向同步", "value": "bidirectional"},
        ],
        "column_directions": [
            {"label": "双向", "value": "bidirectional"},
            {"label": "仅写入 MySQL", "value": "to_mysql_only"},
            {"label": "仅写入腾讯表格", "value": "from_mysql_only"},
        ],
    }
