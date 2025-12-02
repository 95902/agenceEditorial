"""Web page crawling utilities using Crawl4AI."""

import asyncio
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
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
