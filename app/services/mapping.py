"""
Field mapping engine for data transformation between Tencent Sheets and MySQL.
Handles type conversion, direction filtering, and data transformation.
"""
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import get_settings


class MappingError(Exception):
    """Error during field mapping or transformation."""
    pass


class MappingEngine:
    """
    Field mapping and type transformation engine.
    """
    
    TRANSFORM_FUNCTIONS: Dict[str, Callable] = {}
    
    def __init__(self, mapping_config: Dict[str, Any]):
        """
        Initialize mapping engine with configuration.
        """
        self.config = mapping_config
        self._column_map: Dict[str, Dict[str, Any]] = {}
        self._primary_keys: List[str] = []
        self._init_column_map()
    
    def _init_column_map(self) -> None:
        """Initialize column mappings from config."""
        columns = self.config.get("columns", [])
        
        for col_def in columns:
            sheet_col = col_def.get("sheet_col", "")
            db_column = col_def.get("db_column", "")
            
            if sheet_col and db_column:
                self._column_map[sheet_col] = col_def
                
                if col_def.get("primary_key", False):
                    self._primary_keys.append(db_column)
        
        self._register_default_transforms()
    
    def _register_default_transforms(self) -> None:
        """Register built-in transform functions."""
        self.TRANSFORM_FUNCTIONS = {
            None: lambda x: x,
            "none": lambda x: x,
            "passthrough": lambda x: x,
            "str": str,
            "string": str,
            "int": lambda x: int(float(x)) if x is not None and x != "" else None,
            "float": lambda x: float(x) if x is not None and x != "" else None,
            "bool": self._parse_bool,
            "date": self._parse_date,
            "datetime": self._parse_datetime,
            "parse_date": self._parse_date,
            "parse_datetime": self._parse_datetime,
            "uppercase": lambda x: str(x).upper() if x else "",
            "lowercase": lambda x: str(x).lower() if x else "",
            "strip": lambda x: str(x).strip() if x else "",
            "trim": lambda x: str(x).strip() if x else "",
            "to_json": json.dumps,
            "from_json": json.loads,
        }
    
    @staticmethod
    def _parse_bool(value: Any) -> Optional[bool]:
        """Parse various representations of boolean."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        
        val_str = str(value).lower().strip()
        if val_str in ("true", "yes", "1", "t", "y"):
            return True
        if val_str in ("false", "no", "0", "f", "n"):
            return False
        return None
    
    @staticmethod
    def _parse_date(value: Any) -> Optional[str]:
        """Parse date and return YYYY-MM-DD format."""
        if value is None or value == "":
            return None
        
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        
        val_str = str(value).strip()
        
        date_formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
            "%d/%m/%Y", "%m/%d/%Y",
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        try:
            from dateutil import parser
            dt = parser.parse(val_str)
            return dt.strftime("%Y-%m-%d")
        except (ImportError, Exception):
            pass
        
        return val_str
    
    @staticmethod
    def _parse_datetime(value: Any) -> Optional[str]:
        """Parse datetime and return YYYY-MM-DD HH:MM:SS format."""
        if value is None or value == "":
            return None
        
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        
        val_str = str(value).strip()
        
        datetime_formats = [
            "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
        ]
        
        for fmt in datetime_formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        
        try:
            from dateutil import parser
            dt = parser.parse(val_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ImportError, Exception):
            pass
        
        return val_str
    
    # Properties
    
    @property
    def primary_keys(self) -> List[str]:
        """Get list of primary key column names."""
        return self._primary_keys
    
    @property
    def sheet_header_row(self) -> int:
        """Get the row number used for sheet headers."""
        return self.config.get("sheet_header_row", 1)
    
    @property
    def data_start_row(self) -> int:
        """Get the row number where data starts."""
        return self.config.get("data_start_row", 2)
    
    def get_sheet_columns(self) -> List[str]:
        """Get list of sheet column letters."""
        return list(self._column_map.keys())
    
    def get_db_columns(self) -> List[str]:
        """Get list of database column names."""
        return [col_def["db_column"] for col_def in self._column_map.values()]
    
    def get_db_column_type(self, db_column: str) -> Optional[str]:
        """Get the MySQL type for a database column."""
        for col_def in self._column_map.values():
            if col_def.get("db_column") == db_column:
                return col_def.get("db_type", "VARCHAR(255)")
        return None
    
    def col_to_db_col(self, sheet_col: str) -> Optional[str]:
        """Convert sheet column letter to database column name."""
        col_def = self._column_map.get(sheet_col)
        return col_def.get("db_column") if col_def else None
    
    def db_col_to_sheet_col(self, db_column: str) -> Optional[str]:
        """Convert database column name to sheet column letter."""
        for sheet_col, col_def in self._column_map.items():
            if col_def.get("db_column") == db_column:
                return sheet_col
        return None
    
    # Direction Filtering
    
    def can_sync_to_mysql(self, sheet_col: str) -> bool:
        """Check if a column can sync to MySQL."""
        col_def = self._column_map.get(sheet_col, {})
        direction = col_def.get("direction", "bidirectional")
        return direction in ("to_mysql", "to_mysql_only", "bidirectional")
    
    def can_sync_from_mysql(self, sheet_col: str) -> bool:
        """Check if a column can sync from MySQL."""
        col_def = self._column_map.get(sheet_col, {})
        direction = col_def.get("direction", "bidirectional")
        return direction in ("from_mysql", "from_mysql_only", "bidirectional")
    
    def can_sync_from_mysql_by_db_col(self, db_column: str) -> bool:
        """Check if a DB column can sync from MySQL."""
        sheet_col = self.db_col_to_sheet_col(db_column)
        if sheet_col:
            return self.can_sync_from_mysql(sheet_col)
        return False
    
    # Transform Functions
    
    def get_transform_func(self, transform_name: Optional[str]) -> Callable:
        """Get transform function by name."""
        if transform_name is None:
            return lambda x: x
        
        func = self.TRANSFORM_FUNCTIONS.get(transform_name)
        if func:
            return func
        
        raise MappingError(f"Unknown transform function: {transform_name}")
    
    def apply_transform(
        self,
        value: Any,
        transform_name: Optional[str],
        direction: str = "to_mysql",
    ) -> Any:
        """Apply transform function to a value."""
        func = self.get_transform_func(transform_name)
        return func(value)
    
    # Data Transformation
    
    def sheet_row_to_db_row(
        self,
        row_data: Dict[str, Any],
        direction: str = "to_mysql",
    ) -> Dict[str, Any]:
        """
        Convert a row from Tencent Sheets format to MySQL format.
        """
        result = {}
        
        for sheet_col, value in row_data.items():
            col_def = self._column_map.get(sheet_col)
            if not col_def:
                continue
            
            db_col = col_def.get("db_column")
            col_direction = col_def.get("direction", "bidirectional")
            
            if direction == "to_mysql" and col_direction not in ("to_mysql", "to_mysql_only", "bidirectional"):
                continue
            if direction == "from_mysql" and col_direction not in ("from_mysql", "from_mysql_only", "bidirectional"):
                continue
            
            transform_name = col_def.get("transform")
            
            try:
                transformed_value = self.apply_transform(value, transform_name, direction)
            except Exception:
                transformed_value = value
            
            result[db_col] = transformed_value
        
        return result
    
    def db_row_to_sheet_row(
        self,
        row_data: Dict[str, Any],
        direction: str = "from_mysql",
    ) -> Dict[str, Any]:
        """
        Convert a row from MySQL format to Tencent Sheets format.
        """
        result = {}
        
        for db_column, value in row_data.items():
            if db_column in ("created_at", "updated_at"):
                continue
            
            sheet_col = self.db_col_to_sheet_col(db_column)
            if not sheet_col:
                continue
            
            col_def = self._column_map.get(sheet_col)
            if not col_def:
                continue
            
            col_direction = col_def.get("direction", "bidirectional")
            if col_direction not in ("from_mysql", "from_mysql_only", "bidirectional"):
                continue
            
            transform_name = col_def.get("transform")
            
            try:
                transformed_value = self.apply_transform(value, transform_name, direction)
            except Exception:
                transformed_value = value
            
            result[sheet_col] = transformed_value
        
        return result
    
    def sheet_rows_to_db_rows(
        self,
        rows_data: List[Dict[str, Any]],
        direction: str = "to_mysql",
    ) -> List[Dict[str, Any]]:
        """Convert multiple rows from Tencent Sheets to MySQL."""
        return [self.sheet_row_to_db_row(row, direction) for row in rows_data]
    
    def db_rows_to_sheet_rows(
        self,
        rows_data: List[Dict[str, Any]],
        direction: str = "from_mysql",
    ) -> List[Dict[str, Any]]:
        """Convert multiple rows from MySQL to Tencent Sheets format."""
        return [self.db_row_to_sheet_row(row, direction) for row in rows_data]
    
    # Range Building
    
    def build_sheet_range(
        self,
        sheet_name: str,
        start_col: Optional[str] = None,
        end_col: Optional[str] = None,
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
    ) -> str:
        """Build a sheet range string like 'Sheet1!A1:Z100'."""
        if start_row is None:
            start_row = self.data_start_row
        if start_col is None:
            start_col = self.get_sheet_columns()[0] if self.get_sheet_columns() else "A"
        if end_col is None:
            end_col = self.get_sheet_columns()[-1] if self.get_sheet_columns() else "Z"
        
        if end_row:
            range_str = f"{sheet_name}!{start_col}{start_row}:{end_col}{end_row}"
        else:
            range_str = f"{sheet_name}!{start_col}{start_row}:{end_col}"
        
        return range_str
    
    @staticmethod
    def get_column_letter(index: int) -> str:
        """Convert 0-based index to column letter."""
        result = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result
    
    @staticmethod
    def get_column_index(letter: str) -> int:
        """Convert column letter to 0-based index."""
        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result - 1
    
    # Validation
    
    def validate_config(self) -> List[str]:
        """Validate the mapping configuration."""
        errors = []
        
        if "columns" not in self.config:
            errors.append("Missing 'columns' key in mapping config")
            return errors
        
        columns = self.config["columns"]
        
        if not columns:
            errors.append("No columns defined in mapping config")
            return errors
        
        db_columns = set()
        sheet_cols = set()
        
        for col_def in columns:
            sheet_col = col_def.get("sheet_col")
            db_column = col_def.get("db_column")
            
            if not sheet_col:
                errors.append(f"Missing sheet_col in column definition: {col_def}")
            
            if not db_column:
                errors.append(f"Missing db_column in column definition: {col_def}")
            
            if sheet_col:
                if sheet_col in sheet_cols:
                    errors.append(f"Duplicate sheet column: {sheet_col}")
                sheet_cols.add(sheet_col)
            
            if db_column:
                if db_column in db_columns:
                    errors.append(f"Duplicate database column: {db_column}")
                db_columns.add(db_column)
            
            transform = col_def.get("transform")
            if transform and transform not in self.TRANSFORM_FUNCTIONS:
                errors.append(f"Unknown transform function: {transform}")
        
        if not any(col.get("primary_key") for col in columns):
            errors.append("No primary key defined in mapping")
        
        return errors
    
    # Serialization
    
    def to_json(self) -> str:
        """Serialize mapping config to JSON string."""
        return json.dumps(self.config, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "MappingEngine":
        """Create MappingEngine from JSON string."""
        config = json.loads(json_str)
        return cls(config)
