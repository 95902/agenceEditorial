"""Article detector based on HTML content analysis."""

import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class ArticleDetector:
    """
    Detect if a page is an article based on HTML structure and content analysis.
    
    This detector uses multiple heuristics to determine if a page contains
    article-like content, useful as a fallback when URL patterns don't match.
    """

    def __init__(
        self,
        min_word_count: int = 150,
        min_score: float = 0.35,
    ) -> None:
        """
        Initialize the article detector.
        
        Args:
            min_word_count: Minimum word count to consider as article
            min_score: Minimum confidence score (0.0 to 1.0)
        """
        self.min_word_count = min_word_count
        self.min_score = min_score

    def detect(
        self,
        html: str,
        url: Optional[str] = None,
    ) -> Tuple[bool, float, Dict[str, any]]:
        """
        Detect if a page is an article.
        
        Args:
            html: HTML content of the page
            url: Optional URL for context
            
        Returns:
            Tuple (is_article, confidence_score, metadata)
        """
        soup = BeautifulSoup(html, "html.parser")
        scores = {}
        
        # 1. Check for <article> tag (strong signal)
        article_tags = soup.find_all("article")
        has_article_tag = len(article_tags) > 0
        scores["article_tag"] = 0.4 if has_article_tag else 0.0
        
        # 2. Check for common article class names
        article_class_patterns = [
            r"post",
            r"entry",
            r"article",
            r"content",
            r"blog",
        ]
        article_class_score = 0.0
        for pattern in article_class_patterns:
            if soup.find(class_=re.compile(pattern, re.I)):
                article_class_score = 0.2
                break
        scores["article_class"] = article_class_score
        
        # 3. Check for title (h1)
        h1_tags = soup.find_all("h1")
        has_h1 = len(h1_tags) > 0
        scores["has_title"] = 0.15 if has_h1 else 0.0
        
        # 4. Check for publication date
        date_indicators = [
            soup.find("time"),
            soup.find(class_=re.compile(r"date|published|pub-date", re.I)),
            soup.find(attrs={"itemprop": "datePublished"}),
            soup.find("meta", property="article:published_time"),
        ]
        has_date = any(date_indicators)
        scores["has_date"] = 0.1 if has_date else 0.0
        
        # 5. Check content length
        # Try to extract main content
        content_text = ""
        
        # Strategy 1: <article> tag
        if article_tags:
            content_text = article_tags[0].get_text(separator=" ", strip=True)
        else:
            # Strategy 2: Common content classes
            for class_name in ["content", "post-content", "article-content", "entry-content", "post-body"]:
                content_elem = soup.find(class_=re.compile(class_name, re.I))
                if content_elem:
                    content_text = content_elem.get_text(separator=" ", strip=True)
                    if len(content_text) > 100:
                        break
            
            # Strategy 3: <main> tag
            if not content_text:
                main_tag = soup.find("main")
                if main_tag:
                    content_text = main_tag.get_text(separator=" ", strip=True)
        
        # Fallback: body content (remove unwanted elements)
        if not content_text:
            body = soup.find("body")
            if body:
                # Remove unwanted elements
                for tag in body.find_all(["header", "footer", "nav", "aside", "script", "style"]):
                    tag.decompose()
                content_text = body.get_text(separator=" ", strip=True)
        
        word_count = len(content_text.split())
        scores["word_count"] = min(0.15, (word_count / self.min_word_count) * 0.15) if word_count >= self.min_word_count else 0.0
        
        # 6. Check for author information
        author_indicators = [
            soup.find("meta", attrs={"name": "author"}),
            soup.find("meta", property="article:author"),
            soup.find(class_=re.compile(r"author|byline", re.I)),
        ]
        has_author = any(author_indicators)
        scores["has_author"] = 0.05 if has_author else 0.0
        
        # Calculate total score
        total_score = sum(scores.values())
        
        # Determine if it's an article
        is_article = (
            total_score >= self.min_score
            and word_count >= self.min_word_count
        )
        
        metadata = {
            "scores": scores,
            "total_score": total_score,
            "word_count": word_count,
            "has_article_tag": has_article_tag,
            "has_h1": has_h1,
            "has_date": has_date,
            "has_author": has_author,
        }
        
        return is_article, total_score, metadata


def quick_detect(html: str, url: Optional[str] = None) -> bool:
    """
    Quick detection function for convenience.
    
    Args:
        html: HTML content
        url: Optional URL
        
    Returns:
        True if detected as article
    """
    detector = ArticleDetector()
    is_article, _, _ = detector.detect(html, url)
    return is_article

