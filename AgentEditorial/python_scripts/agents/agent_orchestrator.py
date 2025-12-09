"""Workflow orchestrator for editorial analysis."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_analyse_client import EditorialAnalysisAgent
from python_scripts.agents.competitor.agent import CompetitorSearchAgent
from python_scripts.agents.agent_scraping import ScrapingAgent
from python_scripts.agents.agent_topic_modeling import TopicModelingAgent
from python_scripts.database.crud_executions import (
    create_site_analysis_result,
    create_workflow_execution,
    get_workflow_execution,
    update_workflow_execution,
)
from python_scripts.database.crud_profiles import (
    create_site_profile,
    get_site_profile_by_domain,
    update_site_profile,
)
from python_scripts.database.models import WorkflowExecution
from python_scripts.ingestion.crawl_pages import crawl_multiple_pages
from python_scripts.ingestion.detect_sitemaps import get_sitemap_urls
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class EditorialAnalysisOrchestrator:
    """Orchestrator for editorial analysis workflow."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize orchestrator."""
        self.db_session = db_session
        self.analysis_agent = EditorialAnalysisAgent()
        self.competitor_agent = CompetitorSearchAgent()
        self.scraping_agent = ScrapingAgent()
        self.topic_modeling_agent = TopicModelingAgent()
        self.logger = get_logger(__name__)

    async def run_editorial_analysis(
        self,
        domain: str,
        max_pages: int = 50,
        execution_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Run complete editorial analysis workflow.

        Args:
            domain: Domain to analyze
            max_pages: Maximum pages to crawl
            execution_id: Optional execution ID (if None, creates new)

        Returns:
            Workflow execution result

        Raises:
            WorkflowError: If workflow fails
        """
        # Create or get execution
        if execution_id:
            execution = await get_workflow_execution(self.db_session, execution_id)
            if not execution:
                raise WorkflowError(f"Execution {execution_id} not found")
        else:
            execution = await create_workflow_execution(
                self.db_session,
                workflow_type="editorial_analysis",
                input_data={"domain": domain, "max_pages": max_pages},
                status="pending",
            )
            execution_id = execution.execution_id

        try:
            # Transition to running
            await update_workflow_execution(
                self.db_session,
                execution,
                status="running",
            )
            self.logger.info("Workflow started", execution_id=str(execution_id), domain=domain)

            # Step 1: Discover URLs via sitemap
            self.logger.info("Step 1: Discovering URLs", domain=domain)
            sitemap_urls = await get_sitemap_urls(domain)
            if not sitemap_urls:
                # Fallback: use homepage
                sitemap_urls = [f"https://{domain}"]

            # Limit URLs
            urls_to_crawl = sitemap_urls[:max_pages]

            # Step 2: Crawl pages
            self.logger.info("Step 2: Crawling pages", domain=domain, url_count=len(urls_to_crawl))
            crawled_pages = await crawl_multiple_pages(
                urls_to_crawl,
                db_session=self.db_session,
                respect_robots=True,
                use_cache=True,
            )

            if not crawled_pages:
                raise WorkflowError(f"No pages crawled for domain {domain}")

            # Step 3: Combine content
            self.logger.info("Step 3: Combining content", page_count=len(crawled_pages))
            combined_content = "\n\n".join([page.get("text", "") for page in crawled_pages])
            total_word_count = sum([page.get("word_count", 0) for page in crawled_pages])

            # Step 4: Run LLM analysis
            self.logger.info("Step 4: Running LLM analysis")
            analysis_result = await self.analysis_agent.execute(
                execution_id,
                {"content": combined_content},
            )

            # Step 5: Get or create site profile
            site_profile = await get_site_profile_by_domain(self.db_session, domain)
            if not site_profile:
                site_profile = await create_site_profile(
                    self.db_session,
                    domain,
                    analysis_date=datetime.now(timezone.utc),
                )

            # Step 6: Update site profile with results
            await update_site_profile(
                self.db_session,
                site_profile,
                language_level=analysis_result.get("language_level"),
                editorial_tone=analysis_result.get("editorial_tone"),
                target_audience=analysis_result.get("target_audience"),
                activity_domains=analysis_result.get("activity_domains"),
                content_structure=analysis_result.get("content_structure"),
                keywords=analysis_result.get("keywords"),
                style_features=analysis_result.get("style_features"),
                pages_analyzed=len(crawled_pages),
                llm_models_used=analysis_result.get("llm_models_used"),
            )

            # Step 7: Save analysis results
            await create_site_analysis_result(
                self.db_session,
                site_profile.id,
                execution_id,
                analysis_phase="synthesis",
                phase_results=analysis_result,
            )

            # Step 8: Update execution status
            await update_workflow_execution(
                self.db_session,
                execution,
                status="completed",
                output_data={
                    "site_profile_id": site_profile.id,
                    "pages_crawled": len(crawled_pages),
                    "total_word_count": total_word_count,
                    "analysis_result": analysis_result,
                },
                was_success=True,
            )

            # Step 9: Launch automatic scraping of client site
            self.logger.info("Step 9: Launching automatic scraping of client site", domain=domain)
            try:
                scraping_result = await self.run_scraping_workflow(
                    domains=[domain],
                    max_articles_per_domain=max_pages,
                    is_client_site=True,
                    site_profile_id=site_profile.id,
                )
                self.logger.info(
                    "Client site scraping completed",
                    domain=domain,
                    articles_scraped=scraping_result.get("total_articles_scraped", 0),
                )
            except Exception as e:
                # Don't fail the entire workflow if scraping fails
                self.logger.error(
                    "Failed to scrape client site",
                    domain=domain,
                    error=str(e),
                )

            self.logger.info(
                "Workflow completed",
                execution_id=str(execution_id),
                domain=domain,
                pages_crawled=len(crawled_pages),
            )

            return {
                "execution_id": str(execution_id),
                "status": "completed",
                "site_profile_id": site_profile.id,
                "pages_crawled": len(crawled_pages),
                "analysis_result": analysis_result,
            }

        except Exception as e:
            # Update execution with error
            error_message = str(e)
            self.logger.error(
                "Workflow failed",
                execution_id=str(execution_id),
                domain=domain,
                error=error_message,
            )

            try:
                await update_workflow_execution(
                    self.db_session,
                    execution,
                    status="failed",
                    error_message=error_message,
                    was_success=False,
                )
            except Exception as update_error:
                self.logger.error(
                    "Failed to update execution status",
                    execution_id=str(execution_id),
                    error=str(update_error),
                )

            raise WorkflowError(f"Editorial analysis workflow failed: {e}") from e

    async def run_competitor_search(
        self,
        domain: str,
        max_competitors: int = 100,
        execution_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Run competitor search workflow.

        Args:
            domain: Domain to find competitors for
            max_competitors: Maximum number of competitors to return
            execution_id: Optional execution ID (if None, creates new)

        Returns:
            Workflow execution result with competitors

        Raises:
            WorkflowError: If workflow fails
        """
        # Create or get execution
        if execution_id:
            execution = await get_workflow_execution(self.db_session, execution_id)
            if not execution:
                raise WorkflowError(f"Execution {execution_id} not found")
        else:
            execution = await create_workflow_execution(
                self.db_session,
                workflow_type="competitor_search",
                input_data={"domain": domain, "max_competitors": max_competitors},
                status="pending",
            )
            execution_id = execution.execution_id

        try:
            # Transition to running
            await update_workflow_execution(
                self.db_session,
                execution,
                status="running",
            )
            self.logger.info("Competitor search started", execution_id=str(execution_id), domain=domain)

            # Run competitor search using execute() to get complete data
            complete_results = await self.competitor_agent.execute(
                execution_id=execution_id,
                input_data={
                    "domain": domain,
                    "max_competitors": max_competitors,
                },
                db_session=self.db_session,
            )

            # Update execution with complete results
            await update_workflow_execution(
                self.db_session,
                execution,
                status="completed",
                output_data=complete_results,  # Contains competitors, all_candidates, excluded_candidates, total_found, total_evaluated, domain
                was_success=True,
            )
            
            results = complete_results.get("competitors", [])

            self.logger.info(
                "Competitor search completed",
                execution_id=str(execution_id),
                domain=domain,
                competitors_found=len(results),
            )

            return {
                "execution_id": str(execution_id),
                "status": "completed",
                **complete_results,  # Include all fields: competitors, all_candidates, excluded_candidates, total_found, total_evaluated, domain
            }

        except Exception as e:
            # Update execution with error
            error_message = str(e)
            self.logger.error(
                "Competitor search failed",
                execution_id=str(execution_id),
                domain=domain,
                error=error_message,
            )

            try:
                await update_workflow_execution(
                    self.db_session,
                    execution,
                    status="failed",
                    error_message=error_message,
                    was_success=False,
                )
            except Exception as update_error:
                self.logger.error(
                    "Failed to update execution status",
                    execution_id=str(execution_id),
                    error=str(update_error),
                )

            raise WorkflowError(f"Competitor search workflow failed: {e}") from e

    async def run_scraping_workflow(
        self,
        domains: List[str],
        max_articles_per_domain: int = 500,
        execution_id: Optional[UUID] = None,
        is_client_site: bool = False,
        site_profile_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run scraping workflow for competitor domains (T107 - US5).

        Args:
            domains: List of domains to scrape
            max_articles_per_domain: Maximum articles per domain
            execution_id: Optional execution ID (if None, creates new)
            is_client_site: Whether this is a client site (uses client_articles collection)
            site_profile_id: Site profile ID (required if is_client_site=True)

        Returns:
            Workflow execution result with scraped articles

        Raises:
            WorkflowError: If workflow fails
        """
        # Create or get execution
        if execution_id:
            execution = await get_workflow_execution(self.db_session, execution_id)
            if not execution:
                raise WorkflowError(f"Execution {execution_id} not found")
        else:
            execution = await create_workflow_execution(
                self.db_session,
                workflow_type="scraping",
                input_data={
                    "domains": domains,
                    "max_articles_per_domain": max_articles_per_domain,
                },
                status="pending",
            )
            execution_id = execution.execution_id

        try:
            # Transition to running
            await update_workflow_execution(
                self.db_session,
                execution,
                status="running",
            )
            self.logger.info(
                "Scraping workflow started",
                execution_id=str(execution_id),
                domains=domains,
            )

            # Run scraping agent
            result = await self.scraping_agent.execute(
                execution_id,
                {
                    "domains": domains,
                    "max_articles_per_domain": max_articles_per_domain,
                },
                db_session=self.db_session,
                is_client_site=is_client_site,
                site_profile_id=site_profile_id,
            )

            # Update execution with results
            await update_workflow_execution(
                self.db_session,
                execution,
                status="completed",
                output_data=result,
                was_success=True,
            )

            stats = result.get("statistics", {})
            self.logger.info(
                "Scraping workflow completed",
                execution_id=str(execution_id),
                domains=domains,
                total_articles_scraped=result.get("total_articles_scraped", 0),
                statistics=stats,
            )

            return result

        except Exception as e:
            # Update execution with error
            error_message = str(e)
            self.logger.error(
                "Scraping workflow failed",
                execution_id=str(execution_id),
                domains=domains,
                error=error_message,
            )

            try:
                await update_workflow_execution(
                    self.db_session,
                    execution,
                    status="failed",
                    error_message=error_message,
                    was_success=False,
                )
            except Exception as update_error:
                self.logger.error(
                    "Failed to update execution status",
                    execution_id=str(execution_id),
                    error=str(update_error),
                )

            raise WorkflowError(f"Scraping workflow failed: {e}") from e

    async def run_trends_analysis_workflow(
        self,
        domains: List[str],
        time_window_days: int = 365,
        min_topic_size: Optional[int] = None,
        nr_topics: Optional[str | int] = None,
        execution_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Run trends analysis workflow with BERTopic (T132 - US7).

        Args:
            domains: List of domains to analyze
            time_window_days: Time window in days (default: 365)
            min_topic_size: Minimum articles per topic (optional)
            nr_topics: Number of topics or "auto" (optional)
            execution_id: Optional execution ID (if None, creates new)

        Returns:
            Workflow execution result with topics and analysis

        Raises:
            WorkflowError: If workflow fails
        """
        # Create or get execution
        if execution_id:
            execution = await get_workflow_execution(self.db_session, execution_id)
            if not execution:
                raise WorkflowError(f"Execution {execution_id} not found")
        else:
            execution = await create_workflow_execution(
                self.db_session,
                workflow_type="trends_analysis",
                input_data={
                    "domains": domains,
                    "time_window_days": time_window_days,
                    "min_topic_size": min_topic_size,
                    "nr_topics": nr_topics,
                },
                status="pending",
            )
            execution_id = execution.execution_id

        try:
            # Transition to running
            await update_workflow_execution(
                self.db_session,
                execution,
                status="running",
            )
            self.logger.info(
                "Trends analysis workflow started",
                execution_id=str(execution_id),
                domains=domains,
                time_window_days=time_window_days,
            )

            # Prepare input data
            input_data = {
                "domains": domains,
                "time_window_days": time_window_days,
            }
            if min_topic_size is not None:
                input_data["min_topic_size"] = min_topic_size
            if nr_topics is not None:
                input_data["nr_topics"] = nr_topics

            # Run topic modeling agent
            result = await self.topic_modeling_agent.execute(
                execution_id,
                input_data,
                db_session=self.db_session,
            )

            # Update execution with results
            await update_workflow_execution(
                self.db_session,
                execution,
                status="completed",
                output_data=result,
                was_success=True,
            )

            stats = result.get("statistics", {})
            self.logger.info(
                "Trends analysis workflow completed",
                execution_id=str(execution_id),
                domains=domains,
                num_topics=stats.get("num_topics", 0),
                total_articles=stats.get("total_articles", 0),
            )

            return result

        except Exception as e:
            # Update execution with error
            error_message = str(e)
            self.logger.error(
                "Trends analysis workflow failed",
                execution_id=str(execution_id),
                domains=domains,
                error=error_message,
            )

            try:
                await update_workflow_execution(
                    self.db_session,
                    execution,
                    status="failed",
                    error_message=error_message,
                    was_success=False,
                )
            except Exception as update_error:
                self.logger.error(
                    "Failed to update execution status",
                    execution_id=str(execution_id),
                    error=str(update_error),
                )

            raise WorkflowError(f"Trends analysis workflow failed: {e}") from e

