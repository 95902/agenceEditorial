"""Scraping agent for competitor articles (T096-T099 - US5)."""

import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.base_agent import BaseAgent
from python_scripts.database.crud_articles import (
    create_competitor_article,
    get_competitor_article_by_hash,
    list_competitor_articles,
    update_qdrant_point_id,
)
from python_scripts.database.crud_client_articles import (
    create_client_article,
    get_client_article_by_hash as get_client_article_by_hash_crud,
    update_qdrant_point_id as update_client_qdrant_point_id,
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.ingestion.article_detector import ArticleDetector
from python_scripts.ingestion.crawl_pages import (
    crawl_page_async,
    extract_article_from_html,
    generate_url_hash,
)
from python_scripts.ingestion.detect_sitemaps import get_sitemap_urls
from python_scripts.ingestion.robots_txt import parse_robots_txt
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.qdrant_client import (
    qdrant_client,
    COLLECTION_NAME,
    get_competitor_collection_name,
)

logger = get_logger(__name__)


class ScrapingAgent(BaseAgent):
    """Agent for scraping competitor articles with article discovery and filtering."""

    # Article URL patterns for French websites
    ARTICLE_URL_PATTERNS = [
        # Patterns existants
        r"/blog/",
        r"/article/",
        r"/actualites/",
        r"/news/",
        r"/posts/",
        r"/post/",
        # Nouveaux patterns français
        r"/actualite/",           # Singulier
        r"/actu/",
        r"/articles/",            # Pluriel
        r"/communiques?/",        # Communiqué(s)
        r"/presse/",
        r"/notre-actu/",
        r"/media/",
        r"/publications?/",       # Publication(s)
        r"/ressources/",
        r"/conseils/",
        r"/guides/",
        r"/tutoriels/",
        r"/veille/",
        r"/insights/",
        r"/etudes/",
        r"/cas-client/",
        r"/cas-clients/",
        r"/temoignage/",
        r"/temoignages/",
        r"/whitepaper/",
        r"/livre-blanc/",
        r"/webinaire/",
        r"/webinaires/",
        # Patterns génériques
        r"/\d{4}/\d{2}/",         # WordPress date pattern (YYYY/MM/)
        r"/\d{4}/\d{2}/\d{2}/",   # WordPress date pattern (YYYY/MM/DD/)
        # Note: Pattern slug SEO trop large, retiré pour éviter de matcher toutes les URLs
    ]

    # Extensions to exclude
    EXCLUDED_EXTENSIONS = [
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg',
        '.css', '.js', '.xml', '.zip', '.doc', '.docx',
        '.xls', '.xlsx', '.ppt', '.pptx', '.mp4', '.mp3',
    ]

    # Patterns pour détecter les articles d'offres d'emploi
    JOB_POSTING_PATTERNS = [
        # Français
        "offre d'emploi", "offres d'emploi", "offre emploi", "offres emploi",
        "poste à pourvoir", "poste à combler", "recrutement", "recrute",
        "nous recrutons", "rejoignez-nous", "rejoindre l'équipe",
        "candidature", "candidater", "postuler", "postulez",
        "cdi", "cdd", "stage", "alternance", "apprentissage",
        "cv", "curriculum vitae", "lettre de motivation",
        "salaire", "rémunération", "avantages", "package",
        "profil recherché", "profil souhaité", "missions",
        "compétences requises", "qualifications",
        # Anglais
        "job offer", "job offers", "job posting", "job postings",
        "we are hiring", "we're hiring", "join our team",
        "apply now", "apply for", "application", "candidate",
        "full-time", "part-time", "contract", "internship",
        "salary", "compensation", "benefits package",
        "required skills", "qualifications", "job description",
    ]

    def __init__(
        self,
        min_word_count: int = 150,
        max_age_days: Optional[int] = 1095,  # 3 ans (3 * 365 jours)
        use_article_detector: bool = True,
    ) -> None:
        """Initialize the scraping agent."""
        super().__init__("scraping")
        self.min_word_count = min_word_count
        self.max_age_days = max_age_days  # None = pas de limite
        self.article_detector = ArticleDetector(min_word_count=min_word_count) if use_article_detector else None

    def _normalize_url_to_domain(self, url: str, target_domain: str) -> str:
        """
        Normalize URL to use the target domain (handle www variations).
        
        Args:
            url: URL to normalize
            target_domain: Target domain to use
            
        Returns:
            Normalized URL
        """
        parsed = urlparse(url)
        target_domain_clean = target_domain.replace("www.", "")
        current_domain_clean = parsed.netloc.replace("www.", "")
        
        # If domain matches (ignoring www), return normalized URL
        if current_domain_clean == target_domain_clean:
            # Use target domain format (preserve www if present in target)
            if target_domain.startswith("www."):
                netloc = f"www.{target_domain_clean}"
            else:
                netloc = target_domain_clean
            
            normalized = parsed._replace(netloc=netloc, scheme="https")
            return normalized.geturl().rstrip("/")
        
        return url

    async def _detect_domain_redirect(self, domain: str) -> str:
        """
        Detect if domain redirects to another domain (e.g., .fr -> .com, .fr -> .ch).
        
        Args:
            domain: Original domain to check
            
        Returns:
            Corrected domain (or original if no redirect)
        """
        try:
            base_url = f"https://{domain}"
            async with httpx.AsyncClient(
                verify=False,
                timeout=10.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(base_url)
                final_url = str(response.url)
                final_domain = urlparse(final_url).netloc
                
                # Remove www. prefix for comparison
                original_domain_clean = domain.replace("www.", "")
                final_domain_clean = final_domain.replace("www.", "")
                
                # If domain changed (e.g., .fr -> .com, .fr -> .ch), use the final domain
                if original_domain_clean != final_domain_clean:
                    self.logger.info(
                        "Domain redirect detected",
                        original_domain=domain,
                        final_domain=final_domain_clean,
                        redirect_url=final_url,
                    )
                    return final_domain_clean
        except Exception as e:
            self.logger.debug("Failed to detect domain redirect", domain=domain, error=str(e))
        
        return domain

    async def discover_article_urls(
        self,
        domain: str,
        max_articles: int = 100,
    ) -> List[str]:
        """
        Discover article URLs using multiple strategies (T096 - US5).
        
        Strategies:
        1. Sitemap XML
        2. RSS feeds
        3. Heuristics (crawl homepage and detect article patterns)
        
        Args:
            domain: Domain name
            max_articles: Maximum number of articles to discover
            
        Returns:
            List of article URLs
        """
        # Detect domain redirect (e.g., .fr -> .com, .fr -> .ch)
        corrected_domain = await self._detect_domain_redirect(domain)
        if corrected_domain != domain:
            self.logger.info(
                "Using corrected domain",
                original=domain,
                corrected=corrected_domain,
            )
            domain = corrected_domain
        
        article_urls = []
        sitemap_count = 0
        rss_count = 0
        heuristic_count = 0
        
        # Strategy 1: Sitemap
        self.logger.info("Discovering articles via sitemap", domain=domain)
        try:
            sitemap_urls = await get_sitemap_urls(domain)
            self.logger.info(
                "Sitemap URLs retrieved",
                domain=domain,
                sitemap_urls_count=len(sitemap_urls),
            )
            # Filter for article/blog URLs
            for url in sitemap_urls:
                if len(article_urls) >= max_articles:
                    break
                
                # Exclude category pages and excluded extensions
                if self._is_category_page(url):
                    continue
                
                if self._has_excluded_extension(url):
                    continue
                
                # Normalize URL to use corrected domain
                normalized_url = self._normalize_url_to_domain(url, domain)
                
                # Check if URL matches article patterns
                if self._is_article_url(normalized_url):
                    article_urls.append(normalized_url)
                    sitemap_count += 1
            
            # Fallback: if no articles found via patterns, take first URLs from sitemap
            if sitemap_count == 0 and len(sitemap_urls) > 0:
                self.logger.info(
                    "No articles found via patterns, using fallback",
                    domain=domain,
                    sitemap_urls_available=len(sitemap_urls),
                )
                
                for url in sitemap_urls:
                    if len(article_urls) >= max_articles:
                        break
                    
                    # Exclude category pages and excluded extensions
                    if self._is_category_page(url):
                        continue
                    
                    if self._has_excluded_extension(url):
                        continue
                    
                    # Normalize URL to use corrected domain
                    normalized_url = self._normalize_url_to_domain(url, domain)
                    article_urls.append(normalized_url)
                    sitemap_count += 1
        except Exception as e:
            self.logger.warning("Sitemap discovery failed", domain=domain, error=str(e))
        
        # Strategy 2: RSS feeds
        if len(article_urls) < max_articles:
            self.logger.info("Discovering articles via RSS", domain=domain)
            rss_urls = await self._discover_rss_feeds(domain)
            self.logger.info(
                "RSS feeds discovered",
                domain=domain,
                rss_feeds_count=len(rss_urls),
            )
            for rss_url in rss_urls:
                if len(article_urls) >= max_articles:
                    break
                feed_urls = await self._parse_rss_feed(rss_url, domain)
                before_count = len(article_urls)
                # Add URLs but respect max_articles limit
                for feed_url in feed_urls:
                    if len(article_urls) >= max_articles:
                        break
                    if feed_url not in article_urls:
                        article_urls.append(feed_url)
                rss_count += len(article_urls) - before_count
        
        # Strategy 3: Heuristics (if still need more)
        if len(article_urls) < max_articles:
            self.logger.info("Discovering articles via heuristics", domain=domain)
            remaining = max_articles - len(article_urls)
            heuristic_urls = await self._discover_via_heuristics(domain, remaining)
            before_count = len(article_urls)
            # Add URLs but respect max_articles limit
            for heuristic_url in heuristic_urls:
                if len(article_urls) >= max_articles:
                    break
                if heuristic_url not in article_urls:
                    article_urls.append(heuristic_url)
            heuristic_count = len(article_urls) - before_count
        
        # Final limit check (safety net)
        if len(article_urls) > max_articles:
            original_count = len(article_urls)
            article_urls = article_urls[:max_articles]
            self.logger.warning(
                "Article URLs exceeded limit, truncated",
                domain=domain,
                original_count=original_count,
                limited_count=max_articles,
            )
        
        self.logger.info(
            "Article discovery complete",
            domain=domain,
            total_discovered=len(article_urls),
            from_sitemap=sitemap_count,
            from_rss=rss_count,
            from_heuristics=heuristic_count,
        )
        return article_urls

    async def _discover_rss_feeds(self, domain: str) -> List[str]:
        """
        Discover RSS feed URLs for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List of RSS feed URLs
        """
        rss_urls = []
        base_url = f"https://{domain}"
        
        # Common RSS feed locations
        common_paths = [
            "/feed",
            "/rss",
            "/rss.xml",
            "/feed.xml",
            "/blog/feed",
            "/blog/rss",
            "/atom.xml",
        ]
        
        for path in common_paths:
            feed_url = urljoin(base_url, path)
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.head(feed_url, follow_redirects=True)
                    if response.status_code == 200:
                        # Check content type
                        content_type = response.headers.get("content-type", "").lower()
                        if "xml" in content_type or "rss" in content_type or "atom" in content_type:
                            rss_urls.append(feed_url)
            except Exception:
                continue
        
        # Also check for RSS links in homepage
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(base_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    # Find RSS link tags
                    for link in soup.find_all("link", type=re.compile(r"application/(rss|atom)\+xml")):
                        href = link.get("href")
                        if href:
                            absolute_url = urljoin(base_url, href)
                            if absolute_url not in rss_urls:
                                rss_urls.append(absolute_url)
        except Exception as e:
            self.logger.debug("Failed to check homepage for RSS", domain=domain, error=str(e))
        
        return rss_urls

    async def _parse_rss_feed(self, feed_url: str, target_domain: str) -> List[str]:
        """
        Parse RSS feed and extract article URLs (with pagination support).
        
        Args:
            feed_url: RSS feed URL
            
        Returns:
            List of article URLs
        """
        all_urls = set()
        max_pages = 3  # Limiter à 3 pages
        
        for page in range(1, max_pages + 1):
            if page > 1:
                # Essayer différentes formes de pagination
                paged_urls = [
                    f"{feed_url}?paged={page}",
                    f"{feed_url}?page={page}",
                    f"{feed_url}/page/{page}/",
                ]
            else:
                paged_urls = [feed_url]
            
            found_urls = False
            for paged_url in paged_urls:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(paged_url)
                        if response.status_code != 200:
                            continue
                        
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
                        
                        if page_urls:
                            # Normalize URLs to use corrected domain
                            normalized_page_urls = [
                                self._normalize_url_to_domain(url, target_domain) for url in page_urls
                            ]
                            all_urls.update(normalized_page_urls)
                            found_urls = True
                            self.logger.debug(
                                "RSS page parsed",
                                feed_url=paged_url,
                                urls_found=len(page_urls),
                            )
                            break  # Succès, passer à la page suivante
                
                except Exception as e:
                    self.logger.debug("Failed to parse RSS page", feed_url=paged_url, error=str(e))
                    continue
            
            # Si aucune URL trouvée sur cette page, arrêter
            if not found_urls:
                break
        
        return list(all_urls)

    async def _discover_via_heuristics(
        self,
        domain: str,
        max_urls: int,
        max_depth: int = 2,
    ) -> List[str]:
        """
        Discover article URLs via heuristics with recursive navigation.
        
        Args:
            domain: Domain name
            max_urls: Maximum URLs to discover
            max_depth: Maximum navigation depth
            
        Returns:
            List of article URLs
        """
        base_url = f"https://{domain}"
        article_urls = set()
        visited = set()
        
        # Pages de blog communes à explorer (commencer par la homepage)
        blog_candidates = [
            base_url,  # Toujours crawler la homepage en premier
            f"{base_url}/blog/",
            f"{base_url}/actualites/",
            f"{base_url}/news/",
            f"{base_url}/articles/",
            f"{base_url}/ressources/",
            f"{base_url}/conseils/",
            f"{base_url}/guides/",
            f"{base_url}/publications/",
        ]
        
        async def crawl_page(url: str, depth: int = 0) -> None:
            """Crawl a page recursively to discover articles."""
            if depth > max_depth or url in visited or len(article_urls) >= max_urls:
                return
            
            visited.add(url)
            
            try:
                result = await crawl_page_async(url)
                if not result.get("success"):
                    self.logger.debug("Failed to crawl page", url=url, domain=domain, status_code=result.get("status_code"))
                    return
                
                html = result.get("html", "")
                soup = BeautifulSoup(html, "html.parser")
                
                # 1. Détecter les articles via balises <article>
                for article_tag in soup.find_all("article"):
                    if len(article_urls) >= max_urls:
                        break
                    link = article_tag.find("a", href=True)
                    if link:
                        href = link.get("href")
                        if href:
                            absolute_url = urljoin(base_url, href)
                            # Normalize URL (remove trailing slash, handle www)
                            absolute_url_normalized = absolute_url.rstrip("/")
                            base_url_normalized = base_url.rstrip("/")
                            
                            # Check if URL is from the same domain (handle www variations)
                            url_domain = urlparse(absolute_url_normalized).netloc.replace("www.", "")
                            base_domain = urlparse(base_url_normalized).netloc.replace("www.", "")
                            
                            if (
                                url_domain == base_domain
                                and not self._is_category_page(absolute_url_normalized)
                                and not self._has_excluded_extension(absolute_url_normalized)
                            ):
                                # Si c'est dans une balise <article>, c'est probablement un article
                                article_urls.add(absolute_url_normalized)
                
                # 1b. Détecter les articles via sélecteurs CSS communs (cards, post items, etc.)
                # Ces sélecteurs sont souvent utilisés pour les listes d'articles
                article_containers = soup.select(
                    "article a[href], "
                    ".post a[href], .article a[href], .blog-post a[href], "
                    ".news-item a[href], .actualite a[href], "
                    ".card a[href], .entry a[href], "
                    "[class*='post'] a[href], [class*='article'] a[href], "
                    "[class*='news'] a[href], [class*='actualite'] a[href]"
                )
                for link in article_containers:
                    if len(article_urls) >= max_urls:
                        break
                    href = link.get("href")
                    if not href:
                        continue
                    absolute_url = urljoin(base_url, href)
                    absolute_url_normalized = absolute_url.rstrip("/")
                    base_url_normalized = base_url.rstrip("/")
                    url_domain = urlparse(absolute_url_normalized).netloc.replace("www.", "")
                    base_domain = urlparse(base_url_normalized).netloc.replace("www.", "")
                    
                    if (
                        url_domain == base_domain
                        and not self._is_category_page(absolute_url_normalized)
                        and not self._has_excluded_extension(absolute_url_normalized)
                    ):
                        article_urls.add(absolute_url_normalized)
                
                # 2. Détecter les liens d'articles
                for link in soup.find_all("a", href=True):
                    if len(article_urls) >= max_urls:
                        break
                    
                    href = link.get("href")
                    if not href:
                        continue
                    
                    absolute_url = urljoin(base_url, href)
                    
                    # Normalize URL (remove trailing slash, handle www)
                    absolute_url_normalized = absolute_url.rstrip("/")
                    base_url_normalized = base_url.rstrip("/")
                    
                    # Vérifier que l'URL est du même domaine (handle www variations)
                    url_domain = urlparse(absolute_url_normalized).netloc.replace("www.", "")
                    base_domain = urlparse(base_url_normalized).netloc.replace("www.", "")
                    
                    if url_domain != base_domain:
                        continue
                    
                    # Exclure les extensions et catégories
                    if self._has_excluded_extension(absolute_url_normalized):
                        continue
                    
                    # Si c'est une page de catégorie, l'explorer récursivement
                    if self._is_category_page(absolute_url_normalized) and absolute_url_normalized not in visited and depth < max_depth:
                        await crawl_page(absolute_url_normalized, depth + 1)
                        continue
                    
                    # Si c'est un article (via patterns), l'ajouter
                    if self._is_article_url(absolute_url_normalized):
                        article_urls.add(absolute_url_normalized)
                    # Sinon, détecter via le contenu du lien (texte, classes, etc.)
                    else:
                        # Vérifier si le lien semble pointer vers un article
                        # en analysant le texte du lien et les classes
                        link_text = link.get_text(strip=True).lower()
                        link_classes = " ".join(link.get("class", [])).lower()
                        
                        # Vérifier aussi les classes du parent (souvent les containers d'articles)
                        parent = link.parent
                        parent_classes = " ".join(parent.get("class", []) if parent and parent.get("class") else []).lower()
                        
                        # Indicateurs qu'un lien pourrait être un article
                        article_indicators = [
                            "article", "blog", "post", "news", "actualite", "actualité",
                            "read more", "lire la suite", "en savoir plus", "découvrir",
                            "suite", "lire", "voir plus", "consulter",
                        ]
                        
                        # Si le lien a des indicateurs d'article, on l'ajoute
                        # OU si le parent a des classes d'article (card, post-item, etc.)
                        has_article_indicator = any(
                            indicator in link_text or 
                            indicator in link_classes or 
                            indicator in parent_classes 
                            for indicator in article_indicators
                        )
                        
                        # Vérifier aussi si l'URL contient un slug qui ressemble à un article
                        # (pas juste une page de catégorie)
                        url_path = urlparse(absolute_url_normalized).path.lower()
                        is_likely_article = (
                            len(url_path.split("/")) >= 3 and  # Au moins /category/slug/
                            not url_path.endswith("/") and  # Pas une page de catégorie
                            "/" in url_path.strip("/")  # A un slug
                        )
                        
                        if (has_article_indicator or is_likely_article) and not self._is_category_page(absolute_url_normalized):
                            article_urls.add(absolute_url_normalized)
                            self.logger.debug(
                                "Article detected via link indicators",
                                url=absolute_url_normalized,
                                link_text=link_text[:50],
                                domain=domain,
                            )
            
            except Exception as e:
                self.logger.debug("Heuristic crawl failed", url=url, error=str(e))
        
        # Explorer les pages candidates
        for candidate_url in blog_candidates:
            if len(article_urls) >= max_urls:
                break
            self.logger.debug("Crawling candidate page", url=candidate_url, domain=domain)
            await crawl_page(candidate_url)
        
        self.logger.info(
            "Heuristic discovery complete",
            domain=domain,
            total_found=len(article_urls),
            pages_crawled=len(visited),
        )
        
        return list(article_urls)[:max_urls]

    def _is_article_url(self, url: str) -> bool:
        """
        Check if URL matches article patterns.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL matches article patterns
        """
        url_lower = url.lower()
        return any(re.search(pattern, url_lower, re.IGNORECASE) for pattern in self.ARTICLE_URL_PATTERNS)

    def _is_category_page(self, url: str) -> bool:
        """
        Detect category, tag, or pagination pages.
        
        Args:
            url: URL to check
            
        Returns:
            True if it's a category/pagination page
        """
        url_lower = url.lower()
        category_patterns = [
            r'/(category|tag|news|actualites?|blog)(/|$)',
            r'/page/\d+/?$',
            r'/\?paged=\d+',
            r'/\?page=\d+',
        ]
        return any(re.search(pattern, url_lower) for pattern in category_patterns)

    def _has_excluded_extension(self, url: str) -> bool:
        """
        Check if URL has an excluded extension.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL has an excluded extension
        """
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in self.EXCLUDED_EXTENSIONS)

    def _is_job_posting(self, article_data: Dict[str, Any]) -> bool:
        """
        Detect if article is a job posting/offer.
        
        Args:
            article_data: Article data dictionary with title and content
            
        Returns:
            True if article appears to be a job posting
        """
        title = article_data.get("title", "").lower()
        content = article_data.get("content", "").lower()
        combined_text = f"{title} {content[:500]}"  # Analyse les 500 premiers caractères du contenu
        
        # Compter les occurrences de patterns d'emploi
        matches = sum(1 for pattern in self.JOB_POSTING_PATTERNS if pattern in combined_text)
        
        # Si 2+ patterns trouvés, c'est probablement une offre d'emploi
        if matches >= 2:
            return True
        
        # Vérifier aussi si le titre contient des patterns forts
        strong_patterns = [
            "offre d'emploi", "offres d'emploi", "recrutement", "recrute",
            "job offer", "we are hiring", "join our team", "apply now"
        ]
        if any(pattern in title for pattern in strong_patterns):
            return True
        
        return False

    def filter_article(
        self,
        article_data: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Filter article based on criteria (T098 - US5).
        
        Criteria:
        - Minimum word count (configurable, default: 150 words)
        - Maximum age (configurable, default: 1095 days = 3 years, None = no limit)
        
        Args:
            article_data: Article data dictionary
            
        Returns:
            Tuple (is_valid, reason_if_invalid)
        """
        # Check word count
        word_count = article_data.get("word_count", 0)
        if word_count < self.min_word_count:
            return False, f"Word count too low: {word_count} < {self.min_word_count}"
        
        # Check age (only if max_age_days is set)
        if self.max_age_days is not None:
            published_date = article_data.get("published_date")
            if published_date:
                if isinstance(published_date, str):
                    try:
                        published_date = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        # If we can't parse, allow it (better to include than exclude)
                        return True, None
                elif not isinstance(published_date, datetime):
                    return True, None
                
                age_days = (datetime.now(timezone.utc) - published_date.replace(tzinfo=timezone.utc)).days
                if age_days > self.max_age_days:
                    return False, f"Article too old: {age_days} days > {self.max_age_days} days"
        
        # Check if article is a job posting
        if self._is_job_posting(article_data):
            return False, "Article is a job posting"
        
        return True, None

    async def scrape_and_save_articles(
        self,
        db_session: AsyncSession,
        domain: str,
        article_urls: List[str],
        is_client_site: bool = False,
        site_profile_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Scrape articles and save to database with deduplication (T099 - US5).
        
        Args:
            db_session: Database session
            domain: Domain name
            article_urls: List of article URLs to scrape
            is_client_site: Whether this is a client site (uses client_articles collection)
            site_profile_id: Site profile ID (required if is_client_site=True)
            
        Returns:
            Dictionary with scraped articles and statistics
        """
        # Get site_profile_id if client site and not provided
        if is_client_site and not site_profile_id:
            site_profile = await get_site_profile_by_domain(db_session, domain)
            if not site_profile:
                raise ValueError(f"Site profile not found for domain: {domain}. Please run editorial analysis first.")
            site_profile_id = site_profile.id
        scraped_articles = []
        stats = {
            "total_urls": len(article_urls),
            "already_exists": 0,
            "crawl_failed": 0,
            "filtered": 0,
            "filtered_reasons": {},
            "saved": 0,
            "errors": 0,
        }
        
        self.logger.info(
            "Starting article scraping",
            domain=domain,
            total_urls=len(article_urls),
        )
        
        for url in article_urls:
            try:
                # Check for duplicates by hash
                url_hash = generate_url_hash(url)
                if is_client_site:
                    existing = await get_client_article_by_hash_crud(db_session, url_hash)
                else:
                    existing = await get_competitor_article_by_hash(db_session, url_hash)
                if existing:
                    stats["already_exists"] += 1
                    continue
                
                # Crawl and extract article
                crawl_result = await crawl_page_async(url)
                if not crawl_result.get("success"):
                    stats["crawl_failed"] += 1
                    self.logger.warning(
                        "Failed to crawl article",
                        domain=domain,
                        url=url,
                        status_code=crawl_result.get("status_code"),
                        error=crawl_result.get("error"),
                    )
                    continue
                
                # Extract article data
                article_data = extract_article_from_html(crawl_result.get("html", ""), url)
                article_data["url"] = url
                article_data["url_hash"] = url_hash
                
                # Filter article
                is_valid, reason = self.filter_article(article_data)
                if not is_valid:
                    stats["filtered"] += 1
                    # Track filtering reasons
                    reason_key = reason.split(":")[0] if ":" in reason else reason
                    stats["filtered_reasons"][reason_key] = stats["filtered_reasons"].get(reason_key, 0) + 1
                    self.logger.info(
                        "Article filtered",
                        domain=domain,
                        url=url,
                        reason=reason,
                        word_count=article_data.get("word_count", 0),
                    )
                    continue
                
                # Save to database
                if is_client_site:
                    article = await create_client_article(
                        db_session,
                        site_profile_id=site_profile_id,
                        url=url,
                        url_hash=url_hash,
                        title=article_data.get("title", ""),
                        content_text=article_data.get("content", ""),
                        author=article_data.get("author"),
                        published_date=article_data.get("published_date"),
                        content_html=article_data.get("content_html"),
                        word_count=article_data.get("word_count", 0),
                        article_metadata={
                            "images": article_data.get("images", []),
                            "description": article_data.get("description", ""),
                        },
                    )
                else:
                    article = await create_competitor_article(
                        db_session,
                        domain=domain,
                        url=url,
                        url_hash=url_hash,
                        title=article_data.get("title", ""),
                        content_text=article_data.get("content", ""),
                        author=article_data.get("author"),
                        published_date=article_data.get("published_date"),
                        content_html=article_data.get("content_html"),
                        word_count=article_data.get("word_count", 0),
                        article_metadata={
                            "images": article_data.get("images", []),
                            "description": article_data.get("description", ""),
                        },
                    )
                
                # Index in Qdrant (T111 - US6)
                try:
                    # Use client collection if this is a client site, otherwise competitor collection
                    if is_client_site:
                        from python_scripts.vectorstore.qdrant_client import get_client_collection_name
                        collection_name = get_client_collection_name(domain)
                    else:
                        # Note: client_domain not available in this context, using default collection
                        # For trend pipeline, collection name is set via ClusteringConfig
                        collection_name = COLLECTION_NAME
                    qdrant_point_id = qdrant_client.index_article(
                        article_id=article.id,
                        domain=domain,
                        title=article_data.get("title", ""),
                        content_text=article_data.get("content", ""),
                        url=url,
                        url_hash=url_hash,
                        published_date=article_data.get("published_date"),
                        author=article_data.get("author"),
                        keywords=article_data.get("keywords"),
                        topic_id=None,  # Will be set later by topic modeling
                        check_duplicate=True,
                        collection_name=collection_name,
                    )
                    
                    # Update article with Qdrant point ID (T114 - US6)
                    if qdrant_point_id:
                        if is_client_site:
                            await update_client_qdrant_point_id(db_session, article, qdrant_point_id)
                        else:
                            await update_qdrant_point_id(db_session, article, qdrant_point_id)
                        self.logger.debug(
                            "Article indexed in Qdrant",
                            article_id=article.id,
                            domain=domain,
                            is_client_site=is_client_site,
                            qdrant_point_id=str(qdrant_point_id),
                        )
                    else:
                        self.logger.warning(
                            "Article not indexed (duplicate or error)",
                            article_id=article.id,
                            domain=domain,
                        )
                except Exception as e:
                    # Don't fail scraping if indexing fails
                    self.logger.error(
                        "Failed to index article in Qdrant",
                        article_id=article.id,
                        domain=domain,
                        error=str(e),
                    )
                
                scraped_articles.append({
                    "id": article.id,
                    "url": article.url,
                    "title": article.title,
                    "word_count": article.word_count,
                })
                stats["saved"] += 1
                
            except Exception as e:
                stats["errors"] += 1
                self.logger.error(
                    "Error scraping article",
                    domain=domain,
                    url=url,
                    error=str(e),
                )
                continue
        
        # Log summary statistics
        self.logger.info(
            "Article scraping statistics",
            domain=domain,
            total_urls=stats["total_urls"],
            already_exists=stats["already_exists"],
            crawl_failed=stats["crawl_failed"],
            filtered=stats["filtered"],
            filtered_reasons=stats["filtered_reasons"],
            saved=stats["saved"],
            errors=stats["errors"],
        )
        
        return {
            "articles": scraped_articles,
            "statistics": stats,
        }

    async def execute(
        self,
        execution_id: UUID,
        input_data: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute scraping workflow.
        
        Args:
            execution_id: Unique execution ID
            input_data: Input data containing domains and max_articles_per_domain
            **kwargs: Additional arguments (db_session required, is_client_site optional)
            
        Returns:
            Output data with scraped articles
        """
        db_session: AsyncSession = kwargs.get("db_session")
        if not db_session:
            raise ValueError("db_session is required")
        
        is_client_site = kwargs.get("is_client_site", False)
        site_profile_id = kwargs.get("site_profile_id", None)
        domains = input_data.get("domains", [])
        max_articles_per_domain = input_data.get("max_articles_per_domain", 500)
        
        self.logger.info(
            "Starting scraping workflow",
            execution_id=str(execution_id),
            domains=domains,
            max_articles_per_domain=max_articles_per_domain,
        )
        
        all_scraped_articles = {}
        global_stats = {
            "total_domains": len(domains),
            "domains_with_articles_discovered": 0,
            "domains_without_articles": 0,
            "domains_with_errors": 0,
            "total_articles_discovered": 0,
            "total_articles_saved": 0,
            "total_articles_already_exists": 0,
            "total_articles_crawl_failed": 0,
            "total_articles_filtered": 0,
            "total_articles_errors": 0,
        }
        
        for domain in domains:
            try:
                # Discover article URLs
                article_urls = await self.discover_article_urls(domain, max_articles_per_domain)
                
                if not article_urls:
                    self.logger.warning("No articles discovered", domain=domain)
                    all_scraped_articles[domain] = []
                    global_stats["domains_without_articles"] += 1
                    continue
                
                global_stats["domains_with_articles_discovered"] += 1
                global_stats["total_articles_discovered"] += len(article_urls)
                
                # Scrape and save articles
                result = await self.scrape_and_save_articles(
                    db_session,
                    domain,
                    article_urls,
                    is_client_site=is_client_site,
                    site_profile_id=site_profile_id,
                )
                
                # Extract articles and statistics
                scraped = result.get("articles", [])
                stats = result.get("statistics", {})
                
                all_scraped_articles[domain] = scraped
                
                # Update global statistics
                global_stats["total_articles_saved"] += stats.get("saved", 0)
                global_stats["total_articles_already_exists"] += stats.get("already_exists", 0)
                global_stats["total_articles_crawl_failed"] += stats.get("crawl_failed", 0)
                global_stats["total_articles_filtered"] += stats.get("filtered", 0)
                global_stats["total_articles_errors"] += stats.get("errors", 0)
                
                self.logger.info(
                    "Domain scraping complete",
                    domain=domain,
                    articles_discovered=len(article_urls),
                    articles_saved=len(scraped),
                    statistics=stats,
                )
                
            except Exception as e:
                self.logger.error("Error scraping domain", domain=domain, error=str(e))
                all_scraped_articles[domain] = []
                global_stats["domains_with_errors"] += 1
        
        total_scraped = sum(len(articles) for articles in all_scraped_articles.values())
        
        # Log global summary
        self.logger.info(
            "Scraping workflow summary",
            execution_id=str(execution_id),
            total_domains=global_stats["total_domains"],
            domains_with_articles=global_stats["domains_with_articles_discovered"],
            domains_without_articles=global_stats["domains_without_articles"],
            domains_with_errors=global_stats["domains_with_errors"],
            total_articles_discovered=global_stats["total_articles_discovered"],
            total_articles_saved=global_stats["total_articles_saved"],
            total_articles_already_exists=global_stats["total_articles_already_exists"],
            total_articles_crawl_failed=global_stats["total_articles_crawl_failed"],
            total_articles_filtered=global_stats["total_articles_filtered"],
            total_articles_errors=global_stats["total_articles_errors"],
        )
        
        return {
            "domains": domains,
            "articles_by_domain": all_scraped_articles,
            "total_articles_scraped": total_scraped,
            "statistics": global_stats,
        }

