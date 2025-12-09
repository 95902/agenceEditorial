"""Phase 0: Site profiling for optimized article discovery."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from python_scripts.ingestion.detect_sitemaps import detect_sitemap_urls, parse_sitemap
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


# CMS Detection Rules
CMS_DETECTION_RULES = {
    "wordpress": {
        "html_patterns": [
            r'<meta name="generator" content="WordPress',
            r"/wp-content/",
            r"/wp-includes/",
        ],
        "url_patterns": [
            r"/wp-json/",
            r"/xmlrpc\.php",
        ],
        "headers": {
            "X-Powered-By": "WordPress",
        },
    },
    "drupal": {
        "html_patterns": [
            r"Drupal\.settings",
            r"/sites/default/files/",
            r'<meta name="generator" content="Drupal',
        ],
    },
    "ghost": {
        "html_patterns": [
            r'<meta name="generator" content="Ghost',
            r"ghost-(?:card|content)",
        ],
    },
    "hubspot": {
        "html_patterns": [
            r'<meta name="generator" content="HubSpot',
            r"hs-scripts\.com",
            r"hsforms\.net",
        ],
    },
}

# Common RSS locations
RSS_LOCATIONS = [
    "/feed/",
    "/rss/",
    "/feed.xml",
    "/rss.xml",
    "/atom.xml",
    "/index.xml",
    "/blog/feed/",
    "/actualites/feed/",
    "/news/feed/",
    "/articles/feed/",
    "/feed/atom/",
    "/feed/rss/",
    "/feed/rss2/",
]

# Common sitemap locations
SITEMAP_LOCATIONS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/wp-sitemap-posts-post-1.xml",
    "/post-sitemap.xml",
    "/sitemap-posts.xml",
    "/blog-sitemap.xml",
    "/news-sitemap.xml",
    "/article-sitemap.xml",
    "/sitemap-blog.xml",
    "/sitemap-news.xml",
    "/sitemap-articles.xml",
    "/sitemaps/sitemap.xml",
    "/sitemap/sitemap.xml",
    "/sitemap/blog.xml",
    "/page-sitemap.xml",
    "/category-sitemap.xml",
]


class SiteProfiler:
    """Profile a website to optimize article discovery."""

    def __init__(self, timeout: float = 10.0):
        """Initialize the profiler."""
        self.timeout = timeout

    async def profile_site(self, domain: str) -> Dict[str, Any]:
        """
        Profile a website and return discovery profile.

        Args:
            domain: Domain name (without protocol)

        Returns:
            Dictionary with profile data
        """
        logger.info("Starting site profiling", domain=domain)
        base_url = f"https://{domain}"

        profile = {
            "domain": domain,
            "cms_detected": None,
            "cms_version": None,
            "has_rest_api": False,
            "api_endpoints": {},
            "sitemap_urls": [],
            "rss_feeds": [],
            "blog_listing_pages": [],
            "url_patterns": {},
            "article_url_regex": None,
            "pagination_pattern": None,
            "content_selector": None,
            "title_selector": None,
            "date_selector": None,
            "author_selector": None,
            "image_selector": None,
        }

        try:
            # 1. Fetch homepage
            async with httpx.AsyncClient(
                verify=False,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(base_url)
                if response.status_code != 200:
                    logger.warning(
                        "Failed to fetch homepage",
                        domain=domain,
                        status_code=response.status_code,
                    )
                    return profile

                html = response.text
                soup = BeautifulSoup(html, "html.parser")

            # 2. Detect CMS
            cms_info = self._detect_cms(html, response.headers)
            profile["cms_detected"] = cms_info.get("cms")
            profile["cms_version"] = cms_info.get("version")

            # 3. Test APIs
            if profile["cms_detected"] == "wordpress":
                api_info = await self._test_wordpress_api(domain)
                if api_info:
                    profile["has_rest_api"] = True
                    profile["api_endpoints"] = api_info

            # 4. Discover sitemaps
            profile["sitemap_urls"] = await self._discover_sitemaps(domain)

            # 5. Discover RSS feeds
            profile["rss_feeds"] = await self._discover_rss_feeds(domain, html, soup)

            # 6. Discover blog listing pages
            profile["blog_listing_pages"] = await self._discover_blog_listing_pages(
                domain, html, soup
            )

            # 7. Analyze URL patterns
            sample_urls = await self._collect_sample_urls(profile)
            if sample_urls:
                profile["url_patterns"] = self._analyze_url_patterns(sample_urls)

            # 8. Detect pagination
            profile["pagination_pattern"] = self._detect_pagination_pattern(html, soup)

            # 9. Test content selectors (if we have sample URLs)
            if sample_urls:
                selector_info = await self._test_content_selectors(sample_urls[0])
                if selector_info:
                    profile.update(selector_info)

            logger.info("Site profiling complete", domain=domain, cms=profile["cms_detected"])
            return profile

        except Exception as e:
            logger.error("Error profiling site", domain=domain, error=str(e))
            return profile

    def _detect_cms(self, html: str, headers: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Detect CMS from HTML and headers."""
        html_lower = html.lower()
        headers_lower = {k.lower(): v.lower() for k, v in headers.items()}

        for cms_name, rules in CMS_DETECTION_RULES.items():
            # Check HTML patterns
            html_matches = sum(
                1 for pattern in rules.get("html_patterns", []) if re.search(pattern, html_lower, re.I)
            )

            # Check URL patterns (in HTML links)
            url_matches = sum(
                1
                for pattern in rules.get("url_patterns", [])
                if re.search(pattern, html_lower, re.I)
            )

            # Check headers
            header_matches = 0
            for header_name, header_value in rules.get("headers", {}).items():
                if headers_lower.get(header_name) == header_value:
                    header_matches += 1

            # If we have matches, it's likely this CMS
            if html_matches > 0 or url_matches > 0 or header_matches > 0:
                # Try to extract version
                version = None
                if cms_name == "wordpress":
                    version_match = re.search(
                        r'content="WordPress\s+([\d.]+)"', html, re.I
                    )
                    if version_match:
                        version = version_match.group(1)

                return {"cms": cms_name, "version": version}

        return {"cms": "custom", "version": None}

    async def _test_wordpress_api(self, domain: str) -> Optional[Dict[str, str]]:
        """Test WordPress REST API availability."""
        base_url = f"https://{domain}"
        test_url = f"{base_url}/wp-json/wp/v2/posts?per_page=1"

        try:
            async with httpx.AsyncClient(
                verify=False,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(test_url)
                if response.status_code == 200:
                    return {
                        "posts": "/wp-json/wp/v2/posts",
                        "categories": "/wp-json/wp/v2/categories",
                        "tags": "/wp-json/wp/v2/tags",
                    }
        except Exception as e:
            logger.debug("WordPress API test failed", domain=domain, error=str(e))

        return None

    async def _discover_sitemaps(self, domain: str) -> List[str]:
        """Discover sitemap URLs."""
        sitemap_urls = []

        # Try standard detection
        try:
            detected = await detect_sitemap_urls(domain)
            sitemap_urls.extend(detected)
        except Exception as e:
            logger.debug("Standard sitemap detection failed", domain=domain, error=str(e))

        # Try common locations
        base_url = f"https://{domain}"
        for path in SITEMAP_LOCATIONS:
            sitemap_url = urljoin(base_url, path)
            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=5.0,
                    follow_redirects=True,
                ) as client:
                    response = await client.head(sitemap_url)
                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "").lower()
                        if "xml" in content_type:
                            if sitemap_url not in sitemap_urls:
                                sitemap_urls.append(sitemap_url)
            except Exception:
                continue

        return sitemap_urls

    async def _discover_rss_feeds(
        self, domain: str, html: str, soup: BeautifulSoup
    ) -> List[str]:
        """Discover RSS feed URLs."""
        rss_feeds = []
        base_url = f"https://{domain}"

        # Extract from HTML
        for link in soup.find_all("link", type=re.compile(r"application/(rss|atom)\+xml")):
            href = link.get("href")
            if href:
                absolute_url = urljoin(base_url, href)
                if absolute_url not in rss_feeds:
                    rss_feeds.append(absolute_url)

        # Try common locations
        for path in RSS_LOCATIONS:
            feed_url = urljoin(base_url, path)
            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=5.0,
                    follow_redirects=True,
                ) as client:
                    response = await client.head(feed_url)
                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "").lower()
                        if "xml" in content_type or "rss" in content_type or "atom" in content_type:
                            if feed_url not in rss_feeds:
                                rss_feeds.append(feed_url)
            except Exception:
                continue

        return rss_feeds

    async def _discover_blog_listing_pages(
        self, domain: str, html: str, soup: BeautifulSoup
    ) -> List[str]:
        """Discover blog listing pages."""
        blog_pages = []
        base_url = f"https://{domain}"

        # Common blog paths
        common_paths = [
            "/blog/",
            "/actualites/",
            "/actualite/",
            "/news/",
            "/articles/",
            "/article/",
            "/ressources/",
            "/conseils/",
            "/publications/",
        ]

        for path in common_paths:
            page_url = urljoin(base_url, path)
            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=5.0,
                    follow_redirects=True,
                ) as client:
                    response = await client.head(page_url)
                    if response.status_code == 200:
                        if page_url not in blog_pages:
                            blog_pages.append(page_url)
            except Exception:
                continue

        return blog_pages

    async def _collect_sample_urls(self, profile: Dict[str, Any]) -> List[str]:
        """Collect sample URLs for pattern analysis."""
        sample_urls = []
        domain = profile["domain"]

        # From RSS
        for rss_url in profile.get("rss_feeds", [])[:2]:  # Limit to 2 feeds
            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(rss_url)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "xml")
                        for item in soup.find_all("item")[:10]:  # First 10 items
                            link = item.find("link")
                            if link and link.text:
                                sample_urls.append(link.text.strip())
                        if len(sample_urls) >= 20:
                            break
            except Exception:
                continue

        # From sitemap
        if len(sample_urls) < 20:
            for sitemap_url in profile.get("sitemap_urls", [])[:1]:  # First sitemap
                try:
                    urls = await parse_sitemap(sitemap_url)
                    sample_urls.extend(urls[:20])
                    if len(sample_urls) >= 20:
                        break
                except Exception:
                    continue

        return sample_urls[:20]  # Limit to 20

    def _analyze_url_patterns(self, urls: List[str]) -> Dict[str, Any]:
        """Analyze URL patterns from sample URLs."""
        patterns = {
            "has_date_pattern": False,
            "date_format": None,
            "has_category": False,
            "has_slug": False,
            "common_prefixes": [],
        }

        date_patterns = [
            (r"/\d{4}/\d{2}/\d{2}/", "YYYY/MM/DD"),
            (r"/\d{4}/\d{2}/", "YYYY/MM"),
        ]

        for url in urls:
            # Check date patterns
            for pattern, format_name in date_patterns:
                if re.search(pattern, url):
                    patterns["has_date_pattern"] = True
                    patterns["date_format"] = format_name
                    break

            # Check for category (path depth >= 3)
            path_parts = urlparse(url).path.strip("/").split("/")
            if len(path_parts) >= 3:
                patterns["has_category"] = True

            # Check for slug (alphanumeric with hyphens)
            if re.search(r"/[\w-]+/[\w-]+/?$", url):
                patterns["has_slug"] = True

            # Extract common prefixes
            for prefix in ["/blog/", "/actualites/", "/news/", "/articles/"]:
                if prefix in url.lower() and prefix not in patterns["common_prefixes"]:
                    patterns["common_prefixes"].append(prefix)

        return patterns

    def _detect_pagination_pattern(self, html: str, soup: BeautifulSoup) -> Optional[str]:
        """Detect pagination pattern."""
        # Look for pagination links
        pagination_patterns = [
            (r'\?page=\d+', "?page={n}"),
            (r'\?paged=\d+', "?paged={n}"),
            (r'/page/\d+/', "/page/{n}/"),
        ]

        for pattern, format_str in pagination_patterns:
            if re.search(pattern, html):
                return format_str

        return None

    async def _test_content_selectors(self, sample_url: str) -> Optional[Dict[str, str]]:
        """Test content selectors on a sample article."""
        selectors = {
            "content_selector": None,
            "title_selector": None,
            "date_selector": None,
            "author_selector": None,
        }

        try:
            async with httpx.AsyncClient(
                verify=False,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(sample_url)
                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                # Test content selectors
                content_selectors = [
                    "[itemprop='articleBody']",
                    "article .entry-content",
                    "article .post-content",
                    ".article-content",
                    "article",
                ]
                for selector in content_selectors:
                    if soup.select_one(selector):
                        selectors["content_selector"] = selector
                        break

                # Test title selectors
                title_selectors = [
                    "[itemprop='headline']",
                    "h1.entry-title",
                    "h1.post-title",
                    "article h1",
                    "h1",
                ]
                for selector in title_selectors:
                    if soup.select_one(selector):
                        selectors["title_selector"] = selector
                        break

                # Test date selectors
                date_selectors = [
                    "[itemprop='datePublished']",
                    "time[datetime]",
                    ".entry-date",
                    ".post-date",
                ]
                for selector in date_selectors:
                    if soup.select_one(selector):
                        selectors["date_selector"] = selector
                        break

                # Test author selectors
                author_selectors = [
                    "[itemprop='author']",
                    ".author-name",
                    ".entry-author",
                ]
                for selector in author_selectors:
                    if soup.select_one(selector):
                        selectors["author_selector"] = selector
                        break

                return selectors if any(selectors.values()) else None

        except Exception as e:
            logger.debug("Content selector test failed", url=sample_url, error=str(e))
            return None



