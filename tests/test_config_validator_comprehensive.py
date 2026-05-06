"""
Comprehensive tests for ConfigValidator.
Tests all validation methods, edge cases, and error/warning generation.
"""
import pytest
import json
from app.services.config_validator import (
    ConfigValidator,
    ValidationError,
    ValidationWarning,
)


# ─── ValidationError Tests ────────────────────────────────────────

class TestValidationError:
    def test_init(self):
        e = ValidationError(field="test", message="error", code="ERR")
        assert e.field == "test"
        assert e.message == "error"
        assert e.code == "ERR"
        assert e.severity == "error"

    def test_init_with_severity(self):
        e = ValidationError(field="f", message="m", code="C", severity="warn")
        assert e.severity == "warn"


# ─── ValidationWarning Tests ─────────────────────────────────────

class TestValidationWarning:
    def test_init(self):
        w = ValidationWarning(field="test", message="warn", code="WRN")
        assert w.field == "test"
        assert w.message == "warn"
        assert w.code == "WRN"


# ─── ConfigValidator Init ────────────────────────────────────────

class TestConfigValidatorInit:
    def test_init(self):
        v = ConfigValidator()
        assert v.errors == []
        assert v.warnings == []


# ─── validate_config ─────────────────────────────────────────────

class TestValidateConfig:
    def make_valid_config(self):
        return {
            "spreadsheet_id": "test_sheet_123",
            "sheet_id": "sheet1",
            "table_name": "test_table",
            "database": "test_db",
            "sync_direction": "bidirectional",
            "poll_interval": 30,
            "mapping_json": {
                "columns": [
                    {"sheet_col": "A", "db_column": "id", "primary_key": True}
                ]
            },
        }

    def test_valid_config(self):
        v = ConfigValidator()
        config = self.make_valid_config()
        is_valid, errors, warnings = v.validate_config(config)
        assert is_valid is True
        assert errors == []

    def test_empty_config(self):
        v = ConfigValidator()
        is_valid, errors, warnings = v.validate_config({})
        assert is_valid is False
        assert len(errors) > 0

    def test_none_config(self):
        v = ConfigValidator()
        is_valid, errors, warnings = v.validate_config(None)
        assert is_valid is False
        assert errors[0].code == "INVALID_CONFIG"

    def test_partial_config(self):
        v = ConfigValidator()
        config = {"spreadsheet_id": "test"}
        is_valid, errors, warnings = v.validate_config(config)
        assert is_valid is False
        error_fields = {e.field for e in errors}
        assert "sheet_id" in error_fields or "table_name" in error_fields


# ─── _validate_spreadsheet_id ──────────────────────────────────

class TestValidateSpreadsheetId:
    def test_empty(self):
        v = ConfigValidator()
        v._validate_spreadsheet_id(None)
        assert len(v.errors) == 1
        assert v.errors[0].code == "EMPTY_FIELD"

    def test_non_string(self):
        v = ConfigValidator()
        v._validate_spreadsheet_id(123)
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_TYPE"

    def test_short_id_warning(self):
        v = ConfigValidator()
        v._validate_spreadsheet_id("abc")
        assert len(v.warnings) == 1
        assert v.warnings[0].code == "SHORT_ID"

    def test_valid_id(self):
        v = ConfigValidator()
        v._validate_spreadsheet_id("valid_spreadsheet_id_123")
        assert len(v.errors) == 0


# ─── _validate_sheet_id ──────────────────────────────────────────

class TestValidateSheetId:
    def test_empty(self):
        v = ConfigValidator()
        v._validate_sheet_id(None)
        assert len(v.errors) == 1
        assert v.errors[0].code == "EMPTY_FIELD"

    def test_non_string(self):
        v = ConfigValidator()
        v._validate_sheet_id(123)
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_TYPE"

    def test_valid_sheet_id(self):
        v = ConfigValidator()
        v._validate_sheet_id("sheet1")
        assert len(v.errors) == 0


# ─── _validate_table_name ────────────────────────────────────────

class TestValidateTableName:
    def test_empty(self):
        v = ConfigValidator()
        v._validate_table_name(None)
        assert len(v.errors) == 1
        assert v.errors[0].code == "EMPTY_FIELD"

    def test_invalid_regex(self):
        v = ConfigValidator()
        v._validate_table_name("123invalid")
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_TABLE_NAME"

    def test_sql_reserved_word(self):
        v = ConfigValidator()
        v._validate_table_name("SELECT")
        assert len(v.errors) == 1
        assert v.errors[0].code == "SQL_RESERVED_WORD"

    def test_too_long(self):
        v = ConfigValidator()
        v._validate_table_name("a" * 65)
        assert len(v.errors) == 1
        assert v.errors[0].code == "TABLE_NAME_TOO_LONG"

    def test_long_warning(self):
        v = ConfigValidator()
        v._validate_table_name("a" * 31)
        assert len(v.warnings) == 1
        assert v.warnings[0].code == "LONG_TABLE_NAME"

    def test_valid_table_name(self):
        v = ConfigValidator()
        v._validate_table_name("my_table_123")
        assert len(v.errors) == 0


# ─── _validate_database ─────────────────────────────────────────

class TestValidateDatabase:
    def test_empty(self):
        v = ConfigValidator()
        v._validate_database(None)
        assert len(v.warnings) == 1
        assert v.warnings[0].code == "NO_DATABASE"

    def test_invalid_regex(self):
        v = ConfigValidator()
        v._validate_database("123invalid")
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_DATABASE_NAME"

    def test_valid_database(self):
        v = ConfigValidator()
        v._validate_database("my_db_123")
        assert len(v.errors) == 0
        assert len(v.warnings) == 0


# ─── _validate_mapping_json ─────────────────────────────────────

class TestValidateMappingJson:
    def test_empty(self):
        v = ConfigValidator()
        v._validate_mapping_json(None)
        assert len(v.errors) == 1
        assert v.errors[0].code == "EMPTY_MAPPING"

    def test_invalid_json_string(self):
        v = ConfigValidator()
        v._validate_mapping_json("{invalid json}")
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_JSON"

    def test_valid_json_string(self):
        v = ConfigValidator()
        v._validate_mapping_json(json.dumps({"columns": [{"sheet_col": "A", "db_column": "id", "primary_key": True}]}))
        assert len(v.errors) == 0

    def test_non_dict(self):
        v = ConfigValidator()
        v._validate_mapping_json([1, 2, 3])
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_MAPPING_TYPE"

    def test_missing_columns(self):
        v = ConfigValidator()
        v._validate_mapping_json({"not_columns": True})
        assert len(v.errors) == 1
        assert v.errors[0].code == "MISSING_COLUMNS"

    def test_columns_not_list(self):
        v = ConfigValidator()
        v._validate_mapping_json({"columns": "not a list"})
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_COLUMNS_TYPE"

    def test_columns_empty(self):
        v = ConfigValidator()
        v._validate_mapping_json({"columns": []})
        assert len(v.errors) == 1
        assert v.errors[0].code == "MISSING_COLUMNS"

    def test_no_primary_key(self):
        v = ConfigValidator()
        v._validate_mapping_json({"columns": [{"sheet_col": "A", "db_column": "name"}]})
        assert len(v.errors) == 1
        assert v.errors[0].code == "NO_PRIMARY_KEY"

    def test_invalid_sheet_header_row(self):
        v = ConfigValidator()
        v._validate_mapping_json({
            "columns": [{"sheet_col": "A", "db_column": "id", "primary_key": True}],
            "sheet_header_row": "not an int",
        })
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_HEADER_ROW"

    def test_invalid_data_start_row(self):
        v = ConfigValidator()
        v._validate_mapping_json({
            "columns": [{"sheet_col": "A", "db_column": "id", "primary_key": True}],
            "sheet_header_row": 1,
            "data_start_row": 1,
        })
        # Expect 2 errors: INVALID_DATA_START_ROW and INVALID_ROW_CONFIGURATION
        assert len(v.errors) >= 1
        error_codes = [e.code for e in v.errors]
        assert "INVALID_DATA_START_ROW" in error_codes

    def test_data_start_row_le_header_row(self):
        v = ConfigValidator()
        v._validate_mapping_json({
            "columns": [{"sheet_col": "A", "db_column": "id", "primary_key": True}],
            "sheet_header_row": 5,
            "data_start_row": 3,
        })
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_ROW_CONFIGURATION"

    def test_valid_mapping(self):
        v = ConfigValidator()
        v._validate_mapping_json({
            "columns": [{"sheet_col": "A", "db_column": "id", "primary_key": True}],
            "sheet_header_row": 1,
            "data_start_row": 2,
        })
        assert len(v.errors) == 0


# ─── _validate_column ───────────────────────────────────────────

class TestValidateColumn:
    def test_empty_sheet_col(self):
        v = ConfigValidator()
        v._validate_column({"db_column": "id"}, 0, set(), set())
        assert any(e.code == "EMPTY_SHEET_COL" for e in v.errors)

    def test_duplicate_sheet_col(self):
        v = ConfigValidator()
        sheet_cols = {"A"}
        v._validate_column({"sheet_col": "A", "db_column": "id"}, 0, sheet_cols, set())
        assert any(e.code == "DUPLICATE_SHEET_COL" for e in v.errors)

    def test_non_standard_sheet_col_warning(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "col1", "db_column": "id"}, 0, set(), set())
        assert any(w.code == "NON_STANDARD_SHEET_COL" for w in v.warnings)

    def test_empty_db_column(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A"}, 0, set(), set())
        assert any(e.code == "EMPTY_DB_COLUMN" for e in v.errors)

    def test_invalid_db_column(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "123invalid"}, 0, set(), set())
        assert any(e.code == "INVALID_DB_COLUMN" for e in v.errors)

    def test_sql_reserved_word_warning(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "SELECT"}, 0, set(), set())
        assert any(w.code == "SQL_RESERVED_WORD" for w in v.warnings)

    def test_duplicate_db_column(self):
        v = ConfigValidator()
        db_cols = {"id"}
        v._validate_column({"sheet_col": "A", "db_column": "id"}, 0, set(), db_cols)
        assert any(e.code == "DUPLICATE_DB_COLUMN" for e in v.errors)

    def test_missing_db_type_warning(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "id", "primary_key": True}, 0, set(), set())
        assert any(w.code == "NO_DB_TYPE" for w in v.warnings)

    def test_invalid_db_type_warning(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "id", "db_type": "UNKNOWN_TYPE"}, 0, set(), set())
        assert any(w.code == "UNCOMMON_DB_TYPE" for w in v.warnings)

    def test_invalid_direction(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "id", "direction": "invalid"}, 0, set(), set())
        assert any(e.code == "INVALID_DIRECTION" for e in v.errors)

    def test_invalid_transform_warning(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "id", "transform": "unknown_func"}, 0, set(), set())
        assert any(w.code == "UNKNOWN_TRANSFORM" for w in v.warnings)

    def test_valid_column(self):
        v = ConfigValidator()
        v._validate_column({"sheet_col": "A", "db_column": "id", "primary_key": True, "db_type": "INT"}, 0, set(), set())
        assert len(v.errors) == 0


# ─── _validate_sync_direction ────────────────────────────────────

class TestValidateSyncDirection:
    def test_empty(self):
        v = ConfigValidator()
        v._validate_sync_direction(None)
        assert len(v.warnings) == 1
        assert v.warnings[0].code == "NO_SYNC_DIRECTION"

    def test_invalid_direction(self):
        v = ConfigValidator()
        v._validate_sync_direction("invalid")
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_SYNC_DIRECTION"

    def test_valid_directions(self):
        for direction in ["to_mysql", "from_mysql", "bidirectional"]:
            v = ConfigValidator()
            v._validate_sync_direction(direction)
            assert len(v.errors) == 0


# ─── _validate_poll_interval ────────────────────────────────────

class TestValidatePollInterval:
    def test_none(self):
        v = ConfigValidator()
        v._validate_poll_interval(None)
        assert len(v.errors) == 0
        assert len(v.warnings) == 0

    def test_non_int(self):
        v = ConfigValidator()
        v._validate_poll_interval("30")
        assert len(v.errors) == 1
        assert v.errors[0].code == "INVALID_INTERVAL_TYPE"

    def test_too_short_warning(self):
        v = ConfigValidator()
        v._validate_poll_interval(3)
        assert len(v.warnings) == 1
        assert v.warnings[0].code == "SHORT_POLL_INTERVAL"

    def test_too_long_warning(self):
        v = ConfigValidator()
        v._validate_poll_interval(4000)
        assert len(v.warnings) == 1
        assert v.warnings[0].code == "LONG_POLL_INTERVAL"

    def test_valid_interval(self):
        v = ConfigValidator()
        v._validate_poll_interval(30)
        assert len(v.errors) == 0
        assert len(v.warnings) == 0


# ─── validate_mapping_only ───────────────────────────────────────

class TestValidateMappingOnly:
    def test_valid_mapping(self):
        v = ConfigValidator()
        mapping = {"columns": [{"sheet_col": "A", "db_column": "id", "primary_key": True}]}
        is_valid, errors, warnings = v.validate_mapping_only(mapping)
        assert is_valid is True

    def test_invalid_mapping(self):
        v = ConfigValidator()
        is_valid, errors, warnings = v.validate_mapping_only({})
        assert is_valid is False


# ─── get_validation_report ──────────────────────────────────────

class TestGetValidationReport:
    def test_with_errors_and_warnings(self):
        v = ConfigValidator()
        v.errors.append(ValidationError(field="f", message="e", code="C"))
        v.warnings.append(ValidationWarning(field="f", message="w", code="C"))
        report = v.get_validation_report()
        assert report["is_valid"] is False
        assert report["error_count"] == 1
        assert report["warning_count"] == 1
        assert len(report["errors"]) == 1
        assert len(report["warnings"]) == 1

    def test_empty(self):
        v = ConfigValidator()
        report = v.get_validation_report()
        assert report["is_valid"] is True
        assert report["error_count"] == 0
