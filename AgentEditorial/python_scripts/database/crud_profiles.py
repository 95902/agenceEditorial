"""CRUD operations for SiteProfile model."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import SiteProfile, SiteAnalysisResult
from python_scripts.database.crud_executions import get_analysis_results_by_profile
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


async def get_client_context_for_enrichment(
    db_session: AsyncSession,
    domain: str,
) -> Optional[Dict[str, Any]]:
    """
    Get complete client context for article enrichment.
    
    Retrieves:
    - SiteProfile: editorial tone, target audience, activity domains, keywords, style
    - SiteAnalysisResult (phase "synthesis"): complete synthesis of the site
    
    Args:
        db_session: Database session
        domain: Client domain (e.g., "innosys.fr")
        
    Returns:
        Dictionary with complete client context, or None if not found
    """
    # Get latest site profile
    profile = await get_site_profile_by_domain(db_session, domain)
    if not profile:
        logger.warning("Site profile not found", domain=domain)
        return None
    
    # Get analysis results (especially synthesis phase)
    analysis_results = await get_analysis_results_by_profile(db_session, profile.id)
    
    # Find synthesis phase result
    synthesis_result = None
    for result in analysis_results:
        if result.analysis_phase == "synthesis":
            synthesis_result = result
            break
    
    # Build context dictionary
    context = {
        "domain": profile.domain,
        "editorial_tone": profile.editorial_tone,
        "language_level": profile.language_level,
        "target_audience": profile.target_audience or {},
        "activity_domains": profile.activity_domains or {},
        "keywords": profile.keywords or {},
        "style_features": profile.style_features or {},
        "content_structure": profile.content_structure or {},
    }
    
    # Add synthesis data if available
    if synthesis_result and synthesis_result.phase_results:
        phase_results = synthesis_result.phase_results
        if isinstance(phase_results, dict):
            # Extract key information from synthesis
            context["synthesis"] = {
                "keywords": phase_results.get("keywords", {}),
                "editorial_tone": phase_results.get("editorial_tone"),
                "target_audience": phase_results.get("target_audience", {}),
                "activity_domains": phase_results.get("activity_domains", {}),
                "content_structure": phase_results.get("content_structure", {}),
                "style_features": phase_results.get("style_features", {}),
            }
            context["llm_model_used"] = synthesis_result.llm_model_used
    
    logger.debug("Client context retrieved", domain=domain, has_synthesis=synthesis_result is not None)
    return context

