"""API router for site analysis endpoints."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import SiteAnalysisRequest
from python_scripts.api.schemas.responses import (
    DataStatus,
    DomainDetail,
    ErrorResponse,
    ExecutionResponse,
    MetricComparison,
    PendingAuditResponse,
    SiteAuditResponse,
    SiteHistoryEntry,
    SiteHistoryResponse,
    SiteProfileResponse,
    WorkflowStep,
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


def _safe_json_field(value: Any) -> Optional[Dict[str, Any]]:
    """
    Safely convert a JSON field value to a dictionary.
    
    Handles cases where the value might be:
    - None -> return None
    - Already a dict -> return as-is
    - A JSON string -> try to parse
    - A malformed/truncated string -> return empty dict with error info
    
    Args:
        value: The value to convert
        
    Returns:
        A dictionary or None
    """
    if value is None:
        return None
    
    if isinstance(value, dict):
        return value
    
    if isinstance(value, str):
        value_stripped = value.strip()
        if value_stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value_stripped)
                if isinstance(parsed, dict):
                    return parsed
                elif isinstance(parsed, list):
                    return {"items": parsed}
                return {"value": parsed}
            except json.JSONDecodeError:
                # Malformed JSON - return empty dict with raw value indicator
                logger.warning(
                    "Malformed JSON field detected",
                    value_preview=value[:100] if len(value) > 100 else value,
                )
                return {"_raw_malformed": value[:200] if len(value) > 200 else value}
        # Not JSON-like string
        return {"value": value}
    
    # Other types - wrap in dict
    return {"value": str(value)}


# ============================================================
# Audit utility functions
# ============================================================

def _map_language_level_to_vocabulary(language_level: Optional[str]) -> str:
    """
    Map language_level to vocabulary description.
    
    Args:
        language_level: Language level string
        
    Returns:
        Vocabulary description
    """
    if not language_level:
        return "langage technique"
    
    mapping = {
        "simple": "langage accessible",
        "intermediate": "langage technique",
        "advanced": "spécialisé en technologie",
        "expert": "très spécialisé",
    }
    
    return mapping.get(language_level.lower(), "langage technique")


def _calculate_article_format(content_structure: Optional[Dict[str, Any]]) -> str:
    """
    Calculate article format from content_structure.
    
    Args:
        content_structure: Content structure dictionary
        
    Returns:
        Format description
    """
    if not content_structure or not isinstance(content_structure, dict):
        return "articles moyens (1000-2000 mots)"
    
    avg_word_count = content_structure.get("average_word_count")
    if not avg_word_count or not isinstance(avg_word_count, (int, float)):
        return "articles moyens (1000-2000 mots)"
    
    if avg_word_count < 1000:
        return "articles courts (< 1000 mots)"
    elif avg_word_count <= 2000:
        return "articles moyens (1000-2000 mots)"
    else:
        return "articles longs (1500-2500 mots)"


def _map_language_level_to_audience_level(language_level: Optional[str]) -> str:
    """
    Map language_level to audience level description.
    
    Args:
        language_level: Language level string
        
    Returns:
        Audience level description
    """
    if not language_level:
        return "Intermédiaire"
    
    mapping = {
        "simple": "Débutant",
        "intermediate": "Intermédiaire",
        "advanced": "Intermédiaire à Expert",
        "expert": "Expert",
    }
    
    return mapping.get(language_level.lower(), "Intermédiaire")


def _extract_audience_sectors(target_audience: Optional[Dict[str, Any]]) -> List[str]:
    """
    Extract sectors from target_audience.
    
    Args:
        target_audience: Target audience dictionary
        
    Returns:
        List of sectors
    """
    if not target_audience or not isinstance(target_audience, dict):
        return []
    
    # Try secondary first
    secondary = target_audience.get("secondary")
    if isinstance(secondary, list):
        return secondary
    
    # Try sectors field
    sectors = target_audience.get("sectors")
    if isinstance(sectors, list):
        return sectors
    
    # Try demographics.sectors
    demographics = target_audience.get("demographics", {})
    if isinstance(demographics, dict):
        demo_sectors = demographics.get("sectors")
        if isinstance(demo_sectors, list):
            return demo_sectors
    
    return []


def _slugify(text: str) -> str:
    """
    Convert text to slug format.
    
    Args:
        text: Text to slugify
        
    Returns:
        Slug string
    """
    import re
    
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text


def _count_articles_for_domain(
    articles: List[Any], domain_label: str
) -> int:
    """
    Count articles that match a domain label.
    
    Uses heuristics: check if domain keywords appear in article title or keywords.
    
    Args:
        articles: List of ClientArticle objects
        domain_label: Domain label to match
        
    Returns:
        Count of matching articles
    """
    if not articles or not domain_label:
        return 0
    
    # Extract keywords from domain label
    domain_keywords = set(domain_label.lower().split())
    
    count = 0
    for article in articles:
        # Check title
        title_lower = article.title.lower() if hasattr(article, "title") else ""
        if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
            count += 1
            continue
        
        # Check keywords field
        if hasattr(article, "keywords") and article.keywords:
            keywords = article.keywords
            if isinstance(keywords, dict):
                primary_keywords = keywords.get("primary_keywords", [])
                if isinstance(primary_keywords, list):
                    keywords_str = " ".join(str(k).lower() for k in primary_keywords)
                    if any(keyword in keywords_str for keyword in domain_keywords if len(keyword) > 3):
                        count += 1
                        continue
    
    return count


def _generate_domain_summary(
    articles: List[Any], domain_label: str, keywords: Optional[Dict[str, Any]]
) -> str:
    """
    Generate domain summary from articles and keywords.
    
    Args:
        articles: List of ClientArticle objects
        domain_label: Domain label
        keywords: Keywords dictionary from site profile
        
    Returns:
        Summary string
    """
    # Try to extract keywords from articles matching this domain
    matching_articles = []
    domain_keywords = set(domain_label.lower().split())
    
    for article in articles[:20]:  # Limit to first 20 for performance
        title_lower = article.title.lower() if hasattr(article, "title") else ""
        if any(keyword in title_lower for keyword in domain_keywords if len(keyword) > 3):
            matching_articles.append(article)
    
    # Extract keywords from matching articles
    extracted_keywords = []
    for article in matching_articles[:5]:  # Limit to 5 articles
        if hasattr(article, "keywords") and article.keywords:
            article_keywords = article.keywords
            if isinstance(article_keywords, dict):
                primary = article_keywords.get("primary_keywords", [])
                if isinstance(primary, list):
                    extracted_keywords.extend(primary[:3])  # Top 3 per article
    
    # Fallback to site profile keywords
    if not extracted_keywords and keywords:
        if isinstance(keywords, dict):
            primary_keywords = keywords.get("primary_keywords", [])
            if isinstance(primary_keywords, list):
                extracted_keywords = primary_keywords[:5]
    
    # Build summary
    if extracted_keywords:
        # Take unique keywords and join
        unique_keywords = list(dict.fromkeys(extracted_keywords))[:5]
        summary = ", ".join(str(k) for k in unique_keywords)
        return f"{summary}"
    else:
        # Fallback to domain label with generic description
        return f"{domain_label}, services et solutions"


async def _check_site_profile(
    db: AsyncSession, domain: str
) -> Optional[SiteProfile]:
    """
    Check if site profile exists for domain.
    
    Args:
        db: Database session
        domain: Domain name
        
    Returns:
        SiteProfile if exists, None otherwise
    """
    return await get_site_profile_by_domain(db, domain)


async def _check_competitors(
    db: AsyncSession, domain: str
) -> Optional[Any]:
    """
    Check if competitor search exists and is completed.
    
    Args:
        db: Database session
        domain: Domain name
        
    Returns:
        WorkflowExecution if exists and completed, None otherwise
    """
    from sqlalchemy import select, desc
    from python_scripts.database.models import WorkflowExecution
    
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "competitor_search",
            WorkflowExecution.status == "completed",
            WorkflowExecution.input_data["domain"].astext == domain,
        )
        .order_by(desc(WorkflowExecution.start_time))
        .limit(1)
    )
    
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()
    
    if execution and execution.output_data:
        competitors_data = execution.output_data.get("competitors", [])
        if competitors_data:
            return execution
    
    return None


async def _check_competitor_articles(
    db: AsyncSession, competitor_domains: List[str]
) -> tuple[int, bool]:
    """
    Count competitor articles and check if sufficient.
    
    Args:
        db: Database session
        competitor_domains: List of competitor domains
        
    Returns:
        Tuple of (count, is_sufficient) where is_sufficient is True if count >= 10
    """
    from python_scripts.database.crud_articles import count_competitor_articles
    
    if not competitor_domains:
        return (0, False)
    
    total_count = 0
    for comp_domain in competitor_domains:
        count = await count_competitor_articles(db, domain=comp_domain)
        total_count += count
    
    return (total_count, total_count >= 10)


async def _check_client_articles(
    db: AsyncSession, site_profile_id: int
) -> tuple[int, bool]:
    """
    Count client articles and check if sufficient.
    
    Args:
        db: Database session
        site_profile_id: Site profile ID
        
    Returns:
        Tuple of (count, is_sufficient) where is_sufficient is True if count >= 5
    """
    from python_scripts.database.crud_client_articles import count_client_articles
    
    count = await count_client_articles(db, site_profile_id=site_profile_id)
    return (count, count >= 5)


async def _check_trend_pipeline(
    db: AsyncSession, domain: str
) -> Optional[Any]:
    """
    Check if trend pipeline exists and is completed.
    
    Args:
        db: Database session
        domain: Client domain name
        
    Returns:
        TrendPipelineExecution if exists and all stages completed, None otherwise
    """
    from sqlalchemy import select, desc
    from python_scripts.database.models import TrendPipelineExecution
    
    stmt = (
        select(TrendPipelineExecution)
        .where(
            TrendPipelineExecution.client_domain == domain,
            TrendPipelineExecution.stage_1_clustering_status == "completed",
            TrendPipelineExecution.stage_2_temporal_status == "completed",
            TrendPipelineExecution.stage_3_llm_status == "completed",
        )
        .order_by(desc(TrendPipelineExecution.start_time))
        .limit(1)
    )
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def build_complete_audit_from_database(
    db: AsyncSession,
    domain: str,
    profile: SiteProfile,
    competitors_execution: Optional[Any],
    trend_execution: Optional[Any],
) -> SiteAuditResponse:
    """
    Build complete audit response from database data.
    
    All data is assumed to exist.
    
    Args:
        db: Database session
        domain: Domain name
        profile: SiteProfile instance
        competitors_execution: WorkflowExecution for competitors (optional)
        trend_execution: TrendPipelineExecution (optional)
        
    Returns:
        Complete SiteAuditResponse
    """
    from python_scripts.database.crud_client_articles import list_client_articles
    from sqlalchemy import select, desc
    from python_scripts.database.models import WorkflowExecution
    
    # 1. URL
    url = f"https://{domain}"
    
    # 2. Profile.style
    style = {
        "tone": profile.editorial_tone or "professionnel",
        "vocabulary": _map_language_level_to_vocabulary(profile.language_level),
        "format": _calculate_article_format(_safe_json_field(profile.content_structure)),
    }
    
    # 3. Profile.themes
    activity_domains = _safe_json_field(profile.activity_domains) or {}
    themes = activity_domains.get("primary_domains", [])
    
    # 4. Domains (domaines d'activité détaillés)
    domains_list = []
    
    # Récupérer les articles client pour calculer les stats
    client_articles = await list_client_articles(
        db, site_profile_id=profile.id, limit=1000
    )
    
    # Pour chaque domaine d'activité
    for domain_label in themes:
        # Calculer topics_count (nombre d'articles correspondants)
        topics_count = _count_articles_for_domain(client_articles, domain_label)
        
        # Calculer confidence (basé sur le nombre d'articles)
        total_articles = len(client_articles)
        if total_articles > 0:
            confidence = min(100, int((topics_count / total_articles) * 100))
        else:
            confidence = 0
        
        # Générer summary (basé sur les mots-clés des articles)
        summary = _generate_domain_summary(
            client_articles, domain_label, _safe_json_field(profile.keywords)
        )
        
        domains_list.append(
            DomainDetail(
                id=_slugify(domain_label),
                label=domain_label,
                confidence=confidence,
                topics_count=topics_count,
                summary=summary,
            )
        )
    
    # 5. Audience
    target_audience = _safe_json_field(profile.target_audience) or {}
    audience = {
        "type": target_audience.get("primary", "Professionnels IT"),
        "level": _map_language_level_to_audience_level(profile.language_level),
        "sectors": _extract_audience_sectors(target_audience),
    }
    
    # 6. Competitors (top 5, triés par similarity puis alphabétique)
    competitors = []
    if competitors_execution:
        competitors_data = competitors_execution.output_data.get("competitors", [])
        # Filtrer et formater les concurrents validés
        competitors_list = []
        for comp in competitors_data:
            if comp.get("validated", False) or comp.get("manual", False):
                relevance = comp.get("relevance_score", 0.0)
                domain_name = comp.get("domain", "")
                if domain_name:  # Ignorer les domaines vides
                    competitors_list.append({
                        "name": domain_name,
                        "similarity": int(relevance * 100),
                    })
        
        # Trier : d'abord par similarity (décroissant), puis par nom (alphabétique)
        competitors_list.sort(key=lambda x: (-x["similarity"], x["name"]))
        
        # Prendre les 5 meilleurs
        competitors = competitors_list[:5]
    
    # 7. took_ms (durée de la dernière analyse)
    took_ms = 0
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "editorial_analysis",
            WorkflowExecution.status == "completed",
            WorkflowExecution.input_data["domain"].astext == domain,
        )
        .order_by(desc(WorkflowExecution.start_time))
        .limit(1)
    )
    result = await db.execute(stmt)
    last_execution = result.scalar_one_or_none()
    
    if last_execution and last_execution.duration_seconds:
        took_ms = last_execution.duration_seconds * 1000
    
    return SiteAuditResponse(
        url=url,
        profile={
            "style": style,
            "themes": themes,
        },
        domains=domains_list,
        audience=audience,
        competitors=competitors,
        took_ms=took_ms,
    )


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


# ============================================================
# Audit endpoint functions
# ============================================================

async def wait_for_execution_completion(
    db: AsyncSession,
    execution_id: UUID,
    timeout: int = 600,
    poll_interval: int = 5,
) -> None:
    """
    Wait for an execution to complete.
    
    Args:
        db: Database session
        execution_id: Execution ID to wait for
        timeout: Maximum wait time in seconds
        poll_interval: Polling interval in seconds
        
    Raises:
        TimeoutError: If execution doesn't complete within timeout
        RuntimeError: If execution fails
    """
    from datetime import timedelta
    from python_scripts.database.crud_executions import get_workflow_execution
    
    start_time = datetime.now()
    timeout_time = start_time + timedelta(seconds=timeout)
    
    while datetime.now() < timeout_time:
        execution = await get_workflow_execution(db, execution_id)
        
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        if execution.status == "completed":
            return
        
        if execution.status == "failed":
            raise RuntimeError(
                f"Execution {execution_id} failed: {execution.error_message or 'Unknown error'}"
            )
        
        await asyncio.sleep(poll_interval)
    
    raise TimeoutError(
        f"Execution {execution_id} did not complete within {timeout} seconds"
    )


async def run_missing_workflows_chain(
    domain: str,
    orchestrator_execution_id: UUID,
    needs_analysis: bool,
    needs_competitors: bool,
    needs_scraping: bool,
    needs_client_scraping: bool,
    needs_trend_pipeline: bool,
    profile_id: Optional[int],
) -> None:
    """
    Execute the chain of missing workflows sequentially.
    
    Order:
    1. Editorial analysis (sites/analyze)
    2. Competitor search (competitors/search) - after #1
    3. Client scraping (discovery/client-scrape) - after #1
    4. Competitor scraping (discovery/scrape) - after #2
    5. Trend pipeline (trend-pipeline/analyze) - after #3 and #4
    
    Args:
        domain: Domain name
        orchestrator_execution_id: Orchestrator execution ID
        needs_analysis: Whether editorial analysis is needed
        needs_competitors: Whether competitor search is needed
        needs_scraping: Whether competitor scraping is needed
        needs_client_scraping: Whether client scraping is needed
        needs_trend_pipeline: Whether trend pipeline is needed
        profile_id: Site profile ID (if already exists)
    """
    from python_scripts.database.db_session import AsyncSessionLocal
    from python_scripts.database.crud_executions import (
        get_workflow_execution,
        update_workflow_execution,
        create_workflow_execution,
    )
    from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator
    from python_scripts.agents.scrapping import EnhancedScrapingAgent
    from sqlalchemy import select, desc
    from python_scripts.database.models import WorkflowExecution
    
    async with AsyncSessionLocal() as db:
        try:
            orchestrator = EditorialAnalysisOrchestrator(db)
            current_profile_id = profile_id
            
            # Étape 1: Editorial Analysis
            if needs_analysis:
                logger.info("Step 1: Starting editorial analysis", domain=domain)
                analysis_execution = await create_workflow_execution(
                    db,
                    workflow_type="editorial_analysis",
                    input_data={"domain": domain, "max_pages": 50},
                    status="pending",
                )
                
                await orchestrator.run_editorial_analysis(
                    domain=domain,
                    max_pages=50,
                    execution_id=analysis_execution.execution_id,
                )
                
                await wait_for_execution_completion(
                    db, analysis_execution.execution_id, timeout=600
                )
                
                # Récupérer le profile créé
                profile = await get_site_profile_by_domain(db, domain)
                if profile:
                    current_profile_id = profile.id
            
            # Étape 2: Competitor Search
            if needs_competitors:
                logger.info("Step 2: Starting competitor search", domain=domain)
                competitor_execution = await create_workflow_execution(
                    db,
                    workflow_type="competitor_search",
                    input_data={"domain": domain, "max_competitors": 20},
                    status="pending",
                )
                
                await orchestrator.run_competitor_search(
                    domain=domain,
                    max_competitors=20,
                    execution_id=competitor_execution.execution_id,
                )
                
                await wait_for_execution_completion(
                    db, competitor_execution.execution_id, timeout=300
                )
            
            # Étape 3: Client Scraping
            if needs_client_scraping and current_profile_id:
                logger.info("Step 3: Starting client site scraping", domain=domain)
                scraping_agent = EnhancedScrapingAgent(min_word_count=150)
                
                await scraping_agent.discover_and_scrape_articles(
                    db,
                    domain,
                    max_articles=100,
                    is_client_site=True,
                    site_profile_id=current_profile_id,
                    force_reprofile=False,
                )
            
            # Étape 4: Competitor Scraping
            if needs_scraping:
                logger.info("Step 4: Starting competitor scraping", domain=domain)
                # Récupérer les concurrents validés
                stmt = (
                    select(WorkflowExecution)
                    .where(
                        WorkflowExecution.workflow_type == "competitor_search",
                        WorkflowExecution.status == "completed",
                        WorkflowExecution.input_data["domain"].astext == domain,
                    )
                    .order_by(desc(WorkflowExecution.start_time))
                    .limit(1)
                )
                result = await db.execute(stmt)
                competitor_exec = result.scalar_one_or_none()
                
                if competitor_exec:
                    competitors_data = competitor_exec.output_data.get("competitors", [])
                    competitor_domains = [
                        c["domain"]
                        for c in competitors_data
                        if c.get("validated", False) or c.get("manual", False)
                    ]
                    
                    if competitor_domains:
                        scraping_execution = await create_workflow_execution(
                            db,
                            workflow_type="enhanced_scraping",
                            input_data={
                                "client_domain": domain,
                                "domains": competitor_domains,
                                "max_articles": 100,
                            },
                            status="pending",
                        )
                        
                        scraping_agent = EnhancedScrapingAgent(min_word_count=150)
                        for comp_domain in competitor_domains:
                            await scraping_agent.discover_and_scrape_articles(
                                db,
                                comp_domain,
                                max_articles=100,
                                is_client_site=False,
                                site_profile_id=None,
                                force_reprofile=False,
                                client_domain=domain,
                            )
                        
                        await update_workflow_execution(
                            db,
                            scraping_execution,
                            status="completed",
                        )
            
            # Étape 5: Trend Pipeline
            if needs_trend_pipeline:
                logger.info("Step 5: Starting trend pipeline", domain=domain)
                from uuid import uuid4
                from python_scripts.api.routers.trend_pipeline import (
                    TrendPipelineRequest,
                    run_trend_pipeline_task,
                )
                
                execution_id = str(uuid4())
                request = TrendPipelineRequest(
                    client_domain=domain,
                    time_window_days=90,
                    skip_llm=False,
                    skip_gap_analysis=False,
                )
                
                await run_trend_pipeline_task(
                    request=request,
                    db=db,
                    execution_id=execution_id,
                )
                
                # Wait for trend pipeline completion (check via TrendPipelineExecution)
                from python_scripts.database.models import TrendPipelineExecution
                from uuid import UUID as UUIDType
                
                max_wait = 1200  # 20 minutes
                start_wait = datetime.now()
                while (datetime.now() - start_wait).total_seconds() < max_wait:
                    stmt = (
                        select(TrendPipelineExecution)
                        .where(
                            TrendPipelineExecution.execution_id == UUIDType(execution_id),
                            TrendPipelineExecution.stage_1_clustering_status == "completed",
                            TrendPipelineExecution.stage_2_temporal_status == "completed",
                            TrendPipelineExecution.stage_3_llm_status == "completed",
                        )
                    )
                    result = await db.execute(stmt)
                    trend_exec = result.scalar_one_or_none()
                    
                    if trend_exec:
                        break
                    
                    await asyncio.sleep(10)
            
            # Mettre à jour l'orchestrator comme complété
            orchestrator_exec = await get_workflow_execution(
                db, orchestrator_execution_id
            )
            if orchestrator_exec:
                await update_workflow_execution(
                    db,
                    orchestrator_exec,
                    status="completed",
                )
            
            logger.info(
                "Missing workflows completed",
                domain=domain,
                orchestrator_execution_id=str(orchestrator_execution_id),
            )
            
        except Exception as e:
            logger.error(
                "Missing workflows chain failed",
                domain=domain,
                error=str(e),
                exc_info=True,
            )
            orchestrator_exec = await get_workflow_execution(
                db, orchestrator_execution_id
            )
            if orchestrator_exec:
                await update_workflow_execution(
                    db,
                    orchestrator_exec,
                    status="failed",
                    error_message=str(e),
                )


@router.get(
    "/{domain}/audit",
    response_model=Union[SiteAuditResponse, PendingAuditResponse],
    summary="Get complete site audit (auto-launches missing workflows)",
    description="""
    Get complete site audit data.
    
    Strategy:
    1. Check if data exists in database
    2. If exists: retrieve and use it
    3. If missing: launch only the missing workflows
    
    Checks in order:
    - Site profile (site_profiles)
    - Competitors (workflow_executions with competitor_search)
    - Scraped articles (competitor_articles count)
    - Trend pipeline (trend_pipeline_executions)
    
    Returns either:
    - Complete audit data if all data is available
    - Pending response with execution_id if workflows are launched
    """,
)
async def get_site_audit(
    domain: str,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Union[SiteAuditResponse, PendingAuditResponse]:
    """
    Get site audit with smart data retrieval.
    
    Vérifie chaque source de données et lance seulement ce qui manque.
    
    Args:
        domain: Domain name
        db: Database session
        background_tasks: FastAPI background tasks
        
    Returns:
        Complete audit data or pending response
    """
    from python_scripts.database.crud_executions import create_workflow_execution
    
    # ============================================================
    # ÉTAPE 1: Vérifier site_profile
    # ============================================================
    profile = await _check_site_profile(db, domain)
    needs_analysis = not profile
    
    # ============================================================
    # ÉTAPE 2: Vérifier competitors
    # ============================================================
    competitors_execution = None
    if profile:  # Seulement si profile existe
        competitors_execution = await _check_competitors(db, domain)
    
    needs_competitors = not competitors_execution
    
    # ============================================================
    # ÉTAPE 3: Vérifier articles scrapés (competitors)
    # ============================================================
    competitor_articles_count = 0
    needs_scraping = False
    
    if competitors_execution:
        # Récupérer les domaines des concurrents validés
        competitors_data = competitors_execution.output_data.get("competitors", [])
        competitor_domains = [
            c.get("domain")
            for c in competitors_data
            if c.get("domain")
            and not c.get("excluded", False)
            and (c.get("validated", False) or c.get("manual", False))
        ]
        
        if competitor_domains:
            # Compter les articles pour ces domaines
            count, is_sufficient = await _check_competitor_articles(
                db, competitor_domains
            )
            competitor_articles_count = count
            needs_scraping = not is_sufficient
        else:
            needs_scraping = True
    else:
        needs_scraping = True
    
    # ============================================================
    # ÉTAPE 4: Vérifier articles client (client_articles)
    # ============================================================
    client_articles_count = 0
    needs_client_scraping = False
    
    if profile:
        count, is_sufficient = await _check_client_articles(db, profile.id)
        client_articles_count = count
        needs_client_scraping = not is_sufficient
    else:
        needs_client_scraping = True
    
    # ============================================================
    # ÉTAPE 5: Vérifier trend pipeline
    # ============================================================
    trend_execution = None
    if profile:  # Seulement si profile existe
        trend_execution = await _check_trend_pipeline(db, domain)
    
    needs_trend_pipeline = not trend_execution
    
    # ============================================================
    # DÉCISION: Lancer les workflows manquants ou retourner les données
    # ============================================================
    
    if (
        needs_analysis
        or needs_competitors
        or needs_scraping
        or needs_client_scraping
        or needs_trend_pipeline
    ):
        # Il manque des données : lancer les workflows nécessaires
        # Créer un orchestrator execution pour suivre la progression
        orchestrator_execution = await create_workflow_execution(
            db,
            workflow_type="audit_orchestrator",
            input_data={
                "domain": domain,
                "needs_analysis": needs_analysis,
                "needs_competitors": needs_competitors,
                "needs_scraping": needs_scraping,
                "needs_client_scraping": needs_client_scraping,
                "needs_trend_pipeline": needs_trend_pipeline,
            },
            status="running",
        )
        
        # Lancer les workflows manquants en chaîne
        background_tasks.add_task(
            run_missing_workflows_chain,
            domain,
            orchestrator_execution.execution_id,
            needs_analysis=needs_analysis,
            needs_competitors=needs_competitors,
            needs_scraping=needs_scraping,
            needs_client_scraping=needs_client_scraping,
            needs_trend_pipeline=needs_trend_pipeline,
            profile_id=profile.id if profile else None,
        )
        
        # Construire la liste des étapes
        workflow_steps = []
        step_num = 1
        
        if needs_analysis:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Editorial Analysis",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_competitors:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Competitor Search",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_client_scraping:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Client Site Scraping",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_scraping:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Competitor Scraping",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_trend_pipeline:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Trend Pipeline",
                    status="pending",
                )
            )
        
        return PendingAuditResponse(
            status="pending",
            execution_id=str(orchestrator_execution.execution_id),
            message="Some data is missing. Launching required workflows...",
            workflow_steps=workflow_steps,
            data_status=DataStatus(
                has_profile=not needs_analysis,
                has_competitors=not needs_competitors,
                has_client_articles=not needs_client_scraping,
                has_competitor_articles=not needs_scraping,
                has_trend_pipeline=not needs_trend_pipeline,
            ),
        )
    
    # ============================================================
    # TOUTES LES DONNÉES SONT DISPONIBLES : Construire la réponse
    # ============================================================
    
    # Récupérer les données complètes depuis la base
    return await build_complete_audit_from_database(
        db,
        domain,
        profile,
        competitors_execution,
        trend_execution,
    )

