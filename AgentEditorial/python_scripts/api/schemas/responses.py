"""Pydantic response schemas for API endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionResponse(BaseModel):
    """Response schema for workflow execution."""

    execution_id: UUID = Field(..., description="Unique execution ID")
    status: str = Field(..., description="Execution status")
    start_time: Optional[datetime] = Field(None, description="Start time")
    estimated_duration_minutes: Optional[int] = Field(None, description="Estimated duration")


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
    relevance_score: float
    confidence_score: float
    metadata: Optional[Dict[str, Any]] = None


class CompetitorListResponse(BaseModel):
    """Response schema for competitor list."""

    competitors: List[CompetitorResponse]
    total: int


class ArticleResponse(BaseModel):
    """Response schema for article."""

    id: int
    domain: str
    url: str
    title: str
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    word_count: int
    created_at: datetime


class ArticleListResponse(BaseModel):
    """Response schema for article list."""

    articles: List[ArticleResponse]
    total: int
    limit: int
    offset: int


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


class ErrorResponse(BaseModel):
    """Response schema for errors."""

    error: str
    detail: Optional[str] = None
    execution_id: Optional[UUID] = None

