"""
Utility functions for JSON parsing and common operations.
"""
import json
from typing import Any, Dict, Optional


def parse_mapping_json(mapping_json: Any) -> Dict[str, Any]:
    """
    Parse mapping_json field from database result.
    Handles both string and dict formats.

    Args:
        mapping_json: The mapping_json value (could be str or dict)

    Returns:
        Parsed mapping dictionary
    """
    if isinstance(mapping_json, str):
        return json.loads(mapping_json)
    return mapping_json if mapping_json else {}


def parse_config_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a sync config database row, converting JSON strings to dicts.

    Args:
        row: Raw database row dictionary

    Returns:
        Parsed row with mapping_json as dict
    """
    if "mapping_json" in row:
        row["mapping_json"] = parse_mapping_json(row["mapping_json"])
    return row
