"""Topic assignment module for assigning topic_id to articles after clustering."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import ClientArticle, CompetitorArticle
from python_scripts.vectorstore.qdrant_client import (
    get_client_collection_name,
    get_competitor_collection_name,
    qdrant_client,
)
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def assign_topics_after_clustering(
    db_session: AsyncSession,
    topics: List[int],
    document_ids: List[UUID],
    client_domain: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assign topic_id to articles after clustering.
    
    Creates a mapping from document_id (qdrant_point_id) to topic_id and updates
    both Qdrant payloads and PostgreSQL topic_id columns.
    
    Args:
        db_session: Database session
        topics: List of topic_id assigned to each document (by index)
        document_ids: List of qdrant_point_id for each document
        client_domain: Client domain name (e.g., "innosys.fr")
        
    Returns:
        Dictionary with assignment results
    """
    if len(topics) != len(document_ids):
        logger.warning(
            "Mismatch between topics and document_ids length",
            topics_len=len(topics),
            document_ids_len=len(document_ids),
        )
        return {
            "success": False,
            "error": "Mismatch between topics and document_ids length",
            "assigned_qdrant": 0,
            "assigned_postgresql": 0,
        }
    
    # Create mapping: document_id (qdrant_point_id) -> topic_id
    # Ignore outliers (topic_id == -1)
    document_topic_mapping: Dict[UUID, int] = {}
    for i, (topic_id, doc_id) in enumerate(zip(topics, document_ids)):
        if topic_id != -1:  # Ignore outliers
            document_topic_mapping[doc_id] = topic_id
    
    if not document_topic_mapping:
        logger.warning("No valid topics to assign (all outliers)")
        return {
            "success": True,
            "assigned_qdrant": 0,
            "assigned_postgresql": 0,
            "total_documents": len(document_ids),
        }
    
    logger.info(
        "Starting topic assignment",
        total_documents=len(document_ids),
        valid_topics=len(document_topic_mapping),
        outliers=len(document_ids) - len(document_topic_mapping),
    )
    
    # Update Qdrant payloads
    qdrant_result = await _update_qdrant_payloads(
        document_topic_mapping=document_topic_mapping,
        client_domain=client_domain,
    )
    
    # Update PostgreSQL topic_id columns
    postgresql_result = await _update_postgresql_topic_ids(
        db_session=db_session,
        document_topic_mapping=document_topic_mapping,
    )
    
    success = qdrant_result.get("success", False) and postgresql_result.get("success", False)
    
    return {
        "success": success,
        "assigned_qdrant": qdrant_result.get("assigned", 0),
        "assigned_postgresql": postgresql_result.get("assigned", 0),
        "errors_qdrant": qdrant_result.get("errors", []),
        "errors_postgresql": postgresql_result.get("errors", []),
        "total_documents": len(document_ids),
        "valid_topics": len(document_topic_mapping),
    }


async def _update_qdrant_payloads(
    document_topic_mapping: Dict[UUID, int],
    client_domain: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update Qdrant payloads with topic_id.
    
    Args:
        document_topic_mapping: Mapping from qdrant_point_id to topic_id
        client_domain: Client domain name (optional, for collection names)
        
    Returns:
        Dictionary with update results
    """
    assigned = 0
    errors = []
    
    # Get collection names
    client_collection = None
    competitor_collection = None
    
    if client_domain:
        client_collection = get_client_collection_name(client_domain)
        competitor_collection = get_competitor_collection_name(client_domain)
    
    # Update each point individually (Qdrant doesn't support batch updates with different payloads)
    # Group by collection for efficiency
    client_points: Dict[UUID, int] = {}
    competitor_points: Dict[UUID, int] = {}
    
    # First, identify which collection each point belongs to by checking PostgreSQL
    # This is faster than checking Qdrant for each point
    point_ids_list = list(document_topic_mapping.keys())
    
    # Check client articles
    if point_ids_list:
        client_stmt = select(ClientArticle.qdrant_point_id).where(
            ClientArticle.qdrant_point_id.in_(point_ids_list)
        )
        # Note: We need db_session but it's not available here
        # We'll use a simpler approach: try both collections
    
    # Try to update points in both collections
    # Process each point individually (Qdrant set_payload requires collection name)
    for point_id, topic_id in document_topic_mapping.items():
        updated = False
        
        # Try client collection first
        if client_collection and qdrant_client.collection_exists(client_collection):
            try:
                qdrant_client.client.set_payload(
                    collection_name=client_collection,
                    payload={"topic_id": topic_id},
                    points=[point_id],
                )
                assigned += 1
                updated = True
            except Exception:
                # Point not in this collection, try next
                pass
        
        # Try competitor collection if not updated yet
        if not updated and competitor_collection and qdrant_client.collection_exists(competitor_collection):
            try:
                qdrant_client.client.set_payload(
                    collection_name=competitor_collection,
                    payload={"topic_id": topic_id},
                    points=[point_id],
                )
                assigned += 1
                updated = True
            except Exception as e:
                # Point not found in any collection
                errors.append({
                    "point_id": str(point_id),
                    "error": f"Point not found in any collection: {str(e)}",
                })
    
    logger.info(
        "Qdrant payloads updated",
        assigned=assigned,
        errors=len(errors),
        total=len(document_topic_mapping),
    )
    
    return {
        "success": len(errors) == 0 or assigned > 0,
        "assigned": assigned,
        "errors": errors,
    }


async def _update_postgresql_topic_ids(
    db_session: AsyncSession,
    document_topic_mapping: Dict[UUID, int],
) -> Dict[str, Any]:
    """
    Update PostgreSQL topic_id columns for articles.
    
    Args:
        db_session: Database session
        document_topic_mapping: Mapping from qdrant_point_id to topic_id
        
    Returns:
        Dictionary with update results
    """
    assigned = 0
    errors = []
    
    # Process in batches for performance
    batch_size = 100
    point_ids = list(document_topic_mapping.keys())
    
    for i in range(0, len(point_ids), batch_size):
        batch_point_ids = point_ids[i:i + batch_size]
        batch_mapping = {
            pid: document_topic_mapping[pid]
            for pid in batch_point_ids
        }
        
        try:
            # Update client articles
            for point_id, topic_id in batch_mapping.items():
                stmt = (
                    update(ClientArticle)
                    .where(ClientArticle.qdrant_point_id == point_id)
                    .values(topic_id=topic_id)
                )
                result = await db_session.execute(stmt)
                if result.rowcount > 0:
                    assigned += result.rowcount
            
            # Update competitor articles
            for point_id, topic_id in batch_mapping.items():
                stmt = (
                    update(CompetitorArticle)
                    .where(CompetitorArticle.qdrant_point_id == point_id)
                    .values(topic_id=topic_id)
                )
                result = await db_session.execute(stmt)
                if result.rowcount > 0:
                    assigned += result.rowcount
            
            await db_session.commit()
            
        except Exception as e:
            await db_session.rollback()
            logger.error("Failed to update PostgreSQL topic_ids", error=str(e))
            errors.append({
                "batch_start": i,
                "batch_end": min(i + batch_size, len(point_ids)),
                "error": str(e),
            })
    
    logger.info(
        "PostgreSQL topic_ids updated",
        assigned=assigned,
        errors=len(errors),
        total=len(document_topic_mapping),
    )
    
    return {
        "success": len(errors) == 0 or assigned > 0,
        "assigned": assigned,
        "errors": errors,
    }

