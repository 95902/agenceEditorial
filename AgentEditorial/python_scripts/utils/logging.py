"""Structured logging setup using structlog with audit context support."""

import logging
import sys
from contextvars import ContextVar
from typing import Any, Optional
from uuid import UUID

import structlog
from structlog.types import EventDict, Processor

from python_scripts.config.settings import settings


# Context variables for audit logging
_execution_id_ctx: ContextVar[Optional[str]] = ContextVar("execution_id", default=None)
_agent_name_ctx: ContextVar[Optional[str]] = ContextVar("agent_name", default=None)
_step_name_ctx: ContextVar[Optional[str]] = ContextVar("step_name", default=None)


def set_execution_context(
    execution_id: Optional[UUID] = None,
    agent_name: Optional[str] = None,
    step_name: Optional[str] = None,
) -> None:
    """
    Set the current execution context for structured logging.

    Args:
        execution_id: Current workflow execution ID
        agent_name: Current agent name
        step_name: Current step name
    """
    if execution_id is not None:
        _execution_id_ctx.set(str(execution_id))
    if agent_name is not None:
        _agent_name_ctx.set(agent_name)
    if step_name is not None:
        _step_name_ctx.set(step_name)


def clear_execution_context() -> None:
    """Clear the current execution context."""
    _execution_id_ctx.set(None)
    _agent_name_ctx.set(None)
    _step_name_ctx.set(None)


def get_execution_context() -> dict[str, Optional[str]]:
    """
    Get the current execution context.

    Returns:
        Dict with execution_id, agent_name, step_name
    """
    return {
        "execution_id": _execution_id_ctx.get(),
        "agent_name": _agent_name_ctx.get(),
        "step_name": _step_name_ctx.get(),
    }


def add_execution_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add execution context to log entries if available."""
    execution_id = _execution_id_ctx.get()
    agent_name = _agent_name_ctx.get()
    step_name = _step_name_ctx.get()

    if execution_id and "execution_id" not in event_dict:
        event_dict["execution_id"] = execution_id
    if agent_name and "agent_name" not in event_dict:
        event_dict["agent_name"] = agent_name
    if step_name and "step_name" not in event_dict:
        event_dict["step_name"] = step_name

    return event_dict


def setup_logging() -> None:
    """Configure structured logging."""
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    # Configure structlog
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_execution_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(),
            ]
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class AuditLogger:
    """
    Logger for audit events with automatic context tracking.
    
    Usage:
        audit = AuditLogger("my_agent")
        audit.set_execution(execution_id)
        audit.log_step_start("crawling", "Starting to crawl pages")
        audit.log_step_complete("crawling", "Crawled 50 pages", details={"pages": 50})
        audit.log_error("crawling", error, "Failed to crawl")
    """

    def __init__(self, agent_name: str) -> None:
        """Initialize audit logger for an agent."""
        self.agent_name = agent_name
        self.logger = get_logger(f"audit.{agent_name}")
        self.execution_id: Optional[UUID] = None

    def set_execution(self, execution_id: UUID) -> None:
        """Set the current execution ID."""
        self.execution_id = execution_id
        set_execution_context(execution_id=execution_id, agent_name=self.agent_name)

    def set_step(self, step_name: str) -> None:
        """Set the current step name."""
        set_execution_context(step_name=step_name)

    def log_step_start(
        self,
        step_name: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        """Log the start of a workflow step."""
        set_execution_context(step_name=step_name)
        self.logger.info(
            "step_started",
            action="step_start",
            step=step_name,
            message=message,
            details=details or {},
        )

    def log_step_complete(
        self,
        step_name: str,
        message: str,
        details: Optional[dict] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Log the completion of a workflow step."""
        self.logger.info(
            "step_completed",
            action="step_complete",
            step=step_name,
            message=message,
            details=details or {},
            duration_seconds=duration_seconds,
        )

    def log_step_warning(
        self,
        step_name: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        """Log a warning during a workflow step."""
        self.logger.warning(
            "step_warning",
            action="step_warning",
            step=step_name,
            message=message,
            details=details or {},
        )

    def log_error(
        self,
        step_name: str,
        error: Exception,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log an error during a workflow step."""
        self.logger.error(
            "step_error",
            action="step_error",
            step=step_name,
            message=message or str(error),
            error_type=type(error).__name__,
            error_message=str(error),
            details=details or {},
            exc_info=True,
        )

    def log_workflow_start(self, workflow_type: str, input_data: Optional[dict] = None) -> None:
        """Log the start of a workflow."""
        self.logger.info(
            "workflow_started",
            action="workflow_start",
            workflow_type=workflow_type,
            input_data=input_data or {},
        )

    def log_workflow_complete(
        self,
        workflow_type: str,
        output_summary: Optional[dict] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Log the completion of a workflow."""
        self.logger.info(
            "workflow_completed",
            action="workflow_complete",
            workflow_type=workflow_type,
            output_summary=output_summary or {},
            duration_seconds=duration_seconds,
        )

    def log_workflow_failed(
        self,
        workflow_type: str,
        error: Exception,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Log a workflow failure."""
        self.logger.error(
            "workflow_failed",
            action="workflow_failed",
            workflow_type=workflow_type,
            error_type=type(error).__name__,
            error_message=str(error),
            duration_seconds=duration_seconds,
            exc_info=True,
        )

