"""TOON (Token-Oriented Object Notation) utilities for LLM optimization.

TOON is a compact data serialization format designed to reduce token usage by 30-60%
compared to JSON when interacting with Large Language Models.

This module provides utilities to convert between JSON and TOON formats.
"""

from typing import Any, Dict, List, Union

try:
    import toons
    TOONS_AVAILABLE = True
except ImportError:
    TOONS_AVAILABLE = False

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def is_toon_available() -> bool:
    """
    Check if the TOON library is available.

    Returns:
        True if toons library is installed, False otherwise
    """
    return TOONS_AVAILABLE


def json_to_toon(data: Union[Dict[str, Any], List[Any]], indent: bool = False) -> str:
    """
    Convert JSON-compatible data to TOON format.

    Args:
        data: Dictionary or list to convert to TOON format
        indent: Whether to use indentation (default: False for compact format)

    Returns:
        TOON-formatted string

    Raises:
        ImportError: If toons library is not installed
        ValueError: If data cannot be converted to TOON

    Example:
        >>> data = [
        ...     {"id": 1, "title": "Article 1", "effort": "medium"},
        ...     {"id": 2, "title": "Article 2", "effort": "high"},
        ... ]
        >>> toon_str = json_to_toon(data)
        >>> print(toon_str)
        id title effort
        1 "Article 1" medium
        2 "Article 2" high
    """
    if not TOONS_AVAILABLE:
        logger.error("TOON library not installed. Install with: pip install toons")
        raise ImportError(
            "toons library is required for TOON conversion. "
            "Install with: pip install toons"
        )

    try:
        # Use toons.dumps() which mirrors json.dumps()
        toon_str = toons.dumps(data, indent=indent)

        logger.debug(
            "Successfully converted JSON to TOON",
            data_type=type(data).__name__,
            original_length=len(str(data)),
            toon_length=len(toon_str),
            reduction_pct=round((1 - len(toon_str) / len(str(data))) * 100, 2)
        )

        return toon_str

    except Exception as e:
        logger.error(
            "Failed to convert JSON to TOON",
            error=str(e),
            data_type=type(data).__name__
        )
        raise ValueError(f"Failed to convert data to TOON format: {e}") from e


def toon_to_json(toon_str: str) -> Union[Dict[str, Any], List[Any]]:
    """
    Convert TOON format string to JSON-compatible data.

    Args:
        toon_str: TOON-formatted string to parse

    Returns:
        Parsed data as dict or list

    Raises:
        ImportError: If toons library is not installed
        ValueError: If TOON string cannot be parsed

    Example:
        >>> toon_str = '''
        ... id title effort
        ... 1 "Article 1" medium
        ... 2 "Article 2" high
        ... '''
        >>> data = toon_to_json(toon_str)
        >>> print(data)
        [{"id": 1, "title": "Article 1", "effort": "medium"}, ...]
    """
    if not TOONS_AVAILABLE:
        logger.error("TOON library not installed. Install with: pip install toons")
        raise ImportError(
            "toons library is required for TOON conversion. "
            "Install with: pip install toons"
        )

    try:
        # Use toons.loads() which mirrors json.loads()
        data = toons.loads(toon_str)

        logger.debug(
            "Successfully converted TOON to JSON",
            data_type=type(data).__name__,
            toon_length=len(toon_str)
        )

        return data

    except Exception as e:
        logger.error(
            "Failed to convert TOON to JSON",
            error=str(e),
            toon_preview=toon_str[:200]
        )
        raise ValueError(f"Failed to parse TOON format: {e}") from e


def safe_json_to_toon(
    data: Union[Dict[str, Any], List[Any]],
    fallback_to_json: bool = True
) -> str:
    """
    Safely convert JSON to TOON with fallback to JSON string if conversion fails.

    Useful for production code where TOON conversion might fail but you still
    need a valid string representation.

    Args:
        data: Dictionary or list to convert
        fallback_to_json: If True, return JSON string on failure (default: True)

    Returns:
        TOON string if successful, JSON string if fallback enabled, or empty string
    """
    import json

    if not TOONS_AVAILABLE:
        if fallback_to_json:
            logger.warning(
                "TOON library not available, falling back to JSON",
                data_type=type(data).__name__
            )
            return json.dumps(data, ensure_ascii=False)
        return ""

    try:
        return json_to_toon(data)
    except Exception as e:
        logger.warning(
            "TOON conversion failed, falling back to JSON",
            error=str(e),
            data_type=type(data).__name__
        )
        if fallback_to_json:
            return json.dumps(data, ensure_ascii=False)
        return ""


def estimate_token_savings(
    data: Union[Dict[str, Any], List[Any]]
) -> Dict[str, Any]:
    """
    Estimate token savings when using TOON vs JSON.

    This provides approximate character count comparison. Actual token count
    depends on the LLM tokenizer used.

    Args:
        data: Data to analyze

    Returns:
        Dictionary with statistics:
        - json_length: Character count in JSON format
        - toon_length: Character count in TOON format
        - savings_chars: Characters saved
        - savings_percent: Percentage reduction
        - toon_available: Whether TOON library is available
    """
    import json

    json_str = json.dumps(data, ensure_ascii=False)
    json_length = len(json_str)

    stats = {
        "json_length": json_length,
        "toon_length": 0,
        "savings_chars": 0,
        "savings_percent": 0.0,
        "toon_available": TOONS_AVAILABLE
    }

    if not TOONS_AVAILABLE:
        logger.warning("TOON library not available, cannot estimate savings")
        return stats

    try:
        toon_str = json_to_toon(data)
        toon_length = len(toon_str)

        stats.update({
            "toon_length": toon_length,
            "savings_chars": json_length - toon_length,
            "savings_percent": round((1 - toon_length / json_length) * 100, 2)
        })

        logger.info(
            "Token savings estimate",
            **stats
        )

    except Exception as e:
        logger.warning(
            "Could not estimate TOON savings",
            error=str(e)
        )

    return stats
