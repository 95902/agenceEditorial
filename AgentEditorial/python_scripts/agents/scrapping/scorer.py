"""Phase 2: Article probability scoring."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class ArticleScorer:
    """Score URLs for article probability."""

    # Scoring rules
    SOURCE_SCORES = {
        "api": 30,
        "rss": 25,
        "sitemap_blog": 20,
        "sitemap": 10,
        "heuristic": 5,
    }

    # Positive URL patterns
    POSITIVE_PATTERNS = [
        (r"/\d{4}/\d{2}/\d{2}/", 18),  # Date full
        (r"/\d{4}/\d{2}/", 15),  # Date month
        (r"/blog/|/actualites?/|/news/", 12),
        (r"/article/|/post/", 10),
        (r"/[\w-]{3,}/[\w-]{3,}/[\w-]+/?$", 8),  # Slug SEO
    ]

    # Negative URL patterns
    NEGATIVE_PATTERNS = [
        (r"/category/|/categorie/", -25),
        (r"/tag/|/tags/", -25),
        (r"/author/|/auteur/", -20),
        (r"/page/|/?paged=", -30),
        (r"/search|/recherche", -30),
        (r"/contact|/about|/a-propos", -25),
        (r"/mentions-legales|/cgv|/cgu", -30),
        (r"/inscription|/login|/register", -30),
    ]

    # File extensions to exclude
    EXCLUDED_EXTENSIONS = [
        ".pdf",
        ".doc",
        ".xls",
        ".jpg",
        ".png",
        ".gif",
        ".svg",
        ".zip",
        ".rar",
    ]

    def calculate_article_score(
        self,
        url_data: Dict[str, Any],
    ) -> tuple[int, Dict[str, Any]]:
        """
        Calculate article probability score.

        Args:
            url_data: Dictionary with url, source, and optional metadata

        Returns:
            Tuple of (score, breakdown)
        """
        score = 0
        breakdown = {}

        url = url_data.get("url", "")
        source = url_data.get("source", "heuristic")

        # Source score
        source_score = self.SOURCE_SCORES.get(source, 0)
        score += source_score
        breakdown["source"] = source_score

        # URL pattern score
        url_score = self._calculate_url_pattern_score(url)
        score += url_score
        breakdown["url_pattern"] = url_score

        # Schema.org (if available)
        if url_data.get("jsonld_type") in ["Article", "BlogPosting", "NewsArticle"]:
            schema_score = 30
            score += schema_score
            breakdown["schema"] = schema_score

        # Open Graph (if available)
        if url_data.get("og_type") == "article":
            og_score = 25
            score += og_score
            breakdown["opengraph"] = og_score

        # Negative signals
        negative_score = self._calculate_negative_signals(url, url_data)
        score += negative_score
        breakdown["negative"] = negative_score

        return score, breakdown

    def _calculate_url_pattern_score(self, url: str) -> int:
        """Calculate score from URL patterns."""
        score = 0
        url_lower = url.lower()

        # Check positive patterns
        for pattern, points in self.POSITIVE_PATTERNS:
            if re.search(pattern, url_lower, re.I):
                score += points
                break  # Only count first match

        # Check URL length
        if len(url) > 60:
            score += 5

        return score

    def _calculate_negative_signals(
        self,
        url: str,
        url_data: Dict[str, Any],
    ) -> int:
        """Calculate negative score from signals."""
        score = 0
        url_lower = url.lower()

        # Check negative patterns
        for pattern, points in self.NEGATIVE_PATTERNS:
            if re.search(pattern, url_lower, re.I):
                score += points  # Negative, so subtract
                break

        # Check file extensions
        if any(url_lower.endswith(ext) for ext in self.EXCLUDED_EXTENSIONS):
            score -= 40

        # Check JSON-LD negative types
        jsonld_type = url_data.get("jsonld_type", "")
        if jsonld_type == "Product":
            score -= 30
        elif jsonld_type == "JobPosting":
            score -= 35
        elif jsonld_type == "Event":
            score -= 25

        return score

    def select_urls_to_scrape(
        self,
        scored_urls: List[Dict[str, Any]],
        max_articles: int,
    ) -> List[str]:
        """
        Select URLs to scrape based on scores.

        Args:
            scored_urls: List of URL data with scores
            max_articles: Maximum articles to select

        Returns:
            List of selected URLs
        """
        # Sort by score descending
        sorted_urls = sorted(
            scored_urls,
            key=lambda x: x.get("initial_score", 0),
            reverse=True,
        )

        selected = []

        # Dynamic threshold adjustment: progressively lower threshold if not enough URLs
        thresholds = [60, 50, 40, 30, 20, 10, 0]  # Progressive lowering
        
        for threshold in thresholds:
            if len(selected) >= max_articles:
                break
            
            for url_data in sorted_urls:
                if url_data["url"] in selected:
                    continue
                score = url_data.get("initial_score", 0)
                if score >= threshold:
                    selected.append(url_data["url"])
                    if len(selected) >= max_articles:
                        break

        return selected

    def get_score_category(self, score: int) -> str:
        """Get score category label."""
        if score >= 60:
            return "very_probable"
        elif score >= 40:
            return "probable"
        elif score >= 20:
            return "uncertain"
        elif score >= 0:
            return "unlikely"
        else:
            return "improbable"




