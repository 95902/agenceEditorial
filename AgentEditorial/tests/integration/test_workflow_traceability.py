"""Integration tests for workflow traceability (audit logs and performance metrics)."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from python_scripts.database.db_session import Base
from python_scripts.database.models import (
    AuditLog,
    PerformanceMetric,
    WorkflowExecution,
)
from python_scripts.database.crud_executions import (
    create_audit_log,
    create_audit_log_from_exception,
    create_performance_metric,
    create_performance_metrics_batch,
    create_workflow_execution,
    get_audit_logs_by_execution,
    get_performance_metrics_by_execution,
    get_performance_metrics_summary,
    get_recent_audit_logs,
)


@pytest_asyncio.fixture
async def async_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        yield session
    
    await engine.dispose()


@pytest_asyncio.fixture
async def workflow_execution(async_session: AsyncSession) -> WorkflowExecution:
    """Create a test workflow execution."""
    execution = await create_workflow_execution(
        db_session=async_session,
        workflow_type="test_workflow",
        input_data={"domain": "example.com"},
        status="running",
    )
    return execution


class TestAuditLogCRUD:
    """Tests for AuditLog CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_audit_log(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test creating a basic audit log entry."""
        audit_log = await create_audit_log(
            db_session=async_session,
            action="workflow_start",
            status="info",
            message="Starting test workflow",
            execution_id=workflow_execution.execution_id,
            agent_name="test_agent",
            step_name="init",
            details={"domain": "example.com"},
        )
        
        assert audit_log.id is not None
        assert audit_log.action == "workflow_start"
        assert audit_log.status == "info"
        assert audit_log.message == "Starting test workflow"
        assert audit_log.execution_id == workflow_execution.execution_id
        assert audit_log.agent_name == "test_agent"
        assert audit_log.step_name == "init"
        assert audit_log.details == {"domain": "example.com"}
        assert audit_log.error_traceback is None

    @pytest.mark.asyncio
    async def test_create_audit_log_from_exception(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test creating an audit log from an exception."""
        test_error = ValueError("Test error for audit")
        
        try:
            raise test_error
        except ValueError as e:
            audit_log = await create_audit_log_from_exception(
                db_session=async_session,
                action="step_failed",
                exception=e,
                execution_id=workflow_execution.execution_id,
                agent_name="test_agent",
                step_name="processing",
                details={"context": "test"},
            )
        
        assert audit_log.id is not None
        assert audit_log.action == "step_failed"
        assert audit_log.status == "error"
        assert "Test error for audit" in audit_log.message
        assert audit_log.error_traceback is not None
        assert "ValueError" in audit_log.error_traceback

    @pytest.mark.asyncio
    async def test_get_audit_logs_by_execution(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test retrieving audit logs by execution ID."""
        # Create multiple audit logs
        await create_audit_log(
            db_session=async_session,
            action="step_start",
            status="info",
            message="Step 1 started",
            execution_id=workflow_execution.execution_id,
        )
        await create_audit_log(
            db_session=async_session,
            action="step_complete",
            status="success",
            message="Step 1 completed",
            execution_id=workflow_execution.execution_id,
        )
        await create_audit_log(
            db_session=async_session,
            action="step_start",
            status="info",
            message="Step 2 started",
            execution_id=workflow_execution.execution_id,
        )
        
        logs = await get_audit_logs_by_execution(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
        )
        
        assert len(logs) == 3
        # Logs should be ordered by timestamp ascending
        assert logs[0].message == "Step 1 started"
        assert logs[1].message == "Step 1 completed"
        assert logs[2].message == "Step 2 started"

    @pytest.mark.asyncio
    async def test_get_recent_audit_logs_with_filters(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test retrieving recent audit logs with filters."""
        # Create logs with different agents and statuses
        await create_audit_log(
            db_session=async_session,
            action="test",
            status="success",
            message="Success 1",
            agent_name="agent_a",
            execution_id=workflow_execution.execution_id,
        )
        await create_audit_log(
            db_session=async_session,
            action="test",
            status="error",
            message="Error 1",
            agent_name="agent_b",
            execution_id=workflow_execution.execution_id,
        )
        await create_audit_log(
            db_session=async_session,
            action="test",
            status="success",
            message="Success 2",
            agent_name="agent_a",
            execution_id=workflow_execution.execution_id,
        )
        
        # Filter by agent
        agent_a_logs = await get_recent_audit_logs(
            db_session=async_session,
            agent_name="agent_a",
        )
        assert len(agent_a_logs) == 2
        
        # Filter by status
        error_logs = await get_recent_audit_logs(
            db_session=async_session,
            status="error",
        )
        assert len(error_logs) == 1
        assert error_logs[0].message == "Error 1"


class TestPerformanceMetricCRUD:
    """Tests for PerformanceMetric CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_performance_metric(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test creating a single performance metric."""
        metric = await create_performance_metric(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metric_type="duration_seconds",
            metric_value=15.5,
            metric_unit="seconds",
            agent_name="test_agent",
            additional_data={"step": "crawling"},
        )
        
        assert metric.id is not None
        assert metric.execution_id == workflow_execution.execution_id
        assert metric.metric_type == "duration_seconds"
        assert float(metric.metric_value) == 15.5
        assert metric.metric_unit == "seconds"
        assert metric.agent_name == "test_agent"
        assert metric.additional_data == {"step": "crawling"}

    @pytest.mark.asyncio
    async def test_create_performance_metrics_batch(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test creating multiple performance metrics in batch."""
        metrics_data = [
            {
                "metric_type": "pages_crawled",
                "metric_value": 50,
                "metric_unit": "pages",
            },
            {
                "metric_type": "word_count",
                "metric_value": 25000,
                "metric_unit": "words",
            },
            {
                "metric_type": "duration_seconds",
                "metric_value": 120.5,
                "metric_unit": "seconds",
            },
        ]
        
        metrics = await create_performance_metrics_batch(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metrics=metrics_data,
            agent_name="test_agent",
        )
        
        assert len(metrics) == 3
        assert all(m.agent_name == "test_agent" for m in metrics)
        
        metric_types = {m.metric_type for m in metrics}
        assert metric_types == {"pages_crawled", "word_count", "duration_seconds"}

    @pytest.mark.asyncio
    async def test_get_performance_metrics_by_execution(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test retrieving performance metrics by execution."""
        # Create some metrics
        await create_performance_metric(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metric_type="duration",
            metric_value=10.0,
        )
        await create_performance_metric(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metric_type="items",
            metric_value=100.0,
        )
        
        metrics = await get_performance_metrics_by_execution(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
        )
        
        assert len(metrics) == 2

    @pytest.mark.asyncio
    async def test_get_performance_metrics_summary(self, async_session: AsyncSession, workflow_execution: WorkflowExecution):
        """Test getting a summary of performance metrics."""
        # Create multiple metrics of the same type
        await create_performance_metric(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metric_type="step_duration",
            metric_value=5.0,
            metric_unit="seconds",
            agent_name="agent_1",
        )
        await create_performance_metric(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metric_type="step_duration",
            metric_value=10.0,
            metric_unit="seconds",
            agent_name="agent_2",
        )
        await create_performance_metric(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
            metric_type="pages_crawled",
            metric_value=50.0,
            metric_unit="pages",
        )
        
        summary = await get_performance_metrics_summary(
            db_session=async_session,
            execution_id=workflow_execution.execution_id,
        )
        
        assert "step_duration" in summary
        assert summary["step_duration"]["total"] == 15.0
        assert summary["step_duration"]["count"] == 2
        assert summary["step_duration"]["average"] == 7.5
        assert summary["step_duration"]["unit"] == "seconds"
        
        assert "pages_crawled" in summary
        assert summary["pages_crawled"]["total"] == 50.0


class TestWorkflowTraceabilityIntegration:
    """Integration tests for complete workflow traceability."""

    @pytest.mark.asyncio
    async def test_complete_workflow_traceability(self, async_session: AsyncSession):
        """Test a complete workflow with audit logs and metrics."""
        # Create workflow execution
        execution = await create_workflow_execution(
            db_session=async_session,
            workflow_type="editorial_analysis",
            input_data={"domain": "example.com", "max_pages": 50},
            status="running",
        )
        
        # Log workflow start
        await create_audit_log(
            db_session=async_session,
            action="workflow_start",
            status="info",
            message="Starting editorial analysis for example.com",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
            details={"domain": "example.com"},
        )
        
        # Step 1: URL Discovery
        await create_audit_log(
            db_session=async_session,
            action="step_start",
            status="info",
            message="Discovering URLs via sitemap",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
            step_name="discovering",
        )
        
        await create_performance_metric(
            db_session=async_session,
            execution_id=execution.execution_id,
            metric_type="discovering_duration",
            metric_value=2.5,
            metric_unit="seconds",
            agent_name="orchestrator",
        )
        await create_performance_metric(
            db_session=async_session,
            execution_id=execution.execution_id,
            metric_type="urls_discovered",
            metric_value=100,
            metric_unit="urls",
            agent_name="orchestrator",
        )
        
        await create_audit_log(
            db_session=async_session,
            action="step_complete",
            status="success",
            message="Discovered 100 URLs",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
            step_name="discovering",
            details={"urls_count": 100},
        )
        
        # Step 2: Crawling
        await create_audit_log(
            db_session=async_session,
            action="step_start",
            status="info",
            message="Crawling 50 pages",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
            step_name="crawling",
        )
        
        await create_performance_metric(
            db_session=async_session,
            execution_id=execution.execution_id,
            metric_type="crawling_duration",
            metric_value=45.0,
            metric_unit="seconds",
            agent_name="orchestrator",
        )
        await create_performance_metric(
            db_session=async_session,
            execution_id=execution.execution_id,
            metric_type="pages_crawled",
            metric_value=50,
            metric_unit="pages",
            agent_name="orchestrator",
        )
        
        await create_audit_log(
            db_session=async_session,
            action="step_complete",
            status="success",
            message="Crawled 50 pages",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
            step_name="crawling",
            details={"pages_crawled": 50, "duration": 45.0},
        )
        
        # Workflow complete
        await create_audit_log(
            db_session=async_session,
            action="workflow_complete",
            status="success",
            message="Editorial analysis completed",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
            details={"total_duration": 50.0, "pages_analyzed": 50},
        )
        
        await create_performance_metric(
            db_session=async_session,
            execution_id=execution.execution_id,
            metric_type="workflow_total_duration",
            metric_value=50.0,
            metric_unit="seconds",
            agent_name="orchestrator",
        )
        
        # Verify audit logs
        logs = await get_audit_logs_by_execution(
            db_session=async_session,
            execution_id=execution.execution_id,
        )
        
        assert len(logs) == 6
        assert logs[0].action == "workflow_start"
        assert logs[-1].action == "workflow_complete"
        
        # Verify steps are logged
        step_names = [log.step_name for log in logs if log.step_name]
        assert "discovering" in step_names
        assert "crawling" in step_names
        
        # Verify metrics
        metrics = await get_performance_metrics_by_execution(
            db_session=async_session,
            execution_id=execution.execution_id,
        )
        
        assert len(metrics) == 5
        
        # Verify summary
        summary = await get_performance_metrics_summary(
            db_session=async_session,
            execution_id=execution.execution_id,
        )
        
        assert "workflow_total_duration" in summary
        assert summary["workflow_total_duration"]["total"] == 50.0
        assert "pages_crawled" in summary
        assert summary["pages_crawled"]["total"] == 50.0

    @pytest.mark.asyncio
    async def test_workflow_failure_traceability(self, async_session: AsyncSession):
        """Test traceability when a workflow fails."""
        execution = await create_workflow_execution(
            db_session=async_session,
            workflow_type="competitor_search",
            input_data={"domain": "example.com"},
            status="running",
        )
        
        # Log workflow start
        await create_audit_log(
            db_session=async_session,
            action="workflow_start",
            status="info",
            message="Starting competitor search",
            execution_id=execution.execution_id,
            agent_name="orchestrator",
        )
        
        # Simulate a failure
        test_error = RuntimeError("Network connection failed")
        
        try:
            raise test_error
        except RuntimeError as e:
            await create_audit_log_from_exception(
                db_session=async_session,
                action="workflow_failed",
                exception=e,
                execution_id=execution.execution_id,
                agent_name="orchestrator",
                step_name="searching",
                details={"duration_seconds": 5.0},
            )
        
        # Record failure metric
        await create_performance_metric(
            db_session=async_session,
            execution_id=execution.execution_id,
            metric_type="workflow_failed_duration",
            metric_value=5.0,
            metric_unit="seconds",
            agent_name="orchestrator",
        )
        
        # Verify audit logs include error
        logs = await get_audit_logs_by_execution(
            db_session=async_session,
            execution_id=execution.execution_id,
        )
        
        assert len(logs) == 2
        error_log = logs[-1]
        assert error_log.action == "workflow_failed"
        assert error_log.status == "error"
        assert "Network connection failed" in error_log.message
        assert error_log.error_traceback is not None
        assert "RuntimeError" in error_log.error_traceback







