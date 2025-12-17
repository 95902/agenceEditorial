"""CRUD operations for client coverage analysis and client strengths."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import ClientCoverageAnalysis, ClientStrength, TopicCluster
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# ClientCoverageAnalysis CRUD
# ============================================================

async def create_client_coverage_analysis(
    db_session: AsyncSession,
    domain: str,
    topic_cluster_id: int,
    client_article_count: int,
    coverage_score: float,
    avg_distance_to_centroid: Optional[float] = None,
) -> ClientCoverageAnalysis:
    """
    Create a client coverage analysis record.
    
    Args:
        db_session: Database session
        domain: Client domain
        topic_cluster_id: Topic cluster ID
        client_article_count: Number of client articles in this topic
        coverage_score: Coverage score (ratio vs competitors)
        avg_distance_to_centroid: Average distance to topic centroid (optional)
        
    Returns:
        Created ClientCoverageAnalysis instance
    """
    coverage = ClientCoverageAnalysis(
        domain=domain,
        topic_cluster_id=topic_cluster_id,
        client_article_count=client_article_count,
        coverage_score=coverage_score,
        avg_distance_to_centroid=avg_distance_to_centroid,
    )
    db_session.add(coverage)
    await db_session.commit()
    await db_session.refresh(coverage)
    logger.debug(
        "Created client coverage analysis",
        coverage_id=coverage.id,
        domain=domain,
        topic_cluster_id=topic_cluster_id,
        coverage_score=coverage_score,
    )
    return coverage


async def create_client_coverage_analysis_batch(
    db_session: AsyncSession,
    client_domain: str,
    coverage_data: List[Dict[str, Any]],
    analysis_id: int,
) -> List[ClientCoverageAnalysis]:
    """
    Create multiple client coverage analyses in batch.
    
    Args:
        db_session: Database session
        client_domain: Client domain
        coverage_data: List of coverage dictionaries from GapAnalyzer.analyze_coverage()
        analysis_id: Analysis ID to find topic clusters
        
    Returns:
        List of created ClientCoverageAnalysis instances
    """
    from python_scripts.database.crud_clusters import get_topic_cluster_by_topic_id
    
    created_analyses = []
    
    for coverage_item in coverage_data:
        topic_id = coverage_item.get("topic_id")
        if topic_id is None:
            logger.warning("Coverage data missing topic_id", coverage_item=coverage_item)
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
        
        try:
            coverage = await create_client_coverage_analysis(
                db_session=db_session,
                domain=client_domain,
                topic_cluster_id=db_cluster.id,
                client_article_count=coverage_item.get("client_count", 0),
                coverage_score=coverage_item.get("coverage_score", 0.0),
                avg_distance_to_centroid=None,  # Not calculated in current implementation
            )
            created_analyses.append(coverage)
        except Exception as e:
            logger.warning(
                f"Failed to save coverage analysis for topic {topic_id}",
                error=str(e),
                topic_id=topic_id,
            )
    
    logger.info(
        "Created client coverage analyses batch",
        total=len(created_analyses),
        requested=len(coverage_data),
    )
    return created_analyses


async def get_client_coverage_by_domain(
    db_session: AsyncSession,
    domain: str,
    analysis_id: Optional[int] = None,
) -> List[ClientCoverageAnalysis]:
    """
    Get client coverage analyses for a domain.
    
    Args:
        db_session: Database session
        domain: Client domain
        analysis_id: Optional analysis ID to filter by topic clusters
        
    Returns:
        List of ClientCoverageAnalysis instances
    """
    query = select(ClientCoverageAnalysis).where(
        ClientCoverageAnalysis.domain == domain,
        ClientCoverageAnalysis.is_valid == True,  # noqa: E712
    )
    
    if analysis_id:
        query = query.join(
            TopicCluster,
            ClientCoverageAnalysis.topic_cluster_id == TopicCluster.id
        ).where(TopicCluster.analysis_id == analysis_id)
    
    query = query.order_by(ClientCoverageAnalysis.coverage_score.asc())
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


# ============================================================
# ClientStrength CRUD
# ============================================================

async def create_client_strength(
    db_session: AsyncSession,
    domain: str,
    topic_cluster_id: int,
    advantage_score: float,
    description: str,
) -> ClientStrength:
    """
    Create a client strength record.
    
    Args:
        db_session: Database session
        domain: Client domain
        topic_cluster_id: Topic cluster ID
        advantage_score: Advantage score (excess over parity)
        description: Description of the strength
        
    Returns:
        Created ClientStrength instance
    """
    strength = ClientStrength(
        domain=domain,
        topic_cluster_id=topic_cluster_id,
        advantage_score=advantage_score,
        description=description,
    )
    db_session.add(strength)
    await db_session.commit()
    await db_session.refresh(strength)
    logger.debug(
        "Created client strength",
        strength_id=strength.id,
        domain=domain,
        topic_cluster_id=topic_cluster_id,
        advantage_score=advantage_score,
    )
    return strength


async def create_client_strengths_batch(
    db_session: AsyncSession,
    client_domain: str,
    strengths_data: List[Dict[str, Any]],
    analysis_id: int,
) -> List[ClientStrength]:
    """
    Create multiple client strengths in batch.
    
    Args:
        db_session: Database session
        client_domain: Client domain
        strengths_data: List of strength dictionaries from GapAnalyzer.identify_strengths()
        analysis_id: Analysis ID to find topic clusters
        
    Returns:
        List of created ClientStrength instances
    """
    from python_scripts.database.crud_clusters import get_topic_cluster_by_topic_id
    
    created_strengths = []
    
    for strength_item in strengths_data:
        topic_id = strength_item.get("topic_id")
        if topic_id is None:
            logger.warning("Strength data missing topic_id", strength_item=strength_item)
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
        
        try:
            strength = await create_client_strength(
                db_session=db_session,
                domain=client_domain,
                topic_cluster_id=db_cluster.id,
                advantage_score=strength_item.get("advantage_score", 0.0),
                description=strength_item.get("description", ""),
            )
            created_strengths.append(strength)
        except Exception as e:
            logger.warning(
                f"Failed to save client strength for topic {topic_id}",
                error=str(e),
                topic_id=topic_id,
            )
    
    logger.info(
        "Created client strengths batch",
        total=len(created_strengths),
        requested=len(strengths_data),
    )
    return created_strengths


async def get_client_strengths_by_domain(
    db_session: AsyncSession,
    domain: str,
    analysis_id: Optional[int] = None,
) -> List[ClientStrength]:
    """
    Get client strengths for a domain.
    
    Args:
        db_session: Database session
        domain: Client domain
        analysis_id: Optional analysis ID to filter by topic clusters
        
    Returns:
        List of ClientStrength instances
    """
    query = select(ClientStrength).where(
        ClientStrength.domain == domain,
        ClientStrength.is_valid == True,  # noqa: E712
    )
    
    if analysis_id:
        query = query.join(
            TopicCluster,
            ClientStrength.topic_cluster_id == TopicCluster.id
        ).where(TopicCluster.analysis_id == analysis_id)
    
    query = query.order_by(ClientStrength.advantage_score.desc())
    
    result = await db_session.execute(query)
    return list(result.scalars().all())






