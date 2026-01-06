"""API router for site analysis endpoints."""

import re
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import SiteAnalysisRequest
from python_scripts.api.schemas.responses import (
    ExecutionResponse,
    MetricComparison,
    SiteHistoryEntry,
    SiteHistoryResponse,
    SiteProfileResponse,
)
from python_scripts.api.services.audit_service import (
    _check_trend_pipeline,
    _save_domain_summaries_to_profile,
)
from python_scripts.api.utils.sites_utils import (
    _safe_json_field,
    compare_metrics,
)
from python_scripts.database.crud_executions import create_workflow_execution
from python_scripts.database.crud_profiles import (
    get_site_profile_by_domain,
    get_site_history,
    list_site_profiles,
)
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sites", tags=["sites"])

# Regex pour valider le format d'un domaine
DOMAIN_REGEX = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
)


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
            exc_info=True,
        )
        raise


@router.post(
    "/analyze",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start editorial analysis",
    description="""
    Start an editorial analysis workflow for a domain.
    
    This endpoint:
    1. Crawls pages from the domain (via sitemap or homepage)
    2. Analyzes editorial style using multiple LLMs (Llama3, Mistral, Phi3)
    3. Creates/updates the site profile with editorial characteristics
    4. Returns an execution_id for tracking progress
    
    Use the execution_id to:
    - Poll status: GET /api/v1/executions/{execution_id}
    - Stream progress: WebSocket /api/v1/executions/{execution_id}/stream
    - Get results: GET /api/v1/sites/{domain}
    """,
    responses={
        202: {
            "description": "Analysis started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "pending",
                        "start_time": None,
                        "estimated_duration_minutes": None,
                    }
                }
            }
        }
    },
)
async def analyze_site(
    request: SiteAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start editorial analysis for a domain.

    This workflow analyzes the editorial style of a website by:
    - Discovering pages via sitemap
    - Crawling and extracting content
    - Running multi-LLM analysis (language level, tone, audience, keywords, etc.)
    - Creating a comprehensive editorial profile

    Args:
        request: Analysis request with domain and max_pages
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id for tracking
        
    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/sites/analyze" \\
          -H "Content-Type: application/json" \\
          -d '{"domain": "innosys.fr", "max_pages": 50}'
        ```
        
        Response:
        ```json
        {
            "execution_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "pending",
            "start_time": null,
            "estimated_duration_minutes": null
        }
        ```
    """
    try:
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
        target_audience=_safe_json_field(profile.target_audience),
        activity_domains=_safe_json_field(profile.activity_domains),
        content_structure=_safe_json_field(profile.content_structure),
        keywords=_safe_json_field(profile.keywords),
        style_features=_safe_json_field(profile.style_features),
        pages_analyzed=profile.pages_analyzed,
        llm_models_used=_safe_json_field(profile.llm_models_used),
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
            target_audience=_safe_json_field(profile.target_audience),
            activity_domains=_safe_json_field(profile.activity_domains),
            content_structure=_safe_json_field(profile.content_structure),
            keywords=_safe_json_field(profile.keywords),
            style_features=_safe_json_field(profile.style_features),
            pages_analyzed=profile.pages_analyzed,
            llm_models_used=_safe_json_field(profile.llm_models_used),
        )
        for profile in profiles
    ]


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
            target_audience=_safe_json_field(profile.target_audience),
            activity_domains=_safe_json_field(profile.activity_domains),
            content_structure=_safe_json_field(profile.content_structure),
            keywords=_safe_json_field(profile.keywords),
            style_features=_safe_json_field(profile.style_features),
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


@router.post(
    "/{domain}/regenerate-summaries",
    response_model=Dict[str, Any],
    summary="Regenerate domain summaries",
    description="""
    Regenerate personalized summaries for all activity domains.
    
    This endpoint:
    1. Generates personalized summaries for each domain based on client articles
    2. Stores summaries in activity_domains.domain_details
    3. Updates topics_count and confidence for each domain
    
    Use this endpoint to:
    - Regenerate summaries after new articles are scraped
    - Update summaries when domain structure changes
    - Force refresh of domain summaries
    """,
    tags=["sites"],
)
async def regenerate_domain_summaries(
    domain: str = Path(
        ...,
        description="Valid domain name (e.g., example.com, innosys.fr)",
        examples=["innosys.fr", "example.com"],
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Regenerate personalized domain summaries and save to profile.
    
    Args:
        domain: Domain name (validated format)
        db: Database session
        
    Returns:
        Dictionary with regeneration results
        
    Raises:
        HTTPException: 422 if domain format is invalid, 404 if profile not found
    """
    # Validation du domaine
    if not DOMAIN_REGEX.match(domain):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid domain format: {domain}. Expected format: example.com",
        )
    
    # Get site profile
    profile = await get_site_profile_by_domain(db, domain)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site profile not found for domain: {domain}",
        )
    
    # Get trend execution if available
    trend_execution = await _check_trend_pipeline(db, domain)
    
    # Generate and save summaries
    try:
        await _save_domain_summaries_to_profile(
            db,
            profile,
            trend_execution=trend_execution,
        )
        
        # Get updated activity_domains to return
        activity_domains = _safe_json_field(profile.activity_domains) or {}
        domain_details = activity_domains.get("domain_details", {})
        
        return {
            "status": "success",
            "message": "Domain summaries regenerated successfully",
            "domain": domain,
            "domains_updated": len(domain_details),
            "domain_details": domain_details,
        }
    except Exception as e:
        logger.error(
            "Error regenerating domain summaries",
            domain=domain,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate summaries: {str(e)}",
        )
