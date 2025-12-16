"""API router for direct image generation."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from python_scripts.config.settings import settings
from python_scripts.database.crud_images import save_image_generation
from python_scripts.image_generation import ImageGenerator
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/images", tags=["Image Generation"])


@router.post(
    "/generate",
    response_model=ImageGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate an image from a prompt",
    description="""
    Generate an image directly from a text prompt using Ideogram (cloud) or Z-Image (local fallback).
    
    This endpoint allows you to generate images without needing to create an article.
    You can specify the prompt, style, and aspect ratio.
    
    The generated image will be saved to the output directory and optionally to the database.
    """,
)
async def generate_image(
    request: ImageGenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> ImageGenerationResponse:
    """
    Generate an image from a text prompt.

    Args:
        request: Image generation request with prompt and optional parameters
        db: Database session

    Returns:
        ImageGenerationResponse with image path and metadata

    Raises:
        HTTPException: 400 if image generation is disabled or invalid parameters
        HTTPException: 500 if generation fails
    """
    start_time = time.time()

    try:
        # Get ImageGenerator instance (uses Ideogram by default)
        # Si la clé API Ideogram n'est pas configurée et que fallback est activé,
        # le système utilisera automatiquement Z-Image local
        generator = ImageGenerator.get_instance()

        # Convert width/height to aspect_ratio for Ideogram
        # Ideogram uses predefined aspect ratios, so we map dimensions to closest ratio
        aspect_ratio = "1:1"  # default
        if request.width and request.height:
            ratio = request.width / request.height
            if abs(ratio - 1.0) < 0.1:
                aspect_ratio = "1:1"
            elif abs(ratio - 4/3) < 0.1:
                aspect_ratio = "4:3"
            elif abs(ratio - 3/4) < 0.1:
                aspect_ratio = "3:4"
            elif abs(ratio - 16/9) < 0.1:
                aspect_ratio = "16:9"
            elif abs(ratio - 9/16) < 0.1:
                aspect_ratio = "9:16"

        # Generate the image
        logger.info(
            "Generating image from prompt",
            prompt=request.prompt[:100],
            provider=generator.provider,
            aspect_ratio=aspect_ratio,
            style=request.style,
        )

        generation_result = await generator.generate(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            style=request.style or "corporate_flat",
            aspect_ratio=aspect_ratio,
        )

        if not generation_result.success:
            raise Exception(f"Image generation failed: {generation_result.error}")

        generation_time = generation_result.generation_time

        # Prepare generation parameters from metadata
        generation_params = generation_result.metadata.copy()
        generation_params["provider"] = generation_result.provider
        if request.style:
            generation_params["style"] = request.style

        # Save to database if requested
        saved_image_id = None
        if request.save_to_db:
            try:
                # Extract Ideogram metadata from generation_params
                provider = generation_params.get("provider", "ideogram")
                ideogram_url = generation_params.get("ideogram_url")
                magic_prompt = generation_params.get("magic_prompt")
                style_type = generation_params.get("style_type")
                aspect_ratio = generation_params.get("aspect_ratio")

                saved_image = await save_image_generation(
                    db=db,
                    site_profile_id=None,  # Pas de profil de site pour génération directe
                    article_topic=request.prompt[:200],  # Utiliser le prompt comme topic
                    prompt_used=generation_result.prompt_used,
                    output_path=str(generation_result.image_path),
                    generation_params=generation_params,
                    quality_score=None,  # Pas de critique IA pour génération directe
                    negative_prompt=generation_result.negative_prompt,
                    critique_details=None,
                    retry_count=0,
                    final_status="success",
                    generation_time_seconds=generation_time,
                    article_id=None,  # Pas d'article associé
                    provider=provider,
                    ideogram_url=ideogram_url,
                    magic_prompt=magic_prompt,
                    style_type=style_type,
                    aspect_ratio=aspect_ratio,
                )
                if saved_image:
                    await db.commit()
                    saved_image_id = saved_image.id
                    logger.info(
                        "Image generation saved to database",
                        image_id=saved_image_id,
                        image_path=str(generation_result.image_path),
                    )
                else:
                    logger.info(
                        "Image generation not saved to database (article_id required)",
                        image_path=str(generation_result.image_path),
                    )
            except Exception as db_error:
                logger.warning(
                    "Failed to save image generation to database",
                    error=str(db_error),
                )
                await db.rollback()
                # Continue even if database save fails

        return ImageGenerationResponse(
            success=True,
            image_path=str(generation_result.image_path),
            prompt_used=generation_result.prompt_used,
            negative_prompt=generation_result.negative_prompt,
            generation_params=generation_params,
            quality_score=None,
            critique_details=None,
            retry_count=0,
            final_status="success",
            generation_time_seconds=generation_time,
            message=f"Image generated successfully. Saved to: {generation_result.image_path}"
            + (f" (ID: {saved_image_id})" if saved_image_id else ""),
        )

    except Exception as e:
        logger.error(
            "Image generation failed",
            error=str(e),
            prompt=request.prompt[:100],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image generation failed: {str(e)}",
        ) from e

