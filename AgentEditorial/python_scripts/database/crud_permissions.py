"""CRUD operations for ScrapingPermission model (T102 - US5)."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import ScrapingPermission
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

# Cache TTL: 24 hours
CACHE_TTL_HOURS = 24


async def get_scraping_permission(
    db_session: AsyncSession,
    domain: str,
) -> Optional[ScrapingPermission]:
    """
    Get scraping permission for a domain (with cache check).

    Args:
        db_session: Database session
        domain: Domain name

    Returns:
        ScrapingPermission if found and not expired, None otherwise
    """
    result = await db_session.execute(
        select(ScrapingPermission).where(ScrapingPermission.domain == domain)
    )
    permission = result.scalar_one_or_none()
    
    if permission:
        # Check if cache is expired
        if permission.cache_expires_at < datetime.now(timezone.utc):
            logger.debug("Scraping permission cache expired", domain=domain)
            return None
        return permission
    
    return None


async def create_or_update_scraping_permission(
    db_session: AsyncSession,
    domain: str,
    scraping_allowed: bool,
    disallowed_paths: list,
    crawl_delay: Optional[int] = None,
    user_agent_required: Optional[str] = None,
    robots_txt_content: Optional[str] = None,
) -> ScrapingPermission:
    """
    Create or update scraping permission for a domain.

    Args:
        db_session: Database session
        domain: Domain name
        scraping_allowed: Whether scraping is allowed
        disallowed_paths: List of disallowed paths
        crawl_delay: Crawl delay in seconds
        user_agent_required: Required user agent
        robots_txt_content: Original robots.txt content

    Returns:
        Created or updated ScrapingPermission instance
    """
    # Check if exists
    result = await db_session.execute(
        select(ScrapingPermission).where(ScrapingPermission.domain == domain)
    )
    permission = result.scalar_one_or_none()
    
    cache_expires_at = datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS)
    
    if permission:
        # Update existing
        permission.scraping_allowed = scraping_allowed
        permission.disallowed_paths = disallowed_paths
        permission.crawl_delay = crawl_delay
        permission.user_agent_required = user_agent_required
        permission.robots_txt_content = robots_txt_content
        permission.cache_expires_at = cache_expires_at
        permission.last_fetched = datetime.now(timezone.utc)
    else:
        # Create new
        permission = ScrapingPermission(
            domain=domain,
            scraping_allowed=scraping_allowed,
            disallowed_paths=disallowed_paths,
            crawl_delay=crawl_delay,
            user_agent_required=user_agent_required,
            robots_txt_content=robots_txt_content,
            cache_expires_at=cache_expires_at,
        )
        db_session.add(permission)
    
    await db_session.commit()
    await db_session.refresh(permission)
    logger.info("Scraping permission saved", domain=domain, allowed=scraping_allowed)
    return permission


async def delete_scraping_permission(
    db_session: AsyncSession,
    domain: str,
) -> None:
    """
    Delete scraping permission for a domain.

    Args:
        db_session: Database session
        domain: Domain name
    """
    result = await db_session.execute(
        select(ScrapingPermission).where(ScrapingPermission.domain == domain)
    )
    permission = result.scalar_one_or_none()
    
    if permission:
        await db_session.delete(permission)
        await db_session.commit()
        logger.info("Scraping permission deleted", domain=domain)

