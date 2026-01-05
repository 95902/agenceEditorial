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
        db_session=db_session,  # Pass db_session to identify article types
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
    db_session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Update Qdrant payloads with topic_id.
    
    Args:
        document_topic_mapping: Mapping from qdrant_point_id to topic_id
        client_domain: Client domain name (optional, for collection names)
        db_session: Database session (optional, for identifying article types)
        
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
    
    # If we have db_session, identify which points are client vs competitor articles
    # This is more efficient than trying both collections
    client_point_ids = set()
    competitor_point_ids = set()
    
    if db_session:
        point_ids_list = list(document_topic_mapping.keys())
        
        # Check client articles
        if point_ids_list:
            try:
                client_stmt = select(ClientArticle.qdrant_point_id).where(
                    ClientArticle.qdrant_point_id.in_(point_ids_list)
                )
                client_result = await db_session.execute(client_stmt)
                client_point_ids = {row[0] for row in client_result.all()}
                
                # Competitor articles are the rest
                competitor_point_ids = set(point_ids_list) - client_point_ids
            except Exception as e:
                logger.warning("Failed to identify article types, will try both collections", error=str(e))
    
    # Update points in batches by collection for better performance
    # Group points by collection
    client_points: Dict[UUID, int] = {}
    competitor_points: Dict[UUID, int] = {}
    
    if client_point_ids or competitor_point_ids:
        # Use identified types
        for point_id, topic_id in document_topic_mapping.items():
            if point_id in client_point_ids:
                client_points[point_id] = topic_id
            elif point_id in competitor_point_ids:
                competitor_points[point_id] = topic_id
    else:
        # Fallback: try both collections (less efficient)
        for point_id, topic_id in document_topic_mapping.items():
            # Try client collection first
            if client_collection and qdrant_client.collection_exists(client_collection):
                try:
                    qdrant_client.client.set_payload(
                        collection_name=client_collection,
                        payload={"topic_id": topic_id},
                        points=[point_id],
                    )
                    assigned += 1
                    continue
                except Exception:
                    pass
            
            # Try competitor collection
            if competitor_collection and qdrant_client.collection_exists(competitor_collection):
                try:
                    qdrant_client.client.set_payload(
                        collection_name=competitor_collection,
                        payload={"topic_id": topic_id},
                        points=[point_id],
                    )
                    assigned += 1
                except Exception as e:
                    errors.append({
                        "point_id": str(point_id),
                        "error": f"Point not found in any collection: {str(e)}",
                    })
    
    # Batch update client collection
    if client_points and client_collection and qdrant_client.collection_exists(client_collection):
        # Qdrant doesn't support batch updates with different payloads, so we update in smaller batches
        batch_size = 50
        client_point_list = list(client_points.items())
        
        for i in range(0, len(client_point_list), batch_size):
            batch = client_point_list[i:i + batch_size]
            try:
                # Update each point individually (Qdrant limitation)
                for point_id, topic_id in batch:
                    qdrant_client.client.set_payload(
                        collection_name=client_collection,
                        payload={"topic_id": topic_id},
                        points=[point_id],
                    )
                    assigned += 1
            except Exception as e:
                logger.warning("Failed to update client collection batch", batch_start=i, error=str(e))
                for point_id, _ in batch:
                    errors.append({
                        "point_id": str(point_id),
                        "error": f"Failed to update in client collection: {str(e)}",
                    })
    
    # Batch update competitor collection
    if competitor_points and competitor_collection and qdrant_client.collection_exists(competitor_collection):
        batch_size = 50
        competitor_point_list = list(competitor_points.items())
        
        for i in range(0, len(competitor_point_list), batch_size):
            batch = competitor_point_list[i:i + batch_size]
            try:
                # Update each point individually (Qdrant limitation)
                for point_id, topic_id in batch:
                    qdrant_client.client.set_payload(
                        collection_name=competitor_collection,
                        payload={"topic_id": topic_id},
                        points=[point_id],
                    )
                    assigned += 1
            except Exception as e:
                logger.warning("Failed to update competitor collection batch", batch_start=i, error=str(e))
                for point_id, _ in batch:
                    errors.append({
                        "point_id": str(point_id),
                        "error": f"Failed to update in competitor collection: {str(e)}",
                    })
    
    logger.info(
        "Qdrant payloads updated",
        assigned=assigned,
        errors=len(errors),
        total=len(document_topic_mapping),
        client_points=len(client_points),
        competitor_points=len(competitor_points),
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
            # First, identify which points are client articles and which are competitor articles
            # This avoids trying to update both tables for each point
            client_stmt = select(ClientArticle.qdrant_point_id).where(
                ClientArticle.qdrant_point_id.in_(batch_point_ids)
            )
            client_result = await db_session.execute(client_stmt)
            client_point_ids = {row[0] for row in client_result.all()}
            
            competitor_stmt = select(CompetitorArticle.qdrant_point_id).where(
                CompetitorArticle.qdrant_point_id.in_(batch_point_ids)
            )
            competitor_result = await db_session.execute(competitor_stmt)
            competitor_point_ids = {row[0] for row in competitor_result.all()}
            
            # Update client articles (only those that exist)
            if client_point_ids:
                for point_id in client_point_ids:
                    if point_id in batch_mapping:
                        topic_id = batch_mapping[point_id]
                        stmt = (
                            update(ClientArticle)
                            .where(ClientArticle.qdrant_point_id == point_id)
                            .values(topic_id=topic_id)
                        )
                        result = await db_session.execute(stmt)
                        if result.rowcount > 0:
                            assigned += result.rowcount
            
            # Update competitor articles (only those that exist)
            if competitor_point_ids:
                for point_id in competitor_point_ids:
                    if point_id in batch_mapping:
                        topic_id = batch_mapping[point_id]
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
            logger.error("Failed to update PostgreSQL topic_ids", error=str(e), exc_info=True)
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

