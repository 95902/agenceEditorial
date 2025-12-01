"""Sitemap detection and parsing utilities."""

import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

from python_scripts.config.settings import settings
from python_scripts.utils.exceptions import CrawlingError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def detect_sitemap_urls(domain: str) -> List[str]:
    """
    Detect sitemap URLs for a domain.

    Tries common sitemap locations:
    - /sitemap.xml
    - /sitemap_index.xml
    - robots.txt (Sitemap directive)

    Args:
        domain: Domain name (without protocol)

    Returns:
        List of sitemap URLs found
    """
    sitemap_urls = []
    base_url = f"https://{domain}"

    # Try robots.txt first
    try:
        robots_url = f"{base_url}/robots.txt"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(robots_url, follow_redirects=True)
            if response.status_code == 200:
                # Parse Sitemap directives
                for line in response.text.split("\n"):
                    line = line.strip()
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        if sitemap_url:
                            sitemap_urls.append(sitemap_url)
    except Exception as e:
        logger.debug("Failed to fetch robots.txt for sitemap detection", domain=domain, error=str(e))

    # Try common sitemap locations
    common_paths = ["/sitemap.xml", "/sitemap_index.xml", "/sitemaps/sitemap.xml"]
    for path in common_paths:
        sitemap_url = urljoin(base_url, path)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(sitemap_url, follow_redirects=True)
                if response.status_code == 200:
                    if sitemap_url not in sitemap_urls:
                        sitemap_urls.append(sitemap_url)
        except Exception:
            continue

    return sitemap_urls


async def parse_sitemap(sitemap_url: str) -> List[str]:
    """
    Parse a sitemap XML and extract URLs.

    Supports:
    - Regular sitemaps (<urlset>)
    - Sitemap indexes (<sitemapindex>)

    Args:
        sitemap_url: URL of the sitemap

    Returns:
        List of URLs found in the sitemap

    Raises:
        CrawlingError: If parsing fails
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(sitemap_url, follow_redirects=True)
            if response.status_code != 200:
                raise CrawlingError(f"Sitemap not accessible: {sitemap_url}")

            xml_content = response.text
            root = ElementTree.fromstring(xml_content)

            urls = []

            # Check if it's a sitemap index
            if root.tag.endswith("sitemapindex"):
                # Parse sitemap index - recursively fetch nested sitemaps
                for sitemap_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"):
                    loc_elem = sitemap_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                    if loc_elem is not None and loc_elem.text:
                        nested_urls = await parse_sitemap(loc_elem.text.strip())
                        urls.extend(nested_urls)
            else:
                # Regular sitemap - extract URLs
                for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
                    loc_elem = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                    if loc_elem is not None and loc_elem.text:
                        urls.append(loc_elem.text.strip())

            logger.info("Sitemap parsed", sitemap_url=sitemap_url, url_count=len(urls))
            return urls

    except ElementTree.ParseError as e:
        logger.error("Failed to parse sitemap XML", sitemap_url=sitemap_url, error=str(e))
        raise CrawlingError(f"Failed to parse sitemap {sitemap_url}: {e}") from e
    except Exception as e:
        logger.error("Failed to fetch sitemap", sitemap_url=sitemap_url, error=str(e))
        raise CrawlingError(f"Failed to fetch sitemap {sitemap_url}: {e}") from e


async def get_sitemap_urls(domain: str) -> List[str]:
    """
    Get all URLs from sitemaps for a domain.

    Args:
        domain: Domain name (without protocol)

    Returns:
        List of all URLs found in sitemaps
    """
    sitemap_urls = await detect_sitemap_urls(domain)
    if not sitemap_urls:
        logger.warning("No sitemaps found", domain=domain)
        return []

    all_urls = []
    for sitemap_url in sitemap_urls:
        try:
            urls = await parse_sitemap(sitemap_url)
            all_urls.extend(urls)
        except CrawlingError as e:
            logger.warning("Failed to parse sitemap", sitemap_url=sitemap_url, error=str(e))
            continue

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    logger.info("Sitemap URLs extracted", domain=domain, total_urls=len(unique_urls))
    return unique_urls

