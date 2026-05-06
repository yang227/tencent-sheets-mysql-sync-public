import pytest
from app.services.mapping import MappingEngine


def test_mapping_engine_init():
    """Test MappingEngine initialization with basic config."""
    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "name", "primary_key": True},
            {"sheet_col": "B", "db_column": "age", "primary_key": False}
        ],
        "sheet_header_row": 1,
        "data_start_row": 2
    }
    
    engine = MappingEngine(config)
    
    assert engine.primary_keys == ["name"]
    assert engine.sheet_header_row == 1
    assert engine.data_start_row == 2


def test_sheet_row_to_db_row():
    """Test converting sheet row to database row."""
    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "name", "direction": "bidirectional"},
            {"sheet_col": "B", "db_column": "age", "direction": "bidirectional", "transform": "int"}
        ]
    }
    
    engine = MappingEngine(config)
    row_data = {"A": "张三", "B": "25"}
    result = engine.sheet_row_to_db_row(row_data)
    
    assert result["name"] == "张三"
    assert result["age"] == 25


def test_db_row_to_sheet_row():
    """Test converting database row to sheet row."""
    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "name", "direction": "bidirectional"},
            {"sheet_col": "B", "db_column": "age", "direction": "bidirectional"}
        ]
    }
    
    engine = MappingEngine(config)
    row_data = {"name": "张三", "age": 25}
    result = engine.db_row_to_sheet_row(row_data)
    
    assert result["A"] == "张三"
    assert result["B"] == 25


def test_primary_keys():
    """Test primary key detection."""
    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "id", "primary_key": True},
            {"sheet_col": "B", "db_column": "name", "primary_key": False}
        ]
    }
    
    engine = MappingEngine(config)
    
    assert engine.primary_keys == ["id"]


def test_get_column_letter():
    """Test column letter conversion."""
    assert MappingEngine.get_column_letter(0) == "A"
    assert MappingEngine.get_column_letter(1) == "B"
    assert MappingEngine.get_column_letter(25) == "Z"
    assert MappingEngine.get_column_letter(26) == "AA"


def test_get_column_index():
    """Test column index conversion."""
    assert MappingEngine.get_column_index("A") == 0
    assert MappingEngine.get_column_index("B") == 1
    assert MappingEngine.get_column_index("Z") == 25
    assert MappingEngine.get_column_index("AA") == 26


def test_build_sheet_range():
    """Test building sheet range string."""
    config = {
        "columns": [
            {"sheet_col": "A"},
            {"sheet_col": "C"}
        ],
        "sheet_header_row": 1,
        "data_start_row": 2
    }
    
    engine = MappingEngine(config)
    # Note: end_col must be provided if not using default columns
    result = engine.build_sheet_range("Sheet1", start_col="A", end_col="C", start_row=2, end_row=100)
    
    assert result == "Sheet1!A2:C100"
    
    # Test with defaults (uses Z as fallback when columns are incomplete)
    result_default = engine.build_sheet_range("Sheet1", start_row=2, end_row=50)
    # Without explicit end_col, it uses the last column from config or defaults to Z
    assert "Sheet1" in result_default
    assert "A2:Z50" in result_default


def test_transform_functions():
    """Test built-in transform functions."""
    config = {"columns": []}
    engine = MappingEngine(config)
    
    # Test int transform
    assert engine.apply_transform("123", "int") == 123
    assert engine.apply_transform("", "int") is None
    
    # Test float transform
    assert engine.apply_transform("12.5", "float") == 12.5
    assert engine.apply_transform("", "float") is None
    
    # Test str transform
    assert engine.apply_transform(123, "str") == "123"
    
    # Test bool transform
    assert engine.apply_transform("true", "bool") is True
    assert engine.apply_transform("false", "bool") is False
    assert engine.apply_transform("1", "bool") is True


def test_direction_filtering():
    """Test direction-based column filtering."""
    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "id", "direction": "bidirectional"},
            {"sheet_col": "B", "db_column": "notes", "direction": "to_mysql_only"},
            {"sheet_col": "C", "db_column": "status", "direction": "from_mysql_only"}
        ]
    }
    
    engine = MappingEngine(config)
    
    assert engine.can_sync_to_mysql("A") is True
    assert engine.can_sync_to_mysql("B") is True
    assert engine.can_sync_to_mysql("C") is False
    
    assert engine.can_sync_from_mysql("A") is True
    assert engine.can_sync_from_mysql("B") is False
    assert engine.can_sync_from_mysql("C") is True


def test_validate_config():
    """Test configuration validation."""
    # Valid config
    config = {
        "columns": [
            {"sheet_col": "A", "db_column": "id", "primary_key": True},
            {"sheet_col": "B", "db_column": "name"}
        ]
    }
    engine = MappingEngine(config)
    errors = engine.validate_config()
    assert len(errors) == 0
    
    # Config without primary key
    config_no_pk = {
        "columns": [
            {"sheet_col": "A", "db_column": "name"}
        ]
    }
    engine_no_pk = MappingEngine(config_no_pk)
    errors = engine_no_pk.validate_config()
    assert "No primary key defined in mapping" in errors
