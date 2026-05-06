"""
配置验证器 - 增强配置校验和错误提示
"""
import re
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationError:
    """验证错误"""
    field: str
    message: str
    code: str
    severity: str = "error"


@dataclass
class ValidationWarning:
    """验证警告"""
    field: str
    message: str
    code: str


class ConfigValidator:
    """
    配置验证器
    提供完整的配置校验和友好的错误提示
    """
    
    SQL_RESERVED_WORDS = {
        "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
        "TABLE", "INDEX", "VIEW", "DATABASE", "SCHEMA", "GRANT", "REVOKE",
        "UNION", "EXISTS", "FROM", "WHERE", "AND", "OR", "NOT", "IN",
        "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON", "AS", "ORDER",
        "BY", "GROUP", "HAVING", "LIMIT", "OFFSET", "DISTINCT", "ALL",
    }
    
    MYSQL_TYPES = {
        "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT",
        "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL",
        "CHAR", "VARCHAR", "TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
        "DATE", "TIME", "DATETIME", "TIMESTAMP", "YEAR",
        "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
        "ENUM", "SET", "JSON", "BIT", "BOOL", "BOOLEAN",
    }
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationWarning] = []
    
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[ValidationError], List[ValidationWarning]]:
        """
        验证完整的同步配置
        
        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        if not config or not isinstance(config, dict):
            self.errors.append(ValidationError(
                field="config",
                message="配置不能为空且必须是对象",
                code="INVALID_CONFIG"
            ))
            return len(self.errors) == 0, self.errors, self.warnings
        
        self._validate_spreadsheet_id(config.get("spreadsheet_id"))
        self._validate_sheet_id(config.get("sheet_id"))
        self._validate_table_name(config.get("table_name"))
        self._validate_database(config.get("database"))
        self._validate_mapping_json(config.get("mapping_json"))
        self._validate_sync_direction(config.get("sync_direction"))
        self._validate_poll_interval(config.get("poll_interval"))
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_spreadsheet_id(self, spreadsheet_id: Optional[str]) -> None:
        """验证腾讯文档表格ID"""
        if not spreadsheet_id:
            self.errors.append(ValidationError(
                field="spreadsheet_id",
                message="腾讯文档表格ID不能为空",
                code="EMPTY_FIELD"
            ))
            return
        
        if not isinstance(spreadsheet_id, str):
            self.errors.append(ValidationError(
                field="spreadsheet_id",
                message="腾讯文档表格ID必须是字符串",
                code="INVALID_TYPE"
            ))
            return
        
        if len(spreadsheet_id) < 5:
            self.warnings.append(ValidationWarning(
                field="spreadsheet_id",
                message="腾讯文档表格ID长度过短，可能不正确",
                code="SHORT_ID"
            ))
    
    def _validate_sheet_id(self, sheet_id: Optional[str]) -> None:
        """验证工作表ID"""
        if not sheet_id:
            self.errors.append(ValidationError(
                field="sheet_id",
                message="工作表ID不能为空",
                code="EMPTY_FIELD"
            ))
            return
        
        if not isinstance(sheet_id, str):
            self.errors.append(ValidationError(
                field="sheet_id",
                message="工作表ID必须是字符串",
                code="INVALID_TYPE"
            ))
    
    def _validate_table_name(self, table_name: Optional[str]) -> None:
        """验证MySQL表名"""
        if not table_name:
            self.errors.append(ValidationError(
                field="table_name",
                message="MySQL表名不能为空",
                code="EMPTY_FIELD"
            ))
            return
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            self.errors.append(ValidationError(
                field="table_name",
                message="MySQL表名只能包含字母、数字和下划线，且必须以字母或下划线开头",
                code="INVALID_TABLE_NAME"
            ))
            return
        
        if table_name.upper() in self.SQL_RESERVED_WORDS:
            self.errors.append(ValidationError(
                field="table_name",
                message=f"表名 '{table_name}' 是SQL保留字，不建议使用",
                code="SQL_RESERVED_WORD"
            ))
            return
        
        if len(table_name) > 64:
            self.errors.append(ValidationError(
                field="table_name",
                message="MySQL表名长度不能超过64个字符",
                code="TABLE_NAME_TOO_LONG"
            ))
        
        if len(table_name) > 30:
            self.warnings.append(ValidationWarning(
                field="table_name",
                message="表名长度较长，建议简写",
                code="LONG_TABLE_NAME"
            ))
    
    def _validate_database(self, database: Optional[str]) -> None:
        """验证数据库名"""
        if not database:
            self.warnings.append(ValidationWarning(
                field="database",
                message="未指定数据库，将使用默认数据库",
                code="NO_DATABASE"
            ))
            return
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', database):
            self.errors.append(ValidationError(
                field="database",
                message="数据库名只能包含字母、数字和下划线",
                code="INVALID_DATABASE_NAME"
            ))
    
    def _validate_mapping_json(self, mapping_json: Optional[Any]) -> None:
        """验证字段映射配置"""
        if not mapping_json:
            self.errors.append(ValidationError(
                field="mapping_json",
                message="字段映射配置不能为空",
                code="EMPTY_MAPPING"
            ))
            return
        
        if isinstance(mapping_json, str):
            try:
                mapping_json = json.loads(mapping_json)
            except json.JSONDecodeError as e:
                self.errors.append(ValidationError(
                    field="mapping_json",
                    message=f"字段映射JSON格式错误: {e}",
                    code="INVALID_JSON"
                ))
                return
        
        if not isinstance(mapping_json, dict):
            self.errors.append(ValidationError(
                field="mapping_json",
                message="字段映射必须是对象",
                code="INVALID_MAPPING_TYPE"
            ))
            return
        
        columns = mapping_json.get("columns")
        if not columns:
            self.errors.append(ValidationError(
                field="mapping_json.columns",
                message="字段映射必须包含columns数组",
                code="MISSING_COLUMNS"
            ))
            return
        
        if not isinstance(columns, list):
            self.errors.append(ValidationError(
                field="mapping_json.columns",
                message="columns必须是数组",
                code="INVALID_COLUMNS_TYPE"
            ))
            return
        
        if len(columns) == 0:
            self.errors.append(ValidationError(
                field="mapping_json.columns",
                message="columns数组不能为空",
                code="EMPTY_COLUMNS"
            ))
            return
        
        sheet_cols = set()
        db_cols = set()
        has_primary_key = False
        
        for i, col in enumerate(columns):
            self._validate_column(col, i, sheet_cols, db_cols)
            
            if col.get("primary_key"):
                has_primary_key = True
        
        if not has_primary_key:
            self.errors.append(ValidationError(
                field="mapping_json.columns",
                message="必须指定至少一个主键字段",
                code="NO_PRIMARY_KEY"
            ))
        
        sheet_header_row = mapping_json.get("sheet_header_row", 1)
        if not isinstance(sheet_header_row, int) or sheet_header_row < 1:
            self.errors.append(ValidationError(
                field="mapping_json.sheet_header_row",
                message="表头行号必须是大于0的整数",
                code="INVALID_HEADER_ROW"
            ))
        
        data_start_row = mapping_json.get("data_start_row", 2)
        if not isinstance(data_start_row, int) or data_start_row < 2:
            self.errors.append(ValidationError(
                field="mapping_json.data_start_row",
                message="数据起始行号必须是大于等于2的整数",
                code="INVALID_DATA_START_ROW"
            ))

        if isinstance(data_start_row, int) and isinstance(sheet_header_row, int):
            if data_start_row <= sheet_header_row:
                self.errors.append(ValidationError(
                    field="mapping_json",
                    message="数据起始行必须大于表头行",
                    code="INVALID_ROW_CONFIGURATION"
                ))
    
    def _validate_column(self, col: Dict, index: int, sheet_cols: set, db_cols: set) -> None:
        """验证单个字段映射"""
        field_prefix = f"mapping_json.columns[{index}]"
        
        sheet_col = col.get("sheet_col")
        if not sheet_col:
            self.errors.append(ValidationError(
                field=f"{field_prefix}.sheet_col",
                message="sheet_col不能为空",
                code="EMPTY_SHEET_COL"
            ))
        else:
            if sheet_col in sheet_cols:
                self.errors.append(ValidationError(
                    field=f"{field_prefix}.sheet_col",
                    message=f"重复的sheet_col: {sheet_col}",
                    code="DUPLICATE_SHEET_COL"
                ))
            else:
                sheet_cols.add(sheet_col)
            
            if not re.match(r'^[A-Z]+$', sheet_col.upper()):
                self.warnings.append(ValidationWarning(
                    field=f"{field_prefix}.sheet_col",
                    message=f"列标识 {sheet_col} 不是标准格式（应为A, B, C等）",
                    code="NON_STANDARD_SHEET_COL"
                ))
        
        db_column = col.get("db_column")
        if not db_column:
            self.errors.append(ValidationError(
                field=f"{field_prefix}.db_column",
                message="db_column不能为空",
                code="EMPTY_DB_COLUMN"
            ))
        else:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db_column):
                self.errors.append(ValidationError(
                    field=f"{field_prefix}.db_column",
                    message=f"db_column '{db_column}' 格式不正确",
                    code="INVALID_DB_COLUMN"
                ))
            elif db_column.upper() in self.SQL_RESERVED_WORDS:
                self.warnings.append(ValidationWarning(
                    field=f"{field_prefix}.db_column",
                    message=f"db_column '{db_column}' 是SQL保留字",
                    code="SQL_RESERVED_WORD"
                ))
            
            if db_column in db_cols:
                self.errors.append(ValidationError(
                    field=f"{field_prefix}.db_column",
                    message=f"重复的db_column: {db_column}",
                    code="DUPLICATE_DB_COLUMN"
                ))
            else:
                db_cols.add(db_column)
        
        db_type = col.get("db_type")
        if not db_type:
            self.warnings.append(ValidationWarning(
                field=f"{field_prefix}.db_type",
                message="未指定db_type，将使用默认VARCHAR(255)",
                code="NO_DB_TYPE"
            ))
        else:
            base_type = db_type.upper().split("(")[0].strip()
            if base_type not in self.MYSQL_TYPES:
                self.warnings.append(ValidationWarning(
                    field=f"{field_prefix}.db_type",
                    message=f"db_type '{db_type}' 不是常见MySQL类型",
                    code="UNCOMMON_DB_TYPE"
                ))
        
        direction = col.get("direction", "bidirectional")
        valid_directions = {"bidirectional", "to_mysql", "to_mysql_only", "from_mysql", "from_mysql_only"}
        if direction not in valid_directions:
            self.errors.append(ValidationError(
                field=f"{field_prefix}.direction",
                message=f"direction '{direction}' 无效，可选值: {', '.join(valid_directions)}",
                code="INVALID_DIRECTION"
            ))
        
        transform = col.get("transform")
        if transform:
            valid_transforms = {
                None, "none", "passthrough", "str", "string", "int", "float",
                "bool", "date", "datetime", "parse_date", "parse_datetime",
                "uppercase", "lowercase", "strip", "trim", "to_json", "from_json"
            }
            if transform not in valid_transforms:
                self.warnings.append(ValidationWarning(
                    field=f"{field_prefix}.transform",
                    message=f"transform '{transform}' 不是预定义函数，可能导致转换失败",
                    code="UNKNOWN_TRANSFORM"
                ))
    
    def _validate_sync_direction(self, sync_direction: Optional[str]) -> None:
        """验证同步方向"""
        if not sync_direction:
            self.warnings.append(ValidationWarning(
                field="sync_direction",
                message="未指定同步方向，将使用默认双向同步",
                code="NO_SYNC_DIRECTION"
            ))
            return
        
        valid_directions = {"to_mysql", "from_mysql", "bidirectional"}
        if sync_direction not in valid_directions:
            self.errors.append(ValidationError(
                field="sync_direction",
                message=f"sync_direction '{sync_direction}' 无效，可选值: {', '.join(valid_directions)}",
                code="INVALID_SYNC_DIRECTION"
            ))
    
    def _validate_poll_interval(self, poll_interval: Optional[int]) -> None:
        """验证轮询间隔"""
        if poll_interval is None:
            return
        
        if not isinstance(poll_interval, int):
            self.errors.append(ValidationError(
                field="poll_interval",
                message="轮询间隔必须是整数",
                code="INVALID_INTERVAL_TYPE"
            ))
            return
        
        if poll_interval < 5:
            self.warnings.append(ValidationWarning(
                field="poll_interval",
                message="轮询间隔过短（<5秒），可能导致API限流",
                code="SHORT_POLL_INTERVAL"
            ))
        
        if poll_interval > 3600:
            self.warnings.append(ValidationWarning(
                field="poll_interval",
                message="轮询间隔过长（>1小时），可能导致数据同步延迟",
                code="LONG_POLL_INTERVAL"
            ))
    
    def validate_mapping_only(self, mapping_json: Dict[str, Any]) -> Tuple[bool, List[ValidationError], List[ValidationWarning]]:
        """仅验证字段映射部分"""
        self.errors = []
        self.warnings = []
        self._validate_mapping_json(mapping_json)
        return len(self.errors) == 0, self.errors, self.warnings
    
    def get_validation_report(self) -> Dict[str, Any]:
        """获取验证报告"""
        return {
            "is_valid": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [
                {
                    "field": e.field,
                    "message": e.message,
                    "code": e.code,
                    "severity": e.severity,
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "field": w.field,
                    "message": w.message,
                    "code": w.code,
                }
                for w in self.warnings
            ],
        }


config_validator = ConfigValidator()
