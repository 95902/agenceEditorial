"""Web page crawling utilities using Crawl4AI."""

import asyncio
import re
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

# Suppress SSL warnings for development
warnings.filterwarnings("ignore", message=".*certificate.*")


async def check_robots_txt(url: str, timeout: float = 5.0) -> bool:
    """
    Check if robots.txt allows crawling the URL.
    
    Args:
        url: The URL to check
        timeout: Timeout for the request
        
    Returns:
        True if crawling is allowed, False otherwise
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            response = await client.get(robots_url)
            if response.status_code == 404:
                return True  # No robots.txt means allowed
            
            content = response.text.lower()
            # Basic check - if user-agent: * with disallow: / then blocked
            if "user-agent: *" in content and "disallow: /" in content:
                return False
                
        return True
    except Exception as e:
        logger.debug(f"Could not check robots.txt for {url}: {e}")
        return True  # Allow by default if we can't check


async def crawl_page_async(
    url: str,
    timeout: float = 30.0,
    check_cache: bool = True,
) -> Dict[str, Any]:
    """
    Crawl a single page and extract content.
    
    Args:
        url: URL to crawl
        timeout: Request timeout in seconds
        check_cache: Whether to check cache (not used, kept for API compatibility)
        
    Returns:
        Dictionary with crawl results
    """
    result = {
        "url": url,
        "success": False,
        "html": "",
        "text": "",
        "title": "",
        "description": "",
        "status_code": None,
        "error": None,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    
    try:
        async with httpx.AsyncClient(
            verify=False,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        ) as client:
            response = await client.get(url)
            result["status_code"] = response.status_code
            
            if response.status_code == 200:
                html = response.text
                result["html"] = html
                result["success"] = True
                
                # Extract title
                import re
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
                if title_match:
                    result["title"] = title_match.group(1).strip()
                
                # Extract meta description
                desc_match = re.search(
                    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                    html,
                    re.IGNORECASE
                )
                if not desc_match:
                    desc_match = re.search(
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
                        html,
                        re.IGNORECASE
                    )
                if desc_match:
                    result["description"] = desc_match.group(1).strip()
                
                # Extract text content (basic)
                # Remove scripts and styles
                text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                # Remove HTML tags
                text = re.sub(r"<[^>]+>", " ", text)
                # Clean whitespace
                text = re.sub(r"\s+", " ", text).strip()
                result["text"] = text[:10000]  # Limit text length
                
            else:
                result["error"] = f"HTTP {response.status_code}"
                
    except httpx.TimeoutException:
        result["error"] = "Timeout"
    except httpx.ConnectError as e:
        result["error"] = f"Connection error: {str(e)[:100]}"
    except Exception as e:
        result["error"] = f"Error: {str(e)[:100]}"
        logger.debug(f"Crawl error for {url}: {e}")
    
    return result


async def crawl_with_permissions(
    url: str,
    db_session: Optional[AsyncSession] = None,
    use_cache: bool = True,
    respect_robots: bool = True,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Crawl a page with permission checks (robots.txt).
    
    Args:
        url: URL to crawl
        db_session: Database session (optional, for caching)
        use_cache: Whether to use cache
        respect_robots: Whether to respect robots.txt
        timeout: Request timeout
        
    Returns:
        Dictionary with crawl results
    """
    # Check robots.txt if requested
    if respect_robots:
        allowed = await check_robots_txt(url)
        if not allowed:
            return {
                "url": url,
                "success": False,
                "error": "Blocked by robots.txt",
                "html": "",
                "text": "",
                "title": "",
                "description": "",
                "status_code": None,
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }
    
    # Crawl the page
    return await crawl_page_async(url, timeout=timeout, check_cache=use_cache)


async def crawl_multiple_pages(
    urls: List[str],
    db_session: Optional[AsyncSession] = None,
    use_cache: bool = True,
    respect_robots: bool = True,
    timeout: float = 30.0,
    max_concurrent: int = 5,
) -> List[Dict[str, Any]]:
    """
    Crawl multiple pages concurrently.
    
    Args:
        urls: List of URLs to crawl
        db_session: Database session (optional)
        use_cache: Whether to use cache
        respect_robots: Whether to respect robots.txt
        timeout: Request timeout per page
        max_concurrent: Maximum concurrent requests
        
    Returns:
        List of crawl results
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def crawl_with_semaphore(url: str) -> Dict[str, Any]:
        async with semaphore:
            return await crawl_with_permissions(
                url,
                db_session=db_session,
                use_cache=use_cache,
                respect_robots=respect_robots,
                timeout=timeout,
            )
    
    tasks = [crawl_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error results
    processed_results = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            processed_results.append({
                "url": url,
                "success": False,
                "error": str(result),
                "html": "",
                "text": "",
                "title": "",
                "description": "",
                "status_code": None,
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            processed_results.append(result)
    
    return processed_results


async def extract_links(html: str, base_url: str) -> List[str]:
    """
    Extract links from HTML content.
    
    Args:
        html: HTML content
        base_url: Base URL for resolving relative links
        
    Returns:
        List of absolute URLs
    """
    import re
    
    links = []
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    
    for match in href_pattern.finditer(html):
        href = match.group(1)
        # Skip anchors, javascript, mailto
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        
        # Convert to absolute URL
        try:
            absolute_url = urljoin(base_url, href)
            # Only keep http/https URLs
            if absolute_url.startswith(("http://", "https://")):
                links.append(absolute_url)
        except Exception:
            continue
    
    return list(set(links))  # Remove duplicates


def extract_article_from_html(
    html: str,
    url: str,
) -> Dict[str, Any]:
    """
    Extract article data from HTML content (T097 - US5).
    
    Extracts:
    - title: Article title
    - author: Article author
    - published_date: Publication date
    - content: Article text content
    - content_html: Article HTML content
    - images: List of image URLs
    - word_count: Word count of the content
    
    Args:
        html: HTML content
        url: Source URL
        
    Returns:
        Dictionary with extracted article data
    """
    soup = BeautifulSoup(html, "html.parser")
    
    article_data = {
        "title": "",
        "author": None,
        "published_date": None,
        "content": "",
        "content_html": "",
        "images": [],
        "word_count": 0,
    }
    
    # Extract title - try multiple strategies
    title = None
    
    # Strategy 1: <title> tag
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
    
    # Strategy 2: <h1> tag
    if not title:
        h1_tag = soup.find("h1")
        if h1_tag:
            title = h1_tag.get_text(strip=True)
    
    # Strategy 3: Open Graph title
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title.get("content").strip()
    
    # Strategy 4: Article title attribute
    if not title:
        article_title = soup.find(attrs={"itemprop": "headline"})
        if article_title:
            title = article_title.get_text(strip=True)
    
    article_data["title"] = title or ""
    
    # Extract author - try multiple strategies
    author = None
    
    # Strategy 1: <meta name="author">
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author.get("content").strip()
    
    # Strategy 2: <meta property="article:author">
    if not author:
        og_author = soup.find("meta", property="article:author")
        if og_author and og_author.get("content"):
            author = og_author.get("content").strip()
    
    # Strategy 3: itemprop="author"
    if not author:
        author_elem = soup.find(attrs={"itemprop": "author"})
        if author_elem:
            author = author_elem.get_text(strip=True)
    
    # Strategy 4: Common class names
    if not author:
        for class_name in ["author", "byline", "post-author"]:
            author_elem = soup.find(class_=re.compile(class_name, re.I))
            if author_elem:
                author = author_elem.get_text(strip=True)
                break
    
    article_data["author"] = author
    
    # Extract published date - try multiple strategies
    published_date = None
    
    # Strategy 1: <meta property="article:published_time">
    og_date = soup.find("meta", property="article:published_time")
    if og_date and og_date.get("content"):
        try:
            published_date = datetime.fromisoformat(og_date.get("content").replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    # Strategy 2: <time datetime>
    if not published_date:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            try:
                published_date = datetime.fromisoformat(time_tag.get("datetime").replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
    
    # Strategy 3: itemprop="datePublished"
    if not published_date:
        date_elem = soup.find(attrs={"itemprop": "datePublished"})
        if date_elem:
            date_str = date_elem.get("content") or date_elem.get_text(strip=True)
            try:
                published_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
    
    # Strategy 4: Common class names
    if not published_date:
        for class_name in ["date", "published", "post-date", "pub-date"]:
            date_elem = soup.find(class_=re.compile(class_name, re.I))
            if date_elem:
                date_str = date_elem.get_text(strip=True)
                # Try to parse common date formats
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"]:
                    try:
                        published_date = datetime.strptime(date_str, fmt)
                        published_date = published_date.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                if published_date:
                    break
    
    if published_date:
        article_data["published_date"] = published_date
    
    # Extract article content - try multiple strategies
    content_html = ""
    content_text = ""
    
    # Strategy 1: <article> tag
    article_tag = soup.find("article")
    if article_tag:
        content_html = str(article_tag)
        content_text = article_tag.get_text(separator=" ", strip=True)
    
    # Strategy 2: Common content class names
    if not content_text:
        for class_name in ["content", "post-content", "article-content", "entry-content", "post-body"]:
            content_elem = soup.find(class_=re.compile(class_name, re.I))
            if content_elem:
                content_html = str(content_elem)
                content_text = content_elem.get_text(separator=" ", strip=True)
                if len(content_text) > 100:  # Only use if substantial content
                    break
    
    # Strategy 3: <main> tag
    if not content_text:
        main_tag = soup.find("main")
        if main_tag:
            content_html = str(main_tag)
            content_text = main_tag.get_text(separator=" ", strip=True)
    
    # Fallback: Use body content (remove header, footer, nav, aside)
    if not content_text or len(content_text) < 100:
        body = soup.find("body")
        if body:
            # Remove unwanted elements
            for tag in body.find_all(["header", "footer", "nav", "aside", "script", "style"]):
                tag.decompose()
            content_html = str(body)
            content_text = body.get_text(separator=" ", strip=True)
    
    # Clean up content
    content_text = re.sub(r"\s+", " ", content_text).strip()
    article_data["content"] = content_text
    article_data["content_html"] = content_html
    article_data["word_count"] = len(content_text.split())
    
    # Extract images
    images = []
    img_tags = soup.find_all("img")
    for img in img_tags:
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if src:
            # Convert to absolute URL
            try:
                absolute_url = urljoin(url, src)
                if absolute_url.startswith(("http://", "https://")):
                    images.append(absolute_url)
            except Exception:
                continue
    
    # Also check for Open Graph images
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        og_image_url = urljoin(url, og_image.get("content"))
        if og_image_url not in images:
            images.insert(0, og_image_url)  # Add at beginning
    
    article_data["images"] = list(set(images))  # Remove duplicates
    
    return article_data


def generate_url_hash(url: str) -> str:
    """
    Generate SHA256 hash of URL for deduplication (T099 - US5).
    
    Args:
        url: URL to hash
        
    Returns:
        Hexadecimal hash string (64 characters)
    """
    import hashlib
    
    # Normalize URL: remove fragment, lowercase, remove trailing slash
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    normalized = normalized.lower().rstrip("/")
    
    # Generate hash
    hash_obj = hashlib.sha256(normalized.encode("utf-8"))
    return hash_obj.hexdigest()
