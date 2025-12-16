"""CRUD operations for WorkflowExecution, SiteAnalysisResult, AuditLog and PerformanceMetric models."""

import traceback
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError

from python_scripts.database.models import (
    AuditLog,
    PerformanceMetric,
    SiteAnalysisResult,
    WorkflowExecution,
)
from python_scripts.utils.json_utils import make_json_serializable
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def _is_session_valid(session: AsyncSession) -> bool:
    """
    Check if a database session is still valid.
    
    Args:
        session: Database session to check
        
    Returns:
        True if session is valid, False otherwise
    """
    try:
        # Check if session is active and bound
        return session.is_active and session.bind is not None
    except Exception:
        return False


async def _safe_commit(session: AsyncSession) -> bool:
    """
    Safely commit a session, handling connection errors.
    
    Args:
        session: Database session to commit
        
    Returns:
        True if commit succeeded, False otherwise
    """
    if not _is_session_valid(session):
        return False
    
    try:
        await session.commit()
        return True
    except (DisconnectionError, InterfaceError, OperationalError) as e:
        # Check if it's a connection-related error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist"]):
            logger.warning("Database connection error during commit", error=str(e))
            try:
                if _is_session_valid(session):
                    await session.rollback()
            except Exception:
                pass
            return False
        # Re-raise if it's not a connection error
        raise
    except Exception as e:
        error_str = str(e).lower()
        # Check if it's a connection-related error
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist"]):
            logger.warning("Database connection error during commit", error=str(e))
            try:
                if _is_session_valid(session):
                    await session.rollback()
            except Exception:
                pass
            return False
        # Re-raise if it's not a connection error
        raise


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
    if not _is_session_valid(db_session):
        raise RuntimeError("Database session is invalid")
    
    execution = WorkflowExecution(
        execution_id=uuid4(),
        workflow_type=workflow_type,
        status=status,
        input_data=input_data or {},
        parent_execution_id=parent_execution_id,
        start_time=datetime.now(timezone.utc) if status == "running" else None,
    )
    try:
        db_session.add(execution)
        if not await _safe_commit(db_session):
            raise RuntimeError("Failed to commit workflow execution")
        await db_session.refresh(execution)
        logger.info(
            "Workflow execution created",
            execution_id=str(execution.execution_id),
            workflow_type=workflow_type,
        )
        return execution
    except (DisconnectionError, InterfaceError, OperationalError, RuntimeError) as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist", "session is invalid"]):
            logger.error(
                "Database connection error while creating workflow execution",
                workflow_type=workflow_type,
                error=str(e),
            )
        raise


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

    if not _is_session_valid(db_session):
        logger.warning(
            "Cannot update workflow execution: session is invalid",
            execution_id=str(execution.execution_id),
        )
        raise RuntimeError("Database session is invalid")
    
    try:
        if not await _safe_commit(db_session):
            raise RuntimeError("Failed to commit workflow execution update")
        await db_session.refresh(execution)
        logger.info(
            "Workflow execution updated",
            execution_id=str(execution.execution_id),
            status=execution.status,
        )
        return execution
    except (DisconnectionError, InterfaceError, OperationalError, RuntimeError) as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist", "session is invalid"]):
            logger.error(
                "Database connection error while updating workflow execution",
                execution_id=str(execution.execution_id),
                error=str(e),
            )
        raise


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
    
    if not _is_session_valid(db_session):
        raise RuntimeError("Database session is invalid")
    
    result = SiteAnalysisResult(
        site_profile_id=site_profile_id,
        execution_id=execution_id,
        analysis_phase=analysis_phase,
        phase_results=normalized_results,
        llm_model_used=llm_model_used,
        processing_time_seconds=processing_time_seconds,
    )
    try:
        db_session.add(result)
        if not await _safe_commit(db_session):
            raise RuntimeError("Failed to commit site analysis result")
        await db_session.refresh(result)
        logger.info(
            "Site analysis result created",
            site_profile_id=site_profile_id,
            execution_id=str(execution_id),
            phase=analysis_phase,
        )
        return result
    except (DisconnectionError, InterfaceError, OperationalError, RuntimeError) as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist", "session is invalid"]):
            logger.error(
                "Database connection error while creating site analysis result",
                site_profile_id=site_profile_id,
                execution_id=str(execution_id),
                error=str(e),
            )
        raise


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


# AuditLog CRUD


async def create_audit_log(
    db_session: AsyncSession,
    action: str,
    status: str,
    message: str,
    execution_id: Optional[UUID] = None,
    agent_name: Optional[str] = None,
    step_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error_traceback: Optional[str] = None,
) -> AuditLog:
    """
    Create a new audit log entry.

    Args:
        db_session: Database session
        action: Action being logged (e.g., "workflow_start", "step_complete")
        status: Status of the action (e.g., "success", "error", "info")
        message: Human-readable message
        execution_id: Optional execution UUID
        agent_name: Optional agent name
        step_name: Optional step name
        details: Optional additional details (JSON)
        error_traceback: Optional error traceback

    Returns:
        Created AuditLog instance
    """
    audit_log = AuditLog(
        execution_id=execution_id,
        action=action,
        agent_name=agent_name,
        step_name=step_name,
        status=status,
        message=message,
        details=make_json_serializable(details) if details else None,
        error_traceback=error_traceback,
        timestamp=datetime.now(timezone.utc),
    )
    
    if not _is_session_valid(db_session):
        logger.warning(
            "Cannot create audit log: session is invalid",
            action=action,
            execution_id=str(execution_id) if execution_id else None,
        )
        raise RuntimeError("Database session is invalid")
    
    try:
        db_session.add(audit_log)
        if not await _safe_commit(db_session):
            raise RuntimeError("Failed to commit audit log")
        await db_session.refresh(audit_log)
        logger.debug(
            "Audit log created",
            action=action,
            status=status,
            execution_id=str(execution_id) if execution_id else None,
        )
        return audit_log
    except (DisconnectionError, InterfaceError) as e:
        logger.warning(
            "Database connection error while creating audit log",
            action=action,
            error=str(e),
            execution_id=str(execution_id) if execution_id else None,
        )
        raise
    except Exception as e:
        logger.error(
            "Error creating audit log",
            action=action,
            error=str(e),
            execution_id=str(execution_id) if execution_id else None,
        )
        raise


async def create_audit_log_from_exception(
    db_session: AsyncSession,
    action: str,
    exception: Exception,
    execution_id: Optional[UUID] = None,
    agent_name: Optional[str] = None,
    step_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Create an audit log entry from an exception.

    Args:
        db_session: Database session
        action: Action that failed
        exception: The exception that occurred
        execution_id: Optional execution UUID
        agent_name: Optional agent name
        step_name: Optional step name
        details: Optional additional details

    Returns:
        Created AuditLog instance
    """
    error_tb = traceback.format_exc()
    return await create_audit_log(
        db_session=db_session,
        action=action,
        status="error",
        message=str(exception),
        execution_id=execution_id,
        agent_name=agent_name,
        step_name=step_name,
        details=details,
        error_traceback=error_tb,
    )


async def get_audit_logs_by_execution(
    db_session: AsyncSession,
    execution_id: UUID,
    limit: int = 100,
) -> List[AuditLog]:
    """
    Get all audit logs for an execution.

    Args:
        db_session: Database session
        execution_id: Execution UUID
        limit: Maximum number of logs to return

    Returns:
        List of AuditLog instances
    """
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.execution_id == execution_id)
        .order_by(AuditLog.timestamp.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_recent_audit_logs(
    db_session: AsyncSession,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[AuditLog]:
    """
    Get recent audit logs with optional filters.

    Args:
        db_session: Database session
        agent_name: Optional filter by agent name
        status: Optional filter by status
        limit: Maximum number of logs to return

    Returns:
        List of AuditLog instances
    """
    query = select(AuditLog)
    
    if agent_name:
        query = query.where(AuditLog.agent_name == agent_name)
    if status:
        query = query.where(AuditLog.status == status)
    
    query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
    result = await db_session.execute(query)
    return list(result.scalars().all())


# PerformanceMetric CRUD


async def create_performance_metric(
    db_session: AsyncSession,
    execution_id: UUID,
    metric_type: str,
    metric_value: float,
    metric_unit: Optional[str] = None,
    agent_name: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> PerformanceMetric:
    """
    Create a new performance metric entry.

    Args:
        db_session: Database session
        execution_id: Execution UUID
        metric_type: Type of metric (e.g., "duration_seconds", "tokens_used", "pages_crawled")
        metric_value: Numeric value of the metric
        metric_unit: Optional unit of measurement (e.g., "seconds", "tokens", "pages")
        agent_name: Optional agent name
        additional_data: Optional additional data (JSON)

    Returns:
        Created PerformanceMetric instance
    """
    if not _is_session_valid(db_session):
        logger.warning(
            "Cannot create performance metric: session is invalid",
            execution_id=str(execution_id),
            metric_type=metric_type,
        )
        raise RuntimeError("Database session is invalid")
    
    metric = PerformanceMetric(
        execution_id=execution_id,
        agent_name=agent_name,
        metric_type=metric_type,
        metric_value=Decimal(str(metric_value)),
        metric_unit=metric_unit,
        additional_data=make_json_serializable(additional_data) if additional_data else None,
    )
    try:
        db_session.add(metric)
        if not await _safe_commit(db_session):
            logger.warning(
                "Failed to commit performance metric",
                execution_id=str(execution_id),
                metric_type=metric_type,
            )
            raise RuntimeError("Failed to commit performance metric")
        await db_session.refresh(metric)
        logger.debug(
            "Performance metric created",
            execution_id=str(execution_id),
            metric_type=metric_type,
            metric_value=metric_value,
        )
        return metric
    except (DisconnectionError, InterfaceError, OperationalError, RuntimeError) as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist", "session is invalid"]):
            logger.warning(
                "Database connection error while creating performance metric",
                execution_id=str(execution_id),
                metric_type=metric_type,
                error=str(e),
            )
        raise


async def create_performance_metrics_batch(
    db_session: AsyncSession,
    execution_id: UUID,
    metrics: List[Dict[str, Any]],
    agent_name: Optional[str] = None,
) -> List[PerformanceMetric]:
    """
    Create multiple performance metrics in batch.

    Args:
        db_session: Database session
        execution_id: Execution UUID
        metrics: List of dicts with keys: metric_type, metric_value, metric_unit (optional), additional_data (optional)
        agent_name: Optional agent name

    Returns:
        List of created PerformanceMetric instances
    """
    if not _is_session_valid(db_session):
        logger.warning(
            "Cannot create performance metrics batch: session is invalid",
            execution_id=str(execution_id),
        )
        raise RuntimeError("Database session is invalid")
    
    created_metrics = []
    for m in metrics:
        metric = PerformanceMetric(
            execution_id=execution_id,
            agent_name=agent_name,
            metric_type=m["metric_type"],
            metric_value=Decimal(str(m["metric_value"])),
            metric_unit=m.get("metric_unit"),
            additional_data=make_json_serializable(m.get("additional_data")) if m.get("additional_data") else None,
        )
        db_session.add(metric)
        created_metrics.append(metric)
    
    try:
        if not await _safe_commit(db_session):
            logger.warning(
                "Failed to commit performance metrics batch",
                execution_id=str(execution_id),
            )
            raise RuntimeError("Failed to commit performance metrics batch")
        for metric in created_metrics:
            await db_session.refresh(metric)
        
        logger.debug(
            "Performance metrics batch created",
            execution_id=str(execution_id),
            count=len(created_metrics),
        )
        return created_metrics
    except (DisconnectionError, InterfaceError, OperationalError, RuntimeError) as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "closed", "disconnected", "does not exist", "session is invalid"]):
            logger.warning(
                "Database connection error while creating performance metrics batch",
                execution_id=str(execution_id),
                error=str(e),
            )
        raise


async def get_performance_metrics_by_execution(
    db_session: AsyncSession,
    execution_id: UUID,
) -> List[PerformanceMetric]:
    """
    Get all performance metrics for an execution.

    Args:
        db_session: Database session
        execution_id: Execution UUID

    Returns:
        List of PerformanceMetric instances
    """
    result = await db_session.execute(
        select(PerformanceMetric)
        .where(PerformanceMetric.execution_id == execution_id)
        .order_by(PerformanceMetric.created_at.asc())
    )
    return list(result.scalars().all())


async def get_performance_metrics_summary(
    db_session: AsyncSession,
    execution_id: UUID,
) -> Dict[str, Any]:
    """
    Get a summary of performance metrics for an execution.

    Args:
        db_session: Database session
        execution_id: Execution UUID

    Returns:
        Dict with metric_type as key and summarized values
    """
    metrics = await get_performance_metrics_by_execution(db_session, execution_id)
    summary: Dict[str, Any] = {}
    
    for metric in metrics:
        metric_type = metric.metric_type
        if metric_type not in summary:
            summary[metric_type] = {
                "total": 0,
                "count": 0,
                "unit": metric.metric_unit,
                "values": [],
            }
        summary[metric_type]["total"] += float(metric.metric_value)
        summary[metric_type]["count"] += 1
        summary[metric_type]["values"].append({
            "value": float(metric.metric_value),
            "agent": metric.agent_name,
            "timestamp": metric.created_at.isoformat() if metric.created_at else None,
        })
    
    # Calculate averages
    for metric_type in summary:
        if summary[metric_type]["count"] > 0:
            summary[metric_type]["average"] = (
                summary[metric_type]["total"] / summary[metric_type]["count"]
            )
    
    return summary

