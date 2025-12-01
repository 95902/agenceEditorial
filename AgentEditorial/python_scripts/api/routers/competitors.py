"""API router for competitor search endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_competitor import CompetitorSearchAgent
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import CompetitorSearchRequest
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
            results = workflow_result.get("competitors", [])

            # Get execution again (in case it was updated by orchestrator)
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                # Store results in execution output_data
                output_data = {
                    "competitors": results,
                    "total_found": len(results),
                    "domain": domain,
                }

                # Update execution with results
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="completed",
                    output_data=output_data,
                )

            logger.info(
                "Competitor search completed",
                execution_id=str(execution_id),
                domain=domain,
                competitors_found=len(results),
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
    description="Start a competitor search workflow for a domain. Returns execution_id for polling.",
)
async def search_competitors(
    request: CompetitorSearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start competitor search for a domain.

    Args:
        request: Search request with domain and max_competitors
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id
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
        competitors = [
            CompetitorResponse(
                domain=comp.get("domain", ""),
                relevance_score=comp.get("relevance_score", 0.0),
                confidence_score=comp.get("confidence_score", 0.0),
                metadata={
                    "reason": comp.get("reason", ""),
                    "combined_score": comp.get("combined_score", 0.0),
                },
            )
            for comp in competitors_data
        ]

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

