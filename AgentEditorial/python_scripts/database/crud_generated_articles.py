"""CRUD operations for generated articles and related entities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import Select, and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import (
    GeneratedArticle,
    GeneratedArticleImage,
    GeneratedArticleVersion,
)
from python_scripts.utils.json_utils import make_json_serializable
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)


async def create_article(
    db_session: AsyncSession,
    *,
    topic: str,
    keywords: Sequence[str],
    tone: str = "professional",
    target_words: int = 2000,
    language: str = "fr",
    site_profile_id: Optional[int] = None,
) -> GeneratedArticle:
    """Create a new generated article entry with an auto-generated plan_id."""
    try:
        article = GeneratedArticle(
            topic=topic,
            keywords=list(keywords),
            tone=tone,
            target_words=target_words,
            language=language,
            site_profile_id=site_profile_id,
            status="initialized",
            progress_percentage=0,
        )
        db_session.add(article)
        await db_session.flush()

        logger.info(
            "generated_article_created",
            article_id=article.id,
            plan_id=str(article.plan_id),
            topic=article.topic,
        )
        return article
    except SQLAlchemyError as exc:
        logger.error(
            "generated_article_create_failed",
            error=str(exc),
            topic=topic,
        )
        raise


async def get_article_by_plan_id(
    db_session: AsyncSession,
    *,
    plan_id: UUID,
) -> Optional[GeneratedArticle]:
    """Get a generated article by its plan_id."""
    stmt: Select[GeneratedArticle] = select(GeneratedArticle).where(
        GeneratedArticle.plan_id == plan_id,
        GeneratedArticle.is_valid.is_(True),
    )
    result = await db_session.execute(stmt)
    article = result.scalar_one_or_none()
    return article


async def update_article_status(
    db_session: AsyncSession,
    *,
    plan_id: UUID,
    status: str,
    current_step: Optional[str] = None,
    progress_percentage: Optional[int] = None,
    error_message: Optional[str] = None,
) -> Optional[GeneratedArticle]:
    """Update status/progress for a generated article."""
    article = await get_article_by_plan_id(db_session, plan_id=plan_id)
    if not article:
        return None

    article.status = status
    if current_step is not None:
        article.current_step = current_step
    if progress_percentage is not None:
        article.progress_percentage = progress_percentage
    if error_message is not None:
        article.error_message = error_message

    logger.info(
        "generated_article_status_updated",
        plan_id=str(plan_id),
        status=status,
        current_step=current_step,
        progress_percentage=progress_percentage,
    )
    return article


async def update_article_plan(
    db_session: AsyncSession,
    *,
    plan_id: UUID,
    plan_json: Dict[str, Any],
) -> Optional[GeneratedArticle]:
    """Update the plan JSON for a generated article."""
    article = await get_article_by_plan_id(db_session, plan_id=plan_id)
    if not article:
        return None

    article.plan_json = make_json_serializable(plan_json)
    logger.info(
        "generated_article_plan_updated",
        plan_id=str(plan_id),
    )
    return article


async def update_article_content(
    db_session: AsyncSession,
    *,
    plan_id: UUID,
    content_markdown: Optional[str] = None,
    content_html: Optional[str] = None,
    quality_metrics: Optional[Dict[str, Any]] = None,
    final_word_count: Optional[int] = None,
    seo_score: Optional[float] = None,
    readability_score: Optional[float] = None,
    slug: Optional[str] = None,
    meta_description: Optional[str] = None,
) -> Optional[GeneratedArticle]:
    """Update content and quality metrics for a generated article."""
    article = await get_article_by_plan_id(db_session, plan_id=plan_id)
    if not article:
        return None

    if content_markdown is not None:
        article.content_markdown = content_markdown
    if content_html is not None:
        article.content_html = content_html
    if quality_metrics is not None:
        article.quality_metrics = make_json_serializable(quality_metrics)
    if final_word_count is not None:
        article.final_word_count = final_word_count
    if seo_score is not None:
        article.seo_score = seo_score
    if readability_score is not None:
        article.readability_score = readability_score
    if slug is not None:
        article.slug = slug
    if meta_description is not None:
        article.meta_description = meta_description

    logger.info(
        "generated_article_content_updated",
        plan_id=str(plan_id),
    )
    return article


async def list_articles(
    db_session: AsyncSession,
    *,
    site_profile_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[GeneratedArticle]:
    """List generated articles with optional filters."""
    conditions = [GeneratedArticle.is_valid.is_(True)]
    if site_profile_id is not None:
        conditions.append(GeneratedArticle.site_profile_id == site_profile_id)
    if status is not None:
        conditions.append(GeneratedArticle.status == status)

    stmt: Select[GeneratedArticle] = (
        select(GeneratedArticle)
        .where(and_(*conditions))
        .order_by(GeneratedArticle.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db_session.execute(stmt)
    return list(result.scalars().all())


async def save_article_image(
    db_session: AsyncSession,
    *,
    article_id: int,
    image_type: Optional[str],
    prompt: Optional[str],
    local_path: Optional[str],
    alt_text: Optional[str],
) -> GeneratedArticleImage:
    """Persist a generated article image."""
    image = GeneratedArticleImage(
        article_id=article_id,
        image_type=image_type,
        prompt=prompt,
        local_path=local_path,
        alt_text=alt_text,
    )
    db_session.add(image)
    await db_session.flush()

    logger.info(
        "generated_article_image_saved",
        article_id=article_id,
        image_id=image.id,
        image_type=image_type,
    )
    return image


async def get_article_images(
    db_session: AsyncSession,
    *,
    article_id: int,
) -> List[GeneratedArticleImage]:
    """Get images associated with a generated article."""
    stmt: Select[GeneratedArticleImage] = select(GeneratedArticleImage).where(
        GeneratedArticleImage.article_id == article_id,
    )
    result = await db_session.execute(stmt)
    return list(result.scalars().all())


async def create_article_version(
    db_session: AsyncSession,
    *,
    article_id: int,
    version: int,
    content_json: Dict[str, Any],
    change_description: Optional[str] = None,
) -> GeneratedArticleVersion:
    """Create a new version entry for a generated article."""
    version_obj = GeneratedArticleVersion(
        article_id=article_id,
        version=version,
        content_json=make_json_serializable(content_json),
        change_description=change_description,
    )
    db_session.add(version_obj)
    await db_session.flush()

    logger.info(
        "generated_article_version_created",
        article_id=article_id,
        version=version,
    )
    return version_obj


async def get_article_versions(
    db_session: AsyncSession,
    *,
    article_id: int,
) -> List[GeneratedArticleVersion]:
    """Get all versions for a generated article ordered by version asc."""
    stmt: Select[GeneratedArticleVersion] = (
        select(GeneratedArticleVersion)
        .where(GeneratedArticleVersion.article_id == article_id)
        .order_by(GeneratedArticleVersion.version.asc())
    )
    result = await db_session.execute(stmt)
    return list(result.scalars().all())


async def delete_article(
    db_session: AsyncSession,
    *,
    plan_id: UUID,
) -> bool:
    """Soft delete an article (mark as invalid)."""
    article = await get_article_by_plan_id(db_session, plan_id=plan_id)
    if not article:
        return False

    article.is_valid = False
    logger.info(
        "generated_article_soft_deleted",
        plan_id=str(plan_id),
        article_id=article.id,
    )
    return True







