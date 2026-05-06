"""
批量操作优化器 - 提升同步性能
"""
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
import json

from app.services.metrics_collector import metrics_collector, Timer

logger = logging.getLogger(__name__)


class BatchOptimizer:
    """
    批量操作优化器
    将逐行操作优化为批量操作，提升性能
    """
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
    
    def optimize_batch_insert(
        self,
        table_name: str,
        rows: List[Dict[str, Any]],
        primary_keys: List[str],
    ) -> Tuple[str, List[Tuple], List[str]]:
        """
        优化批量INSERT语句
        
        Returns:
            (sql, params_list, columns)
        """
        if not rows:
            return "", [], []
        
        columns = list(rows[0].keys())
        columns_str = ", ".join([f"`{col}`" for col in columns])
        
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"""
        INSERT INTO `{table_name}` ({columns_str})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE
        {", ".join([f"`{col}` = VALUES(`{col}`)" for col in columns if col not in primary_keys])}
        """
        
        params_list = [tuple(row.get(col) for col in columns) for row in rows]
        
        return sql, params_list, columns
    
    def split_into_batches(self, items: List[Any], batch_size: Optional[int] = None) -> List[List[Any]]:
        """将列表分割成多个批次"""
        if batch_size is None:
            batch_size = self.batch_size
        
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    def estimate_batch_size(self, row_size: int, available_memory: int = 100 * 1024 * 1024) -> int:
        """
        根据行大小估算最佳批量大小
        
        Args:
            row_size: 每行预估大小（字节）
            available_memory: 可用内存（默认100MB）
            
        Returns:
            推荐的批量大小
        """
        if row_size <= 0:
            return self.batch_size
        
        estimated_batch = available_memory // (row_size * 2)
        
        return max(10, min(estimated_batch, 1000))
    
    def should_use_batch(self, item_count: int, threshold: int = 5) -> bool:
        """判断是否应该使用批量操作"""
        return item_count >= threshold


class DataValidator:
    """
    数据验证和清洗
    确保数据质量符合要求
    """
    
    def __init__(self):
        self.validation_errors: List[Dict[str, Any]] = []
        self.validation_warnings: List[Dict[str, Any]] = []
    
    def validate_value(
        self,
        value: Any,
        field_name: str,
        db_type: str,
        is_required: bool = False,
        max_length: Optional[int] = None,
    ) -> Tuple[bool, Any]:
        """
        验证单个值
        
        Returns:
            (is_valid, cleaned_value)
        """
        cleaned_value = value
        
        if value is None or value == "":
            if is_required:
                self.validation_errors.append({
                    "field": field_name,
                    "message": f"字段 {field_name} 不能为空",
                    "value": value,
                })
                return False, None
            return True, None
        
        if isinstance(value, str):
            cleaned_value = value.strip()
            
            if max_length and len(cleaned_value) > max_length:
                self.validation_warnings.append({
                    "field": field_name,
                    "message": f"字段 {field_name} 长度超过限制，已截断",
                    "original_length": len(cleaned_value),
                    "max_length": max_length,
                })
                cleaned_value = cleaned_value[:max_length]
        
        db_type_upper = db_type.upper()
        
        if "INT" in db_type_upper:
            return self._validate_int(cleaned_value, field_name)
        elif "FLOAT" in db_type_upper or "DOUBLE" in db_type_upper or "DECIMAL" in db_type_upper:
            return self._validate_float(cleaned_value, field_name)
        elif "BOOL" in db_type_upper:
            return self._validate_bool(cleaned_value, field_name)
        elif "DATE" in db_type_upper or "TIME" in db_type_upper:
            return self._validate_datetime(cleaned_value, field_name, db_type_upper)
        else:
            return True, cleaned_value
    
    def _validate_int(self, value: Any, field_name: str) -> Tuple[bool, Optional[int]]:
        """验证整数类型"""
        if isinstance(value, int):
            return True, value
        
        try:
            if isinstance(value, float):
                if value.is_integer():
                    return True, int(value)
                else:
                    self.validation_warnings.append({
                        "field": field_name,
                        "message": f"字段 {field_name} 浮点数被截断为整数",
                        "value": value,
                    })
                    return True, int(value)
            
            return True, int(value)
        except (ValueError, TypeError):
            self.validation_errors.append({
                "field": field_name,
                "message": f"字段 {field_name} 无法转换为整数: {value}",
                "value": value,
            })
            return False, None
    
    def _validate_float(self, value: Any, field_name: str) -> Tuple[bool, Optional[float]]:
        """验证浮点数类型"""
        try:
            if isinstance(value, (int, float)):
                return True, float(value)
            return True, float(value)
        except (ValueError, TypeError):
            self.validation_errors.append({
                "field": field_name,
                "message": f"字段 {field_name} 无法转换为浮点数: {value}",
                "value": value,
            })
            return False, None
    
    def _validate_bool(self, value: Any, field_name: str) -> Tuple[bool, Optional[bool]]:
        """验证布尔类型"""
        if isinstance(value, bool):
            return True, value
        
        if isinstance(value, (int, float)):
            return True, bool(value)
        
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ("true", "yes", "1", "t", "y", "on"):
                return True, True
            elif value_lower in ("false", "no", "0", "f", "n", "off", ""):
                return True, False
        
        self.validation_warnings.append({
            "field": field_name,
            "message": f"字段 {field_name} 布尔值转换失败，使用默认值False",
            "value": value,
        })
        return True, False
    
    def _validate_datetime(self, value: Any, field_name: str, db_type: str) -> Tuple[bool, Optional[str]]:
        """验证日期时间类型"""
        if isinstance(value, str):
            return True, value
        
        if hasattr(value, "isoformat"):
            return True, value.isoformat()
        
        self.validation_warnings.append({
            "field": field_name,
            "message": f"字段 {field_name} 日期格式不标准，尝试原值",
            "value": str(value),
        })
        return True, str(value)
    
    def validate_row(
        self,
        row: Dict[str, Any],
        mapping: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        验证整行数据
        
        Returns:
            (is_valid, cleaned_row)
        """
        cleaned_row = {}
        
        for col_def in mapping.get("columns", []):
            field_name = col_def.get("db_column")
            sheet_col = col_def.get("sheet_col")
            db_type = col_def.get("db_type", "VARCHAR(255)")
            is_primary = col_def.get("primary_key", False)
            is_required = is_primary
            
            value = row.get(sheet_col)
            
            is_valid, cleaned_value = self.validate_value(
                value,
                field_name,
                db_type,
                is_required=is_required,
            )
            
            if is_valid and cleaned_value is not None:
                cleaned_row[field_name] = cleaned_value
        
        return len(self.validation_errors) == 0, cleaned_row
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """获取验证错误"""
        return self.validation_errors
    
    def get_warnings(self) -> List[Dict[str, Any]]:
        """获取验证警告"""
        return self.validation_warnings
    
    def clear(self) -> None:
        """清空验证记录"""
        self.validation_errors.clear()
        self.validation_warnings.clear()


batch_optimizer = BatchOptimizer()
data_validator = DataValidator()
