"""Phase 3: Adaptive article extraction with boilerplate removal."""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

try:
    from trafilatura import extract
    from trafilatura.settings import use_config
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

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
    """Adaptive article extractor using site profile with boilerplate removal."""

    def __init__(self, timeout: float = 30.0, use_trafilatura: bool = True):
        """
        Initialize the extractor.

        Args:
            timeout: HTTP timeout in seconds
            use_trafilatura: Use Trafilatura for boilerplate removal (recommended)
        """
        self.timeout = timeout
        self.use_trafilatura = use_trafilatura and TRAFILATURA_AVAILABLE

        if self.use_trafilatura:
            logger.info("Trafilatura boilerplate removal enabled")
        else:
            if use_trafilatura and not TRAFILATURA_AVAILABLE:
                logger.warning("Trafilatura requested but not available, falling back to CSS selectors")
            logger.info("Using CSS selectors only (no boilerplate removal)")

    async def extract_article_adaptive(
        self,
        html: str,
        url: str,
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract article using site profile with boilerplate removal.

        Strategy:
        1. Try Trafilatura for clean content extraction (RECOMMENDED - removes boilerplate)
        2. Fallback to structured data (JSON-LD, Open Graph)
        3. Fallback to profile selectors
        4. Fallback to generic CSS selectors

        Args:
            html: HTML content
            url: Article URL
            profile: Site discovery profile

        Returns:
            Dictionary with extracted article data including data quality metrics
        """
        soup = BeautifulSoup(html, "html.parser")
        article = {}
        extraction_method = "unknown"

        # 1. TRY TRAFILATURA FIRST (Best - removes header/footer/nav)
        if self.use_trafilatura:
            trafilatura_content, trafilatura_metadata = self._extract_with_trafilatura(html, url)
            if trafilatura_content:
                article["content"] = trafilatura_content
                article["extraction_method"] = "trafilatura"
                extraction_method = "trafilatura"

                # Use trafilatura metadata as base
                if trafilatura_metadata.get("title"):
                    article["title"] = trafilatura_metadata["title"]
                if trafilatura_metadata.get("author"):
                    article["author"] = trafilatura_metadata["author"]
                if trafilatura_metadata.get("date"):
                    article["published_time"] = trafilatura_metadata["date"]

                logger.debug(f"Trafilatura extraction successful for {url}")

        # 2. Try structured data (JSON-LD, Open Graph)
        jsonld = self._extract_jsonld_info(html, soup)
        if jsonld.get("is_article"):
            # Complement with JSON-LD if not already extracted
            for key, value in jsonld.get("metadata", {}).items():
                if not article.get(key) and value:
                    article[key] = value

        opengraph = self._extract_opengraph_info(html, soup)
        if opengraph.get("is_article"):
            # Complement with OG if not in other sources
            for key in ["title", "description", "published_time", "author"]:
                if not article.get(key) and opengraph.get(key):
                    article[key] = opengraph[key]

        # 3. Use profile selectors (if available and content not already extracted)
        if not article.get("content") and profile.get("content_selector"):
            content = soup.select_one(profile["content_selector"])
            if content:
                article["content"] = self._clean_text(content.get_text())
                article["content_html"] = str(content)
                article["extraction_method"] = "profile_selector"
                extraction_method = "profile_selector"

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

        # 4. Fallback to generic selectors
        if not article.get("content"):
            for selector in CONTENT_SELECTORS_PRIORITY:
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 200:
                    article["content"] = self._clean_text(content.get_text())
                    article["content_html"] = str(content)
                    article["_content_selector_used"] = selector
                    article["extraction_method"] = f"css_selector:{selector}"
                    extraction_method = "css_selector"
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

        # 5. Calculate metrics and data quality
        content_text = article.get("content", "")
        article["word_count"] = len(content_text.split())
        article["url"] = url

        # Add data quality metrics
        article["data_quality"] = self._calculate_data_quality(
            article=article,
            html=html,
            extraction_method=extraction_method
        )

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

    def _extract_with_trafilatura(
        self,
        html: str,
        url: str,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Extract clean content using Trafilatura (boilerplate removal).

        Args:
            html: HTML content
            url: Article URL

        Returns:
            Tuple of (clean_content, metadata)
        """
        if not TRAFILATURA_AVAILABLE:
            return None, {}

        try:
            # Extract with metadata
            clean_content = extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=False,  # Favor recall to get more content
                output_format="txt",
                url=url,
            )

            # Extract metadata separately
            from trafilatura.metadata import extract_metadata
            metadata_obj = extract_metadata(html, url=url)

            metadata = {}
            if metadata_obj:
                metadata = {
                    "title": metadata_obj.title,
                    "author": metadata_obj.author,
                    "date": metadata_obj.date,
                    "sitename": metadata_obj.sitename,
                }

            return clean_content, metadata

        except Exception as e:
            logger.warning(f"Trafilatura extraction failed for {url}: {e}")
            return None, {}

    def _calculate_data_quality(
        self,
        article: Dict[str, Any],
        html: str,
        extraction_method: str,
    ) -> Dict[str, Any]:
        """
        Calculate data quality metrics to detect boilerplate pollution.

        Args:
            article: Extracted article data
            html: Original HTML
            extraction_method: Method used for extraction

        Returns:
            Dictionary with quality metrics
        """
        content_text = article.get("content", "")
        word_count = len(content_text.split())

        # Calculate content density (content words / total HTML size)
        html_size = len(html)
        content_density = (len(content_text) / html_size) if html_size > 0 else 0

        # Detect boilerplate pollution
        # Check for common boilerplate indicators in content
        boilerplate_indicators = [
            "menu", "navigation", "footer", "header", "sidebar",
            "copyright", "all rights reserved", "politique de confidentialité",
            "mentions légales", "cookies", "contact us",
        ]

        boilerplate_score = 0
        content_lower = content_text.lower()
        for indicator in boilerplate_indicators:
            if indicator in content_lower:
                boilerplate_score += 1

        # Boilerplate detected if score > 3 and low density
        boilerplate_detected = boilerplate_score > 3 and content_density < 0.15

        # Calculate keyword uniqueness (requires multiple articles, so return 0 for now)
        # This will be calculated at the profile level
        keyword_uniqueness = 1.0 if extraction_method == "trafilatura" else 0.0

        return {
            "extraction_method": extraction_method,
            "content_density": round(content_density, 3),
            "word_count": word_count,
            "boilerplate_detected": boilerplate_detected,
            "boilerplate_score": boilerplate_score,
            "keyword_uniqueness": keyword_uniqueness,  # Will be calculated later at profile level
        }

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






















