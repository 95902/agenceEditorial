"""Base agent abstract class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID

from python_scripts.utils.logging import get_logger


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, agent_name: str) -> None:
        """Initialize agent."""
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_name}")

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
        """Log a workflow step."""
        self.logger.info(
            "workflow_step",
            step=step_name,
            status=status,
            message=message,
            details=details or {},
        )

