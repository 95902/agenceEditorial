"""Pydantic request schemas for API endpoints."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SiteAnalysisRequest(BaseModel):
    """Request schema for site analysis."""

    domain: str = Field(..., description="Domain to analyze (e.g., 'example.com')", examples=["innosys.fr"])
    max_pages: int = Field(50, ge=1, le=500, description="Maximum pages to analyze", examples=[50])
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "innosys.fr",
                "max_pages": 50
            }
        }


class CompetitorSearchRequest(BaseModel):
    """Request schema for competitor search."""

    domain: str = Field(..., description="Domain to find competitors for", examples=["innosys.fr"])
    max_competitors: int = Field(100, ge=3, le=100, description="Maximum competitors to return (3-100)", examples=[10])
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "innosys.fr",
                "max_competitors": 100
            }
        }


class CompetitorValidationRequest(BaseModel):
    """Request schema for competitor validation (T092 - US4)."""

    competitors: List[dict] = Field(
        ...,
        description="List of competitors with validation flags (validated, manual, excluded)",
    )


class GapsAnalysisRequest(BaseModel):
    """Request schema for gaps analysis."""

    client_domain: str = Field(..., description="Client domain to compare")
    competitor_domains: Optional[List[str]] = Field(None, description="Optional list of competitor domains")



