"""CRUD operations for topic temporal metrics."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import TopicCluster, TopicTemporalMetrics
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_topic_temporal_metric(
    db_session: AsyncSession,
    topic_cluster_id: int,
    window_start: date,
    window_end: date,
    volume: int,
    velocity: Optional[float] = None,
    freshness_ratio: Optional[float] = None,
    source_diversity: int = 0,
    cohesion_score: Optional[float] = None,
    potential_score: Optional[float] = None,
    drift_detected: bool = False,
    drift_distance: Optional[float] = None,
) -> TopicTemporalMetrics:
    """
    Create a topic temporal metric record.
    
    Args:
        db_session: Database session
        topic_cluster_id: Topic cluster ID
        window_start: Start date of the time window
        window_end: End date of the time window
        volume: Number of articles in the window
        velocity: Growth rate (optional)
        freshness_ratio: Ratio of recent articles (optional)
        source_diversity: Number of different source domains
        cohesion_score: Topic cohesion score (optional)
        potential_score: Potential score for prioritization (optional)
        drift_detected: Whether drift was detected
        drift_distance: Drift distance if detected (optional)
        
    Returns:
        Created TopicTemporalMetrics instance
    """
    metric = TopicTemporalMetrics(
        topic_cluster_id=topic_cluster_id,
        window_start=window_start,
        window_end=window_end,
        volume=volume,
        velocity=velocity,
        freshness_ratio=freshness_ratio,
        source_diversity=source_diversity,
        cohesion_score=cohesion_score,
        potential_score=potential_score,
        drift_detected=drift_detected,
        drift_distance=drift_distance,
    )
    db_session.add(metric)
    await db_session.commit()
    await db_session.refresh(metric)
    logger.debug(
        "Created topic temporal metric",
        metric_id=metric.id,
        topic_cluster_id=topic_cluster_id,
        volume=volume,
    )
    return metric


async def create_topic_temporal_metrics_batch(
    db_session: AsyncSession,
    metrics_data: List[Dict[str, Any]],
    analysis_id: int,
) -> List[TopicTemporalMetrics]:
    """
    Create multiple topic temporal metrics in batch.
    
    Args:
        db_session: Database session
        metrics_data: List of metric dictionaries from TemporalAnalyzer
        analysis_id: Analysis ID to find topic clusters
        
    Returns:
        List of created TopicTemporalMetrics instances
    """
    from python_scripts.database.crud_clusters import get_topic_cluster_by_topic_id
    
    created_metrics = []
    
    for metric_data in metrics_data:
        topic_id = metric_data.get("topic_id")
        if topic_id is None:
            logger.warning("Metric data missing topic_id", metric_data=metric_data)
            continue
        
        # Get database cluster record
        db_cluster = await get_topic_cluster_by_topic_id(
            db_session,
            analysis_id,
            topic_id,
        )
        if not db_cluster:
            logger.warning(
                f"Database cluster not found for topic {topic_id}",
                analysis_id=analysis_id,
            )
            continue
        
        # Extract window information from metrics_by_window
        metrics_by_window = metric_data.get("metrics_by_window", {})
        
        # For now, save the main window (30d) or first available window
        # The TemporalAnalyzer calculates metrics for multiple windows (7d, 30d, etc.)
        # We'll save the primary window (30d) or the first available
        window_name = "30d" if "30d" in metrics_by_window else (
            list(metrics_by_window.keys())[0] if metrics_by_window else None
        )
        
        if not window_name:
            # If no window data, create a metric with overall data
            window_start = date.today()
            window_end = date.today()
            volume = metric_data.get("total_count", 0)
        else:
            # Calculate window dates (30d = last 30 days, 7d = last 7 days, etc.)
            from datetime import timedelta
            days = int(window_name.replace("d", ""))
            window_end = date.today()
            window_start = window_end - timedelta(days=days)
            window_metrics = metrics_by_window[window_name]
            volume = window_metrics.get("volume", 0)
        
        try:
            metric = await create_topic_temporal_metric(
                db_session=db_session,
                topic_cluster_id=db_cluster.id,
                window_start=window_start,
                window_end=window_end,
                volume=volume,
                velocity=metric_data.get("velocity"),
                freshness_ratio=metric_data.get("freshness_ratio"),
                source_diversity=metric_data.get("source_diversity", 0),
                cohesion_score=metric_data.get("cohesion_score"),
                potential_score=metric_data.get("potential_score"),
                drift_detected=metric_data.get("drift_detected", False),
                drift_distance=metric_data.get("drift_distance"),
            )
            created_metrics.append(metric)
        except Exception as e:
            logger.warning(
                f"Failed to save temporal metric for topic {topic_id}",
                error=str(e),
                topic_id=topic_id,
            )
    
    logger.info(
        "Created topic temporal metrics batch",
        total=len(created_metrics),
        requested=len(metrics_data),
    )
    return created_metrics


async def get_temporal_metrics_by_topic_cluster(
    db_session: AsyncSession,
    topic_cluster_id: int,
) -> List[TopicTemporalMetrics]:
    """
    Get temporal metrics for a specific topic cluster.
    
    Args:
        db_session: Database session
        topic_cluster_id: Topic cluster ID
        
    Returns:
        List of TopicTemporalMetrics instances
    """
    result = await db_session.execute(
        select(TopicTemporalMetrics).where(
            TopicTemporalMetrics.topic_cluster_id == topic_cluster_id,
            TopicTemporalMetrics.is_valid == True,  # noqa: E712
        ).order_by(TopicTemporalMetrics.window_start.desc())
    )
    return list(result.scalars().all())


async def get_temporal_metrics_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> List[TopicTemporalMetrics]:
    """
    Get all temporal metrics for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Analysis ID (from topic_clusters.analysis_id)
        
    Returns:
        List of TopicTemporalMetrics instances
    """
    result = await db_session.execute(
        select(TopicTemporalMetrics)
        .join(TopicCluster, TopicTemporalMetrics.topic_cluster_id == TopicCluster.id)
        .where(
            TopicCluster.analysis_id == analysis_id,
            TopicTemporalMetrics.is_valid == True,  # noqa: E712
        )
        .order_by(TopicTemporalMetrics.window_start.desc())
    )
    return list(result.scalars().all())
