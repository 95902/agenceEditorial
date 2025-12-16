"""CRUD operations for editorial gaps and content roadmap."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import EditorialGap, ContentRoadmap, TopicCluster
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_editorial_gap(
    db_session: AsyncSession,
    client_domain: str,
    topic_cluster_id: int,
    coverage_score: float,
    priority_score: float,
    diagnostic: str,
    opportunity_description: str,
    risk_assessment: str,
) -> EditorialGap:
    """
    Create an editorial gap record.
    
    Args:
        db_session: Database session
        client_domain: Client domain
        topic_cluster_id: Topic cluster ID
        coverage_score: Coverage score
        priority_score: Priority score
        diagnostic: Diagnostic text
        opportunity_description: Opportunity description
        risk_assessment: Risk assessment text
        
    Returns:
        Created EditorialGap instance
    """
    gap = EditorialGap(
        client_domain=client_domain,
        topic_cluster_id=topic_cluster_id,
        coverage_score=coverage_score,
        priority_score=priority_score,
        diagnostic=diagnostic,
        opportunity_description=opportunity_description,
        risk_assessment=risk_assessment,
    )
    db_session.add(gap)
    await db_session.commit()
    await db_session.refresh(gap)
    logger.debug("Created editorial gap", gap_id=gap.id, topic_cluster_id=topic_cluster_id)
    return gap


async def create_content_roadmap_item(
    db_session: AsyncSession,
    client_domain: str,
    gap_id: int,
    recommendation_id: int,
    priority_order: int,
    estimated_effort: str = "medium",
    status: str = "pending",
) -> ContentRoadmap:
    """
    Create a content roadmap item.
    
    Args:
        db_session: Database session
        client_domain: Client domain
        gap_id: Editorial gap ID
        recommendation_id: Article recommendation ID
        priority_order: Priority order (lower = higher priority)
        estimated_effort: Estimated effort ('easy', 'medium', 'complex')
        status: Status ('pending', 'in_progress', 'completed')
        
    Returns:
        Created ContentRoadmap instance
    """
    roadmap_item = ContentRoadmap(
        client_domain=client_domain,
        gap_id=gap_id,
        recommendation_id=recommendation_id,
        priority_order=priority_order,
        estimated_effort=estimated_effort,
        status=status,
    )
    db_session.add(roadmap_item)
    await db_session.commit()
    await db_session.refresh(roadmap_item)
    logger.debug("Created roadmap item", roadmap_id=roadmap_item.id, gap_id=gap_id)
    return roadmap_item


async def get_editorial_gaps_by_domain(
    db_session: AsyncSession,
    client_domain: str,
    analysis_id: Optional[int] = None,
) -> List[EditorialGap]:
    """
    Get editorial gaps for a client domain.
    
    Args:
        db_session: Database session
        client_domain: Client domain
        analysis_id: Optional analysis ID to filter by topic clusters
        
    Returns:
        List of EditorialGap instances
    """
    query = select(EditorialGap).where(
        EditorialGap.client_domain == client_domain,
        EditorialGap.is_valid == True,  # noqa: E712
    )
    
    if analysis_id:
        query = query.join(
            TopicCluster,
            EditorialGap.topic_cluster_id == TopicCluster.id
        ).where(TopicCluster.analysis_id == analysis_id)
    
    query = query.order_by(EditorialGap.priority_score.desc())
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def get_content_roadmap_by_domain(
    db_session: AsyncSession,
    client_domain: str,
) -> List[ContentRoadmap]:
    """
    Get content roadmap for a client domain.
    
    Args:
        db_session: Database session
        client_domain: Client domain
        
    Returns:
        List of ContentRoadmap instances
    """
    result = await db_session.execute(
        select(ContentRoadmap).where(
            ContentRoadmap.client_domain == client_domain,
            ContentRoadmap.is_valid == True,  # noqa: E712
        ).order_by(ContentRoadmap.priority_order)
    )
    return list(result.scalars().all())









