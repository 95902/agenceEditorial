"""CRUD operations for CompetitorArticle model (T100 - US5)."""

from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import CompetitorArticle
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_competitor_article(
    db_session: AsyncSession,
    domain: str,
    url: str,
    url_hash: str,
    title: str,
    content_text: str,
    **kwargs: dict,
) -> CompetitorArticle:
    """
    Create a new competitor article.

    Args:
        db_session: Database session
        domain: Domain name
        url: Article URL
        url_hash: SHA256 hash of the URL
        title: Article title
        content_text: Article text content
        **kwargs: Additional article fields (author, published_date, content_html, word_count, keywords, article_metadata, qdrant_point_id)

    Returns:
        Created CompetitorArticle instance
    """
    article = CompetitorArticle(
        domain=domain,
        url=url,
        url_hash=url_hash,
        title=title,
        content_text=content_text,
        **kwargs,
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    logger.info("Competitor article created", domain=domain, url=url, article_id=article.id)
    return article


async def get_competitor_article_by_url(
    db_session: AsyncSession,
    url: str,
) -> Optional[CompetitorArticle]:
    """
    Get competitor article by URL.

    Args:
        db_session: Database session
        url: Article URL

    Returns:
        CompetitorArticle if found, None otherwise
    """
    result = await db_session.execute(
        select(CompetitorArticle).where(
            CompetitorArticle.url == url,
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_competitor_article_by_hash(
    db_session: AsyncSession,
    url_hash: str,
) -> Optional[CompetitorArticle]:
    """
    Get competitor article by URL hash.

    Args:
        db_session: Database session
        url_hash: SHA256 hash of the URL

    Returns:
        CompetitorArticle if found, None otherwise
    """
    result = await db_session.execute(
        select(CompetitorArticle).where(
            CompetitorArticle.url_hash == url_hash,
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_competitor_article_by_id(
    db_session: AsyncSession,
    article_id: int,
) -> Optional[CompetitorArticle]:
    """
    Get competitor article by ID.

    Args:
        db_session: Database session
        article_id: Article ID

    Returns:
        CompetitorArticle if found, None otherwise
    """
    result = await db_session.execute(
        select(CompetitorArticle).where(
            CompetitorArticle.id == article_id,
            CompetitorArticle.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def list_competitor_articles(
    db_session: AsyncSession,
    domain: Optional[str] = None,
    domains: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    min_word_count: Optional[int] = None,
    max_age_days: Optional[int] = None,
) -> List[CompetitorArticle]:
    """
    List competitor articles with optional filters.

    Args:
        db_session: Database session
        domain: Filter by single domain (optional)
        domains: Filter by multiple domains (optional)
        limit: Maximum number of articles to return
        offset: Number of articles to skip
        min_word_count: Minimum word count filter (optional)
        max_age_days: Maximum age in days filter (optional)

    Returns:
        List of CompetitorArticle instances
    """
    query = select(CompetitorArticle).where(
        CompetitorArticle.is_valid == True  # noqa: E712
    )

    if domain:
        query = query.where(CompetitorArticle.domain == domain)
    elif domains:
        query = query.where(CompetitorArticle.domain.in_(domains))

    if min_word_count is not None:
        query = query.where(CompetitorArticle.word_count >= min_word_count)

    if max_age_days is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        # Include articles without published_date OR those within the time window
        query = query.where(
            or_(
                CompetitorArticle.published_date.is_(None),
                CompetitorArticle.published_date >= cutoff_date.date()
            )
        )

    query = query.order_by(CompetitorArticle.published_date.desc().nulls_last())
    query = query.limit(limit).offset(offset)

    result = await db_session.execute(query)
    return list(result.scalars().all())


async def count_competitor_articles(
    db_session: AsyncSession,
    domain: Optional[str] = None,
) -> int:
    """
    Count competitor articles for a domain.

    Args:
        db_session: Database session
        domain: Filter by domain (optional)

    Returns:
        Total count of articles
    """
    query = select(func.count(CompetitorArticle.id)).where(
        CompetitorArticle.is_valid == True  # noqa: E712
    )

    if domain:
        query = query.where(CompetitorArticle.domain == domain)

    result = await db_session.execute(query)
    return result.scalar_one() or 0


async def update_competitor_article(
    db_session: AsyncSession,
    article: CompetitorArticle,
    **kwargs: dict,
) -> CompetitorArticle:
    """
    Update competitor article fields.

    Args:
        db_session: Database session
        article: CompetitorArticle instance to update
        **kwargs: Fields to update

    Returns:
        Updated CompetitorArticle instance
    """
    for key, value in kwargs.items():
        if hasattr(article, key):
            setattr(article, key, value)

    article.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(article)
    logger.info("Competitor article updated", article_id=article.id, domain=article.domain)
    return article


async def delete_competitor_article(
    db_session: AsyncSession,
    article: CompetitorArticle,
) -> None:
    """
    Soft delete a competitor article.

    Args:
        db_session: Database session
        article: CompetitorArticle instance to delete
    """
    article.is_valid = False
    article.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    logger.info("Competitor article deleted", article_id=article.id, domain=article.domain)


async def update_qdrant_point_id(
    db_session: AsyncSession,
    article: CompetitorArticle,
    qdrant_point_id: UUID,
) -> CompetitorArticle:
    """
    Update the Qdrant point ID for an article.

    Args:
        db_session: Database session
        article: CompetitorArticle instance
        qdrant_point_id: Qdrant point ID

    Returns:
        Updated CompetitorArticle instance
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


async def get_articles_by_domain_batch(
    db_session: AsyncSession,
    domains: List[str],
    limit_per_domain: int = 100,
) -> dict[str, List[CompetitorArticle]]:
    """
    Get articles for multiple domains in batch.

    Args:
        db_session: Database session
        domains: List of domain names
        limit_per_domain: Maximum articles per domain

    Returns:
        Dictionary mapping domain to list of articles
    """
    result = {}
    for domain in domains:
        articles = await list_competitor_articles(
            db_session,
            domain=domain,
            limit=limit_per_domain,
        )
        result[domain] = articles
    return result


async def update_article_topic_id(
    db_session: AsyncSession,
    article: CompetitorArticle,
    topic_id: Optional[int],
) -> CompetitorArticle:
    """
    Update the topic_id for an article (T127 - US7).
    
    Args:
        db_session: Database session
        article: CompetitorArticle instance
        topic_id: Topic ID to assign (None to remove)
        
    Returns:
        Updated CompetitorArticle instance
    """
    article.topic_id = topic_id
    article.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(article)
    logger.info(
        "Article topic_id updated",
        article_id=article.id,
        topic_id=topic_id,
    )
    return article


async def update_articles_topic_ids_batch(
    db_session: AsyncSession,
    article_topic_mapping: Dict[int, int],
) -> None:
    """
    Update topic_ids for multiple articles in batch (T127 - US7).
    
    Args:
        db_session: Database session
        article_topic_mapping: Dictionary mapping article_id to topic_id
    """
    from sqlalchemy import update
    
    if not article_topic_mapping:
        return
    
    # Update articles in batch
    for article_id, topic_id in article_topic_mapping.items():
        await db_session.execute(
            update(CompetitorArticle)
            .where(CompetitorArticle.id == article_id)
            .values(
                topic_id=topic_id,
                updated_at=datetime.now(timezone.utc),
            )
        )
    
    await db_session.commit()
    logger.info(
        "Articles topic_ids updated in batch",
        count=len(article_topic_mapping),
    )

