"""Phase 3: Adaptive article extraction."""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


# Content selectors by priority
CONTENT_SELECTORS_PRIORITY = [
    "[itemprop='articleBody']",
    "[itemprop='text']",
    "article .entry-content",
    "article .post-content",
    ".single-post .entry-content",
    ".article-content",
    ".article-body",
    ".post-body",
    ".content-body",
    "main article",
    "article main",
    "#content article",
    "article",
    ".post",
    ".article",
    "main",
]

# Title selectors by priority
TITLE_SELECTORS_PRIORITY = [
    "[itemprop='headline']",
    "[itemprop='name']",
    "h1.entry-title",
    "h1.post-title",
    "h1.article-title",
    ".entry-header h1",
    "article h1",
    "main h1",
    "#content h1",
    "h1",
]

# Date selectors by priority
DATE_SELECTORS_PRIORITY = [
    "[itemprop='datePublished']",
    "time[datetime]",
    ".entry-date",
    ".post-date",
    ".article-date",
    ".published",
    ".meta-date",
    ".posted-on time",
    ".entry-meta time",
]

# Author selectors by priority
AUTHOR_SELECTORS_PRIORITY = [
    "[itemprop='author']",
    "[rel='author']",
    ".author-name",
    ".entry-author",
    ".post-author",
    ".article-author",
    ".byline",
    "a[href*='/author/']",
]


class AdaptiveExtractor:
    """Adaptive article extractor using site profile."""

    def __init__(self, timeout: float = 30.0):
        """Initialize the extractor."""
        self.timeout = timeout

    async def extract_article_adaptive(
        self,
        html: str,
        url: str,
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract article using site profile for optimization.

        Args:
            html: HTML content
            url: Article URL
            profile: Site discovery profile

        Returns:
            Dictionary with extracted article data
        """
        soup = BeautifulSoup(html, "html.parser")
        article = {}

        # 1. Try structured data first (JSON-LD, Open Graph)
        jsonld = self._extract_jsonld_info(html, soup)
        if jsonld.get("is_article"):
            article.update(jsonld.get("metadata", {}))

        opengraph = self._extract_opengraph_info(html, soup)
        if opengraph.get("is_article"):
            # Complement with OG if not in JSON-LD
            for key in ["title", "description", "published_time", "author"]:
                if not article.get(key) and opengraph.get(key):
                    article[key] = opengraph[key]

        # 2. Use profile selectors (if available)
        if profile.get("content_selector"):
            content = soup.select_one(profile["content_selector"])
            if content:
                article["content"] = self._clean_text(content.get_text())
                article["content_html"] = str(content)

        if profile.get("title_selector") and not article.get("title"):
            title = soup.select_one(profile["title_selector"])
            if title:
                article["title"] = self._clean_text(title.get_text())

        if profile.get("date_selector") and not article.get("published_time"):
            date = soup.select_one(profile["date_selector"])
            if date:
                parsed_date = self._extract_date(date)
                if parsed_date:
                    article["published_time"] = parsed_date

        if profile.get("author_selector") and not article.get("author"):
            author = soup.select_one(profile["author_selector"])
            if author:
                article["author"] = self._clean_text(author.get_text())

        # 3. Fallback to generic selectors
        if not article.get("content"):
            for selector in CONTENT_SELECTORS_PRIORITY:
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 200:
                    article["content"] = self._clean_text(content.get_text())
                    article["content_html"] = str(content)
                    article["_content_selector_used"] = selector
                    break

        if not article.get("title"):
            for selector in TITLE_SELECTORS_PRIORITY:
                title = soup.select_one(selector)
                if title:
                    article["title"] = self._clean_text(title.get_text())
                    article["_title_selector_used"] = selector
                    break

        if not article.get("published_time"):
            for selector in DATE_SELECTORS_PRIORITY:
                date = soup.select_one(selector)
                if date:
                    parsed_date = self._extract_date(date)
                    if parsed_date:
                        article["published_time"] = parsed_date
                        article["_date_selector_used"] = selector
                        break

        if not article.get("author"):
            for selector in AUTHOR_SELECTORS_PRIORITY:
                author = soup.select_one(selector)
                if author:
                    article["author"] = self._clean_text(author.get_text())
                    article["_author_selector_used"] = selector
                    break

        # 4. Calculate metrics
        content_text = article.get("content", "")
        article["word_count"] = len(content_text.split())
        article["url"] = url

        return article

    def _extract_jsonld_info(
        self,
        html: str,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        """Extract JSON-LD information."""
        info = {
            "is_article": False,
            "metadata": {},
        }

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)

                # Handle arrays
                if isinstance(data, list):
                    for item in data:
                        if self._process_jsonld_item(item, info):
                            break
                else:
                    self._process_jsonld_item(data, info)

            except json.JSONDecodeError:
                continue

        return info

    def _process_jsonld_item(self, item: Dict, info: Dict) -> bool:
        """Process a JSON-LD item."""
        item_type = item.get("@type", "")

        # Article types
        if item_type in ["Article", "BlogPosting", "NewsArticle", "TechArticle"]:
            info["is_article"] = True
            info["metadata"] = {
                "title": item.get("headline"),
                "description": item.get("description"),
                "published_time": item.get("datePublished"),
                "modified_time": item.get("dateModified"),
                "author": item.get("author", {}).get("name") if isinstance(item.get("author"), dict) else item.get("author"),
            }
            return True

        return False

    def _extract_opengraph_info(
        self,
        html: str,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        """Extract Open Graph information."""
        og_data = {}

        for meta in soup.find_all("meta", property=True):
            prop = meta.get("property", "")
            content = meta.get("content", "")

            if prop.startswith("og:") or prop.startswith("article:"):
                og_data[prop] = content

        return {
            "is_article": og_data.get("og:type") == "article",
            "title": og_data.get("og:title"),
            "description": og_data.get("og:description"),
            "published_time": og_data.get("article:published_time"),
            "modified_time": og_data.get("article:modified_time"),
            "author": og_data.get("article:author"),
        }

    def _extract_date(self, element) -> Optional[datetime]:
        """Extract date from HTML element."""
        # Try datetime attribute
        datetime_attr = element.get("datetime")
        if datetime_attr:
            try:
                return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Try itemprop
        if element.get("itemprop") == "datePublished":
            datetime_attr = element.get("datetime")
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

        # Try text content
        text = element.get_text(strip=True)
        if text:
            # Try common date formats
            date_patterns = [
                r"\d{4}-\d{2}-\d{2}",
                r"\d{2}/\d{2}/\d{4}",
                r"\d{2}-\d{2}-\d{4}",
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        date_str = match.group(0)
                        # Try parsing
                        if "-" in date_str:
                            return datetime.strptime(date_str, "%Y-%m-%d")
                        elif "/" in date_str:
                            return datetime.strptime(date_str, "%d/%m/%Y")
                    except (ValueError, AttributeError):
                        pass

        return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def validate_article(
        self,
        article: Dict[str, Any],
        min_word_count: int = 150,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate extracted article.

        Args:
            article: Article data dictionary
            min_word_count: Minimum word count

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Check word count
        word_count = article.get("word_count", 0)
        if word_count < min_word_count:
            return False, f"Word count too low: {word_count} < {min_word_count}"

        # Check if has title
        if not article.get("title"):
            return False, "Missing title"

        # Check if has content
        if not article.get("content"):
            return False, "Missing content"

        return True, None
















