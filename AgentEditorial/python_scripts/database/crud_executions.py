"""CRUD operations for WorkflowExecution and SiteAnalysisResult models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import SiteAnalysisResult, WorkflowExecution
from python_scripts.database.crud_topics import make_json_serializable
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


# WorkflowExecution CRUD

async def create_workflow_execution(
    db_session: AsyncSession,
    workflow_type: str,
    input_data: Optional[Dict[str, Any]] = None,
    status: str = "pending",
    parent_execution_id: Optional[UUID] = None,
) -> WorkflowExecution:
    """
    Create a new workflow execution.

    Args:
        db_session: Database session
        workflow_type: Type of workflow (e.g., "editorial_analysis")
        input_data: Input data for the workflow
        status: Initial status (default: "pending")
        parent_execution_id: Optional parent execution ID

    Returns:
        Created WorkflowExecution instance
    """
    execution = WorkflowExecution(
        execution_id=uuid4(),
        workflow_type=workflow_type,
        status=status,
        input_data=input_data or {},
        parent_execution_id=parent_execution_id,
        start_time=datetime.now(timezone.utc) if status == "running" else None,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    logger.info(
        "Workflow execution created",
        execution_id=str(execution.execution_id),
        workflow_type=workflow_type,
    )
    return execution


async def get_workflow_execution(
    db_session: AsyncSession,
    execution_id: UUID,
) -> Optional[WorkflowExecution]:
    """
    Get workflow execution by ID.

    Args:
        db_session: Database session
        execution_id: Execution UUID

    Returns:
        WorkflowExecution if found, None otherwise
    """
    result = await db_session.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.execution_id == execution_id,
            WorkflowExecution.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def update_workflow_execution(
    db_session: AsyncSession,
    execution: WorkflowExecution,
    status: Optional[str] = None,
    output_data: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    was_success: Optional[bool] = None,
) -> WorkflowExecution:
    """
    Update workflow execution.

    Args:
        db_session: Database session
        execution: WorkflowExecution instance to update
        status: New status
        output_data: Output data
        error_message: Error message if failed
        was_success: Whether execution was successful

    Returns:
        Updated WorkflowExecution instance
    """
    if status:
        execution.status = status
        if status == "running" and not execution.start_time:
            execution.start_time = datetime.now(timezone.utc)
        elif status in ("completed", "failed"):
            execution.end_time = datetime.now(timezone.utc)
            if execution.start_time:
                delta = execution.end_time - execution.start_time
                execution.duration_seconds = int(delta.total_seconds())

    if output_data is not None:
        # Ensure output_data is JSON-serializable (handle infinity, NaN, etc.)
        execution.output_data = make_json_serializable(output_data)

    if error_message is not None:
        execution.error_message = error_message

    if was_success is not None:
        execution.was_success = was_success

    await db_session.commit()
    await db_session.refresh(execution)
    logger.info(
        "Workflow execution updated",
        execution_id=str(execution.execution_id),
        status=execution.status,
    )
    return execution


# SiteAnalysisResult CRUD

async def create_site_analysis_result(
    db_session: AsyncSession,
    site_profile_id: int,
    execution_id: UUID,
    analysis_phase: str,
    phase_results: Dict[str, Any],
    llm_model_used: Optional[str] = None,
    processing_time_seconds: Optional[int] = None,
) -> SiteAnalysisResult:
    """
    Create a new site analysis result.

    Args:
        db_session: Database session
        site_profile_id: Site profile ID
        execution_id: Execution UUID
        analysis_phase: Phase name (e.g., "llama3_analysis", "synthesis")
        phase_results: Results for this phase
        llm_model_used: LLM model used (if applicable)
        processing_time_seconds: Processing time in seconds

    Returns:
        Created SiteAnalysisResult instance
    """
    # Import here to avoid circular dependency
    from python_scripts.utils.json_utils import normalize_json_dict
    
    # Normalize phase_results to ensure all JSON strings are parsed
    normalized_results = normalize_json_dict(phase_results) if isinstance(phase_results, dict) else phase_results
    
    result = SiteAnalysisResult(
        site_profile_id=site_profile_id,
        execution_id=execution_id,
        analysis_phase=analysis_phase,
        phase_results=normalized_results,
        llm_model_used=llm_model_used,
        processing_time_seconds=processing_time_seconds,
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(result)
    logger.info(
        "Site analysis result created",
        site_profile_id=site_profile_id,
        execution_id=str(execution_id),
        phase=analysis_phase,
    )
    return result


async def get_analysis_results_by_execution(
    db_session: AsyncSession,
    execution_id: UUID,
) -> List[SiteAnalysisResult]:
    """
    Get all analysis results for an execution.

    Args:
        db_session: Database session
        execution_id: Execution UUID

    Returns:
        List of SiteAnalysisResult instances
    """
    result = await db_session.execute(
        select(SiteAnalysisResult).where(
            SiteAnalysisResult.execution_id == execution_id,
            SiteAnalysisResult.is_valid == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def get_analysis_results_by_profile(
    db_session: AsyncSession,
    site_profile_id: int,
) -> List[SiteAnalysisResult]:
    """
    Get all analysis results for a site profile.

    Args:
        db_session: Database session
        site_profile_id: Site profile ID

    Returns:
        List of SiteAnalysisResult instances
    """
    result = await db_session.execute(
        select(SiteAnalysisResult).where(
            SiteAnalysisResult.site_profile_id == site_profile_id,
            SiteAnalysisResult.is_valid == True,  # noqa: E712
        )
        .order_by(SiteAnalysisResult.created_at.desc())
    )
    return list(result.scalars().all())

