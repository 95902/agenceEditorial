"""TOON formatting utilities for LLM prompts.

This module provides specialized formatters to convert structured data
into TOON format for inclusion in LLM prompts, reducing token usage
while maintaining readability and structure.
"""

from typing import Any, Dict, List, Optional, Union

from python_scripts.utils.logging import get_logger
from python_scripts.utils.toon_utils import (
    is_toon_available,
    json_to_toon,
    safe_json_to_toon,
    estimate_token_savings
)

logger = get_logger(__name__)


class ToonFormatter:
    """
    Formatter for converting data structures to TOON format for LLM prompts.

    This class provides methods to format various data structures (lists, dicts)
    into TOON format, with automatic fallback to JSON if TOON is not available
    or if conversion fails.
    """

    def __init__(self, enable_toon: bool = True, log_savings: bool = True):
        """
        Initialize the TOON formatter.

        Args:
            enable_toon: Whether to use TOON format (default: True)
                        If False, always use JSON format
            log_savings: Whether to log token savings statistics (default: True)
        """
        self.enable_toon = enable_toon and is_toon_available()
        self.log_savings = log_savings

        if enable_toon and not is_toon_available():
            logger.warning(
                "TOON library not available, will use JSON format. "
                "Install with: pip install toons"
            )

    def format_for_prompt(
        self,
        data: Union[Dict[str, Any], List[Any]],
        label: Optional[str] = None
    ) -> str:
        """
        Format data for inclusion in an LLM prompt.

        Args:
            data: Data to format (dict or list)
            label: Optional label to prepend to the formatted data

        Returns:
            Formatted string (TOON if enabled and available, otherwise JSON)

        Example:
            >>> formatter = ToonFormatter()
            >>> articles = [
            ...     {"id": 1, "title": "Article 1", "effort": "medium"},
            ...     {"id": 2, "title": "Article 2", "effort": "high"}
            ... ]
            >>> formatted = formatter.format_for_prompt(articles, "Articles")
            >>> print(formatted)
            Articles:
            id title effort
            1 "Article 1" medium
            2 "Article 2" high
        """
        if self.log_savings and self.enable_toon:
            # Log token savings statistics
            savings = estimate_token_savings(data)
            if savings["toon_available"]:
                logger.info(
                    "TOON formatting statistics",
                    label=label or "unlabeled",
                    **savings
                )

        # Format the data
        if self.enable_toon:
            formatted_data = safe_json_to_toon(data, fallback_to_json=True)
        else:
            import json
            formatted_data = json.dumps(data, ensure_ascii=False, indent=2)

        # Add label if provided
        if label:
            return f"{label}:\n{formatted_data}"

        return formatted_data

    def format_article_list(
        self,
        articles: List[Dict[str, Any]],
        include_fields: Optional[List[str]] = None
    ) -> str:
        """
        Format a list of articles for LLM prompts.

        Args:
            articles: List of article dictionaries
            include_fields: Optional list of fields to include (default: all fields)

        Returns:
            TOON or JSON formatted string

        Example:
            >>> formatter = ToonFormatter()
            >>> articles = [
            ...     {"id": 1, "title": "Article 1", "hook": "Hook 1", "effort": "medium"},
            ...     {"id": 2, "title": "Article 2", "hook": "Hook 2", "effort": "high"}
            ... ]
            >>> formatted = formatter.format_article_list(articles, ["id", "title", "effort"])
        """
        # Filter fields if specified
        if include_fields:
            filtered_articles = [
                {k: v for k, v in article.items() if k in include_fields}
                for article in articles
            ]
        else:
            filtered_articles = articles

        return self.format_for_prompt(filtered_articles, label="Articles")

    def format_cluster_list(
        self,
        clusters: List[Dict[str, Any]]
    ) -> str:
        """
        Format a list of topic clusters for LLM prompts.

        Args:
            clusters: List of cluster dictionaries

        Returns:
            TOON or JSON formatted string
        """
        return self.format_for_prompt(clusters, label="Topic Clusters")

    def format_recommendations(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> str:
        """
        Format article recommendations for LLM prompts.

        Args:
            recommendations: List of recommendation dictionaries

        Returns:
            TOON or JSON formatted string
        """
        return self.format_for_prompt(recommendations, label="Recommendations")

    def format_site_profiles(
        self,
        profiles: List[Dict[str, Any]]
    ) -> str:
        """
        Format site profiles for LLM prompts.

        Args:
            profiles: List of site profile dictionaries

        Returns:
            TOON or JSON formatted string
        """
        return self.format_for_prompt(profiles, label="Site Profiles")


def create_toon_formatter(
    enable_toon: bool = True,
    log_savings: bool = True
) -> ToonFormatter:
    """
    Factory function to create a ToonFormatter instance.

    Args:
        enable_toon: Whether to use TOON format (default: True)
        log_savings: Whether to log token savings statistics (default: True)

    Returns:
        ToonFormatter instance
    """
    return ToonFormatter(enable_toon=enable_toon, log_savings=log_savings)


# Convenience function for quick formatting
def format_data_for_llm(
    data: Union[Dict[str, Any], List[Any]],
    label: Optional[str] = None,
    use_toon: bool = True
) -> str:
    """
    Quick helper to format data for LLM prompts.

    Args:
        data: Data to format
        label: Optional label
        use_toon: Whether to use TOON format (default: True)

    Returns:
        Formatted string (TOON or JSON)

    Example:
        >>> from python_scripts.agents.utils.toon_formatter import format_data_for_llm
        >>> data = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        >>> formatted = format_data_for_llm(data, "Items")
    """
    formatter = ToonFormatter(enable_toon=use_toon, log_savings=False)
    return formatter.format_for_prompt(data, label=label)
