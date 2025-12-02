"""Workflow orchestrator for editorial analysis."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_analysis import EditorialAnalysisAgent
from python_scripts.agents.agent_competitor import CompetitorSearchAgent
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
                self.db_session,
                urls_to_crawl,
                domain,
                max_pages=max_pages,
                respect_robots_txt=True,
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

            # Run competitor search
            results = await self.competitor_agent.search_competitors(
                domain=domain,
                max_competitors=max_competitors,
                db_session=self.db_session,
            )

            # Update execution with results
            await update_workflow_execution(
                self.db_session,
                execution,
                status="completed",
                output_data={
                    "competitors": results,
                    "total_found": len(results),
                    "domain": domain,
                },
                was_success=True,
            )

            self.logger.info(
                "Competitor search completed",
                execution_id=str(execution_id),
                domain=domain,
                competitors_found=len(results),
            )

            return {
                "execution_id": str(execution_id),
                "status": "completed",
                "competitors": results,
                "total_found": len(results),
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

