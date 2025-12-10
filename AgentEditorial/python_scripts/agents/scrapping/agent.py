"""Enhanced scraping agent with 4-phase discovery pipeline."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.base_agent import BaseAgent
from python_scripts.database.crud_articles import (
    create_competitor_article,
    get_competitor_article_by_hash,
    update_qdrant_point_id,
)
from python_scripts.database.crud_client_articles import (
    create_client_article,
    get_client_article_by_hash as get_client_article_by_hash_crud,
    update_qdrant_point_id as update_client_qdrant_point_id,
)
from python_scripts.database.crud_error_logs import log_error_from_exception
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.ingestion.crawl_pages import crawl_page_async, generate_url_hash
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.qdrant_client import (
    COLLECTION_NAME,
    get_client_collection_name,
    get_competitor_collection_name,
    qdrant_client,
)

from .crud import (
    create_site_discovery_profile,
    get_site_discovery_profile,
    save_discovery_log,
    save_url_discovery_score,
    update_site_discovery_profile,
    update_url_scrape_status,
    update_url_validation,
)
from .discovery import ArticleDiscovery
from .extractor import AdaptiveExtractor
from .profiler import SiteProfiler
from .scorer import ArticleScorer

logger = get_logger(__name__)


def _convert_published_time_to_date(published_time: Any) -> Optional[date]:
    """
    Convert published_time (datetime, str, or None) to date object.
    
    Args:
        published_time: Can be datetime, ISO string, or None
        
    Returns:
        date object or None
    """
    if published_time is None:
        return None
    
    # If it's already a date object
    if isinstance(published_time, date):
        return published_time
    
    # If it's a datetime object, extract the date
    if isinstance(published_time, datetime):
        return published_time.date()
    
    # If it's a string, try to parse it
    if isinstance(published_time, str):
        try:
            # Try ISO format first
            dt = datetime.fromisoformat(published_time.replace("Z", "+00:00"))
            return dt.date()
        except (ValueError, AttributeError):
            # Try other formats
            try:
                dt = datetime.strptime(published_time, "%Y-%m-%d")
                return dt.date()
            except (ValueError, AttributeError):
                logger.debug("Failed to parse published_time", published_time=published_time)
                return None
    
    return None


class EnhancedScrapingAgent(BaseAgent):
    """Enhanced scraping agent with 4-phase discovery pipeline."""

    def __init__(
        self,
        min_word_count: int = 150,
        max_age_days: Optional[int] = 1095,
    ) -> None:
        """Initialize the enhanced scraping agent."""
        super().__init__("scraping_enhanced")
        self.min_word_count = min_word_count
        self.max_age_days = max_age_days

        # Initialize components
        self.profiler = SiteProfiler()
        self.discovery = ArticleDiscovery()
        self.scorer = ArticleScorer()
        self.extractor = AdaptiveExtractor()

    async def discover_and_scrape_articles(
        self,
        db_session: AsyncSession,
        domain: str,
        max_articles: int = 100,
        is_client_site: bool = False,
        site_profile_id: Optional[int] = None,
        force_reprofile: bool = False,
        execution_id: Optional[UUID] = None,
        client_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete pipeline: discover and scrape articles.

        Args:
            db_session: Database session
            domain: Domain name
            max_articles: Maximum articles to scrape
            is_client_site: Whether this is a client site
            site_profile_id: Site profile ID (required if is_client_site=True)
            force_reprofile: Force reprofiling even if profile exists
            execution_id: Execution ID for logging
            client_domain: Client domain name (used to generate collection name for competitors)

        Returns:
            Dictionary with scraped articles and statistics
        """
        start_time = datetime.now(timezone.utc)
        stats = {
            "discovered": 0,
            "scraped": 0,
            "valid": 0,
            "sources_used": [],
        }

        try:
            # PHASE 0: Load or create profile
            profile = await get_site_discovery_profile(db_session, domain)

            should_reprofile = (
                force_reprofile
                or profile is None
                or (profile.last_profiled_at is None)
                or (
                    (datetime.now(timezone.utc) - profile.last_profiled_at).days > 7
                )
            )

            if should_reprofile:
                logger.info("Profilage du site", domain=domain)
                profile_data = await self.profiler.profile_site(domain)
                if profile:
                    # Update existing
                    await update_site_discovery_profile(
                        db_session,
                        domain,
                        profile_data,
                    )
                    # Reload
                    profile = await get_site_discovery_profile(db_session, domain)
                else:
                    # Create new
                    profile = await create_site_discovery_profile(
                        db_session,
                        domain,
                        profile_data,
                    )

            # Convert profile to dict for easier access
            profile_dict = {
                "cms_detected": profile.cms_detected if profile else None,
                "has_rest_api": profile.has_rest_api if profile else False,
                "api_endpoints": profile.api_endpoints if profile else {},
                "sitemap_urls": profile.sitemap_urls if profile else [],
                "rss_feeds": profile.rss_feeds if profile else [],
                "blog_listing_pages": profile.blog_listing_pages if profile else [],
                "url_patterns": profile.url_patterns if profile else {},
                "content_selector": profile.content_selector if profile else None,
                "title_selector": profile.title_selector if profile else None,
                "date_selector": profile.date_selector if profile else None,
                "author_selector": profile.author_selector if profile else None,
            }

            # PHASE 1: Multi-source discovery
            discovered_urls = []

            # 1a. API REST (if available)
            if profile_dict.get("has_rest_api") and profile_dict.get("api_endpoints"):
                api_articles = await self.discovery.discover_via_api(
                    domain,
                    profile_dict["api_endpoints"],
                    max_articles,
                )
                for article in api_articles:
                    discovered_urls.append({
                        "url": article["url"],
                        "source": "api",
                        "title_hint": article.get("title"),
                        "date_hint": article.get("date"),
                    })
                stats["sources_used"].append("api")
                logger.info("API discovery", domain=domain, count=len(api_articles))

            # 1b. RSS (complement if needed)
            if len(discovered_urls) < max_articles and profile_dict.get("rss_feeds"):
                remaining = max_articles - len(discovered_urls)
                rss_urls = await self.discovery.discover_via_rss(
                    profile_dict["rss_feeds"],
                    remaining,
                )
                for url in rss_urls:
                    if url not in [u["url"] for u in discovered_urls]:
                        discovered_urls.append({"url": url, "source": "rss"})
                stats["sources_used"].append("rss")
                logger.info("RSS discovery", domain=domain, count=len(rss_urls))

            # 1c. Sitemap (complement if needed)
            if len(discovered_urls) < max_articles and profile_dict.get("sitemap_urls"):
                remaining = max_articles - len(discovered_urls)
                sitemap_urls = await self.discovery.discover_via_sitemap(
                    profile_dict["sitemap_urls"],
                    remaining,
                )
                for url in sitemap_urls:
                    if url not in [u["url"] for u in discovered_urls]:
                        discovered_urls.append({"url": url, "source": "sitemap"})
                stats["sources_used"].append("sitemap")
                logger.info("Sitemap discovery", domain=domain, count=len(sitemap_urls))

            # 1d. Heuristics (last resort)
            if len(discovered_urls) < max_articles:
                remaining = max_articles - len(discovered_urls)
                heuristic_urls = await self.discovery.discover_via_heuristics(
                    domain,
                    profile_dict,
                    remaining,
                )
                for url in heuristic_urls:
                    if url not in [u["url"] for u in discovered_urls]:
                        discovered_urls.append({"url": url, "source": "heuristic"})
                stats["sources_used"].append("heuristic")
                logger.info("Heuristic discovery", domain=domain, count=len(heuristic_urls))

            stats["discovered"] = len(discovered_urls)

            # PHASE 2: Scoring
            scored_urls = []
            for url_data in discovered_urls:
                score, breakdown = self.scorer.calculate_article_score(url_data)
                url_hash = generate_url_hash(url_data["url"])

                scored_urls.append({
                    **url_data,
                    "initial_score": score,
                    "score_breakdown": breakdown,
                    "url_hash": url_hash,
                })

                # Save score to database
                await save_url_discovery_score(
                    db_session,
                    domain,
                    url_data["url"],
                    url_hash,
                    url_data["source"],
                    score,
                    breakdown,
                    title_hint=url_data.get("title_hint"),
                )

            # Sort and select
            scored_urls.sort(key=lambda x: x["initial_score"], reverse=True)
            urls_to_scrape = self.scorer.select_urls_to_scrape(scored_urls, max_articles)

            # Log rejected URLs (score too low)
            rejected_urls = [
                url_data for url_data in scored_urls
                if url_data["url"] not in urls_to_scrape
            ]
            if rejected_urls:
                logger.debug(
                    "URLs rejected by scoring",
                    domain=domain,
                    rejected_count=len(rejected_urls),
                    min_rejected_score=min(u["initial_score"] for u in rejected_urls) if rejected_urls else 0,
                    max_rejected_score=max(u["initial_score"] for u in rejected_urls) if rejected_urls else 0,
                    sample_rejected=rejected_urls[:5],  # Log first 5
                )

            logger.info(
                "Scoring complete",
                domain=domain,
                total=len(scored_urls),
                selected=len(urls_to_scrape),
                rejected=len(rejected_urls),
                min_score=scored_urls[-1]["initial_score"] if scored_urls else 0,
                max_score=scored_urls[0]["initial_score"] if scored_urls else 0,
            )

            # PHASE 3: Extraction
            scraped_articles = []
            extraction_results = []

            for url_data in scored_urls:
                if url_data["url"] not in urls_to_scrape:
                    continue

                url = url_data["url"]
                url_hash = url_data["url_hash"]

                try:
                    # Check for duplicates
                    if is_client_site:
                        existing = await get_client_article_by_hash_crud(db_session, url_hash)
                    else:
                        existing = await get_competitor_article_by_hash(db_session, url_hash)

                    if existing:
                        stats["scraped"] += 1
                        continue

                    # Crawl
                    crawl_result = await crawl_page_async(url)
                    if not crawl_result.get("success"):
                        await update_url_scrape_status(
                            db_session,
                            domain,
                            url_hash,
                            "failed",
                            crawl_result.get("error"),
                        )
                        continue

                    stats["scraped"] += 1
                    await update_url_scrape_status(
                        db_session,
                        domain,
                        url_hash,
                        "success",
                    )

                    # Extract adaptively
                    article = await self.extractor.extract_article_adaptive(
                        crawl_result.get("html", ""),
                        url,
                        profile_dict,
                    )

                    # Validate
                    is_valid, reason = self.extractor.validate_article(
                        article,
                        self.min_word_count,
                    )

                    extraction_results.append({
                        **article,
                        "_content_selector_used": article.get("_content_selector_used"),
                        "_title_selector_used": article.get("_title_selector_used"),
                        "_date_selector_used": article.get("_date_selector_used"),
                    })

                    # Log detailed rejection reasons
                    if not is_valid:
                        logger.debug(
                            "Article validation failed",
                            domain=domain,
                            url=url,
                            reason=reason,
                            word_count=article.get("word_count", 0),
                            has_title=bool(article.get("title")),
                            has_content=bool(article.get("content")),
                            min_word_count=self.min_word_count,
                        )

                    if is_valid:
                        # Get published_time (datetime) and convert to date for database
                        published_time = article.get("published_time")
                        published_date = _convert_published_time_to_date(published_time)
                        
                        # Save to database
                        if is_client_site:
                            if not site_profile_id:
                                site_profile = await get_site_profile_by_domain(
                                    db_session,
                                    domain,
                                )
                                if not site_profile:
                                    raise ValueError(
                                        f"Site profile not found for domain: {domain}"
                                    )
                                site_profile_id = site_profile.id

                            saved_article = await create_client_article(
                                db_session,
                                site_profile_id=site_profile_id,
                                url=url,
                                url_hash=url_hash,
                                title=article.get("title", ""),
                                content_text=article.get("content", ""),
                                author=article.get("author"),
                                published_date=published_date,
                                content_html=article.get("content_html"),
                                word_count=article.get("word_count", 0),
                                article_metadata={
                                    "description": article.get("description", ""),
                                },
                            )
                        else:
                            saved_article = await create_competitor_article(
                                db_session,
                                domain=domain,
                                url=url,
                                url_hash=url_hash,
                                title=article.get("title", ""),
                                content_text=article.get("content", ""),
                                author=article.get("author"),
                                published_date=published_date,
                                content_html=article.get("content_html"),
                                word_count=article.get("word_count", 0),
                                article_metadata={
                                    "description": article.get("description", ""),
                                },
                            )

                        # Index in Qdrant
                        try:
                            if is_client_site:
                                collection_name = get_client_collection_name(domain)
                            else:
                                # Use client_domain to generate collection name if available
                                if client_domain:
                                    collection_name = get_competitor_collection_name(client_domain)
                                else:
                                    # Fallback to default collection name
                                    collection_name = COLLECTION_NAME
                            # Convert published_time to datetime if it's not already
                            published_datetime = None
                            if published_time:
                                if isinstance(published_time, datetime):
                                    published_datetime = published_time
                                elif isinstance(published_time, str):
                                    try:
                                        published_datetime = datetime.fromisoformat(
                                            published_time.replace("Z", "+00:00")
                                        )
                                    except (ValueError, AttributeError):
                                        pass
                                elif isinstance(published_time, date):
                                    # Convert date to datetime at midnight UTC
                                    published_datetime = datetime.combine(
                                        published_time, datetime.min.time()
                                    ).replace(tzinfo=timezone.utc)
                            
                            qdrant_point_id = qdrant_client.index_article(
                                article_id=saved_article.id,
                                domain=domain,
                                title=article.get("title", ""),
                                content_text=article.get("content", ""),
                                url=url,
                                url_hash=url_hash,
                                published_date=published_datetime,
                                author=article.get("author"),
                                keywords=None,
                                topic_id=None,
                                check_duplicate=True,
                                collection_name=collection_name,
                            )

                            if qdrant_point_id:
                                if is_client_site:
                                    await update_client_qdrant_point_id(
                                        db_session,
                                        saved_article,
                                        qdrant_point_id,
                                    )
                                else:
                                    await update_qdrant_point_id(
                                        db_session,
                                        saved_article,
                                        qdrant_point_id,
                                    )
                        except Exception as e:
                            logger.error("Qdrant indexing failed", error=str(e))
                            # Log error to error_logs table
                            try:
                                await log_error_from_exception(
                                    db_session=db_session,
                                    exception=e,
                                    component="qdrant",
                                    context={
                                        "article_id": saved_article.id,
                                        "domain": domain,
                                        "url": url,
                                        "collection": collection_name,
                                        "method": "index_article",
                                    },
                                    severity="error",
                                    execution_id=execution_id,
                                    domain=domain,
                                    agent_name="enhanced_scraping",
                                )
                            except Exception as log_err:
                                logger.error("Failed to log error to database", error=str(log_err))

                        scraped_articles.append({
                            "id": saved_article.id,
                            "url": saved_article.url,
                            "title": saved_article.title,
                            "word_count": saved_article.word_count,
                        })
                        stats["valid"] += 1

                        await update_url_validation(
                            db_session,
                            domain,
                            url_hash,
                            True,
                            None,
                            url_data["initial_score"],
                        )
                    else:
                        await update_url_validation(
                            db_session,
                            domain,
                            url_hash,
                            False,
                            reason,
                            url_data["initial_score"],
                        )

                except Exception as e:
                    logger.error("Error scraping article", url=url, error=str(e))
                    # Log error to error_logs table
                    try:
                        await log_error_from_exception(
                            db_session=db_session,
                            exception=e,
                            component="scraping",
                            context={
                                "url": url,
                                "url_hash": url_hash,
                                "domain": domain,
                                "method": "extract_article_adaptive",
                            },
                            severity="error",
                            execution_id=execution_id,
                            domain=domain,
                            agent_name="enhanced_scraping",
                        )
                    except Exception as log_err:
                        logger.error("Failed to log error to database", error=str(log_err))
                    
                    await update_url_scrape_status(
                        db_session,
                        domain,
                        url_hash,
                        "error",
                        str(e),
                    )
                    continue

            # FEEDBACK: Update profile with results
            if profile and extraction_results:
                valid_count = stats["valid"]
                total_scraped = stats["scraped"]
                success_rate = valid_count / total_scraped if total_scraped > 0 else 0

                # Analyze selectors
                from collections import Counter

                content_selectors = Counter()
                title_selectors = Counter()
                date_selectors = Counter()

                total_word_count = 0
                for result in extraction_results:
                    if result.get("word_count", 0) >= self.min_word_count:
                        total_word_count += result["word_count"]
                        if result.get("_content_selector_used"):
                            content_selectors[result["_content_selector_used"]] += 1
                        if result.get("_title_selector_used"):
                            title_selectors[result["_title_selector_used"]] += 1
                        if result.get("_date_selector_used"):
                            date_selectors[result["_date_selector_used"]] += 1

                update_data = {
                    "total_urls_discovered": stats["discovered"],
                    "total_articles_valid": valid_count,
                    "success_rate": success_rate,
                    "last_crawled_at": datetime.now(timezone.utc),
                }

                if content_selectors:
                    update_data["content_selector"] = content_selectors.most_common(1)[0][0]
                if title_selectors:
                    update_data["title_selector"] = title_selectors.most_common(1)[0][0]
                if date_selectors:
                    update_data["date_selector"] = date_selectors.most_common(1)[0][0]

                if valid_count > 0:
                    update_data["avg_article_word_count"] = total_word_count / valid_count

                await update_site_discovery_profile(db_session, domain, update_data)

            # Log final statistics
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            await save_discovery_log(
                db_session,
                domain,
                "discover_and_scrape",
                "success" if stats["valid"] > 0 else "partial",
                phase="complete",
                urls_found=stats["discovered"],
                urls_scraped=stats["scraped"],
                urls_valid=stats["valid"],
                sources_used=stats["sources_used"],
                duration_seconds=duration,
            )

            logger.info(
                "Scraping complete",
                domain=domain,
                discovered=stats["discovered"],
                scraped=stats["scraped"],
                valid=stats["valid"],
                duration=duration,
            )

            return {
                "domain": domain,
                "articles": scraped_articles,
                "statistics": stats,
            }

        except Exception as e:
            logger.error("Error in discover_and_scrape_articles", domain=domain, error=str(e))
            # Log error to error_logs table
            try:
                await log_error_from_exception(
                    db_session=db_session,
                    exception=e,
                    component="scraping",
                    context={
                        "domain": domain,
                        "method": "discover_and_scrape_articles",
                        "max_articles": max_articles,
                        "is_client_site": is_client_site,
                    },
                    severity="error",
                    execution_id=execution_id,
                    domain=domain,
                    agent_name="enhanced_scraping",
                )
            except Exception as log_err:
                logger.error("Failed to log error to database", error=str(log_err))
            raise

    async def execute(
        self,
        execution_id: UUID,
        input_data: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute enhanced scraping workflow.

        Args:
            execution_id: Unique execution ID
            input_data: Input data containing domains and max_articles_per_domain
            **kwargs: Additional arguments (db_session required)

        Returns:
            Output data with scraped articles
        """
        db_session: AsyncSession = kwargs.get("db_session")
        if not db_session:
            raise ValueError("db_session is required")

        is_client_site = kwargs.get("is_client_site", False)
        site_profile_id = kwargs.get("site_profile_id", None)
        domains = input_data.get("domains", [])
        max_articles_per_domain = input_data.get("max_articles_per_domain", 100)

        logger.info(
            "Starting enhanced scraping workflow",
            execution_id=str(execution_id),
            domains=domains,
            max_articles_per_domain=max_articles_per_domain,
        )

        all_results = {}
        global_stats = {
            "total_domains": len(domains),
            "domains_with_articles": 0,
            "domains_without_articles": 0,
            "domains_with_errors": 0,
            "total_articles_discovered": 0,
            "total_articles_scraped": 0,
            "total_articles_valid": 0,
        }

        for domain in domains:
            try:
                result = await self.discover_and_scrape_articles(
                    db_session,
                    domain,
                    max_articles_per_domain,
                    is_client_site=is_client_site,
                    site_profile_id=site_profile_id,
                    execution_id=execution_id,
                )

                all_results[domain] = result
                stats = result.get("statistics", {})

                global_stats["total_articles_discovered"] += stats.get("discovered", 0)
                global_stats["total_articles_scraped"] += stats.get("scraped", 0)
                global_stats["total_articles_valid"] += stats.get("valid", 0)

                if stats.get("valid", 0) > 0:
                    global_stats["domains_with_articles"] += 1
                else:
                    global_stats["domains_without_articles"] += 1

            except Exception as e:
                logger.error("Error scraping domain", domain=domain, error=str(e))
                # Log error to error_logs table
                try:
                    await log_error_from_exception(
                        db_session=db_session,
                        exception=e,
                        component="scraping",
                        context={
                            "domain": domain,
                            "method": "discover_and_scrape_articles",
                        },
                        severity="error",
                        execution_id=execution_id,
                        domain=domain,
                        agent_name="enhanced_scraping",
                    )
                except Exception as log_err:
                    logger.error("Failed to log error to database", error=str(log_err))
                
                all_results[domain] = {"articles": [], "statistics": {}}
                global_stats["domains_with_errors"] += 1

        return {
            "domains": domains,
            "results_by_domain": all_results,
            "total_articles_scraped": global_stats["total_articles_valid"],
            "statistics": global_stats,
        }

