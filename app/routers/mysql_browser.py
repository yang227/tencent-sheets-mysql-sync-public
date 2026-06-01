from fastapi import APIRouter, Depends

from app.services.mysql_service import MySQLService, get_mysql_service
from app.services.db_exception import DatabaseServiceError
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mysql", tags=["mysql-browser"])


def get_db() -> MySQLService:
    return get_mysql_service()


@router.get("/databases")
async def list_databases(db: MySQLService = Depends(get_db)):
    try:
        return db.list_databases()
    except DatabaseServiceError as exc:
        logger.error("list_databases: %s", exc)
        return []


@router.get("/databases/{database}/tables")
async def list_tables(database: str, db: MySQLService = Depends(get_db)):
    try:
        return db.list_tables(database)
    except DatabaseServiceError as exc:
        logger.error("list_tables: %s", exc)
        return []


@router.get("/tables/{table_name}/columns")
async def get_columns(table_name: str, database: str = "", db: MySQLService = Depends(get_db)):
    try:
        db_name = database if database else None
        columns = db.get_table_columns(table_name, db_name)
        return [
            {
                "name": col["COLUMN_NAME"],
                "type": col["DATA_TYPE"],
                "nullable": col["IS_NULLABLE"] == "YES",
                "key": col["COLUMN_KEY"],
                "default": col["COLUMN_DEFAULT"],
                "extra": col["EXTRA"],
            }
            for col in columns
        ]
    except DatabaseServiceError as exc:
        logger.error("get_columns: %s", exc)
        return []