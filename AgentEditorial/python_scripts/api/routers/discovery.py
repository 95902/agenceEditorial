"""API router for enhanced discovery endpoints."""

import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.responses import ExecutionResponse
from python_scripts.database.crud_executions import (
    create_workflow_execution,
    get_workflow_execution,
    update_workflow_execution,
)
from python_scripts.database.crud_profiles import get_site_profile_by_domain
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])


class EnhancedScrapingRequest:
    """Request schema for enhanced scraping."""

    def __init__(
        self,
        domains: Optional[List[str]] = None,
        max_articles: int = 100,
        is_client_site: bool = False,
        site_profile_id: Optional[int] = None,
        force_reprofile: bool = False,
    ):
        self.domains = domains or []
        self.max_articles = max_articles
        self.is_client_site = is_client_site
        self.site_profile_id = site_profile_id
        self.force_reprofile = force_reprofile


async def run_enhanced_scraping_background(
    domains: List[str],
    max_articles: int,
    execution_id: UUID,
    is_client_site: bool = False,
    site_profile_id: Optional[int] = None,
    force_reprofile: bool = False,
) -> None:
    """
    Background task to run enhanced scraping workflow.

    Args:
        domains: List of domains to scrape
        max_articles: Maximum articles per domain
        execution_id: Execution ID
        is_client_site: Whether this is a client site
        site_profile_id: Site profile ID (required if is_client_site=True)
        force_reprofile: Force reprofiling even if profile exists
    """
    try:
        from python_scripts.database.db_session import AsyncSessionLocal

        # Create new session for background task
        async with AsyncSessionLocal() as db_session:
            # Get execution object
            execution = await get_workflow_execution(db_session, execution_id)
            if not execution:
                logger.error("Execution not found", execution_id=str(execution_id))
                return

            # Extract client_domain from input_data if available
            client_domain = None
            if execution.input_data:
                client_domain = execution.input_data.get("client_domain")

            # Update execution status to running
            await update_workflow_execution(
                db_session,
                execution,
                status="running",
            )

            # Import and run enhanced scraping agent
            from python_scripts.agents.scrapping import EnhancedScrapingAgent

            agent = EnhancedScrapingAgent(min_word_count=150)

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
                    # Get site_profile_id if client site and not provided
                    current_site_profile_id = site_profile_id
                    if is_client_site and not current_site_profile_id:
                        site_profile = await get_site_profile_by_domain(db_session, domain)
                        if not site_profile:
                            logger.warning(
                                "Site profile not found for client site",
                                domain=domain,
                            )
                            all_results[domain] = {
                                "articles": [],
                                "statistics": {},
                                "error": "Site profile not found. Please run editorial analysis first.",
                            }
                            global_stats["domains_with_errors"] += 1
                            continue
                        current_site_profile_id = site_profile.id

                    result = await agent.discover_and_scrape_articles(
                        db_session,
                        domain,
                        max_articles,
                        is_client_site=is_client_site,
                        site_profile_id=current_site_profile_id,
                        force_reprofile=force_reprofile,
                        client_domain=client_domain,
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
                    all_results[domain] = {
                        "articles": [],
                        "statistics": {},
                        "error": str(e),
                    }
                    global_stats["domains_with_errors"] += 1

            workflow_result = {
                "domains": domains,
                "results_by_domain": all_results,
                "total_articles_scraped": global_stats["total_articles_valid"],
                "statistics": global_stats,
            }

            # Get execution again (in case it was updated)
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                # Update execution with results
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="completed",
                    output_data=workflow_result,
                )

            logger.info(
                "Enhanced scraping workflow completed",
                execution_id=str(execution_id),
                domains=domains,
                total_articles=global_stats["total_articles_valid"],
            )

    except WorkflowError as e:
        logger.error("Enhanced scraping workflow error", execution_id=str(execution_id), error=str(e))
        from python_scripts.database.db_session import AsyncSessionLocal
        async with AsyncSessionLocal() as db_session:
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="failed",
                    error_message=str(e),
                )
    except Exception as e:
        logger.error(
            "Unexpected error in enhanced scraping workflow",
            execution_id=str(execution_id),
            error=str(e),
        )
        from python_scripts.database.db_session import AsyncSessionLocal
        async with AsyncSessionLocal() as db_session:
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="failed",
                    error_message=f"Unexpected error: {str(e)}",
                )


@router.post(
    "/scrape",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enhanced scraping with 4-phase discovery",
    description="""
    Start enhanced scraping with 4-phase discovery pipeline:
    
    1. **Phase 0 - Profiling**: Analyze site structure, detect CMS, APIs, sitemaps, RSS
    2. **Phase 1 - Discovery**: Multi-source discovery (API REST, RSS, sitemaps, heuristics)
    3. **Phase 2 - Scoring**: Probability scoring for each discovered URL
    4. **Phase 3 - Extraction**: Adaptive extraction using site profile
    
    This endpoint provides better article discovery rates and accuracy compared to standard scraping.
    
    Supports two modes:
    - **Direct domains**: Provide 'domains' list directly
    - **Auto-fetch competitors**: Provide 'client_domain' to automatically fetch validated competitors
    """,
)
async def enhanced_scrape(
    domains: Optional[List[str]] = Query(None, description="List of domains to scrape (required if client_domain not provided)"),
    client_domain: Optional[str] = Query(None, description="Client domain to fetch validated competitors from (required if domains not provided)"),
    max_articles: int = Query(100, ge=1, le=1000, description="Maximum articles per domain"),
    is_client_site: bool = Query(False, description="Whether this is a client site"),
    site_profile_id: Optional[int] = Query(None, description="Site profile ID (required if is_client_site=True)"),
    force_reprofile: bool = Query(False, description="Force reprofiling even if profile exists"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start enhanced scraping workflow with 4-phase discovery.

    Args:
        domains: List of domains to scrape (required if client_domain not provided)
        client_domain: Client domain to fetch validated competitors from (required if domains not provided)
        max_articles: Maximum articles per domain
        is_client_site: Whether this is a client site
        site_profile_id: Site profile ID (required if is_client_site=True)
        force_reprofile: Force reprofiling even if profile exists
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id
    """
    try:
        domains_to_scrape = []
        current_is_client_site = is_client_site
        
        # Mode 1: Explicit domains provided
        if domains:
            domains_to_scrape = domains
            logger.info("Using explicit domains", domains=domains_to_scrape)
        
        # Mode 2: Fetch validated competitors from client_domain
        elif client_domain:
            from sqlalchemy import select, desc
            from python_scripts.database.models import WorkflowExecution
            
            # Find latest completed competitor search for this domain
            stmt = (
                select(WorkflowExecution)
                .where(
                    WorkflowExecution.workflow_type == "competitor_search",
                    WorkflowExecution.status == "completed",
                    WorkflowExecution.input_data["domain"].astext == client_domain,
                )
                .order_by(desc(WorkflowExecution.start_time))
                .limit(1)
            )
            
            result = await db.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if not execution or not execution.output_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No competitor search results found for domain: {client_domain}. Please run competitor search first.",
                )
            
            # Extract validated competitors (only those with validated=True or manual=True)
            competitors_data = execution.output_data.get("competitors", [])
            if not competitors_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {client_domain}",
                )
            
            # Extract domains from validated competitors
            domains_to_scrape = [
                comp.get("domain")
                for comp in competitors_data
                if comp.get("domain") and not comp.get("excluded", False)
            ]
            
            if not domains_to_scrape:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {client_domain}",
                )
            
            # Force is_client_site=false when using client_domain (we're scraping competitors)
            current_is_client_site = False
            
            logger.info(
                "Fetched validated competitors",
                client_domain=client_domain,
                competitor_count=len(domains_to_scrape),
                domains=domains_to_scrape,
            )
        
        else:
            # Neither domains nor client_domain provided
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'domains' or 'client_domain' must be provided",
            )
        
        # Validate client site requirements (only if is_client_site=true)
        if current_is_client_site:
            for domain in domains_to_scrape:
                site_profile = await get_site_profile_by_domain(db, domain)
                if not site_profile:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Site profile not found for domain: {domain}. Please run editorial analysis first.",
                    )

        # Create workflow execution
        execution = await create_workflow_execution(
            db,
            workflow_type="enhanced_scraping",
            input_data={
                "domains": domains_to_scrape,
                "max_articles": max_articles,
                "is_client_site": current_is_client_site,
                "site_profile_id": site_profile_id,
                "force_reprofile": force_reprofile,
                "client_domain": client_domain if client_domain else None,
            },
            status="pending",
        )

        execution_id = execution.execution_id

        # Start background task
        background_tasks.add_task(
            run_enhanced_scraping_background,
            domains=domains_to_scrape,
            max_articles=max_articles,
            execution_id=execution_id,
            is_client_site=current_is_client_site,
            site_profile_id=site_profile_id,
            force_reprofile=force_reprofile,
        )

        logger.info(
            "Enhanced scraping workflow started",
            execution_id=str(execution_id),
            domains=domains_to_scrape,
            max_articles=max_articles,
            is_client_site=current_is_client_site,
            mode="auto-fetch" if client_domain else "explicit",
            client_domain=client_domain,
        )

        return ExecutionResponse(
            execution_id=execution_id,
            status="pending",
            start_time=execution.start_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start enhanced scraping workflow", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start enhanced scraping workflow: {e}",
        )


@router.get(
    "/profile/{domain}",
    status_code=status.HTTP_200_OK,
    summary="Get site discovery profile",
    description="Retrieve the discovery profile for a domain.",
)
async def get_discovery_profile(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get site discovery profile.

    Args:
        domain: Domain name
        db: Database session

    Returns:
        Discovery profile data
    """
    try:
        from python_scripts.agents.scrapping.crud import get_site_discovery_profile

        profile = await get_site_discovery_profile(db, domain)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No discovery profile found for domain: {domain}",
            )

        return {
            "domain": profile.domain,
            "cms_detected": profile.cms_detected,
            "cms_version": profile.cms_version,
            "has_rest_api": profile.has_rest_api,
            "api_endpoints": profile.api_endpoints,
            "sitemap_urls": profile.sitemap_urls,
            "rss_feeds": profile.rss_feeds,
            "blog_listing_pages": profile.blog_listing_pages,
            "url_patterns": profile.url_patterns,
            "content_selector": profile.content_selector,
            "title_selector": profile.title_selector,
            "date_selector": profile.date_selector,
            "author_selector": profile.author_selector,
            "total_urls_discovered": profile.total_urls_discovered,
            "total_articles_valid": profile.total_articles_valid,
            "success_rate": float(profile.success_rate) if profile.success_rate else 0.0,
            "avg_article_word_count": float(profile.avg_article_word_count) if profile.avg_article_word_count else None,
            "last_profiled_at": profile.last_profiled_at.isoformat() if profile.last_profiled_at else None,
            "last_crawled_at": profile.last_crawled_at.isoformat() if profile.last_crawled_at else None,
            "profile_version": profile.profile_version,
            "is_active": profile.is_active,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get discovery profile", domain=domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get discovery profile: {e}",
        )


@router.post(
    "/profile/{domain}/reprofile",
    status_code=status.HTTP_200_OK,
    summary="Force reprofile a domain",
    description="Force reprofiling of a domain (Phase 0).",
)
async def reprofile_domain(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Force reprofile a domain.

    Args:
        domain: Domain name
        db: Database session

    Returns:
        Updated profile data
    """
    try:
        from python_scripts.agents.scrapping import EnhancedScrapingAgent
        from python_scripts.agents.scrapping.crud import (
            create_site_discovery_profile,
            get_site_discovery_profile,
            update_site_discovery_profile,
        )

        agent = EnhancedScrapingAgent()
        profile_data = await agent.profiler.profile_site(domain)

        existing_profile = await get_site_discovery_profile(db, domain)
        if existing_profile:
            await update_site_discovery_profile(db, domain, profile_data)
            profile = await get_site_discovery_profile(db, domain)
        else:
            profile = await create_site_discovery_profile(db, domain, profile_data)

        return {
            "domain": profile.domain,
            "cms_detected": profile.cms_detected,
            "has_rest_api": profile.has_rest_api,
            "sitemap_urls": profile.sitemap_urls,
            "rss_feeds": profile.rss_feeds,
            "last_profiled_at": profile.last_profiled_at.isoformat() if profile.last_profiled_at else None,
        }

    except Exception as e:
        logger.error("Failed to reprofile domain", domain=domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reprofile domain: {e}",
        )

