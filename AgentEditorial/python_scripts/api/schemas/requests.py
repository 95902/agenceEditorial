"""Pydantic request schemas for API endpoints."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SiteAnalysisRequest(BaseModel):
    """Request schema for site analysis."""

    domain: str = Field(..., description="Domain to analyze (e.g., 'example.com')")
    max_pages: int = Field(50, ge=1, le=200, description="Maximum pages to analyze")


class CompetitorSearchRequest(BaseModel):
    """Request schema for competitor search."""

    domain: str = Field(..., description="Domain to find competitors for")
    max_competitors: int = Field(10, ge=3, le=100, description="Maximum competitors to return (3-100)")


class CompetitorValidationRequest(BaseModel):
    """Request schema for competitor validation."""

    competitors: List[dict] = Field(..., description="List of competitors with validation flags")


class ScrapingRequest(BaseModel):
    """Request schema for competitor scraping."""

    domains: List[str] = Field(..., description="List of competitor domains to scrape")
    max_articles_per_domain: int = Field(100, ge=1, le=100, description="Maximum articles per domain")


class TrendsAnalysisRequest(BaseModel):
    """Request schema for trends analysis."""

    domains: List[str] = Field(..., description="List of domains to analyze")
    time_window_days: int = Field(30, ge=7, le=90, description="Time window in days (7, 30, or 90)")


class GapsAnalysisRequest(BaseModel):
    """Request schema for gaps analysis."""

    client_domain: str = Field(..., description="Client domain to compare")
    competitor_domains: Optional[List[str]] = Field(None, description="Optional list of competitor domains")

