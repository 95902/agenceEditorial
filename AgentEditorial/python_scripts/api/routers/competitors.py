"""API router for competitor search endpoints."""

import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.competitor.agent import CompetitorSearchAgent
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import (
    CompetitorSearchRequest,
    CompetitorValidationRequest,
)
from python_scripts.api.schemas.responses import (
    CompetitorListResponse,
    CompetitorResponse,
    ErrorResponse,
    ExecutionResponse,
)
from python_scripts.database.crud_executions import (
    create_workflow_execution,
    get_workflow_execution,
    update_workflow_execution,
)
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/competitors", tags=["competitors"])


async def auto_validate_competitors(
    db_session: AsyncSession,
    domain: str,
    execution,
) -> None:
    """
    Automatically validate all competitors found in a search execution.
    
    This function marks all competitors as validated=True by default,
    allowing them to be scraped without manual validation.
    
    Args:
        db_session: Database session
        domain: Domain name
        execution: WorkflowExecution object with search results
    """
    try:
        if not execution or not execution.output_data:
            logger.warning(
                "Cannot auto-validate: no execution data",
                domain=domain,
            )
            return
        
        competitors = execution.output_data.get("competitors", [])
        if not competitors:
            logger.info(
                "No competitors to validate",
                domain=domain,
            )
            return
        
        # Auto-validate all competitors (mark as validated=True)
        validated_competitors = []
        for comp in competitors:
            validated_comp = comp.copy()
            
            # Mark as validated unless explicitly excluded
            if not comp.get("excluded", False):
                validated_comp["validation_status"] = "validated"
                validated_comp["validated"] = True
                validated_comp["manual"] = False
                validated_comp["excluded"] = False
            else:
                # Keep excluded status
                validated_comp["validation_status"] = "excluded"
                validated_comp["validated"] = False
                validated_comp["manual"] = False
                validated_comp["excluded"] = True
            
            validated_competitors.append(validated_comp)
        
        # Update execution output_data with validation flags
        updated_output_data = execution.output_data.copy()
        updated_output_data["competitors"] = validated_competitors
        updated_output_data["validation_date"] = time.time()
        updated_output_data["auto_validated"] = True  # Flag to indicate auto-validation
        
        # Update execution
        from python_scripts.database.crud_executions import update_workflow_execution
        
        await update_workflow_execution(
            db_session,
            execution,
            output_data=updated_output_data,
        )
        
        validated_count = sum(1 for c in validated_competitors if c.get("validated", False))
        excluded_count = sum(1 for c in validated_competitors if c.get("excluded", False))
        
        logger.info(
            "Competitors auto-validated",
            domain=domain,
            total=len(validated_competitors),
            validated=validated_count,
            excluded=excluded_count,
        )
        
    except Exception as e:
        logger.error(
            "Failed to auto-validate competitors",
            domain=domain,
            error=str(e),
        )
        # Don't raise - validation failure shouldn't break the search


async def run_competitor_search_background(
    domain: str,
    max_competitors: int,
    execution_id: UUID,
) -> None:
    """
    Background task to run competitor search.

    Args:
        domain: Domain to find competitors for
        max_competitors: Maximum number of competitors
        execution_id: Execution ID
    """
    try:
        from python_scripts.database.db_session import AsyncSessionLocal

        # Create new session for background task
        async with AsyncSessionLocal() as db_session:
            # Get execution object
            from python_scripts.database.crud_executions import get_workflow_execution

            execution = await get_workflow_execution(db_session, execution_id)
            if not execution:
                logger.error("Execution not found", execution_id=str(execution_id))
                return

            # Update execution status to running
            await update_workflow_execution(
                db_session,
                execution,
                status="running",
            )

            # Run competitor search using orchestrator
            from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator

            orchestrator = EditorialAnalysisOrchestrator(db_session)
            workflow_result = await orchestrator.run_competitor_search(
                domain=domain,
                max_competitors=max_competitors,
                execution_id=execution_id,
            )
            
            # The orchestrator already saves complete output_data via execute()
            # Just get the results for logging
            results = workflow_result.get("competitors", [])

            logger.info(
                "Competitor search completed",
                execution_id=str(execution_id),
                domain=domain,
                competitors_found=len(results),
            )
            
            # Auto-validate all competitors found
            # Reload execution to get latest output_data
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                await auto_validate_competitors(
                    db_session,
                    domain,
                    execution,
                )
                logger.info(
                    "Auto-validation completed",
                    execution_id=str(execution_id),
                    domain=domain,
                )

    except Exception as e:
        logger.error(
            "Background competitor search failed",
            execution_id=str(execution_id),
            domain=domain,
            error=str(e),
        )
        # Update execution status to failed
        try:
            from python_scripts.database.db_session import AsyncSessionLocal
            from python_scripts.database.crud_executions import get_workflow_execution

            async with AsyncSessionLocal() as db_session:
                execution = await get_workflow_execution(db_session, execution_id)
                if execution:
                    await update_workflow_execution(
                        db_session,
                        execution,
                        status="failed",
                        error_message=str(e),
                    )
        except Exception:
            pass


@router.post(
    "/search",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start competitor search",
    description="""
    Start a competitor search workflow for a domain.
    
    This endpoint:
    1. Searches competitors using multiple sources (Tavily, DuckDuckGo)
    2. Filters and validates candidates using LLM classification
    3. Ranks competitors by relevance and confidence scores
    4. **Automatically validates all found competitors** (validated=True)
    5. Returns validated competitors with metadata
    
    **Note**: All competitors are automatically validated after the search completes.
    You no longer need to call POST /api/v1/competitors/{domain}/validate separately.
    
    Use the execution_id to:
    - Poll status: GET /api/v1/executions/{execution_id}
    - Stream progress: WebSocket /api/v1/executions/{execution_id}/stream
    - Get results: GET /api/v1/competitors/{domain}
    """,
    responses={
        202: {
            "description": "Competitor search started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "pending",
                        "start_time": None,
                        "estimated_duration_minutes": 8,
                    }
                }
            }
        }
    },
)
async def search_competitors(
    request: CompetitorSearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start competitor search for a domain.

    This workflow identifies competitors by:
    - Multi-source search (Tavily API, DuckDuckGo, web crawling)
    - LLM-based filtering to remove false positives
    - Relevance scoring and ranking
    - Validation and deduplication
    - **Automatic validation**: All found competitors are automatically marked as validated=True

    **Important**: After the search completes, all competitors are automatically validated.
    You can immediately use them for scraping without calling the validate endpoint.

    Args:
        request: Search request with domain and max_competitors (3-100)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id for tracking

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/competitors/search" \\
          -H "Content-Type: application/json" \\
          -d '{"domain": "innosys.fr", "max_competitors": 100}'
        ```

        Response:
        ```json
        {
            "execution_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "pending",
            "start_time": null,
            "estimated_duration_minutes": 8
        }
        ```
    """
    try:
        # Create execution record
        execution = await create_workflow_execution(
            db,
            workflow_type="competitor_search",
            input_data={
                "domain": request.domain,
                "max_competitors": request.max_competitors,
            },
            status="pending",
        )

        # Start background task
        background_tasks.add_task(
            run_competitor_search_background,
            request.domain,
            request.max_competitors,
            execution.execution_id,
        )

        logger.info(
            "Competitor search started",
            execution_id=str(execution.execution_id),
            domain=request.domain,
        )

        return ExecutionResponse(
            execution_id=execution.execution_id,
            status="pending",
            start_time=execution.start_time,
        )

    except Exception as e:
        logger.error("Failed to start competitor search", domain=request.domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start competitor search: {e}",
        )


@router.get(
    "/{domain}",
    response_model=CompetitorListResponse,
    summary="Get competitors for a domain",
    description="Get the list of competitors found for a domain from the latest search.",
)
async def get_competitors(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> CompetitorListResponse:
    """
    Get competitors for a domain from the latest search execution.

    Args:
        domain: Domain name
        db: Database session

    Returns:
        List of competitors

    Raises:
        HTTPException: If no competitors found
    """
    try:
        from sqlalchemy import select, desc

        from python_scripts.database.models import WorkflowExecution

        # Find latest completed competitor search for this domain
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
            )
            .order_by(desc(WorkflowExecution.start_time))
            .limit(1)
        )

        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution or not execution.output_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No competitor search results found for domain: {domain}",
            )

        # Extract competitors from output_data
        competitors_data = execution.output_data.get("competitors", [])
        if not competitors_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No competitors found for domain: {domain}",
            )

        # Convert to response format
        competitors = []
        for comp in competitors_data:
            # Ensure scores are not None
            relevance_score = comp.get("relevance_score")
            if relevance_score is None:
                relevance_score = 0.0
            else:
                relevance_score = float(relevance_score)
            
            confidence_score = comp.get("confidence_score")
            if confidence_score is None:
                confidence_score = 0.0
            else:
                confidence_score = float(confidence_score)
            
            competitors.append(
                CompetitorResponse(
                    domain=comp.get("domain", ""),
                    relevance_score=relevance_score,
                    confidence_score=confidence_score,
                    metadata={
                        "reason": comp.get("reason", ""),
                        "combined_score": comp.get("combined_score", 0.0),
                    },
                )
            )

        return CompetitorListResponse(
            competitors=competitors,
            total=len(competitors),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get competitors", domain=domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get competitors: {e}",
        )


@router.post(
    "/{domain}/validate",
    response_model=CompetitorListResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and adjust competitor list",
    description="Validate or adjust the competitor list for a domain. Mark competitors as validated, manual, or excluded.",
)
async def validate_competitors(
    domain: str,
    request: CompetitorValidationRequest,
    db: AsyncSession = Depends(get_db),
) -> CompetitorListResponse:
    """
    Validate and adjust competitor list for a domain (T089-T092 - US4).

    Args:
        domain: Domain name
        request: Validation request with competitor list and flags
        db: Database session

    Returns:
        Updated competitor list

    Raises:
        HTTPException: If no competitor search found or validation fails
    """
    try:
        from sqlalchemy import select, desc

        from python_scripts.database.models import WorkflowExecution

        # Find latest completed competitor search for this domain
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "competitor_search",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
            )
            .order_by(desc(WorkflowExecution.start_time))
            .limit(1)
        )

        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution or not execution.output_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No competitor search results found for domain: {domain}",
            )

        # Get existing competitors
        existing_competitors = execution.output_data.get("competitors", [])
        all_candidates = execution.output_data.get("all_candidates", [])

        # Create domain mapping for quick lookup (normalize domains to lowercase for comparison)
        competitor_map = {comp.get("domain", "").lower(): comp for comp in existing_competitors}
        candidate_map = {cand.get("domain", "").lower(): cand for cand in all_candidates}

        # Collect domains from request for quick lookup
        requested_domains = set()
        for comp_data in request.competitors:
            comp_domain = comp_data.get("domain")
            if comp_domain:
                requested_domains.add(comp_domain.lower())

        # Process validation request
        validated_competitors = []
        processed_domains = set()

        # Process competitors from request
        for comp_data in request.competitors:
            comp_domain = comp_data.get("domain")
            if not comp_domain:
                continue

            comp_domain_lower = comp_domain.lower()
            processed_domains.add(comp_domain_lower)

            # Get competitor data (from existing or candidates)
            competitor = competitor_map.get(comp_domain_lower) or candidate_map.get(comp_domain_lower)
            if not competitor:
                # New manual competitor
                competitor = {
                    "domain": comp_domain,
                    "url": comp_data.get("url", f"https://{comp_domain}"),
                    "title": comp_data.get("title", ""),
                    "reason": comp_data.get("reason", "Manually added"),
                    "source": "manual",
                    "relevance_score": comp_data.get("relevance_score", 0.5),
                    "confidence_score": comp_data.get("confidence_score", 0.5),
                    "combined_score": comp_data.get("combined_score", 0.5),
                }

            # Apply validation flags
            validation_status = comp_data.get("validation_status", "validated")
            competitor["validation_status"] = validation_status
            competitor["validated"] = validation_status == "validated"
            competitor["manual"] = validation_status == "manual"
            competitor["excluded"] = validation_status == "excluded"

            # Only include validated and manual competitors
            if validation_status in ["validated", "manual"]:
                validated_competitors.append(competitor)

        # Preserve existing competitors that were NOT in the request
        # (they are kept as validated by default since they were already in the list)
        for existing_comp in existing_competitors:
            existing_domain = existing_comp.get("domain", "").lower()
            if existing_domain not in processed_domains:
                # Not in request, preserve it as validated
                # Create a copy to avoid modifying the original dict
                preserved_comp = existing_comp.copy()
                preserved_comp["validation_status"] = "validated"
                preserved_comp["validated"] = True
                preserved_comp["manual"] = False
                preserved_comp["excluded"] = False
                validated_competitors.append(preserved_comp)

        # Update execution output_data with validation flags
        updated_output_data = execution.output_data.copy()
        updated_output_data["competitors"] = validated_competitors
        updated_output_data["validation_date"] = time.time()

        # Update execution
        from python_scripts.database.crud_executions import update_workflow_execution

        await update_workflow_execution(
            db,
            execution,
            output_data=updated_output_data,
        )

        logger.info(
            "Competitors validated",
            domain=domain,
            validated_count=len(validated_competitors),
        )

        # Convert to response format
        competitors = []
        for comp in validated_competitors:
            # Ensure scores are not None
            relevance_score = comp.get("relevance_score")
            if relevance_score is None:
                relevance_score = 0.0
            else:
                relevance_score = float(relevance_score)
            
            confidence_score = comp.get("confidence_score")
            if confidence_score is None:
                confidence_score = 0.0
            else:
                confidence_score = float(confidence_score)
            
            competitors.append(
                CompetitorResponse(
                    domain=comp.get("domain", ""),
                    relevance_score=relevance_score,
                    confidence_score=confidence_score,
                    metadata={
                        "reason": comp.get("reason", ""),
                        "combined_score": comp.get("combined_score", 0.0),
                        "validation_status": comp.get("validation_status", "validated"),
                        "validated": comp.get("validated", False),
                        "manual": comp.get("manual", False),
                        "excluded": comp.get("excluded", False),
                    },
                )
            )

        return CompetitorListResponse(
            competitors=competitors,
            total=len(competitors),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate competitors", domain=domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate competitors: {e}",
        )

