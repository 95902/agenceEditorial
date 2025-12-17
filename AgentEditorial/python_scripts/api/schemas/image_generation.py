"""Schemas for image generation API."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ImageGenerationRequest(BaseModel):
    """Request schema for image generation."""

    prompt: str = Field(..., min_length=10, max_length=1000, description="Prompt for image generation")
    negative_prompt: Optional[str] = Field(
        None,
        max_length=500,
        description="Negative prompt to exclude unwanted elements",
    )
    width: Optional[int] = Field(768, ge=256, le=2048, description="Image width in pixels")
    height: Optional[int] = Field(768, ge=256, le=2048, description="Image height in pixels")
    steps: Optional[int] = Field(12, ge=1, le=50, description="Number of inference steps")
    guidance_scale: Optional[float] = Field(7.5, ge=1.0, le=20.0, description="Guidance scale for generation")
    style: Optional[str] = Field(
        "corporate_flat",
        description="Image style (corporate_flat, corporate_3d, tech_isometric, tech_gradient, modern_minimal)",
    )
    save_to_db: Optional[bool] = Field(
        True,
        description="Whether to save image metadata to database",
    )


class ImageGenerationResponse(BaseModel):
    """Response schema for image generation."""

    success: bool
    image_path: str
    prompt_used: str
    negative_prompt: Optional[str]
    generation_params: Dict[str, Any]
    quality_score: Optional[float] = None
    critique_details: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    final_status: str
    generation_time_seconds: Optional[float] = None
    message: str


