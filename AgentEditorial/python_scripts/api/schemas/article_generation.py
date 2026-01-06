"""Pydantic schemas for article generation API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ToneType(str, Enum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    EDUCATIONAL = "educational"
    PERSUASIVE = "persuasive"


class ArticleStatus(str, Enum):
    INITIALIZED = "initialized"
    PLANNING = "planning"
    RESEARCHING = "researching"
    WRITING = "writing"
    GENERATING_IMAGES = "generating_images"
    REVIEWING = "reviewing"
    VALIDATED = "validated"
    FAILED = "failed"


class ArticleGenerationRequest(BaseModel):
    topic: str = Field(..., min_length=10, max_length=500)
    keywords: str = Field(..., description="Comma-separated keywords")
    tone: ToneType = ToneType.PROFESSIONAL
    target_words: int = Field(default=2000, ge=500, le=10000)
    language: str = Field(default="fr", pattern="^(fr|en|es|de)$")
    site_profile_id: Optional[int] = None
    generate_images: bool = True


class ArticleGenerationResponse(BaseModel):
    plan_id: str
    status: ArticleStatus
    topic: str
    message: str


class ArticleStatusResponse(BaseModel):
    plan_id: str
    status: ArticleStatus
    current_step: Optional[str]
    progress_percentage: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class ArticleImageResponse(BaseModel):
    id: int
    image_type: Optional[str]
    local_path: Optional[str]
    alt_text: Optional[str]


class ArticleDetailResponse(BaseModel):
    plan_id: str
    status: ArticleStatus
    topic: str
    keywords: List[str]
    plan: Optional[dict]
    content_markdown: Optional[str]
    content_html: Optional[str]
    quality_metrics: Optional[dict]
    images: List[ArticleImageResponse]
    created_at: datetime
    validated_at: Optional[datetime]


class ArticleListItemResponse(BaseModel):
    plan_id: str
    status: ArticleStatus
    topic: str
    created_at: datetime
    site_profile_id: Optional[int]


class ArticleListResponse(BaseModel):
    items: List[ArticleListItemResponse]
    total: int

















