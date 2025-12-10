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


def make_json_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable objects to serializable types.
    
    Handles:
    - pandas Timestamp -> str (ISO format)
    - numpy types (int64, float64, etc.) -> Python int/float
    - datetime objects -> str (ISO format)
    - float("inf"), float("-inf"), float("nan") -> None or large number
    - nested dicts and lists
    """
    import pandas as pd
    import numpy as np
    from datetime import datetime
    
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        val = float(obj)
        # Handle infinity and NaN
        if np.isinf(val):
            return None if val > 0 else None  # Replace inf with None
        elif np.isnan(val):
            return None
        return val
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (float, int)):
        # Handle Python float infinity and NaN
        if isinstance(obj, float):
            if obj == float("inf") or obj == float("-inf"):
                return None
            elif obj != obj:  # NaN check
                return None
        return obj
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    else:
        return obj










