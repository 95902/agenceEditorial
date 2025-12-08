"""CRUD operations for SiteProfile model."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import SiteProfile
from python_scripts.utils.json_utils import normalize_json_value
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_site_profile(
    db_session: AsyncSession,
    domain: str,
    **kwargs: dict,
) -> SiteProfile:
    """
    Create a new site profile.

    Args:
        db_session: Database session
        domain: Domain name
        **kwargs: Additional profile fields

    Returns:
        Created SiteProfile instance
    """
    profile = SiteProfile(domain=domain, **kwargs)
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    logger.info("Site profile created", domain=domain, profile_id=profile.id)
    return profile


async def get_site_profile_by_domain(
    db_session: AsyncSession,
    domain: str,
) -> Optional[SiteProfile]:
    """
    Get site profile by domain.

    Args:
        db_session: Database session
        domain: Domain name

    Returns:
        SiteProfile if found, None otherwise
    """
    result = await db_session.execute(
        select(SiteProfile).where(
            SiteProfile.domain == domain,
            SiteProfile.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_site_profile_by_id(
    db_session: AsyncSession,
    profile_id: int,
) -> Optional[SiteProfile]:
    """
    Get site profile by ID.

    Args:
        db_session: Database session
        profile_id: Profile ID

    Returns:
        SiteProfile if found, None otherwise
    """
    result = await db_session.execute(
        select(SiteProfile).where(
            SiteProfile.id == profile_id,
            SiteProfile.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def update_site_profile(
    db_session: AsyncSession,
    profile: SiteProfile,
    **kwargs: dict,
) -> SiteProfile:
    """
    Update site profile fields.

    Args:
        db_session: Database session
        profile: SiteProfile instance to update
        **kwargs: Fields to update

    Returns:
        Updated SiteProfile instance
    """
    # JSON fields that should be normalized
    json_fields = {
        "target_audience",
        "activity_domains",
        "content_structure",
        "keywords",
        "style_features",
        "llm_models_used",
    }
    
    for key, value in kwargs.items():
        if hasattr(profile, key):
            # Normalize JSON fields to ensure proper structure
            if key in json_fields and value is not None:
                normalized_value = normalize_json_value(value)
                setattr(profile, key, normalized_value)
            else:
                setattr(profile, key, value)

    profile.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(profile)
    logger.info("Site profile updated", domain=profile.domain, profile_id=profile.id)
    return profile


async def list_site_profiles(
    db_session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> List[SiteProfile]:
    """
    List all site profiles.

    Args:
        db_session: Database session
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of SiteProfile instances
    """
    result = await db_session.execute(
        select(SiteProfile)
        .where(SiteProfile.is_valid == True)  # noqa: E712
        .order_by(SiteProfile.analysis_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_site_history(
    db_session: AsyncSession,
    domain: str,
    limit: int = 50,
) -> List[SiteProfile]:
    """
    Get historical analyses for a domain.

    Args:
        db_session: Database session
        domain: Domain name
        limit: Maximum number of historical records

    Returns:
        List of SiteProfile instances ordered by analysis_date
    """
    result = await db_session.execute(
        select(SiteProfile)
        .where(
            SiteProfile.domain == domain,
            SiteProfile.is_valid == True,  # noqa: E712
        )
        .order_by(SiteProfile.analysis_date.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

