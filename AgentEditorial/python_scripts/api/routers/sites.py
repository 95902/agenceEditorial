"""API router for site analysis endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import SiteAnalysisRequest
from python_scripts.api.schemas.responses import (
    ExecutionResponse,
    ErrorResponse,
    MetricComparison,
    SiteHistoryEntry,
    SiteHistoryResponse,
    SiteProfileResponse,
)
from python_scripts.database.crud_executions import get_workflow_execution
from python_scripts.database.crud_profiles import (
    get_site_profile_by_domain,
    get_site_history,
    list_site_profiles,
)
from python_scripts.database.models import SiteProfile
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sites", tags=["sites"])


async def run_analysis_background(
    domain: str,
    max_pages: int,
    execution_id: UUID,
) -> None:
    """
    Background task to run editorial analysis.

    Args:
        domain: Domain to analyze
        max_pages: Maximum pages to crawl
        execution_id: Execution ID
    """
    try:
        from python_scripts.database.db_session import AsyncSessionLocal

        # Create new session for background task
        async with AsyncSessionLocal() as db_session:
            orchestrator = EditorialAnalysisOrchestrator(db_session)
            await orchestrator.run_editorial_analysis(
                domain=domain,
                max_pages=max_pages,
                execution_id=execution_id,
            )
    except Exception as e:
        logger.error(
            "Background analysis failed",
            execution_id=str(execution_id),
            domain=domain,
            error=str(e),
        )


@router.post(
    "/analyze",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start editorial analysis",
    description="Start an editorial analysis workflow for a domain. Returns execution_id for polling.",
)
async def analyze_site(
    request: SiteAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start editorial analysis for a domain.

    Args:
        request: Analysis request with domain and max_pages
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id
    """
    try:
        from python_scripts.database.crud_executions import create_workflow_execution

        # Create execution record
        execution = await create_workflow_execution(
            db,
            workflow_type="editorial_analysis",
            input_data={"domain": request.domain, "max_pages": request.max_pages},
            status="pending",
        )

        # Start background task
        background_tasks.add_task(
            run_analysis_background,
            request.domain,
            request.max_pages,
            execution.execution_id,
        )

        logger.info(
            "Analysis started",
            execution_id=str(execution.execution_id),
            domain=request.domain,
        )

        return ExecutionResponse(
            execution_id=execution.execution_id,
            status="pending",
            start_time=execution.start_time,
        )

    except Exception as e:
        logger.error("Failed to start analysis", domain=request.domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {e}",
        )


@router.get(
    "/{domain}",
    response_model=SiteProfileResponse,
    summary="Get site profile",
    description="Get the latest editorial profile for a domain.",
)
async def get_site_profile(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> SiteProfileResponse:
    """
    Get site profile by domain.

    Args:
        domain: Domain name
        db: Database session

    Returns:
        Site profile response

    Raises:
        HTTPException: If profile not found
    """
    profile = await get_site_profile_by_domain(db, domain)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for domain: {domain}",
        )

    return SiteProfileResponse(
        domain=profile.domain,
        analysis_date=profile.analysis_date,
        language_level=profile.language_level,
        editorial_tone=profile.editorial_tone,
        target_audience=profile.target_audience,
        activity_domains=profile.activity_domains,
        content_structure=profile.content_structure,
        keywords=profile.keywords,
        style_features=profile.style_features,
        pages_analyzed=profile.pages_analyzed,
        llm_models_used=profile.llm_models_used,
    )


@router.get(
    "",
    response_model=List[SiteProfileResponse],
    summary="List all analyzed sites",
    description="Get a list of all domains that have been analyzed.",
)
async def list_sites(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[SiteProfileResponse]:
    """
    List all analyzed sites.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        db: Database session

    Returns:
        List of site profiles
    """
    profiles = await list_site_profiles(db, limit=limit, offset=offset)
    return [
        SiteProfileResponse(
            domain=profile.domain,
            analysis_date=profile.analysis_date,
            language_level=profile.language_level,
            editorial_tone=profile.editorial_tone,
            target_audience=profile.target_audience,
            activity_domains=profile.activity_domains,
            content_structure=profile.content_structure,
            keywords=profile.keywords,
            style_features=profile.style_features,
            pages_analyzed=profile.pages_analyzed,
            llm_models_used=profile.llm_models_used,
        )
        for profile in profiles
    ]


def compare_metrics(
    current_profile: SiteProfile,
    previous_profile: Optional[SiteProfile],
) -> List[MetricComparison]:
    """
    Compare metrics between current and previous analysis.

    Args:
        current_profile: Current site profile
        previous_profile: Previous site profile (if available)

    Returns:
        List of metric comparisons
    """
    comparisons: List[MetricComparison] = []

    if not previous_profile:
        return comparisons

    # Compare pages_analyzed
    if current_profile.pages_analyzed and previous_profile.pages_analyzed:
        change = (
            (current_profile.pages_analyzed - previous_profile.pages_analyzed)
            / previous_profile.pages_analyzed
            * 100
            if previous_profile.pages_analyzed > 0
            else 0
        )
        trend = "increasing" if change > 0 else "decreasing" if change < 0 else "stable"
        comparisons.append(
            MetricComparison(
                metric_name="pages_analyzed",
                current_value=current_profile.pages_analyzed,
                previous_value=previous_profile.pages_analyzed,
                change=round(change, 2),
                trend=trend,
            )
        )

    # Compare language_level (if changed)
    if current_profile.language_level and previous_profile.language_level:
        if current_profile.language_level != previous_profile.language_level:
            comparisons.append(
                MetricComparison(
                    metric_name="language_level",
                    current_value=current_profile.language_level,
                    previous_value=previous_profile.language_level,
                    change=None,
                    trend="changed",
                )
            )

    # Compare editorial_tone (if changed)
    if current_profile.editorial_tone and previous_profile.editorial_tone:
        if current_profile.editorial_tone != previous_profile.editorial_tone:
            comparisons.append(
                MetricComparison(
                    metric_name="editorial_tone",
                    current_value=current_profile.editorial_tone,
                    previous_value=previous_profile.editorial_tone,
                    change=None,
                    trend="changed",
                )
            )

    return comparisons


@router.get(
    "/{domain}/history",
    response_model=SiteHistoryResponse,
    summary="Get site analysis history",
    description="Get historical analyses for a domain with metric comparisons.",
)
async def get_site_history_endpoint(
    domain: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> SiteHistoryResponse:
    """
    Get historical analyses for a domain.

    Args:
        domain: Domain name
        limit: Maximum number of historical records
        db: Database session

    Returns:
        Site history response with comparisons

    Raises:
        HTTPException: If no history found
    """
    # Get current profile
    current_profile = await get_site_profile_by_domain(db, domain)
    if not current_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for domain: {domain}",
        )

    # Get historical profiles
    history_profiles = await get_site_history(db, domain, limit=limit)

    if not history_profiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis history found for domain: {domain}",
        )

    # Convert to history entries
    history_entries = [
        SiteHistoryEntry(
            analysis_date=profile.analysis_date,
            language_level=profile.language_level,
            editorial_tone=profile.editorial_tone,
            pages_analyzed=profile.pages_analyzed,
            target_audience=profile.target_audience,
            activity_domains=profile.activity_domains,
            content_structure=profile.content_structure,
            keywords=profile.keywords,
            style_features=profile.style_features,
        )
        for profile in history_profiles
    ]

    # Compare metrics (current vs previous)
    previous_profile = history_profiles[1] if len(history_profiles) > 1 else None
    metric_comparisons = compare_metrics(current_profile, previous_profile)

    return SiteHistoryResponse(
        domain=domain,
        total_analyses=len(history_profiles),
        history=history_entries,
        metric_comparisons=metric_comparisons if metric_comparisons else None,
        first_analysis_date=history_profiles[-1].analysis_date if history_profiles else None,
        last_analysis_date=history_profiles[0].analysis_date if history_profiles else None,
    )

