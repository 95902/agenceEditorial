"""Base agent abstract class with audit logging support."""

import time
import traceback
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.utils.logging import AuditLogger, get_logger, set_execution_context


class BaseAgent(ABC):
    """
    Base class for all agents with built-in audit logging and performance tracking.
    
    All agents should inherit from this class and implement the execute() method.
    The base class provides:
    - Structured logging with execution context
    - Audit log creation for workflow steps
    - Performance metric tracking helpers
    - Error handling with stack traces
    """

    def __init__(self, agent_name: str) -> None:
        """
        Initialize agent with logging and audit support.
        
        Args:
            agent_name: Unique name for this agent (used in logs and audits)
        """
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_name}")
        self.audit = AuditLogger(agent_name)
        self._current_execution_id: Optional[UUID] = None
        self._step_timers: Dict[str, float] = {}

    def set_execution_context(self, execution_id: UUID) -> None:
        """
        Set the execution context for this agent.
        
        Args:
            execution_id: The current workflow execution ID
        """
        self._current_execution_id = execution_id
        self.audit.set_execution(execution_id)
        set_execution_context(
            execution_id=execution_id,
            agent_name=self.agent_name,
        )

    @abstractmethod
    async def execute(
        self,
        execution_id: UUID,
        input_data: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute agent workflow.

        Args:
            execution_id: Unique execution ID
            input_data: Input data for the agent
            **kwargs: Additional arguments

        Returns:
            Output data from the agent
        """
        pass

    def log_step(
        self,
        step_name: str,
        status: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a workflow step.
        
        Args:
            step_name: Name of the step
            status: Status (started, completed, error, warning)
            message: Human-readable message
            details: Optional additional details
        """
        self.logger.info(
            "workflow_step",
            step=step_name,
            status=status,
            message=message,
            details=details or {},
        )

    def start_step_timer(self, step_name: str) -> None:
        """
        Start a timer for a step (for performance tracking).
        
        Args:
            step_name: Name of the step
        """
        self._step_timers[step_name] = time.time()
        self.audit.log_step_start(step_name, f"Starting {step_name}")

    def stop_step_timer(
        self,
        step_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Stop a timer for a step and return the duration.
        
        Args:
            step_name: Name of the step
            message: Optional completion message
            details: Optional additional details
            
        Returns:
            Duration in seconds
        """
        start_time = self._step_timers.pop(step_name, None)
        if start_time is None:
            return 0.0
        
        duration = time.time() - start_time
        self.audit.log_step_complete(
            step_name,
            message or f"Completed {step_name}",
            details=details,
            duration_seconds=duration,
        )
        return duration

    @asynccontextmanager
    async def step_context(
        self,
        step_name: str,
        message: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Context manager for tracking a step's execution time and status.
        
        Usage:
            async with self.step_context("crawling") as ctx:
                # do work
                ctx["pages_crawled"] = 50
            # Automatically logs completion with duration
            
        Args:
            step_name: Name of the step
            message: Optional step description
            
        Yields:
            Dict for storing step context/results
        """
        step_data: Dict[str, Any] = {}
        self.start_step_timer(step_name)
        
        try:
            yield step_data
            self.stop_step_timer(
                step_name,
                message=message or f"Completed {step_name}",
                details=step_data if step_data else None,
            )
        except Exception as e:
            duration = time.time() - self._step_timers.pop(step_name, time.time())
            self.audit.log_error(
                step_name,
                e,
                message=f"Failed during {step_name}",
                details={"duration_seconds": duration, **step_data},
            )
            raise

    async def create_audit_log(
        self,
        db_session: AsyncSession,
        action: str,
        status: str,
        message: str,
        step_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """
        Create an audit log entry in the database.
        
        Args:
            db_session: Database session
            action: Action being logged
            status: Status (success, error, info, warning)
            message: Human-readable message
            step_name: Optional step name
            details: Optional additional details
            error: Optional exception for error logs
        """
        from python_scripts.database.crud_executions import (
            create_audit_log,
            create_audit_log_from_exception,
        )
        
        if error:
            await create_audit_log_from_exception(
                db_session=db_session,
                action=action,
                exception=error,
                execution_id=self._current_execution_id,
                agent_name=self.agent_name,
                step_name=step_name,
                details=details,
            )
        else:
            await create_audit_log(
                db_session=db_session,
                action=action,
                status=status,
                message=message,
                execution_id=self._current_execution_id,
                agent_name=self.agent_name,
                step_name=step_name,
                details=details,
            )

    async def record_performance_metric(
        self,
        db_session: AsyncSession,
        metric_type: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a performance metric in the database.
        
        Args:
            db_session: Database session
            metric_type: Type of metric (e.g., "duration_seconds", "pages_crawled")
            metric_value: Numeric value
            metric_unit: Optional unit (e.g., "seconds", "pages")
            additional_data: Optional additional context
        """
        if not self._current_execution_id:
            self.logger.warning(
                "Cannot record metric without execution_id",
                metric_type=metric_type,
            )
            return

        from python_scripts.database.crud_executions import create_performance_metric
        
        await create_performance_metric(
            db_session=db_session,
            execution_id=self._current_execution_id,
            metric_type=metric_type,
            metric_value=metric_value,
            metric_unit=metric_unit,
            agent_name=self.agent_name,
            additional_data=additional_data,
        )

    def format_error_traceback(self, error: Exception) -> str:
        """
        Format an exception's traceback for logging.
        
        Args:
            error: The exception
            
        Returns:
            Formatted traceback string
        """
        return traceback.format_exc()

