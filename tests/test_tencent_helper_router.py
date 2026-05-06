from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_sheet_fields_returns_structured_payload():
    client = TestClient(app)

    async def fake_fetch_sheet_fields(db, spreadsheet_id, sheet_name, header_row, tencent_config_id=None):
        return {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "headerRow": header_row,
            "fields": [
                {"sheet_col": "A", "sheet_header": "name", "display_name": "A - name"},
                {"sheet_col": "B", "sheet_header": "age", "display_name": "B - age"},
            ],
            "demo": False,
        }

    with patch("app.routers.tencent_helper.fetch_sheet_fields", side_effect=fake_fetch_sheet_fields):
        response = client.get(
            "/api/tencent/sheet-fields",
            params={"spreadsheetId": "sheet123", "sheetName": "Sheet1", "headerRow": 1},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fields"][0]["sheet_col"] == "A"
    assert payload["fields"][1]["sheet_header"] == "age"


def test_auto_map_returns_suggestions():
    client = TestClient(app)

    async def fake_fetch_sheet_fields(db, spreadsheet_id, sheet_name, header_row, tencent_config_id=None):
        return {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "headerRow": header_row,
            "fields": [
                {"sheet_col": "A", "sheet_header": "name", "display_name": "A - name"},
                {"sheet_col": "B", "sheet_header": "age", "display_name": "B - age"},
            ],
            "demo": False,
        }

    class FakeDB:
        def get_table_columns(self, table_name, database):
            return [
                {
                    "COLUMN_NAME": "name",
                    "DATA_TYPE": "varchar",
                    "IS_NULLABLE": "NO",
                    "COLUMN_KEY": "",
                    "COLUMN_DEFAULT": None,
                    "EXTRA": "",
                },
                {
                    "COLUMN_NAME": "age",
                    "DATA_TYPE": "int",
                    "IS_NULLABLE": "YES",
                    "COLUMN_KEY": "PRI",
                    "COLUMN_DEFAULT": None,
                    "EXTRA": "",
                },
            ]

    from app.routers.tencent_helper import get_db

    app.dependency_overrides[get_db] = lambda: FakeDB()
    with patch("app.routers.tencent_helper.fetch_sheet_fields", side_effect=fake_fetch_sheet_fields):
        response = client.get(
            "/api/tencent/auto-map",
            params={
                "spreadsheetId": "sheet123",
                "sheetName": "Sheet1",
                "tableName": "users",
                "database": "biz",
                "headerRow": 1,
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["suggested_mappings"]) == 2
    assert payload["suggested_mappings"][0]["db_column"] == "name"


def test_auto_map_uses_saved_mysql_config_when_provided():
    client = TestClient(app)

    async def fake_fetch_sheet_fields(db, spreadsheet_id, sheet_name, header_row, tencent_config_id=None):
        return {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "headerRow": header_row,
            "fields": [
                {"sheet_col": "A", "sheet_header": "name", "display_name": "A - name"},
            ],
            "demo": False,
        }

    class RuntimeDB:
        def get_table_columns(self, table_name, database):
            assert table_name == "users"
            assert database == "biz"
            return [
                {
                    "COLUMN_NAME": "name",
                    "DATA_TYPE": "varchar",
                    "IS_NULLABLE": "NO",
                    "COLUMN_KEY": "PRI",
                    "COLUMN_DEFAULT": None,
                    "EXTRA": "",
                }
            ]

    class FakeDB:
        pass

    from app.routers.tencent_helper import get_db

    app.dependency_overrides[get_db] = lambda: FakeDB()
    with patch("app.routers.tencent_helper.fetch_sheet_fields", side_effect=fake_fetch_sheet_fields):
        with patch("app.routers.tencent_helper.MySQLConfigService") as mock_service:
            mock_service.return_value.build_mysql_service.return_value = RuntimeDB()
            response = client.get(
                "/api/tencent/auto-map",
                params={
                    "spreadsheetId": "sheet123",
                    "sheetName": "Sheet1",
                    "tableName": "users",
                    "database": "biz",
                    "headerRow": 1,
                    "mysqlConfigId": 9,
                },
            )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mysqlConfigId"] == 9
    assert payload["mysql_fields"][0]["name"] == "name"
