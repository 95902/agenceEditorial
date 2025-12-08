"""CRUD operations for ClientArticle model."""

from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import ClientArticle
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_client_article(
    db_session: AsyncSession,
    site_profile_id: int,
    url: str,
    url_hash: str,
    title: str,
    content_text: str,
    **kwargs: dict,
) -> ClientArticle:
    """
    Create a new client article.

    Args:
        db_session: Database session
        site_profile_id: Site profile ID
        url: Article URL
        url_hash: SHA256 hash of the URL
        title: Article title
        content_text: Article text content
        **kwargs: Additional article fields (author, published_date, content_html, word_count, keywords, article_metadata, qdrant_point_id)

    Returns:
        Created ClientArticle instance
    """
    article = ClientArticle(
        site_profile_id=site_profile_id,
        url=url,
        url_hash=url_hash,
        title=title,
        content_text=content_text,
        **kwargs,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    logger.info("Client article created", site_profile_id=site_profile_id, url=url, article_id=article.id)
    return article


async def get_client_article_by_url(
    db_session: AsyncSession,
    url: str,
) -> Optional[ClientArticle]:
    """
    Get client article by URL.

    Args:
        db_session: Database session
        url: Article URL

    Returns:
        ClientArticle if found, None otherwise
    """
    result = await db_session.execute(
        select(ClientArticle).where(
            ClientArticle.url == url,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_client_article_by_hash(
    db_session: AsyncSession,
    url_hash: str,
) -> Optional[ClientArticle]:
    """
    Get client article by URL hash.

    Args:
        db_session: Database session
        url_hash: SHA256 hash of the URL

    Returns:
        ClientArticle if found, None otherwise
    """
    result = await db_session.execute(
        select(ClientArticle).where(
            ClientArticle.url_hash == url_hash,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_client_article_by_id(
    db_session: AsyncSession,
    article_id: int,
) -> Optional[ClientArticle]:
    """
    Get client article by ID.

    Args:
        db_session: Database session
        article_id: Article ID

    Returns:
        ClientArticle if found, None otherwise
    """
    result = await db_session.execute(
        select(ClientArticle).where(
            ClientArticle.id == article_id,
            ClientArticle.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def list_client_articles(
    db_session: AsyncSession,
    site_profile_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    min_word_count: Optional[int] = None,
    max_age_days: Optional[int] = None,
) -> List[ClientArticle]:
    """
    List client articles with optional filters.

    Args:
        db_session: Database session
        site_profile_id: Filter by site profile ID (optional)
        limit: Maximum number of articles to return
        offset: Number of articles to skip
        min_word_count: Minimum word count filter (optional)
        max_age_days: Maximum age in days filter (optional)

    Returns:
        List of ClientArticle instances
    """
    query = select(ClientArticle).where(
        ClientArticle.is_valid == True  # noqa: E712
    )

    if site_profile_id:
        query = query.where(ClientArticle.site_profile_id == site_profile_id)

    if min_word_count is not None:
        query = query.where(ClientArticle.word_count >= min_word_count)

    if max_age_days is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        # Include articles without published_date OR those within the time window
        query = query.where(
            or_(
                ClientArticle.published_date.is_(None),
                ClientArticle.published_date >= cutoff_date.date()
            )
        )

    query = query.order_by(ClientArticle.published_date.desc().nulls_last())
    query = query.limit(limit).offset(offset)

    result = await db_session.execute(query)
    return list(result.scalars().all())


async def count_client_articles(
    db_session: AsyncSession,
    site_profile_id: Optional[int] = None,
) -> int:
    """
    Count client articles for a site profile.

    Args:
        db_session: Database session
        site_profile_id: Filter by site profile ID (optional)

    Returns:
        Total count of articles
    """
    query = select(func.count(ClientArticle.id)).where(
        ClientArticle.is_valid == True  # noqa: E712
    )

    if site_profile_id:
        query = query.where(ClientArticle.site_profile_id == site_profile_id)

    result = await db_session.execute(query)
    return result.scalar_one() or 0


async def update_client_article(
    db_session: AsyncSession,
    article: ClientArticle,
    **kwargs: dict,
) -> ClientArticle:
    """
    Update client article fields.

    Args:
        db_session: Database session
        article: ClientArticle instance to update
        **kwargs: Fields to update

    Returns:
        Updated ClientArticle instance
    """
    for key, value in kwargs.items():
        if hasattr(article, key):
            setattr(article, key, value)

    article.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(article)
    logger.info("Client article updated", article_id=article.id, site_profile_id=article.site_profile_id)
    return article


async def delete_client_article(
    db_session: AsyncSession,
    article: ClientArticle,
) -> None:
    """
    Soft delete a client article.

    Args:
        db_session: Database session
        article: ClientArticle instance to delete
    """
    article.is_valid = False
    article.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    logger.info("Client article deleted", article_id=article.id, site_profile_id=article.site_profile_id)


async def update_qdrant_point_id(
    db_session: AsyncSession,
    article: ClientArticle,
    qdrant_point_id: UUID,
) -> ClientArticle:
    """
    Update the Qdrant point ID for an article.

    Args:
        db_session: Database session
        article: ClientArticle instance
        qdrant_point_id: Qdrant point ID

    Returns:
        Updated ClientArticle instance
    """
    article.qdrant_point_id = qdrant_point_id
    article.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(article)
    logger.info(
        "Qdrant point ID updated",
        article_id=article.id,
        qdrant_point_id=str(qdrant_point_id),
    )
    return article

