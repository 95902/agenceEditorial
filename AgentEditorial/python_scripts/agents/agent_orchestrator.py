"""Workflow orchestrator for editorial analysis with full traceability."""

import time
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_analyse_client import EditorialAnalysisAgent
from python_scripts.agents.competitor.agent import CompetitorSearchAgent
from python_scripts.database.crud_executions import (
    create_audit_log,
    create_audit_log_from_exception,
    create_performance_metric,
    create_performance_metrics_batch,
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
from python_scripts.utils.logging import (
    AuditLogger,
    get_logger,
    set_execution_context,
    clear_execution_context,
)

logger = get_logger(__name__)


class EditorialAnalysisOrchestrator:
    """
    Orchestrator for editorial analysis workflow with full traceability.
    
    Features:
    - Audit logging for all workflow steps
    - Performance metrics tracking (duration, pages, tokens)
    - Comprehensive error handling with stack traces
    - WebSocket progress streaming
    """

    AGENT_NAME = "editorial_orchestrator"

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize orchestrator with audit logging support."""
        self.db_session = db_session
        self.analysis_agent = EditorialAnalysisAgent()
        self.competitor_agent = CompetitorSearchAgent()
        self.logger = get_logger(__name__)
        self.audit = AuditLogger(self.AGENT_NAME)
        self._step_timers: Dict[str, float] = {}
        self._current_execution_id: Optional[UUID] = None

    def _start_step_timer(self, step_name: str) -> None:
        """Start a timer for a step."""
        self._step_timers[step_name] = time.time()

    def _get_step_duration(self, step_name: str) -> float:
        """Get the duration of a step and remove the timer."""
        start_time = self._step_timers.pop(step_name, None)
        if start_time is None:
            return 0.0
        return time.time() - start_time

    async def _log_audit(
        self,
        action: str,
        status: str,
        message: str,
        step_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an audit entry to the database."""
        try:
            await create_audit_log(
                db_session=self.db_session,
                action=action,
                status=status,
                message=message,
                execution_id=self._current_execution_id,
                agent_name=self.AGENT_NAME,
                step_name=step_name,
                details=details,
            )
        except Exception as e:
            self.logger.warning(
                "Failed to create audit log",
                error=str(e),
                action=action,
            )

    async def _log_audit_error(
        self,
        action: str,
        error: Exception,
        step_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an error audit entry with stack trace."""
        try:
            await create_audit_log_from_exception(
                db_session=self.db_session,
                action=action,
                exception=error,
                execution_id=self._current_execution_id,
                agent_name=self.AGENT_NAME,
                step_name=step_name,
                details=details,
            )
        except (RuntimeError, Exception) as e:
            # If session is invalid, try to create a new session for logging
            if "session is invalid" in str(e) or "connection" in str(e).lower():
                try:
                    from python_scripts.database.db_session import AsyncSessionLocal
                    async with AsyncSessionLocal() as new_session:
                        await create_audit_log_from_exception(
                            db_session=new_session,
                            action=action,
                            exception=error,
                            execution_id=self._current_execution_id,
                            agent_name=self.AGENT_NAME,
                            step_name=step_name,
                            details=details,
                        )
                except Exception as retry_error:
                    self.logger.warning(
                        "Failed to create audit error log even with new session",
                        error=str(retry_error),
                        original_error=str(error),
                    )
            else:
                self.logger.warning(
                    "Failed to create audit error log",
                    error=str(e),
                    original_error=str(error),
                )

    async def _record_metric(
        self,
        metric_type: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a performance metric."""
        if not self._current_execution_id:
            return
        try:
            await create_performance_metric(
                db_session=self.db_session,
                execution_id=self._current_execution_id,
                metric_type=metric_type,
                metric_value=metric_value,
                metric_unit=metric_unit,
                agent_name=self.AGENT_NAME,
                additional_data=additional_data,
            )
        except (RuntimeError, Exception) as e:
            # If session is invalid, try to create a new session for logging
            if "session is invalid" in str(e) or "connection" in str(e).lower():
                try:
                    from python_scripts.database.db_session import AsyncSessionLocal
                    async with AsyncSessionLocal() as new_session:
                        await create_performance_metric(
                            db_session=new_session,
                            execution_id=self._current_execution_id,
                            metric_type=metric_type,
                            metric_value=metric_value,
                            metric_unit=metric_unit,
                            agent_name=self.AGENT_NAME,
                            additional_data=additional_data,
                        )
                except Exception as retry_error:
                    self.logger.warning(
                        "Failed to record performance metric even with new session",
                        error=str(retry_error),
                        metric_type=metric_type,
                    )
            else:
                self.logger.warning(
                    "Failed to record performance metric",
                    error=str(e),
                    metric_type=metric_type,
                )

    async def _record_step_metrics(
        self,
        step_name: str,
        duration_seconds: float,
        additional_metrics: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Record metrics for a completed step."""
        if not self._current_execution_id:
            return

        metrics = [
            {
                "metric_type": f"{step_name}_duration",
                "metric_value": duration_seconds,
                "metric_unit": "seconds",
            }
        ]
        
        if additional_metrics:
            metrics.extend(additional_metrics)
        
        try:
            await create_performance_metrics_batch(
                db_session=self.db_session,
                execution_id=self._current_execution_id,
                metrics=metrics,
                agent_name=self.AGENT_NAME,
            )
        except Exception as e:
            self.logger.warning(
                "Failed to record step metrics",
                error=str(e),
                step_name=step_name,
            )

    async def _send_progress(
        self,
        execution_id: UUID,
        step: str,
        progress: int,
        message: str,
        status: str = "running",
    ) -> None:
        """
        Send progress update via WebSocket if available.
        
        Args:
            execution_id: Execution UUID
            step: Current step name
            progress: Progress percentage (0-100)
            message: Progress message
            status: Current status
        """
        try:
            from python_scripts.api.routers.executions import websocket_manager
            
            await websocket_manager.send_progress(
                execution_id,
                {
                    "step": step,
                    "progress": progress,
                    "message": message,
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            # Don't fail workflow if WebSocket fails
            logger.debug("Failed to send progress", execution_id=str(execution_id), error=str(e))

    async def run_editorial_analysis(
        self,
        domain: str,
        max_pages: int = 50,
        execution_id: Optional[UUID] = None,
        generate_image: bool = False,
        image_style: str = "corporate_flat",
    ) -> Dict[str, Any]:
        """
        Run complete editorial analysis workflow with full traceability.

        Args:
            domain: Domain to analyze
            max_pages: Maximum pages to crawl
            execution_id: Optional execution ID (if None, creates new)
            generate_image: If True, generate an editorial image after analysis
            image_style: Style for image generation (corporate_flat, corporate_3d, tech_isometric, etc.)

        Returns:
            Workflow execution result

        Raises:
            WorkflowError: If workflow fails
        """
        workflow_start_time = time.time()
        
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
        
        # Set execution context for logging
        self._current_execution_id = execution_id
        set_execution_context(execution_id=execution_id, agent_name=self.AGENT_NAME)
        self.audit.set_execution(execution_id)

        try:
            # Transition to running
            await update_workflow_execution(
                self.db_session,
                execution,
                status="running",
            )
            
            # Log workflow start
            await self._log_audit(
                action="workflow_start",
                status="info",
                message=f"Starting editorial analysis for {domain}",
                details={"domain": domain, "max_pages": max_pages},
            )
            self.logger.info("Workflow started", execution_id=str(execution_id), domain=domain)

            # Step 1: Discover URLs via sitemap
            self._start_step_timer("discovering")
            await self._send_progress(execution_id, "discovering", 10, f"Discovering URLs for {domain}...")
            await self._log_audit("step_start", "info", "Discovering URLs via sitemap", step_name="discovering")
            
            sitemap_urls = await get_sitemap_urls(domain)
            if not sitemap_urls:
                sitemap_urls = [f"https://{domain}"]
            urls_to_crawl = sitemap_urls[:max_pages]
            
            discovering_duration = self._get_step_duration("discovering")
            await self._record_step_metrics(
                "discovering",
                discovering_duration,
                additional_metrics=[
                    {"metric_type": "urls_discovered", "metric_value": len(sitemap_urls), "metric_unit": "urls"},
                    {"metric_type": "urls_to_crawl", "metric_value": len(urls_to_crawl), "metric_unit": "urls"},
                ],
            )
            await self._log_audit(
                "step_complete",
                "success",
                f"Discovered {len(sitemap_urls)} URLs, will crawl {len(urls_to_crawl)}",
                step_name="discovering",
                details={"urls_discovered": len(sitemap_urls), "urls_to_crawl": len(urls_to_crawl)},
            )

            # Step 2: Crawl pages
            self._start_step_timer("crawling")
            await self._send_progress(execution_id, "crawling", 25, f"Crawling {len(urls_to_crawl)} pages...")
            await self._log_audit("step_start", "info", f"Crawling {len(urls_to_crawl)} pages", step_name="crawling")
            
            crawled_pages = await crawl_multiple_pages(
                urls_to_crawl,
                db_session=self.db_session,
                respect_robots=True,
                use_cache=True,
            )

            if not crawled_pages:
                raise WorkflowError(f"No pages crawled for domain {domain}")
            
            crawling_duration = self._get_step_duration("crawling")
            await self._record_step_metrics(
                "crawling",
                crawling_duration,
                additional_metrics=[
                    {"metric_type": "pages_crawled", "metric_value": len(crawled_pages), "metric_unit": "pages"},
                ],
            )
            await self._log_audit(
                "step_complete",
                "success",
                f"Crawled {len(crawled_pages)} pages",
                step_name="crawling",
                details={"pages_crawled": len(crawled_pages), "duration_seconds": crawling_duration},
            )

            # Step 3: Combine content
            self._start_step_timer("combining")
            await self._send_progress(execution_id, "combining", 50, "Combining page content...")
            
            combined_content = "\n\n".join([page.get("text", "") for page in crawled_pages])
            total_word_count = sum([page.get("word_count", 0) for page in crawled_pages])
            
            combining_duration = self._get_step_duration("combining")
            await self._record_step_metrics(
                "combining",
                combining_duration,
                additional_metrics=[
                    {"metric_type": "total_word_count", "metric_value": total_word_count, "metric_unit": "words"},
                ],
            )

            # Step 4: Run LLM analysis
            self._start_step_timer("analyzing")
            await self._send_progress(execution_id, "analyzing", 70, "Analyzing editorial style with LLM...")
            await self._log_audit("step_start", "info", "Running LLM editorial analysis", step_name="analyzing")
            
            analysis_result = await self.analysis_agent.execute(
                execution_id,
                {
                    "content": combined_content,
                    "domain": domain,
                },
            )
            
            analyzing_duration = self._get_step_duration("analyzing")
            await self._record_step_metrics("analyzing", analyzing_duration)
            await self._log_audit(
                "step_complete",
                "success",
                "LLM analysis completed",
                step_name="analyzing",
                details={"duration_seconds": analyzing_duration},
            )

            # Step 5: Get or create site profile
            self._start_step_timer("saving")
            await self._send_progress(execution_id, "saving", 85, "Saving site profile...")
            
            site_profile = await get_site_profile_by_domain(self.db_session, domain)
            if not site_profile:
                site_profile = await create_site_profile(
                    self.db_session,
                    domain,
                    analysis_date=datetime.now(timezone.utc),
                )
            
            # Step 5b: Generate image if requested (after site_profile is created)
            if generate_image:
                try:
                    from python_scripts.agents.agent_image_generation import generate_article_image
                    from python_scripts.database.crud_images import save_image_generation
                    
                    await self._log_audit("step_start", "info", "Generating editorial image", step_name="image_generation")
                    await self._send_progress(execution_id, "generating_image", 88, "Generating editorial image...")
                    
                    # Generate image using the synthesized profile
                    image_result = await generate_article_image(
                        site_profile=analysis_result,  # Use the synthesized profile
                        article_topic=domain,  # Use domain as topic
                        style=image_style,
                        max_retries=3,
                    )
                    
                    # Extract Ideogram metadata from generation_params if available
                    generation_params = image_result.generation_params or {}
                    provider = generation_params.get("provider", "ideogram")
                    ideogram_url = generation_params.get("ideogram_url")
                    magic_prompt = generation_params.get("magic_prompt")
                    style_type = generation_params.get("style_type")
                    aspect_ratio = generation_params.get("aspect_ratio")

                    # Save to database (note: article_id=None means it won't be saved due to FK constraint)
                    saved_image = await save_image_generation(
                        db=self.db_session,
                        site_profile_id=site_profile.id,
                        article_topic=domain,
                        prompt_used=image_result.prompt_used,
                        output_path=str(image_result.image_path),
                        generation_params=generation_params,
                        quality_score=image_result.quality_score,
                        negative_prompt=image_result.negative_prompt,
                        critique_details=image_result.critique_details,
                        retry_count=image_result.retry_count,
                        final_status=image_result.final_status,
                        generation_time_seconds=None,
                        article_id=None,  # Pas d'article associé pour l'instant
                        provider=provider,
                        ideogram_url=ideogram_url,
                        magic_prompt=magic_prompt,
                        style_type=style_type,
                        aspect_ratio=aspect_ratio,
                    )
                    
                    await self.db_session.commit()
                    
                    # Add image info to analysis result
                    # Note: saved_image may be None if article_id is None (FK constraint)
                    image_info = {
                        "image_path": str(image_result.image_path),
                        "quality_score": image_result.quality_score,
                        "final_status": image_result.final_status,
                        "retry_count": image_result.retry_count,
                    }
                    if saved_image is not None:
                        image_info["image_id"] = saved_image.id
                    
                    analysis_result["image_generation"] = image_info
                    
                    if saved_image is not None:
                        logger.info(
                            "Image generation completed and saved",
                            image_id=saved_image.id,
                            site_profile_id=site_profile.id,
                            execution_id=str(execution_id),
                        )
                    else:
                        logger.info(
                            "Image generation completed (not saved to DB: no article_id)",
                            image_path=str(image_result.image_path),
                            site_profile_id=site_profile.id,
                            execution_id=str(execution_id),
                        )
                    
                    await self._log_audit("step_complete", "success", "Image generated successfully", step_name="image_generation")
                    
                except Exception as image_error:
                    logger.error(
                        "Image generation failed",
                        error=str(image_error),
                        execution_id=str(execution_id),
                    )
                    # Don't fail the whole analysis if image generation fails
                    analysis_result["image_generation"] = {
                        "error": str(image_error),
                        "status": "failed",
                    }
                    if self.db_session:
                        await self.db_session.rollback()
                    await self._log_audit("step_error", "error", f"Image generation failed: {image_error}", step_name="image_generation")

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
            
            saving_duration = self._get_step_duration("saving")
            await self._record_step_metrics("saving", saving_duration)

            # Step 8: Update execution status
            await self._send_progress(execution_id, "completing", 95, "Finalizing analysis...")
            
            workflow_duration = time.time() - workflow_start_time
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
            
            # Record total workflow metrics
            await self._record_metric("workflow_total_duration", workflow_duration, "seconds")
            await self._log_audit(
                "workflow_complete",
                "success",
                f"Editorial analysis completed for {domain}",
                details={
                    "site_profile_id": site_profile.id,
                    "pages_crawled": len(crawled_pages),
                    "total_word_count": total_word_count,
                    "duration_seconds": workflow_duration,
                },
            )
            
            await self._send_progress(execution_id, "complete", 100, "Analysis completed successfully", status="completed")

            self.logger.info(
                "Workflow completed",
                execution_id=str(execution_id),
                domain=domain,
                pages_crawled=len(crawled_pages),
                duration_seconds=workflow_duration,
            )

            return {
                "execution_id": str(execution_id),
                "status": "completed",
                "site_profile_id": site_profile.id,
                "pages_crawled": len(crawled_pages),
                "analysis_result": analysis_result,
            }

        except Exception as e:
            workflow_duration = time.time() - workflow_start_time
            error_message = str(e)
            error_traceback = traceback.format_exc()
            
            # Log the error with full traceback
            self.logger.error(
                "Workflow failed",
                execution_id=str(execution_id),
                domain=domain,
                error=error_message,
                traceback=error_traceback,
            )
            
            # Create audit log for the error
            await self._log_audit_error(
                action="workflow_failed",
                error=e,
                details={
                    "domain": domain,
                    "duration_seconds": workflow_duration,
                },
            )
            
            # Record failure metric
            await self._record_metric("workflow_failed_duration", workflow_duration, "seconds")

            try:
                await update_workflow_execution(
                    self.db_session,
                    execution,
                    status="failed",
                    error_message=f"{error_message}\n\nTraceback:\n{error_traceback}",
                    was_success=False,
                )
                await self._send_progress(
                    execution_id, "error", 0, f"Workflow failed: {error_message}", status="failed"
                )
            except (RuntimeError, Exception) as update_error:
                # If session is invalid, try to create a new session for updating
                if "session is invalid" in str(update_error) or "connection" in str(update_error).lower():
                    try:
                        from python_scripts.database.db_session import AsyncSessionLocal
                        async with AsyncSessionLocal() as new_session:
                            # Re-fetch execution with new session
                            execution = await get_workflow_execution(new_session, execution_id)
                            if execution:
                                await update_workflow_execution(
                                    new_session,
                                    execution,
                                    status="failed",
                                    error_message=f"{error_message}\n\nTraceback:\n{error_traceback}",
                                    was_success=False,
                                )
                    except Exception as retry_error:
                        self.logger.error(
                            "Failed to update execution status even with new session",
                            execution_id=str(execution_id),
                            error=str(retry_error),
                        )
                else:
                    self.logger.error(
                        "Failed to update execution status",
                        execution_id=str(execution_id),
                        error=str(update_error),
                    )

            raise WorkflowError(f"Editorial analysis workflow failed: {e}") from e
        
        finally:
            # Clean up execution context
            clear_execution_context()
            self._current_execution_id = None

    async def run_competitor_search(
        self,
        domain: str,
        max_competitors: int = 100,
        execution_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Run competitor search workflow with full traceability.

        Args:
            domain: Domain to find competitors for
            max_competitors: Maximum number of competitors to return
            execution_id: Optional execution ID (if None, creates new)

        Returns:
            Workflow execution result with competitors

        Raises:
            WorkflowError: If workflow fails
        """
        workflow_start_time = time.time()
        
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

        # Set execution context for logging
        self._current_execution_id = execution_id
        set_execution_context(execution_id=execution_id, agent_name=self.AGENT_NAME)
        self.audit.set_execution(execution_id)

        try:
            # Transition to running
            await update_workflow_execution(
                self.db_session,
                execution,
                status="running",
            )
            
            # Log workflow start
            await self._log_audit(
                action="workflow_start",
                status="info",
                message=f"Starting competitor search for {domain}",
                details={"domain": domain, "max_competitors": max_competitors},
            )
            self.logger.info("Competitor search started", execution_id=str(execution_id), domain=domain)

            # Run competitor search
            self._start_step_timer("searching")
            await self._send_progress(execution_id, "searching", 30, f"Searching competitors for {domain}...")
            await self._log_audit("step_start", "info", "Searching for competitors", step_name="searching")
            
            complete_results = await self.competitor_agent.execute(
                execution_id=execution_id,
                input_data={
                    "domain": domain,
                    "max_competitors": max_competitors,
                },
                db_session=self.db_session,
            )
            
            searching_duration = self._get_step_duration("searching")
            competitors = complete_results.get("competitors", [])
            total_found = complete_results.get("total_found", 0)
            total_evaluated = complete_results.get("total_evaluated", 0)
            
            await self._record_step_metrics(
                "searching",
                searching_duration,
                additional_metrics=[
                    {"metric_type": "competitors_found", "metric_value": len(competitors), "metric_unit": "competitors"},
                    {"metric_type": "total_candidates", "metric_value": total_found, "metric_unit": "candidates"},
                    {"metric_type": "candidates_evaluated", "metric_value": total_evaluated, "metric_unit": "candidates"},
                ],
            )
            await self._log_audit(
                "step_complete",
                "success",
                f"Found {len(competitors)} competitors from {total_found} candidates",
                step_name="searching",
                details={
                    "competitors_found": len(competitors),
                    "total_candidates": total_found,
                    "duration_seconds": searching_duration,
                },
            )
            
            await self._send_progress(execution_id, "validating", 80, "Validating and ranking competitors...")

            # Update execution with complete results
            await self._send_progress(execution_id, "completing", 95, "Finalizing competitor search...")
            
            workflow_duration = time.time() - workflow_start_time
            await update_workflow_execution(
                self.db_session,
                execution,
                status="completed",
                output_data=complete_results,
                was_success=True,
            )
            
            # Record total workflow metrics
            await self._record_metric("workflow_total_duration", workflow_duration, "seconds")
            await self._log_audit(
                "workflow_complete",
                "success",
                f"Competitor search completed for {domain}",
                details={
                    "competitors_found": len(competitors),
                    "duration_seconds": workflow_duration,
                },
            )
            
            await self._send_progress(
                execution_id, "complete", 100,
                f"Found {len(competitors)} competitors",
                status="completed"
            )

            self.logger.info(
                "Competitor search completed",
                execution_id=str(execution_id),
                domain=domain,
                competitors_found=len(competitors),
                duration_seconds=workflow_duration,
            )

            return {
                "execution_id": str(execution_id),
                "status": "completed",
                **complete_results,
            }

        except Exception as e:
            workflow_duration = time.time() - workflow_start_time
            error_message = str(e)
            error_traceback = traceback.format_exc()
            
            # Log the error with full traceback
            self.logger.error(
                "Competitor search failed",
                execution_id=str(execution_id),
                domain=domain,
                error=error_message,
                traceback=error_traceback,
            )
            
            # Create audit log for the error
            await self._log_audit_error(
                action="workflow_failed",
                error=e,
                details={
                    "domain": domain,
                    "duration_seconds": workflow_duration,
                },
            )
            
            # Record failure metric
            await self._record_metric("workflow_failed_duration", workflow_duration, "seconds")

            try:
                await update_workflow_execution(
                    self.db_session,
                    execution,
                    status="failed",
                    error_message=f"{error_message}\n\nTraceback:\n{error_traceback}",
                    was_success=False,
                )
                await self._send_progress(
                    execution_id, "error", 0, f"Workflow failed: {error_message}", status="failed"
                )
            except (RuntimeError, Exception) as update_error:
                # If session is invalid, try to create a new session for updating
                if "session is invalid" in str(update_error) or "connection" in str(update_error).lower():
                    try:
                        from python_scripts.database.db_session import AsyncSessionLocal
                        async with AsyncSessionLocal() as new_session:
                            # Re-fetch execution with new session
                            execution = await get_workflow_execution(new_session, execution_id)
                            if execution:
                                await update_workflow_execution(
                                    new_session,
                                    execution,
                                    status="failed",
                                    error_message=f"{error_message}\n\nTraceback:\n{error_traceback}",
                                    was_success=False,
                                )
                    except Exception as retry_error:
                        self.logger.error(
                            "Failed to update execution status even with new session",
                            execution_id=str(execution_id),
                            error=str(retry_error),
                        )
                else:
                    self.logger.error(
                        "Failed to update execution status",
                        execution_id=str(execution_id),
                        error=str(update_error),
                    )

            raise WorkflowError(f"Competitor search workflow failed: {e}") from e
        
        finally:
            # Clean up execution context
            clear_execution_context()
            self._current_execution_id = None


