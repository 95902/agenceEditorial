"""API router for trend pipeline (4-stage hybrid extraction)."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.trend_pipeline.agent import TrendPipelineAgent
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
        examples=["innosys.fr"],
    )
    domains: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="Domains to analyze (required if client_domain not provided)",
        examples=[["competitor1.fr", "competitor2.fr"]],
    )
    time_window_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Time window in days (default: 365)",
        examples=[365],
    )
    skip_llm: bool = Field(
        default=False,
        description="Skip LLM enrichment stage (faster)",
        examples=[False],
    )
    skip_gap_analysis: bool = Field(
        default=False,
        description="Skip gap analysis stage",
        examples=[False],
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "client_domain": "innosys.fr",
                "domains": ["competitor1.fr", "competitor2.fr"],
                "time_window_days": 365,
                "skip_llm": False,
                "skip_gap_analysis": False,
            }
        }


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


class TrendSynthesisSummary(BaseModel):
    """Summary of a trend synthesis."""
    topic_id: int
    topic_label: str
    synthesis: str
    saturated_angles: Optional[List[str]] = None
    opportunities: Optional[List[str]] = None
    llm_model_used: str


class ArticleRecommendationSummary(BaseModel):
    """Summary of an article recommendation."""
    id: int
    topic_id: int
    topic_label: str
    title: str
    hook: str
    outline: dict  # Can be a dict or list converted to dict
    effort_level: str
    differentiation_score: Optional[float] = None


class LLMResultsResponse(BaseModel):
    """Response schema for LLM results."""
    execution_id: str
    syntheses: List[TrendSynthesisSummary]
    recommendations: List[ArticleRecommendationSummary]
    total_syntheses: int
    total_recommendations: int


# ============================================================
# Background task
# ============================================================

async def run_trend_pipeline_task(
    request: TrendPipelineRequest,
    db: AsyncSession,
    execution_id: str,
) -> None:
    """Background task to run trend pipeline."""
    from python_scripts.database.crud_executions import create_workflow_execution, update_workflow_execution
    
    workflow_execution = None
    try:
        # Create workflow execution entry
        workflow_execution = await create_workflow_execution(
            db_session=db,
            workflow_type="trend_pipeline",
            input_data={
                "client_domain": request.client_domain,
                "domains": request.domains,
                "time_window_days": request.time_window_days,
                "skip_llm": request.skip_llm,
                "skip_gap_analysis": request.skip_gap_analysis,
            },
            status="running",
        )
        await db.commit()
        
        logger.info(
            "Created workflow execution for trend pipeline",
            workflow_execution_id=str(workflow_execution.execution_id),
            trend_execution_id=execution_id,
        )
        
        agent = TrendPipelineAgent(db, client_domain=request.client_domain)
        
        # Determine domains
        domains = request.domains or []
        
        # Mode: Fetch validated competitors from client_domain
        if request.client_domain and not domains:
            from sqlalchemy import select, desc
            from python_scripts.database.models import WorkflowExecution
            
            # Find latest completed competitor search for this domain
            stmt = (
                select(WorkflowExecution)
                .where(
                    WorkflowExecution.workflow_type == "competitor_search",
                    WorkflowExecution.status == "completed",
                    WorkflowExecution.input_data["domain"].astext == request.client_domain,
                )
                .order_by(desc(WorkflowExecution.start_time))
                .limit(1)
            )
            
            result = await db.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if not execution or not execution.output_data:
                logger.error(
                    "No competitor search results found",
                    client_domain=request.client_domain,
                )
                raise ValueError(
                    f"No competitor search results found for domain: {request.client_domain}. "
                    "Please run competitor search first."
                )
            
            # Extract validated competitors
            competitors_data = execution.output_data.get("competitors", [])
            if not competitors_data:
                logger.error(
                    "No validated competitors found",
                    client_domain=request.client_domain,
                )
                raise ValueError(
                    f"No validated competitors found for domain: {request.client_domain}"
                )
            
            # Extract domains from validated competitors
            for comp in competitors_data:
                validation_status = comp.get("validation_status", "validated")
                validated = comp.get("validated", False)
                excluded = comp.get("excluded", False)
                
                # Include only validated or manual competitors (not excluded)
                if not excluded and (validation_status in ["validated", "manual"] or validated):
                    domain = comp.get("domain")
                    if domain:
                        domains.append(domain)
            
            if not domains:
                logger.error(
                    "No validated competitors to analyze",
                    client_domain=request.client_domain,
                )
                raise ValueError(
                    f"No validated competitors found for domain: {request.client_domain}. "
                    "Please validate competitors first."
                )
            
            logger.info(
                "Fetched validated competitors",
                client_domain=request.client_domain,
                competitor_count=len(domains),
                domains=domains[:10],  # Log first 10
            )
        
        # Execute pipeline with provided execution_id
        result = await agent.execute(
            domains=domains,
            client_domain=request.client_domain,
            time_window_days=request.time_window_days,
            skip_llm=request.skip_llm,
            skip_gap_analysis=request.skip_gap_analysis,
            execution_id=execution_id,  # Pass execution_id to agent
        )
        
        # Update workflow execution with results
        if workflow_execution:
            await update_workflow_execution(
                db_session=db,
                execution=workflow_execution,
                status="completed",
                output_data={
                    "trend_execution_id": execution_id,
                    "total_clusters": result.get("stages", {}).get("clustering", {}).get("total_clusters", 0),
                    "total_gaps": result.get("stages", {}).get("gap_analysis", {}).get("total_gaps", 0),
                    "success": result.get("success", False),
                },
                was_success=result.get("success", False),
            )
            await db.commit()
            logger.info(
                "Updated workflow execution",
                workflow_execution_id=str(workflow_execution.execution_id),
                status="completed",
            )
        
    except Exception as e:
        logger.error("Trend pipeline task failed", error=str(e), execution_id=execution_id)
        
        # Update workflow execution with error
        if workflow_execution:
            await update_workflow_execution(
                db_session=db,
                execution=workflow_execution,
                status="failed",
                error_message=str(e),
                was_success=False,
            )
            await db.commit()
        
        raise


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
    """
    Start trend pipeline analysis.
    
    This endpoint launches the 4-stage hybrid trend extraction pipeline:
    
    1. **Clustering (Stage 1)**: BERTopic + HDBSCAN for topic discovery from competitor articles
    2. **Temporal Analysis (Stage 2)**: Volume, velocity, freshness, and source diversity metrics
    3. **LLM Enrichment (Stage 3)**: Trend synthesis, article recommendations, and weak signal analysis
    4. **Gap Analysis (Stage 4)**: Coverage gaps, client strengths, and content roadmap
    
    Args:
        request: Trend pipeline request with domains or client_domain
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        Execution response with execution_id for tracking
        
    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/trend-pipeline/analyze" \\
          -H "Content-Type: application/json" \\
          -d '{
            "client_domain": "innosys.fr",
            "time_window_days": 365,
            "skip_llm": false,
            "skip_gap_analysis": false
          }'
        ```
    """
    if not request.domains and not request.client_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'domains' or 'client_domain' must be provided",
        )
    
    # Generate execution ID
    from uuid import uuid4
    execution_id = str(uuid4())
    
    # Add background task with execution_id
    background_tasks.add_task(
        run_trend_pipeline_task,
        request=request,
        db=db,
        execution_id=execution_id,
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
    description="Get the status of each stage of the trend pipeline execution.",
    responses={
        200: {
            "description": "Pipeline status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "stage_1_clustering_status": "completed",
                        "stage_2_temporal_status": "completed",
                        "stage_3_llm_status": "running",
                        "stage_4_gap_status": "pending",
                        "total_clusters": 25,
                        "total_gaps": 0,
                        "duration_seconds": 120,
                    }
                }
            }
        },
        404: {
            "description": "Execution not found"
        }
    },
)
async def get_pipeline_status(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> TrendPipelineStatusResponse:
    """
    Get status of a pipeline execution.
    
    Returns the status of each of the 4 stages:
    - Stage 1: Clustering (BERTopic)
    - Stage 2: Temporal Analysis
    - Stage 3: LLM Enrichment
    - Stage 4: Gap Analysis
    
    Args:
        execution_id: Pipeline execution ID
        db: Database session
        
    Returns:
        Pipeline status with stage-by-stage progress
        
    Raises:
        HTTPException: 404 if execution not found
        
    Example:
        ```bash
        curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/status"
        ```
    """
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
    description="Get topic clusters discovered by BERTopic clustering (Stage 1).",
    responses={
        200: {
            "description": "Clusters retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "clusters": [
                            {
                                "topic_id": 0,
                                "label": "Cloud Solutions",
                                "size": 150,
                                "coherence_score": 0.85,
                                "top_terms": ["cloud", "saas", "infrastructure"]
                            }
                        ],
                        "total": 25
                    }
                }
            }
        },
        404: {
            "description": "Execution not found"
        }
    },
)
async def get_pipeline_clusters(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClustersResponse:
    """
    Get topic clusters from a pipeline execution.
    
    Returns all topic clusters discovered during Stage 1 (Clustering) of the trend pipeline.
    Each cluster represents a group of semantically similar articles.
    
    Args:
        execution_id: Pipeline execution ID
        db: Database session
        
    Returns:
        List of topic clusters with labels, sizes, and top terms
        
    Raises:
        HTTPException: 404 if execution not found
        
    Example:
        ```bash
        curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/clusters"
        ```
    """
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
    description="Get editorial content gaps identified by gap analysis (Stage 4).",
    responses={
        200: {
            "description": "Gaps retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "gaps": [
                            {
                                "topic_id": 5,
                                "topic_label": "AI and Machine Learning",
                                "coverage_score": 0.2,
                                "priority_score": 0.85,
                                "diagnostic": "Low coverage in AI topics"
                            }
                        ],
                        "total": 12
                    }
                }
            }
        },
        404: {
            "description": "Execution not found"
        }
    },
)
async def get_pipeline_gaps(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> GapsResponse:
    """
    Get editorial gaps from a pipeline execution.
    
    Returns content gaps identified during Stage 4 (Gap Analysis) of the trend pipeline.
    Gaps represent topics where competitors have more coverage than the client.
    
    Args:
        execution_id: Pipeline execution ID
        db: Database session
        
    Returns:
        List of editorial gaps with priority scores and diagnostics
        
    Raises:
        HTTPException: 404 if execution not found
        
    Example:
        ```bash
        curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/gaps"
        ```
    """
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
    description="Get prioritized content roadmap with article recommendations (Stage 4).",
    responses={
        200: {
            "description": "Roadmap retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "roadmap": [
                            {
                                "priority_order": 1,
                                "priority_tier": "high",
                                "gap_label": "AI and Machine Learning",
                                "recommendation_title": "How AI Transforms Business Operations",
                                "estimated_effort": "medium"
                            }
                        ],
                        "total": 15
                    }
                }
            }
        },
        404: {
            "description": "Execution not found"
        }
    },
)
async def get_pipeline_roadmap(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> RoadmapResponse:
    """
    Get content roadmap from a pipeline execution.
    
    Returns a prioritized content roadmap generated during Stage 4 (Gap Analysis).
    The roadmap links editorial gaps to article recommendations, ordered by priority.
    
    Args:
        execution_id: Pipeline execution ID
        db: Database session
        
    Returns:
        Prioritized content roadmap with article recommendations
        
    Raises:
        HTTPException: 404 if execution not found
        
    Example:
        ```bash
        curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/roadmap"
        ```
    """
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


@router.get(
    "/{execution_id}/llm-results",
    response_model=LLMResultsResponse,
    summary="Get LLM enrichment results",
    description="Get trend syntheses and article recommendations generated by LLM (Stage 3).",
    responses={
        200: {
            "description": "LLM results retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "trend_analyses": [
                            {
                                "topic_id": 0,
                                "synthesis": "Cloud solutions are trending...",
                                "opportunities": ["Hybrid cloud", "Edge computing"]
                            }
                        ],
                        "article_recommendations": [
                            {
                                "article_id": 38,
                                "title": "Article Title",
                                "hook": "Article hook",
                                "effort_level": "medium"
                            }
                        ],
                        "total_trends": 25,
                        "total_recommendations": 50
                    }
                }
            }
        },
        404: {
            "description": "Execution not found"
        }
    },
)
async def get_pipeline_llm_results(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> LLMResultsResponse:
    """
    Get LLM enrichment results from a pipeline execution.
    
    Returns trend syntheses and article recommendations generated during Stage 3 (LLM Enrichment).
    This includes:
    - Trend syntheses: LLM-generated summaries of each topic
    - Article recommendations: Suggested article titles, hooks, and outlines
    - Opportunities: Identified content opportunities per topic
    
    Args:
        execution_id: Pipeline execution ID
        db: Database session
        
    Returns:
        LLM enrichment results with trend analyses and recommendations
        
    Raises:
        HTTPException: 404 if execution not found
        
    Example:
        ```bash
        curl "http://localhost:8000/api/v1/trend-pipeline/{execution_id}/llm-results"
        ```
    """
    from sqlalchemy import select
    from python_scripts.database.models import (
        TrendPipelineExecution, TrendAnalysis, ArticleRecommendation, TopicCluster
    )
    from python_scripts.database.crud_llm_results import (
        get_trend_analyses_by_analysis,
        get_article_recommendations_by_analysis,
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
    
    # Get trend analyses
    trend_analyses = await get_trend_analyses_by_analysis(db, execution.id)
    
    # Get article recommendations
    article_recommendations = await get_article_recommendations_by_analysis(db, execution.id)
    
    # Build syntheses summaries
    syntheses = []
    for ta in trend_analyses:
        # Get topic cluster for label
        cluster_result = await db.execute(
            select(TopicCluster).where(TopicCluster.id == ta.topic_cluster_id)
        )
        cluster = cluster_result.scalar_one_or_none()
        
        syntheses.append(TrendSynthesisSummary(
            topic_id=cluster.topic_id if cluster else -1,
            topic_label=cluster.label if cluster else "Unknown",
            synthesis=ta.synthesis,
            saturated_angles=ta.saturated_angles if isinstance(ta.saturated_angles, list) else None,
            opportunities=ta.opportunities if isinstance(ta.opportunities, list) else None,
            llm_model_used=ta.llm_model_used,
        ))
    
    # Build recommendations summaries
    recommendations = []
    for ar in article_recommendations:
        # Get topic cluster for label
        cluster_result = await db.execute(
            select(TopicCluster).where(TopicCluster.id == ar.topic_cluster_id)
        )
        cluster = cluster_result.scalar_one_or_none()
        
        # Normalize outline: convert list to dict if needed
        outline = ar.outline
        if isinstance(outline, list):
            # Convert list to dict with numbered keys
            outline = {f"section_{i+1}": item for i, item in enumerate(outline)}
        elif not isinstance(outline, dict):
            # Fallback: wrap in dict
            outline = {"content": outline}
        
        recommendations.append(ArticleRecommendationSummary(
            id=ar.id,
            topic_id=cluster.topic_id if cluster else -1,
            topic_label=cluster.label if cluster else "Unknown",
            title=ar.title,
            hook=ar.hook,
            outline=outline,
            effort_level=ar.effort_level,
            differentiation_score=float(ar.differentiation_score) if ar.differentiation_score else None,
        ))
    
    return LLMResultsResponse(
        execution_id=execution_id,
        syntheses=syntheses,
        recommendations=recommendations,
        total_syntheses=len(syntheses),
        total_recommendations=len(recommendations),
    )

