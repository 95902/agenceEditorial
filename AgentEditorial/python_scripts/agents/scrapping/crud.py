"""CRUD operations for discovery-related database models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from python_scripts.database.models import (
    DiscoveryLog,
    SiteDiscoveryProfile,
    UrlDiscoveryScore,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Site Discovery Profile CRUD
# ============================================================================


async def get_site_discovery_profile(
    db_session: AsyncSession,
    domain: str,
) -> Optional[SiteDiscoveryProfile]:
    """Get site discovery profile by domain."""
    stmt = select(SiteDiscoveryProfile).where(SiteDiscoveryProfile.domain == domain)
    result = await db_session.execute(stmt)
    return result.scalar_one_or_none()


async def create_site_discovery_profile(
    db_session: AsyncSession,
    domain: str,
    profile_data: Dict[str, Any],
) -> SiteDiscoveryProfile:
    """Create a new site discovery profile."""
    profile = SiteDiscoveryProfile(
        domain=domain,
        cms_detected=profile_data.get("cms_detected"),
        cms_version=profile_data.get("cms_version"),
        has_rest_api=profile_data.get("has_rest_api", False),
        api_endpoints=profile_data.get("api_endpoints", {}),
        sitemap_urls=profile_data.get("sitemap_urls", []),
        rss_feeds=profile_data.get("rss_feeds", []),
        blog_listing_pages=profile_data.get("blog_listing_pages", []),
        url_patterns=profile_data.get("url_patterns", {}),
        article_url_regex=profile_data.get("article_url_regex"),
        pagination_pattern=profile_data.get("pagination_pattern"),
        content_selector=profile_data.get("content_selector"),
        title_selector=profile_data.get("title_selector"),
        date_selector=profile_data.get("date_selector"),
        author_selector=profile_data.get("author_selector"),
        image_selector=profile_data.get("image_selector"),
        last_profiled_at=datetime.now(timezone.utc),
        is_active=True,
        notes=profile_data.get("notes"),
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


async def update_site_discovery_profile(
    db_session: AsyncSession,
    domain: str,
    update_data: Dict[str, Any],
) -> Optional[SiteDiscoveryProfile]:
    """Update site discovery profile."""
    stmt = (
        update(SiteDiscoveryProfile)
        .where(SiteDiscoveryProfile.domain == domain)
        .values(**update_data)
        .returning(SiteDiscoveryProfile)
    )
    result = await db_session.execute(stmt)
    await db_session.flush()
    return result.scalar_one_or_none()


# ============================================================================
# URL Discovery Score CRUD
# ============================================================================


async def save_url_discovery_score(
    db_session: AsyncSession,
    domain: str,
    url: str,
    url_hash: str,
    discovery_source: str,
    initial_score: int,
    score_breakdown: Dict[str, Any],
    discovered_in: Optional[str] = None,
    title_hint: Optional[str] = None,
    date_hint: Optional[datetime] = None,
) -> UrlDiscoveryScore:
    """Save or update URL discovery score."""
    # Check if exists
    stmt = select(UrlDiscoveryScore).where(
        UrlDiscoveryScore.domain == domain,
        UrlDiscoveryScore.url_hash == url_hash,
    )
    result = await db_session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update
        existing.initial_score = initial_score
        existing.score_breakdown = score_breakdown
        existing.discovered_in = discovered_in
        existing.title_hint = title_hint
        existing.date_hint = date_hint
        await db_session.flush()
        return existing
    else:
        # Create
        score = UrlDiscoveryScore(
            domain=domain,
            url=url,
            url_hash=url_hash,
            discovery_source=discovery_source,
            discovered_in=discovered_in,
            initial_score=initial_score,
            score_breakdown=score_breakdown,
            title_hint=title_hint,
            date_hint=date_hint,
        )
        db_session.add(score)
        await db_session.flush()
        return score


async def update_url_scrape_status(
    db_session: AsyncSession,
    domain: str,
    url_hash: str,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Update URL scrape status."""
    stmt = (
        update(UrlDiscoveryScore)
        .where(
            UrlDiscoveryScore.domain == domain,
            UrlDiscoveryScore.url_hash == url_hash,
        )
        .values(
            was_scraped=True,
            scrape_status=status,
            scraped_at=datetime.now(timezone.utc),
        )
    )
    await db_session.execute(stmt)
    await db_session.flush()


async def update_url_validation(
    db_session: AsyncSession,
    domain: str,
    url_hash: str,
    is_valid: bool,
    reason: Optional[str] = None,
    final_score: Optional[int] = None,
) -> None:
    """Update URL validation status."""
    stmt = (
        update(UrlDiscoveryScore)
        .where(
            UrlDiscoveryScore.domain == domain,
            UrlDiscoveryScore.url_hash == url_hash,
        )
        .values(
            is_valid_article=is_valid,
            validation_reason=reason,
            final_score=final_score,
        )
    )
    await db_session.execute(stmt)
    await db_session.flush()


# ============================================================================
# Discovery Log CRUD
# ============================================================================


async def save_discovery_log(
    db_session: AsyncSession,
    domain: str,
    operation: str,
    status: str,
    phase: Optional[str] = None,
    execution_id: Optional[str] = None,
    urls_found: int = 0,
    urls_scraped: int = 0,
    urls_valid: int = 0,
    sources_used: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    duration_seconds: Optional[float] = None,
) -> DiscoveryLog:
    """Save discovery log."""
    from uuid import UUID

    log = DiscoveryLog(
        domain=domain,
        execution_id=UUID(execution_id) if execution_id else None,
        operation=operation,
        phase=phase,
        status=status,
        urls_found=urls_found,
        urls_scraped=urls_scraped,
        urls_valid=urls_valid,
        sources_used=sources_used or [],
        errors=errors or [],
        duration_seconds=duration_seconds,
    )
    db_session.add(log)
    await db_session.flush()
    return log

