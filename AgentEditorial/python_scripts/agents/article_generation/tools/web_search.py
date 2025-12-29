"""Web search tool for article generation (DuckDuckGo-based)."""

from __future__ import annotations

from typing import List

from ddgs import DDGS

from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)


class WebSearchClient:
    """Simple web search wrapper using DuckDuckGo Search."""

    def __init__(self) -> None:
        self._client = DDGS()

    def search(self, query: str, max_results: int = 5) -> List[dict]:
        """Run a web search and return a list of result dicts."""
        try:
            results = list(
                self._client.text(
                    query,
                    max_results=max_results,
                )
            )
            logger.info(
                "web_search_completed",
                query=query,
                results_count=len(results),
            )
            return results
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "web_search_failed",
                query=query,
                error=str(exc),
            )
            return []











