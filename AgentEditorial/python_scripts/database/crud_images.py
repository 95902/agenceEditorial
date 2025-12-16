"""CRUD operations for image generations."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from python_scripts.database.models import GeneratedArticleImage
from python_scripts.image_generation.image_generator import GenerationResult
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def save_image_generation(
    db: AsyncSession,
    site_profile_id: Optional[int],
    article_topic: str,
    prompt_used: str,
    output_path: str,
    generation_params: dict[str, Any],
    quality_score: Optional[float] = None,
    negative_prompt: Optional[str] = None,
    critique_details: Optional[dict[str, Any]] = None,
    retry_count: int = 0,
    final_status: str = "success",
    generation_time_seconds: Optional[float] = None,
    article_id: Optional[int] = None,
    provider: str = "ideogram",
    ideogram_url: Optional[str] = None,
    magic_prompt: Optional[str] = None,
    style_type: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
) -> Optional[GeneratedArticleImage]:
    """
    Sauvegarde une génération d'image avec toutes les métadonnées.

    Args:
        db: Session de base de données
        site_profile_id: ID du profil de site (optionnel)
        article_topic: Sujet de l'article
        prompt_used: Prompt utilisé pour la génération
        output_path: Chemin vers l'image générée
        generation_params: Paramètres de génération (width, height, steps, etc. ou model, style_type pour Ideogram)
        quality_score: Score de qualité (optionnel)
        negative_prompt: Negative prompt utilisé (optionnel)
        critique_details: Détails de la critique (optionnel)
        retry_count: Nombre de tentatives
        final_status: Statut final (success, failed, retry_exhausted)
        generation_time_seconds: Temps de génération en secondes (optionnel)
        article_id: ID de l'article associé (optionnel mais required dans le modèle)
        provider: Provider utilisé ("ideogram" ou "local")
        ideogram_url: URL originale Ideogram (optionnel)
        magic_prompt: Prompt amélioré par Ideogram (optionnel)
        style_type: Style Ideogram (DESIGN, ILLUSTRATION, etc.) (optionnel)
        aspect_ratio: Ratio d'aspect (1:1, 4:3, etc.) (optionnel)

    Returns:
        GeneratedArticleImage sauvegardé ou None si article_id est None (contrainte FK)
    """
    # Note: article_id est required dans le modèle actuel avec contrainte FK
    # Si pas d'article, on retourne None et on log un warning
    if article_id is None:
        logger.warning(
            "Cannot save image generation without article_id (FK constraint)",
            site_profile_id=site_profile_id,
            article_topic=article_topic,
        )
        return None

    image = GeneratedArticleImage(
        article_id=article_id,
        site_profile_id=site_profile_id,
        prompt=prompt_used,
        negative_prompt=negative_prompt,
        local_path=output_path,
        generation_params=generation_params,
        quality_score=quality_score,
        critique_details=critique_details,
        retry_count=retry_count,
        final_status=final_status,
        generation_time_seconds=generation_time_seconds,
        image_type="article_header",  # Par défaut
        provider=provider,
        ideogram_url=ideogram_url,
        magic_prompt=magic_prompt,
        style_type=style_type,
        aspect_ratio=aspect_ratio,
    )

    db.add(image)
    await db.flush()

    logger.info(
        "Image generation saved",
        image_id=image.id,
        site_profile_id=site_profile_id,
        article_topic=article_topic,
        quality_score=quality_score,
        final_status=final_status,
    )

    return image


async def get_images_by_site(
    db: AsyncSession, site_profile_id: int
) -> list[GeneratedArticleImage]:
    """
    Récupère toutes les images générées pour un site.

    Args:
        db: Session de base de données
        site_profile_id: ID du profil de site

    Returns:
        Liste des images générées
    """
    stmt = (
        select(GeneratedArticleImage)
        .where(GeneratedArticleImage.site_profile_id == site_profile_id)
        .order_by(GeneratedArticleImage.created_at.desc())
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_recent_generations(
    db: AsyncSession, limit: int = 10
) -> list[GeneratedArticleImage]:
    """
    Récupère les générations d'images les plus récentes.

    Args:
        db: Session de base de données
        limit: Nombre maximum d'images à retourner

    Returns:
        Liste des images générées récemment
    """
    stmt = (
        select(GeneratedArticleImage)
        .order_by(GeneratedArticleImage.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_quality_score(
    db: AsyncSession,
    image_id: int,
    score: float,
    critique: dict[str, Any],
) -> GeneratedArticleImage:
    """
    Met à jour le score de qualité et les détails de critique d'une image.

    Args:
        db: Session de base de données
        image_id: ID de l'image
        score: Nouveau score de qualité
        critique: Détails de la critique

    Returns:
        GeneratedArticleImage mis à jour

    Raises:
        ValueError: Si l'image n'existe pas
    """
    stmt = select(GeneratedArticleImage).where(GeneratedArticleImage.id == image_id)
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()

    if not image:
        raise ValueError(f"Image with id {image_id} not found")

    image.quality_score = score
    image.critique_details = critique

    await db.flush()

    logger.info(
        "Image quality score updated",
        image_id=image_id,
        score=score,
    )

    return image
