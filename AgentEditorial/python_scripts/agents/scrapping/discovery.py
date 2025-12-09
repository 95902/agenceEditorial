"""Phase 1: Enhanced multi-source article discovery."""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from python_scripts.ingestion.detect_sitemaps import parse_sitemap
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class ArticleDiscovery:
    """Enhanced article discovery with multiple sources."""

    def __init__(self, timeout: float = 10.0):
        """Initialize the discovery engine."""
        self.timeout = timeout

    async def discover_via_api(
        self,
        domain: str,
        api_endpoints: Dict[str, str],
        max_articles: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Discover articles via REST API (WordPress, Ghost, etc.).

        Args:
            domain: Domain name
            api_endpoints: Dictionary with API endpoints
            max_articles: Maximum articles to discover

        Returns:
            List of article data dictionaries
        """
        articles = []
        base_url = f"https://{domain}"

        # WordPress REST API
        if "posts" in api_endpoints:
            posts_endpoint = api_endpoints["posts"]
            api_url = urljoin(base_url, posts_endpoint)

            try:
                page = 1
                per_page = 100  # WordPress max

                while len(articles) < max_articles:
                    params = {
                        "per_page": min(per_page, max_articles - len(articles)),
                        "page": page,
                        "orderby": "date",
                        "order": "desc",
                        "_fields": "id,date,modified,slug,title,excerpt,link,author,categories,tags",
                    }

                    async with httpx.AsyncClient(
                        verify=False,
                        timeout=self.timeout,
                        follow_redirects=True,
                    ) as client:
                        response = await client.get(api_url, params=params)
                        if response.status_code != 200:
                            break

                        data = response.json()
                        if not data or not isinstance(data, list):
                            break

                        for post in data:
                            if len(articles) >= max_articles:
                                break

                            title = post.get("title", {})
                            if isinstance(title, dict):
                                title = title.get("rendered", "")

                            articles.append({
                                "url": post.get("link", ""),
                                "title": title,
                                "date": post.get("date"),
                                "source": "api",
                            })

                        # Check if there are more pages
                        total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                        if page >= total_pages or len(data) < per_page:
                            break

                        page += 1

                logger.info(
                    "API discovery complete",
                    domain=domain,
                    articles_found=len(articles),
                )

            except Exception as e:
                logger.warning("API discovery failed", domain=domain, error=str(e))

        return articles

    async def discover_via_rss(
        self,
        rss_feeds: List[str],
        max_articles: int = 100,
    ) -> List[str]:
        """
        Discover articles via RSS feeds with pagination support.

        Args:
            rss_feeds: List of RSS feed URLs
            max_articles: Maximum articles to discover

        Returns:
            List of article URLs
        """
        all_urls = set()

        for feed_url in rss_feeds:
            if len(all_urls) >= max_articles:
                break

            try:
                urls = await self._parse_rss_with_pagination(feed_url, max_pages=5)
                all_urls.update(urls)
            except Exception as e:
                logger.debug("RSS feed parsing failed", feed_url=feed_url, error=str(e))
                continue

        return list(all_urls)[:max_articles]

    async def _parse_rss_with_pagination(
        self,
        feed_url: str,
        max_pages: int = 5,
    ) -> List[str]:
        """Parse RSS feed with pagination support."""
        all_urls = set()

        for page in range(1, max_pages + 1):
            if page == 1:
                current_url = feed_url
            else:
                # Try different pagination formats
                pagination_formats = [
                    f"{feed_url}?paged={page}",
                    f"{feed_url}?page={page}",
                    f"{feed_url}/page/{page}/",
                ]
                current_url = pagination_formats[0]

            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(current_url)
                    if response.status_code != 200:
                        break

                    soup = BeautifulSoup(response.text, "xml")
                    page_urls = []

                    # RSS format
                    for item in soup.find_all("item"):
                        link = item.find("link")
                        if link and link.text:
                            page_urls.append(link.text.strip())

                    # Atom format
                    for entry in soup.find_all("entry"):
                        link = entry.find("link")
                        if link:
                            href = link.get("href") or link.text
                            if href:
                                page_urls.append(href.strip())

                    if not page_urls:
                        break

                    all_urls.update(page_urls)

                    # Check for next page (Atom)
                    next_link = soup.find("link", rel="next")
                    if not next_link and page > 1:
                        break

            except Exception as e:
                logger.debug("RSS page parsing failed", url=current_url, error=str(e))
                break

        return list(all_urls)

    async def discover_via_sitemap(
        self,
        sitemap_urls: List[str],
        max_articles: int = 100,
    ) -> List[str]:
        """
        Discover articles via sitemaps with intelligent filtering.

        Args:
            sitemap_urls: List of sitemap URLs
            max_articles: Maximum articles to discover

        Returns:
            List of article URLs
        """
        all_urls = []

        for sitemap_url in sitemap_urls:
            if len(all_urls) >= max_articles:
                break

            try:
                urls = await parse_sitemap(sitemap_url)
                # Filter and score URLs
                filtered = await self._filter_sitemap_urls(urls, max_articles - len(all_urls))
                all_urls.extend([url["url"] for url in filtered])
            except Exception as e:
                logger.debug("Sitemap parsing failed", sitemap_url=sitemap_url, error=str(e))
                continue

        return all_urls[:max_articles]

    async def _filter_sitemap_urls(
        self,
        urls: List[str],
        max_urls: int,
    ) -> List[Dict[str, Any]]:
        """Filter and score sitemap URLs."""
        filtered = []

        for url in urls:
            if len(filtered) >= max_urls:
                break

            score = 0
            metadata = {"url": url, "source": "sitemap"}

            # Positive patterns
            if re.search(r"/blog/|/actualites?/|/news/|/article/", url, re.I):
                score += 15
            if re.search(r"/\d{4}/\d{2}/", url):  # Date pattern
                score += 10
            if len(url.split("/")) >= 4:  # Sufficient depth
                score += 5

            # Negative patterns
            if re.search(r"/category/|/tag/|/author/|/page/", url, re.I):
                score -= 20
            if re.search(r"/contact|/about|/mentions-legales|/cgv", url, re.I):
                score -= 25
            if any(url.lower().endswith(ext) for ext in [".pdf", ".jpg", ".png"]):
                score -= 30

            metadata["initial_score"] = score
            if score >= 0:
                filtered.append(metadata)

        return sorted(filtered, key=lambda x: x["initial_score"], reverse=True)

    async def discover_via_heuristics(
        self,
        domain: str,
        profile: Dict[str, Any],
        max_urls: int,
    ) -> List[str]:
        """
        Discover articles via heuristics (HTML crawling).

        Args:
            domain: Domain name
            profile: Site discovery profile
            max_urls: Maximum URLs to discover

        Returns:
            List of article URLs
        """
        article_urls = set()
        base_url = f"https://{domain}"

        # Use blog listing pages from profile
        blog_pages = profile.get("blog_listing_pages", [])
        if not blog_pages:
            # Fallback to common paths
            blog_pages = [
                f"{base_url}/blog/",
                f"{base_url}/actualites/",
                f"{base_url}/news/",
            ]

        # Article container selectors
        article_selectors = [
            "article",
            "main article",
            "[role='article']",
            "[itemtype*='Article']",
            "[itemtype*='BlogPosting']",
            ".post",
            ".blog-post",
            ".article",
            ".news-item",
            ".entry",
        ]

        for blog_page in blog_pages[:3]:  # Limit to 3 pages
            if len(article_urls) >= max_urls:
                break

            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(blog_page)
                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.text, "html.parser")

                    # Extract JSON-LD
                    jsonld_info = self._extract_jsonld_info(soup)
                    if jsonld_info.get("article_urls"):
                        article_urls.update(jsonld_info["article_urls"])

                    # Extract from article containers
                    for selector in article_selectors:
                        containers = soup.select(f"{selector} a[href]")
                        for link in containers:
                            if len(article_urls) >= max_urls:
                                break
                            href = link.get("href")
                            if href:
                                absolute_url = urljoin(base_url, href)
                                url_domain = urlparse(absolute_url).netloc.replace("www.", "")
                                base_domain = urlparse(base_url).netloc.replace("www.", "")
                                if url_domain == base_domain:
                                    article_urls.add(absolute_url)

            except Exception as e:
                logger.debug("Heuristic discovery failed", url=blog_page, error=str(e))
                continue

        return list(article_urls)[:max_urls]

    def _extract_jsonld_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract JSON-LD information from HTML."""
        info = {
            "is_article": False,
            "is_listing": False,
            "article_urls": [],
            "metadata": {},
        }

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)

                # Handle arrays
                if isinstance(data, list):
                    for item in data:
                        self._process_jsonld_item(item, info)
                else:
                    self._process_jsonld_item(data, info)

            except json.JSONDecodeError:
                continue

        return info

    def _process_jsonld_item(self, item: Dict, info: Dict) -> None:
        """Process a JSON-LD item."""
        item_type = item.get("@type", "")

        # Article types
        if item_type in ["Article", "BlogPosting", "NewsArticle", "TechArticle"]:
            info["is_article"] = True
            url = item.get("url") or item.get("mainEntityOfPage", {}).get("@id")
            if url:
                info["article_urls"].append(url)

        # Listing pages
        elif item_type in ["CollectionPage", "Blog", "WebPage"]:
            if item_type in ["CollectionPage", "Blog"]:
                info["is_listing"] = True

            # Extract related articles
            main_entity = item.get("mainEntity", [])
            if isinstance(main_entity, list):
                for entity in main_entity:
                    if entity.get("@type") in ["Article", "BlogPosting"]:
                        url = entity.get("url")
                        if url:
                            info["article_urls"].append(url)



