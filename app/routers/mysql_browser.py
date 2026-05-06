from fastapi import APIRouter, Depends

from app.services.mysql_service import MySQLService, get_mysql_service

router = APIRouter(prefix="/api/mysql", tags=["mysql-browser"])


def get_db() -> MySQLService:
    return get_mysql_service()


@router.get("/databases")
async def list_databases(db: MySQLService = Depends(get_db)):
    try:
        return db.list_mysql_databases()
    except Exception:
        return []


@router.get("/databases/{database}/tables")
async def list_tables(database: str, db: MySQLService = Depends(get_db)):
    try:
        return db.list_mysql_tables(database)
    except Exception:
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
    except Exception:
        return []
