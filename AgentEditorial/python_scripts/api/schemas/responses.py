"""Pydantic response schemas for API endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
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

