"""CRUD operations for BertopicAnalysis model (T125 - US7)."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import numpy as np

from python_scripts.database.models import BertopicAnalysis
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable objects to serializable types.
    
    Handles:
    - pandas Timestamp -> str (ISO format)
    - numpy types (int64, float64, etc.) -> Python int/float
    - datetime objects -> str (ISO format)
    - float("inf"), float("-inf"), float("nan") -> None or large number
    - nested dicts and lists
    """
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        val = float(obj)
        # Handle infinity and NaN
        if np.isinf(val):
            return None if val > 0 else None  # Replace inf with None
        elif np.isnan(val):
            return None
        return val
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (float, int)):
        # Handle Python float infinity and NaN
        if isinstance(obj, float):
            if obj == float("inf") or obj == float("-inf"):
                return None
            elif obj != obj:  # NaN check
                return None
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj


async def create_bertopic_analysis(
    db_session: AsyncSession,
    analysis_date: datetime,
    time_window_days: int,
    domains_included: Dict[str, any],
    topics: Dict[str, any],
    topic_hierarchy: Optional[Dict[str, any]] = None,
    topics_over_time: Optional[Dict[str, any]] = None,
    visualizations: Optional[Dict[str, any]] = None,
    model_parameters: Optional[Dict[str, any]] = None,
) -> BertopicAnalysis:
    """
    Create a new BERTopic analysis record.
    
    Args:
        db_session: Database session
        analysis_date: Date of the analysis
        time_window_days: Time window in days
        domains_included: Dictionary of domains included in analysis
        topics: Dictionary of discovered topics
        topic_hierarchy: Optional topic hierarchy
        topics_over_time: Optional temporal evolution data
        visualizations: Optional visualization paths
        model_parameters: Optional model parameters used
        
    Returns:
        Created BertopicAnalysis instance
    """
    # Convert all data to JSON-serializable format
    domains_included_clean = make_json_serializable(domains_included)
    topics_clean = make_json_serializable(topics)
    topic_hierarchy_clean = make_json_serializable(topic_hierarchy) if topic_hierarchy else None
    topics_over_time_clean = make_json_serializable(topics_over_time) if topics_over_time else None
    visualizations_clean = make_json_serializable(visualizations) if visualizations else None
    model_parameters_clean = make_json_serializable(model_parameters) if model_parameters else None
    
    analysis = BertopicAnalysis(
        analysis_date=analysis_date.date() if isinstance(analysis_date, datetime) else analysis_date,
        time_window_days=time_window_days,
        domains_included=domains_included_clean,
        topics=topics_clean,
        topic_hierarchy=topic_hierarchy_clean,
        topics_over_time=topics_over_time_clean,
        visualizations=visualizations_clean,
        model_parameters=model_parameters_clean,
    )
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)
    logger.info(
        "BERTopic analysis created",
        analysis_id=analysis.id,
        analysis_date=analysis.analysis_date,
        num_topics=len(topics_clean),
    )
    return analysis


async def get_bertopic_analysis_by_id(
    db_session: AsyncSession,
    analysis_id: int,
) -> Optional[BertopicAnalysis]:
    """
    Get BERTopic analysis by ID.
    
    Args:
        db_session: Database session
        analysis_id: Analysis ID
        
    Returns:
        BertopicAnalysis if found, None otherwise
    """
    result = await db_session.execute(
        select(BertopicAnalysis).where(
            BertopicAnalysis.id == analysis_id,
            BertopicAnalysis.is_valid == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def list_bertopic_analyses(
    db_session: AsyncSession,
    time_window_days: Optional[int] = None,
    domain: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[BertopicAnalysis]:
    """
    List BERTopic analyses with optional filters.
    
    Args:
        db_session: Database session
        time_window_days: Filter by time window (optional)
        domain: Filter by domain included (optional)
        limit: Maximum number of analyses to return
        offset: Number of analyses to skip
        
    Returns:
        List of BertopicAnalysis instances
    """
    query = select(BertopicAnalysis).where(
        BertopicAnalysis.is_valid == True  # noqa: E712
    )
    
    if time_window_days is not None:
        query = query.where(BertopicAnalysis.time_window_days == time_window_days)
    
    if domain:
        # Check if domain is in domains_included JSONB field
        query = query.where(BertopicAnalysis.domains_included.has_key(domain))
    
    query = query.order_by(desc(BertopicAnalysis.analysis_date))
    query = query.limit(limit).offset(offset)
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def get_latest_bertopic_analysis(
    db_session: AsyncSession,
    domain: Optional[str] = None,
) -> Optional[BertopicAnalysis]:
    """
    Get the latest BERTopic analysis.
    
    Args:
        db_session: Database session
        domain: Filter by domain (optional)
        
    Returns:
        Latest BertopicAnalysis if found, None otherwise
    """
    query = select(BertopicAnalysis).where(
        BertopicAnalysis.is_valid == True  # noqa: E712
    )
    
    if domain:
        query = query.where(BertopicAnalysis.domains_included.has_key(domain))
    
    query = query.order_by(desc(BertopicAnalysis.analysis_date)).limit(1)
    
    result = await db_session.execute(query)
    return result.scalar_one_or_none()


async def update_bertopic_analysis(
    db_session: AsyncSession,
    analysis: BertopicAnalysis,
    **kwargs: Dict[str, any],
) -> BertopicAnalysis:
    """
    Update BERTopic analysis fields.
    
    Args:
        db_session: Database session
        analysis: BertopicAnalysis instance to update
        **kwargs: Fields to update
        
    Returns:
        Updated BertopicAnalysis instance
    """
    for key, value in kwargs.items():
        if hasattr(analysis, key):
            setattr(analysis, key, value)
    
    analysis.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(analysis)
    logger.info("BERTopic analysis updated", analysis_id=analysis.id)
    return analysis


async def delete_bertopic_analysis(
    db_session: AsyncSession,
    analysis: BertopicAnalysis,
) -> None:
    """
    Soft delete a BERTopic analysis.
    
    Args:
        db_session: Database session
        analysis: BertopicAnalysis instance to delete
    """
    analysis.is_valid = False
    analysis.updated_at = datetime.now(timezone.utc)
    await db_session.commit()
    logger.info("BERTopic analysis deleted", analysis_id=analysis.id)

