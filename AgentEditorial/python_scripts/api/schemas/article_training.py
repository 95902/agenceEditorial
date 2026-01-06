"""Pydantic schemas for article training API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ArticleFeedbackRequest(BaseModel):
    """Request schema for manual feedback on an article."""

    plan_id: str = Field(..., description="Plan ID of the article")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comments: Optional[str] = Field(None, max_length=1000, description="Optional comments")
    is_positive: bool = Field(True, description="Whether this is a positive example")


class ArticleFeedbackResponse(BaseModel):
    """Response schema for feedback submission."""

    success: bool
    learning_data_id: Optional[int] = None
    message: str


class PatternResponse(BaseModel):
    """Response schema for a learned pattern."""

    pattern_type: str
    pattern_data: Dict[str, Any]
    confidence: float
    examples_count: int


class AnalysisResponse(BaseModel):
    """Response schema for article analysis."""

    patterns: List[PatternResponse]
    total_analyzed: int
    patterns_found: int
    analysis_date: datetime


class PromptImprovementRequest(BaseModel):
    """Request schema for prompt improvement."""

    topic: str
    keywords: List[str]
    tone: str = "professional"
    target_words: int = 2000
    site_profile_id: Optional[int] = None


class PromptImprovementResponse(BaseModel):
    """Response schema for prompt improvement."""

    original_prompt: str
    improved_prompt: str
    improvements: List[str]
    confidence: float
    patterns_used: List[str]


class TrainingStatsResponse(BaseModel):
    """Response schema for training statistics."""

    total_articles: int
    positive_examples: int
    negative_examples: int
    automatic_feedback: int
    manual_feedback: int
    with_learned_patterns: int
    average_global_score: Optional[float] = None













