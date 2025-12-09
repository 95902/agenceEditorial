"""Pydantic request schemas for API endpoints."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SiteAnalysisRequest(BaseModel):
    """Request schema for site analysis."""

    domain: str = Field(..., description="Domain to analyze (e.g., 'example.com')")
    max_pages: int = Field(50, ge=1, le=500, description="Maximum pages to analyze")


class CompetitorSearchRequest(BaseModel):
    """Request schema for competitor search."""

    domain: str = Field(..., description="Domain to find competitors for")
    max_competitors: int = Field(10, ge=3, le=100, description="Maximum competitors to return (3-100)")


class CompetitorValidationRequest(BaseModel):
    """Request schema for competitor validation (T092 - US4)."""

    competitors: List[dict] = Field(
        ...,
        description="List of competitors with validation flags (validated, manual, excluded)",
    )


class ScrapingRequest(BaseModel):
    """Request schema for competitor scraping (T105 - US5).
    
    Supports two modes:
    1. Explicit domains: Provide 'domains' list directly
    2. Auto-fetch: Provide 'client_domain' to automatically fetch validated competitors
    """

    domains: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="List of competitor domains to scrape (required if client_domain not provided)",
    )
    client_domain: Optional[str] = Field(
        None,
        description="Client domain to fetch validated competitors from (required if domains not provided)",
    )
    max_articles_per_domain: int = Field(
        default=500,
        ge=1,
        le=1000,
        description="Maximum articles per domain (1-1000)",
    )
    
    @model_validator(mode="after")
    def validate_domains_or_client_domain(self):
        """Validate that either domains or client_domain is provided."""
        # Ignore client_domain if it's empty, None, or just a placeholder string
        if self.client_domain in (None, "", "string"):
            self.client_domain = None
        
        # If domains is provided, ignore client_domain
        if self.domains:
            self.client_domain = None
        
        # Validate that at least one is provided
        if not self.domains and not self.client_domain:
            raise ValueError("Either 'domains' or 'client_domain' must be provided")
        
        return self


class TrendsAnalysisRequest(BaseModel):
    """Request schema for trends analysis (T130 - US7).
    
    Supports two modes:
    1. Explicit domains: Provide 'domains' list directly
    2. Auto-fetch: Provide 'client_domain' to automatically fetch validated competitors
    """
    
    client_domain: Optional[str] = Field(
        None,
        description="Client domain to analyze competitors for (required if domains not provided)",
    )
    domains: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="Optional: explicit list of domains to analyze (required if client_domain not provided)",
    )
    time_window_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Time window in days (30-3650, default: 365)",
    )
    min_topic_size: Optional[int] = Field(
        default=None,
        ge=5,
        le=50,
        description="Minimum articles per topic (optional, default: 10)",
    )
    nr_topics: Optional[str | int] = Field(
        default=None,
        description="Number of topics (int) or 'auto' for automatic discovery (optional)",
    )
    use_qdrant_embeddings: bool = Field(
        default=True,
        description="Whether to use embeddings from Qdrant (default: True)",
    )
    filter_semantic_duplicates: bool = Field(
        default=True,
        description="Whether to filter semantic duplicates before analysis (default: True)",
    )
    min_semantic_quality: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum semantic quality threshold (0.0-1.0, uses percentile if provided, optional)",
    )
    
    @model_validator(mode='after')
    def validate_domains_or_client(self) -> 'TrendsAnalysisRequest':
        """Ensure either domains or client_domain is provided, but not both."""
        if self.domains and self.client_domain:
            raise ValueError("Cannot provide both 'domains' and 'client_domain'. Use one or the other.")
        if not self.domains and not self.client_domain:
            raise ValueError("Must provide either 'domains' or 'client_domain'.")
        return self
    
    @model_validator(mode='after')
    def validate_nr_topics(self) -> 'TrendsAnalysisRequest':
        """Validate nr_topics value."""
        if self.nr_topics is not None:
            if isinstance(self.nr_topics, str):
                if self.nr_topics.lower() != "auto":
                    raise ValueError("nr_topics must be an integer, 'auto', or null")
            elif isinstance(self.nr_topics, int):
                if self.nr_topics < 1:
                    raise ValueError("nr_topics must be a positive integer")
        return self


class GapsAnalysisRequest(BaseModel):
    """Request schema for gaps analysis."""

    client_domain: str = Field(..., description="Client domain to compare")
    competitor_domains: Optional[List[str]] = Field(None, description="Optional list of competitor domains")



