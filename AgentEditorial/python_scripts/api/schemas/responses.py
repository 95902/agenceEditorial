"""Pydantic response schemas for API endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionResponse(BaseModel):
    """Response schema for workflow execution."""

    execution_id: UUID = Field(..., description="Unique execution ID", examples=["123e4567-e89b-12d3-a456-426614174000"])
    status: str = Field(..., description="Execution status (pending, running, completed, failed)", examples=["pending"])
    start_time: Optional[datetime] = Field(None, description="Start time", examples=["2025-01-09T18:00:00Z"])
    estimated_duration_minutes: Optional[int] = Field(None, description="Estimated duration in minutes", examples=[10])
    
    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "pending",
                "start_time": "2025-01-09T18:00:00Z",
                "estimated_duration_minutes": 10
            }
        }


class SiteProfileResponse(BaseModel):
    """Response schema for site profile."""

    domain: str
    analysis_date: datetime
    language_level: Optional[str] = None
    editorial_tone: Optional[str] = None
    target_audience: Optional[Dict[str, Any]] = None
    activity_domains: Optional[Dict[str, Any]] = None
    content_structure: Optional[Dict[str, Any]] = None
    keywords: Optional[Dict[str, Any]] = None
    style_features: Optional[Dict[str, Any]] = None
    pages_analyzed: int
    llm_models_used: Optional[Dict[str, Any]] = None


class SiteListResponse(BaseModel):
    """Response schema for site list."""

    sites: List[SiteProfileResponse]
    total: int


class CompetitorResponse(BaseModel):
    """Response schema for competitor."""

    domain: str
    relevance_score: float = 0.0
    confidence_score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class CompetitorListResponse(BaseModel):
    """Response schema for competitor list."""

    competitors: List[CompetitorResponse]
    total: int


class ArticleResponse(BaseModel):
    """Response schema for article (T105 - US5)."""

    id: int = Field(..., description="Article ID")
    domain: str = Field(..., description="Domain name")
    url: str = Field(..., description="Article URL")
    title: str = Field(..., description="Article title")
    author: Optional[str] = Field(None, description="Article author")
    published_date: Optional[datetime] = Field(None, description="Publication date")
    word_count: int = Field(..., description="Word count")
    created_at: datetime = Field(..., description="Creation timestamp")


class ArticleListResponse(BaseModel):
    """Response schema for article list (T105 - US5)."""

    articles: List[ArticleResponse] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")


class TopicResponse(BaseModel):
    """Response schema for topic."""

    id: int
    keywords: List[str]
    name: str
    size: int
    coherence: float


class TopicsResponse(BaseModel):
    """Response schema for topics."""

    topics: List[TopicResponse]
    total: int
    time_window_days: int


class GapResponse(BaseModel):
    """Response schema for content gap."""

    topic_id: int
    topic_keywords: List[str]
    gap_score: float
    frequency: int
    recommendation: Optional[Dict[str, Any]] = None


class GapsResponse(BaseModel):
    """Response schema for gaps analysis."""

    gaps: List[GapResponse]
    total: int


class SiteHistoryEntry(BaseModel):
    """Response schema for a single historical analysis entry."""

    analysis_date: datetime
    language_level: Optional[str] = None
    editorial_tone: Optional[str] = None
    pages_analyzed: int
    target_audience: Optional[Dict[str, Any]] = None
    activity_domains: Optional[Dict[str, Any]] = None
    content_structure: Optional[Dict[str, Any]] = None
    keywords: Optional[Dict[str, Any]] = None
    style_features: Optional[Dict[str, Any]] = None


class MetricComparison(BaseModel):
    """Response schema for metric comparison between time periods."""

    metric_name: str
    current_value: Any
    previous_value: Optional[Any] = None
    change: Optional[float] = None  # Percentage change
    trend: Optional[str] = None  # "increasing", "decreasing", "stable"


class SiteHistoryResponse(BaseModel):
    """Response schema for site analysis history."""

    domain: str
    total_analyses: int
    history: List[SiteHistoryEntry]
    metric_comparisons: Optional[List[MetricComparison]] = None
    first_analysis_date: Optional[datetime] = None
    last_analysis_date: Optional[datetime] = None


# ============================================================
# Error Response Schema
# ============================================================

class ErrorResponse(BaseModel):
    """Response schema for errors."""

    error: str
    detail: Optional[str] = None
    execution_id: Optional[UUID] = None


# ============================================================
# Site Audit Response Schemas
# ============================================================

class DomainDetail(BaseModel):
    """Response schema for activity domain detail."""

    id: str = Field(..., description="Domain slug identifier")
    label: str = Field(..., description="Domain label")
    confidence: int = Field(..., description="Confidence score (0-100)", ge=0, le=100)
    topics_count: int = Field(..., description="Number of articles for this domain", ge=0)
    summary: str = Field(..., description="Domain summary description")


class WorkflowStep(BaseModel):
    """Response schema for workflow step status."""

    step: int = Field(..., description="Step number")
    name: str = Field(..., description="Step name")
    status: Literal["pending", "running", "completed", "failed"] = Field(
        ..., description="Step status"
    )
    execution_id: Optional[str] = Field(None, description="Execution ID for this step")


class DataStatus(BaseModel):
    """Response schema for data availability status."""

    has_profile: bool = Field(..., description="Site profile exists")
    has_competitors: bool = Field(..., description="Competitors data exists")
    has_client_articles: bool = Field(..., description="Client articles exist")
    has_competitor_articles: bool = Field(..., description="Competitor articles exist")
    has_trend_pipeline: bool = Field(..., description="Trend pipeline data exists")


class PendingAuditResponse(BaseModel):
    """Response schema for pending audit (workflows in progress)."""

    status: Literal["pending"] = Field(..., description="Status is pending")
    execution_id: str = Field(..., description="Orchestrator execution ID")
    message: str = Field(..., description="Status message")
    workflow_steps: List[WorkflowStep] = Field(..., description="List of workflow steps")
    data_status: DataStatus = Field(..., description="Current data availability status")


class SiteAuditResponse(BaseModel):
    """Response schema for complete site audit."""

    url: str = Field(..., description="Site URL")
    profile: Dict[str, Any] = Field(
        ...,
        description="Site profile with style and themes",
        example={
            "style": {
                "tone": "professionnel",
                "vocabulary": "spécialisé en technologie",
                "format": "articles longs (1500-2500 mots)",
            },
            "themes": ["Cloud Computing", "Cybersécurité"],
        },
    )
    domains: List[DomainDetail] = Field(..., description="Activity domains with details")
    audience: Dict[str, Any] = Field(
        ...,
        description="Target audience information",
        example={
            "type": "Professionnels IT",
            "level": "Intermédiaire à Expert",
            "sectors": ["Entreprises", "Startups Tech", "DSI"],
        },
    )
    competitors: List[Dict[str, Any]] = Field(
        ...,
        description="List of competitors",
        example=[{"name": "TechNews.fr", "similarity": 85}],
    )
    took_ms: int = Field(..., description="Analysis duration in milliseconds", ge=0)

