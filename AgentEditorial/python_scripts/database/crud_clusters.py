"""CRUD operations for topic clusters and outliers."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import TopicCluster, TopicOutlier
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# TopicCluster CRUD
# ============================================================

async def create_topic_cluster(
    db_session: AsyncSession,
    analysis_id: int,
    topic_id: int,
    label: str,
    top_terms: Dict[str, Any],
    size: int,
    document_ids: Dict[str, Any],
    centroid_vector_id: Optional[str] = None,
    coherence_score: Optional[float] = None,
) -> TopicCluster:
    """
    Create a new topic cluster.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        topic_id: BERTopic topic ID
        label: Human-readable label
        top_terms: Top terms with scores
        size: Number of documents in cluster
        document_ids: List of document IDs
        centroid_vector_id: Qdrant vector ID for centroid
        coherence_score: Cluster coherence score
        
    Returns:
        Created TopicCluster
    """
    cluster = TopicCluster(
        analysis_id=analysis_id,
        topic_id=topic_id,
        label=label,
        top_terms=top_terms,
        size=size,
        document_ids=document_ids,
        centroid_vector_id=centroid_vector_id,
        coherence_score=coherence_score,
    )
    
    db_session.add(cluster)
    await db_session.commit()
    await db_session.refresh(cluster)
    
    logger.info(
        "Created topic cluster",
        cluster_id=cluster.id,
        topic_id=topic_id,
        size=size,
    )
    
    return cluster


async def create_topic_clusters_batch(
    db_session: AsyncSession,
    analysis_id: int,
    clusters_data: List[Dict[str, Any]],
) -> List[TopicCluster]:
    """
    Create multiple topic clusters in batch.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        clusters_data: List of cluster dictionaries
        
    Returns:
        List of created TopicClusters
    """
    clusters = []
    
    for data in clusters_data:
        cluster = TopicCluster(
            analysis_id=analysis_id,
            topic_id=data["topic_id"],
            label=data.get("label", f"Topic_{data['topic_id']}"),
            top_terms=data.get("top_terms", {}),
            size=data.get("size", 0),
            document_ids=data.get("document_ids", {}),
            centroid_vector_id=data.get("centroid_vector_id"),
            coherence_score=data.get("coherence_score"),
        )
        clusters.append(cluster)
    
    db_session.add_all(clusters)
    await db_session.commit()
    
    for cluster in clusters:
        await db_session.refresh(cluster)
    
    logger.info(
        "Created topic clusters batch",
        count=len(clusters),
        analysis_id=analysis_id,
    )
    
    return clusters


async def get_topic_cluster_by_id(
    db_session: AsyncSession,
    cluster_id: int,
) -> Optional[TopicCluster]:
    """
    Get a topic cluster by ID.
    
    Args:
        db_session: Database session
        cluster_id: Cluster ID
        
    Returns:
        TopicCluster if found, None otherwise
    """
    result = await db_session.execute(
        select(TopicCluster).where(
            TopicCluster.id == cluster_id,
            TopicCluster.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_topic_clusters_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> List[TopicCluster]:
    """
    Get all topic clusters for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        
    Returns:
        List of TopicClusters
    """
    result = await db_session.execute(
        select(TopicCluster).where(
            TopicCluster.analysis_id == analysis_id,
            TopicCluster.is_valid == True,  # noqa: E712
        ).order_by(desc(TopicCluster.size))
    )
    return list(result.scalars().all())


async def get_topic_cluster_by_topic_id(
    db_session: AsyncSession,
    analysis_id: int,
    topic_id: int,
) -> Optional[TopicCluster]:
    """
    Get a topic cluster by analysis and topic ID.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        topic_id: BERTopic topic ID
        
    Returns:
        TopicCluster if found, None otherwise
    """
    result = await db_session.execute(
        select(TopicCluster).where(
            TopicCluster.analysis_id == analysis_id,
            TopicCluster.topic_id == topic_id,
            TopicCluster.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def update_topic_cluster(
    db_session: AsyncSession,
    cluster_id: int,
    **kwargs,
) -> Optional[TopicCluster]:
    """
    Update a topic cluster.
    
    Args:
        db_session: Database session
        cluster_id: Cluster ID
        **kwargs: Fields to update
        
    Returns:
        Updated TopicCluster if found, None otherwise
    """
    cluster = await get_topic_cluster_by_id(db_session, cluster_id)
    
    if cluster is None:
        return None
    
    for key, value in kwargs.items():
        if hasattr(cluster, key):
            setattr(cluster, key, value)
    
    await db_session.commit()
    await db_session.refresh(cluster)
    
    return cluster


async def delete_topic_clusters_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> int:
    """
    Soft delete all topic clusters for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        
    Returns:
        Number of clusters deleted
    """
    clusters = await get_topic_clusters_by_analysis(db_session, analysis_id)
    
    for cluster in clusters:
        cluster.is_valid = False
    
    await db_session.commit()
    
    return len(clusters)


# ============================================================
# TopicOutlier CRUD
# ============================================================

async def create_topic_outlier(
    db_session: AsyncSession,
    analysis_id: int,
    document_id: str,
    article_id: Optional[int] = None,
    potential_category: Optional[str] = None,
    embedding_distance: Optional[float] = None,
) -> TopicOutlier:
    """
    Create a new topic outlier.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        document_id: Qdrant document ID
        article_id: Database article ID (optional)
        potential_category: Suggested category
        embedding_distance: Distance to nearest centroid
        
    Returns:
        Created TopicOutlier
    """
    outlier = TopicOutlier(
        analysis_id=analysis_id,
        document_id=document_id,
        article_id=article_id,
        potential_category=potential_category,
        embedding_distance=embedding_distance,
    )
    
    db_session.add(outlier)
    await db_session.commit()
    await db_session.refresh(outlier)
    
    return outlier


async def create_topic_outliers_batch(
    db_session: AsyncSession,
    analysis_id: int,
    outliers_data: List[Dict[str, Any]],
) -> List[TopicOutlier]:
    """
    Create multiple topic outliers in batch.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        outliers_data: List of outlier dictionaries
        
    Returns:
        List of created TopicOutliers
    """
    outliers = []
    
    for data in outliers_data:
        outlier = TopicOutlier(
            analysis_id=analysis_id,
            document_id=data["document_id"],
            article_id=data.get("article_id"),
            potential_category=data.get("potential_category"),
            embedding_distance=data.get("embedding_distance"),
        )
        outliers.append(outlier)
    
    db_session.add_all(outliers)
    await db_session.commit()
    
    for outlier in outliers:
        await db_session.refresh(outlier)
    
    logger.info(
        "Created topic outliers batch",
        count=len(outliers),
        analysis_id=analysis_id,
    )
    
    return outliers


async def get_outliers_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
    limit: Optional[int] = None,
) -> List[TopicOutlier]:
    """
    Get all outliers for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        limit: Maximum number of outliers to return
        
    Returns:
        List of TopicOutliers
    """
    query = select(TopicOutlier).where(
        TopicOutlier.analysis_id == analysis_id,
        TopicOutlier.is_valid == True,  # noqa: E712
    ).order_by(TopicOutlier.embedding_distance)
    
    if limit:
        query = query.limit(limit)
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def get_outliers_by_category(
    db_session: AsyncSession,
    analysis_id: int,
    category: str,
) -> List[TopicOutlier]:
    """
    Get outliers by potential category.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        category: Potential category to filter
        
    Returns:
        List of TopicOutliers
    """
    result = await db_session.execute(
        select(TopicOutlier).where(
            TopicOutlier.analysis_id == analysis_id,
            TopicOutlier.potential_category == category,
            TopicOutlier.is_valid == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def delete_outliers_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> int:
    """
    Soft delete all outliers for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Pipeline execution ID
        
    Returns:
        Number of outliers deleted
    """
    outliers = await get_outliers_by_analysis(db_session, analysis_id)
    
    for outlier in outliers:
        outlier.is_valid = False
    
    await db_session.commit()
    
    return len(outliers)

