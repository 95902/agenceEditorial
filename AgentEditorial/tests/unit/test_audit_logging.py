"""Unit tests for audit logging functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from python_scripts.utils.logging import (
    AuditLogger,
    set_execution_context,
    clear_execution_context,
    get_execution_context,
)


@pytest.fixture
def audit_logger() -> AuditLogger:
    """Create an audit logger for testing."""
    return AuditLogger("test_agent")


@pytest.fixture
def execution_id():
    """Create a test execution ID."""
    return uuid4()


class TestExecutionContext:
    """Tests for execution context management."""

    def test_set_execution_context(self, execution_id):
        """Test setting execution context."""
        set_execution_context(
            execution_id=execution_id,
            agent_name="test_agent",
            step_name="test_step",
        )
        
        context = get_execution_context()
        assert context["execution_id"] == str(execution_id)
        assert context["agent_name"] == "test_agent"
        assert context["step_name"] == "test_step"
        
        # Cleanup
        clear_execution_context()

    def test_clear_execution_context(self, execution_id):
        """Test clearing execution context."""
        set_execution_context(
            execution_id=execution_id,
            agent_name="test_agent",
            step_name="test_step",
        )
        
        clear_execution_context()
        
        context = get_execution_context()
        assert context["execution_id"] is None
        assert context["agent_name"] is None
        assert context["step_name"] is None

    def test_partial_context_update(self, execution_id):
        """Test partial context updates."""
        set_execution_context(execution_id=execution_id)
        set_execution_context(agent_name="test_agent")
        
        context = get_execution_context()
        assert context["execution_id"] == str(execution_id)
        assert context["agent_name"] == "test_agent"
        
        clear_execution_context()


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_init(self, audit_logger):
        """Test AuditLogger initialization."""
        assert audit_logger.agent_name == "test_agent"
        assert audit_logger.execution_id is None

    def test_set_execution(self, audit_logger, execution_id):
        """Test setting execution ID."""
        audit_logger.set_execution(execution_id)
        assert audit_logger.execution_id == execution_id
        
        # Check context was set
        context = get_execution_context()
        assert context["execution_id"] == str(execution_id)
        assert context["agent_name"] == "test_agent"
        
        clear_execution_context()

    def test_set_step(self, audit_logger):
        """Test setting step name."""
        audit_logger.set_step("processing")
        
        context = get_execution_context()
        assert context["step_name"] == "processing"
        
        clear_execution_context()

    @patch("python_scripts.utils.logging.get_logger")
    def test_log_step_start(self, mock_get_logger, audit_logger, execution_id):
        """Test logging step start."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Create fresh logger with mocked dependency
        logger = AuditLogger("test_agent")
        logger.logger = mock_logger
        logger.set_execution(execution_id)
        
        logger.log_step_start("crawling", "Starting crawl operation")
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "step_started"
        assert call_args[1]["step"] == "crawling"
        assert call_args[1]["action"] == "step_start"
        
        clear_execution_context()

    @patch("python_scripts.utils.logging.get_logger")
    def test_log_step_complete(self, mock_get_logger, audit_logger, execution_id):
        """Test logging step completion."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = AuditLogger("test_agent")
        logger.logger = mock_logger
        logger.set_execution(execution_id)
        
        logger.log_step_complete(
            "crawling",
            "Crawled 50 pages",
            details={"pages": 50},
            duration_seconds=10.5,
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "step_completed"
        assert call_args[1]["step"] == "crawling"
        assert call_args[1]["duration_seconds"] == 10.5
        
        clear_execution_context()

    @patch("python_scripts.utils.logging.get_logger")
    def test_log_error(self, mock_get_logger, audit_logger, execution_id):
        """Test logging errors."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = AuditLogger("test_agent")
        logger.logger = mock_logger
        logger.set_execution(execution_id)
        
        test_error = ValueError("Test error message")
        logger.log_error("crawling", test_error, "Failed to crawl")
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "step_error"
        assert call_args[1]["step"] == "crawling"
        assert call_args[1]["error_type"] == "ValueError"
        assert call_args[1]["error_message"] == "Test error message"
        
        clear_execution_context()

    @patch("python_scripts.utils.logging.get_logger")
    def test_log_workflow_start(self, mock_get_logger, audit_logger, execution_id):
        """Test logging workflow start."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = AuditLogger("test_agent")
        logger.logger = mock_logger
        logger.set_execution(execution_id)
        
        logger.log_workflow_start(
            "editorial_analysis",
            input_data={"domain": "example.com"},
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "workflow_started"
        assert call_args[1]["workflow_type"] == "editorial_analysis"
        
        clear_execution_context()

    @patch("python_scripts.utils.logging.get_logger")
    def test_log_workflow_complete(self, mock_get_logger, audit_logger, execution_id):
        """Test logging workflow completion."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = AuditLogger("test_agent")
        logger.logger = mock_logger
        logger.set_execution(execution_id)
        
        logger.log_workflow_complete(
            "editorial_analysis",
            output_summary={"pages_crawled": 50},
            duration_seconds=120.5,
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "workflow_completed"
        assert call_args[1]["duration_seconds"] == 120.5
        
        clear_execution_context()

    @patch("python_scripts.utils.logging.get_logger")
    def test_log_workflow_failed(self, mock_get_logger, audit_logger, execution_id):
        """Test logging workflow failure."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = AuditLogger("test_agent")
        logger.logger = mock_logger
        logger.set_execution(execution_id)
        
        test_error = RuntimeError("Workflow crashed")
        logger.log_workflow_failed(
            "editorial_analysis",
            test_error,
            duration_seconds=30.0,
        )
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "workflow_failed"
        assert call_args[1]["error_type"] == "RuntimeError"
        
        clear_execution_context()


class TestRetryUtilities:
    """Tests for retry utilities."""

    @pytest.mark.asyncio
    async def test_async_retry_decorator_success(self):
        """Test async retry decorator on successful operation."""
        from python_scripts.utils.retry import async_retry_with_backoff

        call_count = 0

        @async_retry_with_backoff(max_attempts=3, log_retry=False)
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_operation()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_decorator_with_retries(self):
        """Test async retry decorator retries on transient failure."""
        from python_scripts.utils.retry import async_retry_with_backoff

        call_count = 0

        @async_retry_with_backoff(max_attempts=3, min_wait=0.1, max_wait=0.2, log_retry=False)
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await flaky_operation()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_decorator_max_attempts_exceeded(self):
        """Test async retry decorator raises after max attempts."""
        from python_scripts.utils.retry import async_retry_with_backoff

        call_count = 0

        @async_retry_with_backoff(max_attempts=3, min_wait=0.1, max_wait=0.2, log_retry=False)
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Permanent failure")

        with pytest.raises(ConnectionError):
            await always_failing_operation()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retryable_operation_context_manager(self):
        """Test RetryableOperation context manager."""
        from python_scripts.utils.retry import RetryableOperation

        call_count = 0

        async def flaky_fetch():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout")
            return {"data": "result"}

        async with RetryableOperation(
            operation_name="test_fetch",
            max_attempts=3,
            min_wait=0.1,
            max_wait=0.2,
        ) as retry_ctx:
            result = await retry_ctx.execute(flaky_fetch)

        assert result == {"data": "result"}
        assert retry_ctx.attempts == 2

    @pytest.mark.asyncio
    async def test_retry_network_operation_decorator(self):
        """Test retry_network_operation convenience decorator."""
        from python_scripts.utils.retry import retry_network_operation

        call_count = 0

        @retry_network_operation(max_attempts=2)
        async def network_call():
            nonlocal call_count
            call_count += 1
            return "response"

        result = await network_call()
        assert result == "response"
        assert call_count == 1







