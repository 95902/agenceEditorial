"""Custom exceptions hierarchy."""


class EditorialAgentException(Exception):
    """Base exception for all editorial agent errors."""

    pass


class CrawlingError(EditorialAgentException):
    """Error during web crawling."""

    pass


class AnalysisError(EditorialAgentException):
    """Error during editorial analysis."""

    pass


class CompetitorSearchError(EditorialAgentException):
    """Error during competitor search."""

    pass


class ScrapingError(EditorialAgentException):
    """Error during article scraping."""

    pass


class TopicModelingError(EditorialAgentException):
    """Error during topic modeling."""

    pass


class DatabaseError(EditorialAgentException):
    """Error during database operations."""

    pass


class VectorStoreError(EditorialAgentException):
    """Error during vector store operations."""

    pass


class LLMError(EditorialAgentException):
    """Error during LLM operations."""

    pass


class ValidationError(EditorialAgentException):
    """Error during data validation."""

    pass


class WorkflowError(EditorialAgentException):
    """Error during workflow execution."""

    pass

