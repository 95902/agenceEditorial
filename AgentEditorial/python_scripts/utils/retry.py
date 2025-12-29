"""Retry utilities with tenacity for I/O operations."""

import asyncio
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    before_sleep_log,
    after_log,
)

from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

# Type variable for generic return types
T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MIN_WAIT_SECONDS = 1
DEFAULT_MAX_WAIT_SECONDS = 60

# Common retryable exceptions
NETWORK_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
    OSError,
)

DATABASE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
)


def retry_with_backoff(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: float = DEFAULT_MIN_WAIT_SECONDS,
    max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
    retry_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    log_retry: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for synchronous functions with exponential backoff retry.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 1)
        max_wait: Maximum wait time between retries in seconds (default: 60)
        retry_exceptions: Tuple of exception types to retry on (default: network exceptions)
        log_retry: Whether to log retry attempts (default: True)

    Returns:
        Decorated function with retry logic

    Usage:
        @retry_with_backoff(max_attempts=5)
        def fetch_data():
            # I/O operation that might fail
            ...
    """
    if retry_exceptions is None:
        retry_exceptions = NETWORK_EXCEPTIONS

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retry_decorator = retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(retry_exceptions),
                before_sleep=before_sleep_log(logger, "WARNING") if log_retry else None,
                after=after_log(logger, "DEBUG") if log_retry else None,
                reraise=True,
            )
            return retry_decorator(func)(*args, **kwargs)

        return wrapper

    return decorator


def async_retry_with_backoff(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: float = DEFAULT_MIN_WAIT_SECONDS,
    max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
    retry_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    log_retry: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for async functions with exponential backoff retry.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 1)
        max_wait: Maximum wait time between retries in seconds (default: 60)
        retry_exceptions: Tuple of exception types to retry on (default: network exceptions)
        log_retry: Whether to log retry attempts (default: True)

    Returns:
        Decorated async function with retry logic

    Usage:
        @async_retry_with_backoff(max_attempts=5)
        async def fetch_data():
            # Async I/O operation that might fail
            ...
    """
    if retry_exceptions is None:
        retry_exceptions = NETWORK_EXCEPTIONS

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(retry_exceptions),
                before_sleep=before_sleep_log(logger, "WARNING") if log_retry else None,
                after=after_log(logger, "DEBUG") if log_retry else None,
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)
            # This should never be reached due to reraise=True
            raise RetryError(f"Failed after {max_attempts} attempts")

        return wrapper  # type: ignore

    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations with detailed logging.

    Usage:
        async with RetryableOperation(
            operation_name="fetch_page",
            max_attempts=3,
            execution_id=execution_id,
        ) as retry_ctx:
            result = await retry_ctx.execute(fetch_function, url)
    """

    def __init__(
        self,
        operation_name: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        min_wait: float = DEFAULT_MIN_WAIT_SECONDS,
        max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
        retry_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        execution_id: Optional[str] = None,
    ) -> None:
        """Initialize the retryable operation context."""
        self.operation_name = operation_name
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.retry_exceptions = retry_exceptions or NETWORK_EXCEPTIONS
        self.execution_id = execution_id
        self.attempts = 0
        self.last_error: Optional[Exception] = None

    async def __aenter__(self) -> "RetryableOperation":
        """Enter the context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit the context."""
        return False

    async def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute the function with retry logic.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function

        Raises:
            Exception: The last exception if all retries fail
        """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=1, min=self.min_wait, max=self.max_wait),
            retry=retry_if_exception_type(self.retry_exceptions),
            reraise=True,
        ):
            with attempt:
                self.attempts = attempt.retry_state.attempt_number
                if self.attempts > 1:
                    logger.warning(
                        "Retrying operation",
                        operation=self.operation_name,
                        attempt=self.attempts,
                        max_attempts=self.max_attempts,
                        execution_id=self.execution_id,
                        last_error=str(self.last_error) if self.last_error else None,
                    )
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except self.retry_exceptions as e:
                    self.last_error = e
                    raise

        # This should never be reached
        raise RetryError(f"Operation '{self.operation_name}' failed after {self.max_attempts} attempts")


# Convenience decorators for common use cases


def retry_network_operation(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for network operations (HTTP calls, etc.).

    Args:
        max_attempts: Maximum retry attempts (default: 3)
    """
    return async_retry_with_backoff(
        max_attempts=max_attempts,
        retry_exceptions=NETWORK_EXCEPTIONS,
    )


def retry_database_operation(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for database operations.

    Args:
        max_attempts: Maximum retry attempts (default: 3)
    """
    return async_retry_with_backoff(
        max_attempts=max_attempts,
        min_wait=0.5,
        max_wait=10,
        retry_exceptions=DATABASE_EXCEPTIONS,
    )


def retry_llm_operation(
    max_attempts: int = 3,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for LLM operations (Ollama calls, etc.).

    LLM operations use random jitter to avoid thundering herd issues.

    Args:
        max_attempts: Maximum retry attempts (default: 3)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_random_exponential(multiplier=1, min=2, max=30),
                retry=retry_if_exception_type((ConnectionError, TimeoutError, asyncio.TimeoutError)),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)
            raise RetryError(f"LLM operation failed after {max_attempts} attempts")

        return wrapper  # type: ignore

    return decorator













