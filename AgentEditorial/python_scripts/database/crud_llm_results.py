"""CRUD operations for LLM enrichment results (TrendAnalysis, ArticleRecommendation)."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import TrendAnalysis, ArticleRecommendation, TopicCluster
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_trend_analysis(
    db_session: AsyncSession,
    topic_cluster_id: int,
    synthesis: str,
    saturated_angles: Optional[dict] = None,
    opportunities: Optional[dict] = None,
    llm_model_used: str = "unknown",
    processing_time_seconds: Optional[int] = None,
) -> TrendAnalysis:
    """
    Create a trend analysis record.
    
    Args:
        db_session: Database session
        topic_cluster_id: Topic cluster ID
        synthesis: LLM-generated synthesis text
        saturated_angles: Saturated angles (optional)
        opportunities: Opportunities (optional)
        llm_model_used: LLM model name
        processing_time_seconds: Processing time in seconds
        
    Returns:
        Created TrendAnalysis instance
    """
    trend_analysis = TrendAnalysis(
        topic_cluster_id=topic_cluster_id,
        synthesis=synthesis,
        saturated_angles=saturated_angles,
        opportunities=opportunities,
        llm_model_used=llm_model_used,
        processing_time_seconds=processing_time_seconds,
    )
    db_session.add(trend_analysis)
    await db_session.commit()
    await db_session.refresh(trend_analysis)
    logger.debug("Created trend analysis", trend_analysis_id=trend_analysis.id, topic_cluster_id=topic_cluster_id)
    return trend_analysis


async def create_article_recommendation(
    db_session: AsyncSession,
    topic_cluster_id: int,
    title: str,
    hook: str,
    outline: dict,
    effort_level: str = "medium",
    differentiation_score: Optional[float] = None,
) -> ArticleRecommendation:
    """
    Create an article recommendation record.
    
    Args:
        db_session: Database session
        topic_cluster_id: Topic cluster ID
        title: Article title
        hook: Article hook/lead
        outline: Article outline (dict)
        effort_level: Effort level ('easy', 'medium', 'complex')
        differentiation_score: Differentiation score (optional)
        
    Returns:
        Created ArticleRecommendation instance
    """
    article_reco = ArticleRecommendation(
        topic_cluster_id=topic_cluster_id,
        title=title,
        hook=hook,
        outline=outline,
        effort_level=effort_level,
        differentiation_score=differentiation_score,
    )
    db_session.add(article_reco)
    await db_session.commit()
    await db_session.refresh(article_reco)
    logger.debug("Created article recommendation", recommendation_id=article_reco.id, topic_cluster_id=topic_cluster_id)
    return article_reco


async def get_trend_analyses_by_topic_cluster(
    db_session: AsyncSession,
    topic_cluster_id: int,
) -> List[TrendAnalysis]:
    """Get trend analyses for a topic cluster."""
    result = await db_session.execute(
        select(TrendAnalysis).where(
            TrendAnalysis.topic_cluster_id == topic_cluster_id,
            TrendAnalysis.is_valid == True,  # noqa: E712
        ).order_by(TrendAnalysis.created_at.desc())
    )
    return list(result.scalars().all())


async def get_article_recommendations_by_topic_cluster(
    db_session: AsyncSession,
    topic_cluster_id: int,
    status: Optional[str] = None,
) -> List[ArticleRecommendation]:
    """Get article recommendations for a topic cluster."""
    query = select(ArticleRecommendation).where(
        ArticleRecommendation.topic_cluster_id == topic_cluster_id,
        ArticleRecommendation.is_valid == True,  # noqa: E712
    )
    
    if status:
        query = query.where(ArticleRecommendation.status == status)
    
    query = query.order_by(ArticleRecommendation.created_at.desc())
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def get_article_recommendations_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> List[ArticleRecommendation]:
    """
    Get article recommendations for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Analysis ID (from topic_clusters.analysis_id)
        
    Returns:
        List of ArticleRecommendation instances
    """
    result = await db_session.execute(
        select(ArticleRecommendation)
        .join(TopicCluster, ArticleRecommendation.topic_cluster_id == TopicCluster.id)
        .where(
            TopicCluster.analysis_id == analysis_id,
            ArticleRecommendation.is_valid == True,  # noqa: E712
        )
        .order_by(ArticleRecommendation.created_at.desc())
    )
    return list(result.scalars().all())


async def get_trend_analyses_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> List[TrendAnalysis]:
    """
    Get trend analyses for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Analysis ID (from topic_clusters.analysis_id)
        
    Returns:
        List of TrendAnalysis instances
    """
    result = await db_session.execute(
        select(TrendAnalysis)
        .join(TopicCluster, TrendAnalysis.topic_cluster_id == TopicCluster.id)
        .where(
            TopicCluster.analysis_id == analysis_id,
            TrendAnalysis.is_valid == True,  # noqa: E712
        )
        .order_by(TrendAnalysis.created_at.desc())
    )
    return list(result.scalars().all())

