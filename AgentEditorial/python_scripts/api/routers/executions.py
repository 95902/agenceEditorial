"""API router for execution tracking endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.responses import ExecutionResponse, ErrorResponse
from python_scripts.database.crud_executions import get_workflow_execution
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get(
    "/{execution_id}",
    response_model=ExecutionResponse,
    summary="Get execution status",
    description="Get the status of a workflow execution by ID.",
)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Get workflow execution status.

    Args:
        execution_id: Execution UUID
        db: Database session

    Returns:
        Execution response with status

    Raises:
        HTTPException: If execution not found
    """
    execution = await get_workflow_execution(db, execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}",
        )

    # Calculate estimated duration if running
    estimated_duration = None
    if execution.status == "running" and execution.start_time:
        from datetime import datetime, timezone

        elapsed = datetime.now(timezone.utc) - execution.start_time
        # Rough estimate: 2 minutes per page
        if execution.input_data and "max_pages" in execution.input_data:
            max_pages = execution.input_data["max_pages"]
            estimated_duration = max_pages * 2  # minutes
        else:
            estimated_duration = int(elapsed.total_seconds() / 60) + 5  # Add buffer

    return ExecutionResponse(
        execution_id=execution.execution_id,
        status=execution.status,
        start_time=execution.start_time,
        estimated_duration_minutes=estimated_duration,
    )

