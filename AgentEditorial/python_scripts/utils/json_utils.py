"""JSON normalization utilities."""

import json
from typing import Any, Dict, List

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def normalize_json_value(value: Any) -> Any:
    """
    Normalize a JSON value recursively.
    
    If value is a string that looks like JSON, parse it.
    Otherwise return as-is.
    
    Args:
        value: Value to normalize
        
    Returns:
        Normalized value
    """
    if value is None:
        return None
    
    if isinstance(value, str):
        value_stripped = value.strip()
        # Check if it looks like JSON (starts with { or [)
        if value_stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value_stripped)
                # Recursively normalize if it's a dict or list
                if isinstance(parsed, dict):
                    return normalize_json_dict(parsed)
                elif isinstance(parsed, list):
                    return normalize_json_list(parsed)
                return parsed
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, return original value
                logger.warning(
                    "Could not parse JSON string",
                    value_preview=value[:100],
                )
                return value
    
    if isinstance(value, dict):
        return normalize_json_dict(value)
    
    if isinstance(value, list):
        return normalize_json_list(value)
    
    return value


def normalize_json_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a dictionary by recursively normalizing all values.
    
    Args:
        data: Dictionary to normalize
        
    Returns:
        Normalized dictionary
    """
    return {k: normalize_json_value(v) for k, v in data.items()}


def normalize_json_list(data: List[Any]) -> List[Any]:
    """
    Normalize a list by recursively normalizing all items.
    
    Args:
        data: List to normalize
        
    Returns:
        Normalized list
    """
    return [normalize_json_value(item) for item in data]










