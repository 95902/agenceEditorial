"""CRUD operations for CrawlCache model."""

import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import CrawlCache
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

# Cache TTL: 30 days
CACHE_TTL_DAYS = 30


def generate_url_hash(url: str) -> str:
    """Generate SHA256 hash for URL."""
    return hashlib.sha256(url.encode()).hexdigest()


def generate_content_hash(content: str) -> str:
    """Generate SHA256 hash for content."""
    return hashlib.sha256(content.encode()).hexdigest()


async def get_crawl_cache(
    db_session: AsyncSession,
    url: str,
) -> Optional[CrawlCache]:
    """
    Get cached crawl result for a URL (if not expired).

    Args:
        db_session: Database session
        url: URL to check

    Returns:
        CrawlCache if found and not expired, None otherwise
    """
    url_hash = generate_url_hash(url)
    
    result = await db_session.execute(
        select(CrawlCache).where(CrawlCache.url_hash == url_hash)
    )
    cached = result.scalar_one_or_none()
    
    if cached:
        # Check if cache is expired
        if cached.expires_at < datetime.now(timezone.utc):
            logger.debug("Crawl cache expired", url=url)
            return None
        
        # Update access metadata
        cached.last_accessed = datetime.now(timezone.utc)
        cached.cache_hit_count += 1
        await db_session.commit()
        await db_session.refresh(cached)
        
        return cached
    
    return None


async def create_or_update_crawl_cache(
    db_session: AsyncSession,
    url: str,
    cached_content: str,
    cached_metadata: Optional[Dict[str, Any]] = None,
    content_hash: Optional[str] = None,
) -> CrawlCache:
    """
    Create or update crawl cache entry.

    Args:
        db_session: Database session
        url: URL that was crawled
        cached_content: Text content to cache
        cached_metadata: Optional metadata (title, description, etc.)
        content_hash: Optional content hash (will be generated if not provided)

    Returns:
        Created or updated CrawlCache instance
    """
    url_hash = generate_url_hash(url)
    
    # Generate content hash if not provided
    if content_hash is None:
        content_hash = generate_content_hash(cached_content)
    
    # Extract domain from URL
    parsed = urlparse(url)
    domain = parsed.netloc
    
    # Check if exists
    result = await db_session.execute(
        select(CrawlCache).where(CrawlCache.url_hash == url_hash)
    )
    cached = result.scalar_one_or_none()
    
    expires_at = datetime.now(timezone.utc) + timedelta(days=CACHE_TTL_DAYS)
    
    if cached:
        # Update existing
        cached.cached_content = cached_content
        cached.cached_metadata = cached_metadata or {}
        cached.content_hash = content_hash
        cached.expires_at = expires_at
        cached.last_accessed = datetime.now(timezone.utc)
    else:
        # Create new
        cached = CrawlCache(
            url=url,
            url_hash=url_hash,
            content_hash=content_hash,
            domain=domain,
            cached_content=cached_content,
            cached_metadata=cached_metadata or {},
            expires_at=expires_at,
            last_accessed=datetime.now(timezone.utc),
        )
        db_session.add(cached)
    
    await db_session.commit()
    await db_session.refresh(cached)
    logger.debug("Crawl cache saved", url=url, domain=domain)
    return cached


async def delete_crawl_cache(
    db_session: AsyncSession,
    url: str,
) -> None:
    """
    Delete crawl cache entry for a URL.

    Args:
        db_session: Database session
        url: URL to delete from cache
    """
    url_hash = generate_url_hash(url)
    
    result = await db_session.execute(
        select(CrawlCache).where(CrawlCache.url_hash == url_hash)
    )
    cached = result.scalar_one_or_none()
    
    if cached:
        await db_session.delete(cached)
        await db_session.commit()
        logger.debug("Crawl cache deleted", url=url)


async def delete_expired_crawl_cache(
    db_session: AsyncSession,
) -> int:
    """
    Delete all expired crawl cache entries.

    Args:
        db_session: Database session

    Returns:
        Number of deleted entries
    """
    now = datetime.now(timezone.utc)
    
    result = await db_session.execute(
        select(CrawlCache).where(CrawlCache.expires_at < now)
    )
    expired = result.scalars().all()
    
    count = len(expired)
    for entry in expired:
        await db_session.delete(entry)
    
    if count > 0:
        await db_session.commit()
        logger.info("Expired crawl cache entries deleted", count=count)
    
    return count


async def get_crawl_cache_by_domain(
    db_session: AsyncSession,
    domain: str,
    limit: int = 100,
) -> List[CrawlCache]:
    """
    Get all cached entries for a domain.

    Args:
        db_session: Database session
        domain: Domain name
        limit: Maximum number of entries to return

    Returns:
        List of CrawlCache entries
    """
    result = await db_session.execute(
        select(CrawlCache)
        .where(
            and_(
                CrawlCache.domain == domain,
                CrawlCache.expires_at >= datetime.now(timezone.utc),
            )
        )
        .order_by(CrawlCache.last_accessed.desc())
        .limit(limit)
    )
    return list(result.scalars().all())








