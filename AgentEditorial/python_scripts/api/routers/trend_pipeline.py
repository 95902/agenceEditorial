"""API router for trend pipeline (4-stage hybrid extraction)."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_trend_pipeline import TrendPipelineAgent
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.responses import ExecutionResponse
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/trend-pipeline", tags=["Trend Pipeline"])


# ============================================================
# Request/Response Schemas
# ============================================================

class TrendPipelineRequest(BaseModel):
    """Request schema for trend pipeline analysis."""
    
    client_domain: Optional[str] = Field(
        None,
        description="Client domain for gap analysis (optional)",
    )
    domains: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="Domains to analyze (required if client_domain not provided)",
    )
    time_window_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Time window in days (default: 365)",
    )
    skip_llm: bool = Field(
        default=False,
        description="Skip LLM enrichment stage (faster)",
    )
    skip_gap_analysis: bool = Field(
        default=False,
        description="Skip gap analysis stage",
    )


class ClusterSummary(BaseModel):
    """Summary of a topic cluster."""
    topic_id: int
    label: str
    size: int
    coherence_score: Optional[float] = None
    top_terms: List[str] = []


class TemporalMetricsSummary(BaseModel):
    """Summary of temporal metrics."""
    topic_id: int
    velocity: float
    velocity_trend: str
    freshness_ratio: float
    potential_score: float


class GapSummary(BaseModel):
    """Summary of an editorial gap."""
    topic_id: int
    topic_label: str
    coverage_score: float
    priority_score: float
    diagnostic: str


class RoadmapItem(BaseModel):
    """Roadmap item summary."""
    priority_order: int
    priority_tier: str
    gap_label: str
    recommendation_title: str
    estimated_effort: str


class TrendPipelineStatusResponse(BaseModel):
    """Response schema for pipeline status."""
    execution_id: str
    stage_1_clustering_status: str
    stage_2_temporal_status: str
    stage_3_llm_status: str
    stage_4_gap_status: str
    total_clusters: int
    total_gaps: int
    duration_seconds: Optional[int] = None


class ClustersResponse(BaseModel):
    """Response schema for clusters."""
    execution_id: str
    clusters: List[ClusterSummary]
    total: int


class TemporalResponse(BaseModel):
    """Response schema for temporal metrics."""
    execution_id: str
    metrics: List[TemporalMetricsSummary]
    total: int


class GapsResponse(BaseModel):
    """Response schema for gaps."""
    execution_id: str
    gaps: List[GapSummary]
    total: int


class RoadmapResponse(BaseModel):
    """Response schema for roadmap."""
    execution_id: str
    roadmap: List[RoadmapItem]
    total: int


# ============================================================
# Background task
# ============================================================

async def run_trend_pipeline_task(
    request: TrendPipelineRequest,
    db: AsyncSession,
) -> None:
    """Background task to run trend pipeline."""
    try:
        agent = TrendPipelineAgent(db)
        
        # Determine domains
        domains = request.domains or []
        if request.client_domain and not domains:
            # Fetch competitor domains for client
            # For now, use client domain
            domains = [request.client_domain]
        
        await agent.execute(
            domains=domains,
            client_domain=request.client_domain,
            time_window_days=request.time_window_days,
            skip_llm=request.skip_llm,
            skip_gap_analysis=request.skip_gap_analysis,
        )
        
    except Exception as e:
        logger.error("Trend pipeline task failed", error=str(e))


# ============================================================
# Endpoints
# ============================================================

@router.post(
    "/analyze",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start trend pipeline analysis",
    description="""
    Start the 4-stage trend extraction pipeline:
    
    1. **Clustering**: BERTopic + HDBSCAN for topic discovery
    2. **Temporal Analysis**: Volume, velocity, freshness metrics
    3. **LLM Enrichment**: Trend synthesis and article recommendations
    4. **Gap Analysis**: Coverage gaps and content roadmap
    """,
)
async def analyze_trends(
    request: TrendPipelineRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """Start trend pipeline analysis."""
    if not request.domains and not request.client_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'domains' or 'client_domain' must be provided",
        )
    
    # Generate execution ID
    from uuid import uuid4
    execution_id = uuid4()
    
    # Add background task
    background_tasks.add_task(
        run_trend_pipeline_task,
        request=request,
        db=db,
    )
    
    return ExecutionResponse(
        execution_id=execution_id,
        status="accepted",
        start_time=None,
        estimated_duration_minutes=10,
    )


@router.get(
    "/{execution_id}/status",
    response_model=TrendPipelineStatusResponse,
    summary="Get pipeline status",
)
async def get_pipeline_status(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> TrendPipelineStatusResponse:
    """Get status of a pipeline execution."""
    from sqlalchemy import select
    from python_scripts.database.models import TrendPipelineExecution
    
    result = await db.execute(
        select(TrendPipelineExecution).where(
            TrendPipelineExecution.execution_id == execution_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found",
        )
    
    return TrendPipelineStatusResponse(
        execution_id=str(execution.execution_id),
        stage_1_clustering_status=execution.stage_1_clustering_status,
        stage_2_temporal_status=execution.stage_2_temporal_status,
        stage_3_llm_status=execution.stage_3_llm_status,
        stage_4_gap_status=execution.stage_4_gap_status,
        total_clusters=execution.total_clusters,
        total_gaps=execution.total_gaps,
        duration_seconds=execution.duration_seconds,
    )


@router.get(
    "/{execution_id}/clusters",
    response_model=ClustersResponse,
    summary="Get clusters from pipeline",
)
async def get_pipeline_clusters(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClustersResponse:
    """Get topic clusters from a pipeline execution."""
    from python_scripts.database.crud_clusters import get_topic_clusters_by_analysis
    from sqlalchemy import select
    from python_scripts.database.models import TrendPipelineExecution
    
    # Get execution
    result = await db.execute(
        select(TrendPipelineExecution).where(
            TrendPipelineExecution.execution_id == execution_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found",
        )
    
    # Get clusters
    clusters = await get_topic_clusters_by_analysis(db, execution.id)
    
    cluster_summaries = [
        ClusterSummary(
            topic_id=c.topic_id,
            label=c.label,
            size=c.size,
            coherence_score=float(c.coherence_score) if c.coherence_score else None,
            top_terms=[t["word"] for t in (c.top_terms.get("terms", []) if c.top_terms else [])[:5]],
        )
        for c in clusters
    ]
    
    return ClustersResponse(
        execution_id=execution_id,
        clusters=cluster_summaries,
        total=len(cluster_summaries),
    )


@router.get(
    "/{execution_id}/gaps",
    response_model=GapsResponse,
    summary="Get editorial gaps",
)
async def get_pipeline_gaps(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> GapsResponse:
    """Get editorial gaps from a pipeline execution."""
    from sqlalchemy import select
    from python_scripts.database.models import TrendPipelineExecution, EditorialGap, TopicCluster
    
    # Get execution
    result = await db.execute(
        select(TrendPipelineExecution).where(
            TrendPipelineExecution.execution_id == execution_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found",
        )
    
    # Get gaps (we need to join with topic_clusters for labels)
    result = await db.execute(
        select(EditorialGap, TopicCluster).join(
            TopicCluster,
            EditorialGap.topic_cluster_id == TopicCluster.id
        ).where(
            TopicCluster.analysis_id == execution.id
        ).order_by(EditorialGap.priority_score.desc())
    )
    
    gap_summaries = []
    for gap, cluster in result.all():
        gap_summaries.append(GapSummary(
            topic_id=cluster.topic_id,
            topic_label=cluster.label,
            coverage_score=float(gap.coverage_score),
            priority_score=float(gap.priority_score),
            diagnostic=gap.diagnostic,
        ))
    
    return GapsResponse(
        execution_id=execution_id,
        gaps=gap_summaries,
        total=len(gap_summaries),
    )


@router.get(
    "/{execution_id}/roadmap",
    response_model=RoadmapResponse,
    summary="Get content roadmap",
)
async def get_pipeline_roadmap(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> RoadmapResponse:
    """Get content roadmap from a pipeline execution."""
    from sqlalchemy import select
    from python_scripts.database.models import (
        TrendPipelineExecution, ContentRoadmap, EditorialGap, 
        TopicCluster, ArticleRecommendation
    )
    
    # Get execution
    result = await db.execute(
        select(TrendPipelineExecution).where(
            TrendPipelineExecution.execution_id == execution_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found",
        )
    
    # Get roadmap items
    result = await db.execute(
        select(ContentRoadmap, EditorialGap, TopicCluster, ArticleRecommendation).join(
            EditorialGap,
            ContentRoadmap.gap_id == EditorialGap.id
        ).join(
            TopicCluster,
            EditorialGap.topic_cluster_id == TopicCluster.id
        ).join(
            ArticleRecommendation,
            ContentRoadmap.recommendation_id == ArticleRecommendation.id
        ).where(
            ContentRoadmap.client_domain == execution.client_domain
        ).order_by(ContentRoadmap.priority_order)
    )
    
    roadmap_items = []
    for roadmap, gap, cluster, reco in result.all():
        roadmap_items.append(RoadmapItem(
            priority_order=roadmap.priority_order,
            priority_tier=roadmap.status,  # Using status as tier for now
            gap_label=cluster.label,
            recommendation_title=reco.title,
            estimated_effort=roadmap.estimated_effort,
        ))
    
    return RoadmapResponse(
        execution_id=execution_id,
        roadmap=roadmap_items,
        total=len(roadmap_items),
    )

