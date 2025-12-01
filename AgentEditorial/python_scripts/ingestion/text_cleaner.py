"""Text cleaning utilities."""

import re
from html import unescape
from html.parser import HTMLParser
from typing import Optional

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class HTMLTextExtractor(HTMLParser):
    """Extract text from HTML."""

    def __init__(self) -> None:
        """Initialize parser."""
        super().__init__()
        self.text = []
        self.skip_tags = {"script", "style", "meta", "link", "head"}

    def handle_data(self, data: str) -> None:
        """Handle text data."""
        if data.strip():
            self.text.append(data.strip())

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Handle start tags."""
        if tag in self.skip_tags:
            self.skip_tags.add(tag)

    def handle_endtag(self, tag: str) -> None:
        """Handle end tags."""
        if tag in self.skip_tags:
            self.skip_tags.remove(tag)


def clean_html_text(html_content: str) -> str:
    """
    Clean HTML content and extract plain text.

    Args:
        html_content: Raw HTML content

    Returns:
        Cleaned plain text
    """
    try:
        # Decode HTML entities
        text = unescape(html_content)

        # Extract text using parser
        parser = HTMLTextExtractor()
        parser.feed(text)
        text = " ".join(parser.text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text
    except Exception as e:
        logger.warning("Failed to clean HTML text", error=str(e))
        # Fallback: simple regex-based extraction
        text = re.sub(r"<[^>]+>", "", html_content)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def extract_meta_description(html_content: str) -> Optional[str]:
    """Extract meta description from HTML."""
    match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
        html_content,
        re.IGNORECASE,
    )
    if match:
        return unescape(match.group(1))
    return None

