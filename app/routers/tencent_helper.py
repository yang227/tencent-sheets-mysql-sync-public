import logging
import re
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.services.mapping import MappingEngine
from app.services.mysql_config_service import MySQLConfigService
from app.services.tencent_config_service import TencentApiConfigService
from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.tencent_api import TencentAPI

router = APIRouter(prefix="/api/tencent", tags=["tencent-helper"])
logger = logging.getLogger(__name__)

DEMO_HEADERS = ["姓名", "年龄", "城市", "部门", "入职日期", "月薪", "备注"]


def get_db() -> MySQLService:
    return get_mysql_service()


def _normalize_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", (value or "").strip().lower())


def _sheet_field(letter: str, header: str) -> Dict[str, Any]:
    return {
        "sheet_col": letter,
        "sheet_header": header,
        "display_name": f"{letter} - {header}" if header else letter,
    }


async def fetch_sheet_fields(
    db: MySQLService,
    spreadsheet_id: str,
    sheet_name: str,
    header_row: int,
    tencent_config_id: int | None = None,
) -> Dict[str, Any]:
    try:
        if tencent_config_id:
            api = TencentApiConfigService(db).build_tencent_api(tencent_config_id)
        else:
            api = TencentAPI.from_env()

        async with api:
            headers, _ = await api.read_sheet_data(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                header_row=header_row,
                data_start_row=header_row + 1,
            )
        fields = [
            _sheet_field(MappingEngine.get_column_letter(index + 1), str(header or "").strip())
            for index, header in enumerate(headers)
            if str(header or "").strip()
        ]
        return {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "headerRow": header_row,
            "fields": fields,
            "demo": False,
        }
    except Exception as exc:
        logger.warning("Failed to fetch Tencent sheet fields: %s", exc)
        return {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "headerRow": header_row,
            "fields": [
                _sheet_field(MappingEngine.get_column_letter(index + 1), header)
                for index, header in enumerate(DEMO_HEADERS)
            ],
            "demo": True,
            "warning": str(exc),
        }


def fetch_mysql_fields(
    db: MySQLService,
    table_name: str,
    database: str,
    mysql_config_id: int | None = None,
) -> List[Dict[str, Any]]:
    runtime_db = (
        MySQLConfigService(db).build_mysql_service(mysql_config_id)
        if mysql_config_id
        else db
    )
    db_name = database or None
    columns = runtime_db.get_table_columns(table_name, db_name)
    return [
        {
            "name": column["COLUMN_NAME"],
            "type": column["DATA_TYPE"],
            "nullable": column["IS_NULLABLE"] == "YES",
            "primary_key": column["COLUMN_KEY"] == "PRI",
            "default": column["COLUMN_DEFAULT"],
            "extra": column["EXTRA"],
        }
        for column in columns
    ]


def build_mapping_suggestions(
    sheet_fields: List[Dict[str, Any]],
    mysql_fields: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    mysql_by_normalized: Dict[str, Dict[str, Any]] = {}
    for mysql_field in mysql_fields:
        mysql_by_normalized[_normalize_name(mysql_field["name"])] = mysql_field

    suggestions: List[Dict[str, Any]] = []
    used_mysql = set()

    for sheet_field in sheet_fields:
        normalized_header = _normalize_name(sheet_field["sheet_header"])
        match = mysql_by_normalized.get(normalized_header)

        if not match:
            for mysql_field in mysql_fields:
                normalized_mysql = _normalize_name(mysql_field["name"])
                if not normalized_header or normalized_mysql in used_mysql:
                    continue
                if normalized_header == normalized_mysql:
                    match = mysql_field
                    break
                if normalized_header in normalized_mysql or normalized_mysql in normalized_header:
                    match = mysql_field
                    break

        if not match:
            continue

        normalized_mysql_name = _normalize_name(match["name"])
        if normalized_mysql_name in used_mysql:
            continue

        used_mysql.add(normalized_mysql_name)
        suggestions.append(
            {
                "sheet_col": sheet_field["sheet_col"],
                "sheet_header": sheet_field["sheet_header"],
                "db_column": match["name"],
                "db_type": match["type"],
                "direction": "bidirectional",
                "primary_key": match["primary_key"],
                "transform": None,
                "match_score": 1.0 if normalized_header == normalized_mysql_name else 0.7,
            }
        )

    return suggestions


@router.get("/sheet-fields")
async def get_sheet_fields(
    spreadsheetId: str = Query(..., description="Tencent spreadsheet ID"),
    sheetName: str = Query(..., description="Sheet ID or sheet name"),
    headerRow: int = Query(1, ge=1, description="Header row number"),
    tencentConfigId: int | None = Query(None, description="Saved Tencent config ID"),
    db: MySQLService = Depends(get_db),
):
    return await fetch_sheet_fields(db, spreadsheetId, sheetName, headerRow, tencentConfigId)


@router.get("/sheet-header")
async def get_sheet_header(
    spreadsheetId: str = Query(..., description="Tencent spreadsheet ID"),
    sheetName: str = Query(..., description="Sheet ID or sheet name"),
    headerRow: int = Query(1, ge=1, description="Header row number"),
    tencentConfigId: int | None = Query(None, description="Saved Tencent config ID"),
    db: MySQLService = Depends(get_db),
):
    result = await fetch_sheet_fields(db, spreadsheetId, sheetName, headerRow, tencentConfigId)
    return {
        "spreadsheetId": result["spreadsheetId"],
        "sheetName": result["sheetName"],
        "headerRow": result["headerRow"],
        "columns": [
            f'{field["sheet_col"]}_{field["sheet_header"]}' for field in result["fields"]
        ],
        "_demo": result.get("demo", False),
        "_warning": result.get("warning"),
    }


@router.get("/auto-map")
async def auto_map_fields(
    spreadsheetId: str = Query(..., description="Tencent spreadsheet ID"),
    sheetName: str = Query(..., description="Sheet ID or sheet name"),
    tableName: str = Query(..., description="MySQL table name"),
    database: str = Query("", description="MySQL database name"),
    headerRow: int = Query(1, ge=1, description="Header row number"),
    tencentConfigId: int | None = Query(None, description="Saved Tencent config ID"),
    mysqlConfigId: int | None = Query(None, description="Saved MySQL config ID"),
    db: MySQLService = Depends(get_db),
):
    sheet_result = await fetch_sheet_fields(db, spreadsheetId, sheetName, headerRow, tencentConfigId)

    try:
        mysql_fields = fetch_mysql_fields(db, tableName, database, mysqlConfigId)
    except Exception as exc:
        logger.warning("Failed to fetch MySQL fields for auto-map: %s", exc)
        mysql_fields = []
        mysql_warning = str(exc)
    else:
        mysql_warning = None

    suggestions = build_mapping_suggestions(sheet_result["fields"], mysql_fields)

    return {
        "spreadsheetId": spreadsheetId,
        "sheetName": sheetName,
        "tableName": tableName,
        "database": database,
        "mysqlConfigId": mysqlConfigId,
        "tencentConfigId": tencentConfigId,
        "sheet_fields": sheet_result["fields"],
        "mysql_fields": mysql_fields,
        "suggested_mappings": suggestions,
        "demo": sheet_result.get("demo", False),
        "warnings": [value for value in [sheet_result.get("warning"), mysql_warning] if value],
    }
