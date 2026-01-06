"""CRUD operations for weak signal analysis."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import WeakSignalAnalysis
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def create_weak_signal_analysis(
    db_session: AsyncSession,
    analysis_id: int,
    outlier_ids: Dict[str, Any],
    common_thread: Optional[str] = None,
    disruption_potential: Optional[float] = None,
    recommendation: str = "monitor",
    llm_model_used: str = "unknown",
) -> WeakSignalAnalysis:
    """
    Create a weak signal analysis record.
    
    Args:
        db_session: Database session
        analysis_id: Analysis ID (from trend_pipeline_executions.id)
        outlier_ids: Dictionary of outlier document IDs
        common_thread: Common thread identified in outliers (optional)
        disruption_potential: Disruption potential score (optional)
        recommendation: Recommendation ('early_adopter', 'wait', 'monitor')
        llm_model_used: LLM model used for analysis
        
    Returns:
        Created WeakSignalAnalysis instance
    """
    signal = WeakSignalAnalysis(
        analysis_id=analysis_id,
        outlier_ids=outlier_ids,
        common_thread=common_thread,
        disruption_potential=disruption_potential,
        recommendation=recommendation,
        llm_model_used=llm_model_used,
    )
    db_session.add(signal)
    await db_session.commit()
    await db_session.refresh(signal)
    logger.debug(
        "Created weak signal analysis",
        signal_id=signal.id,
        analysis_id=analysis_id,
        recommendation=recommendation,
    )
    return signal


async def get_weak_signals_by_analysis(
    db_session: AsyncSession,
    analysis_id: int,
) -> List[WeakSignalAnalysis]:
    """
    Get weak signal analyses for an analysis.
    
    Args:
        db_session: Database session
        analysis_id: Analysis ID
        
    Returns:
        List of WeakSignalAnalysis instances
    """
    result = await db_session.execute(
        select(WeakSignalAnalysis).where(
            WeakSignalAnalysis.analysis_id == analysis_id,
            WeakSignalAnalysis.is_valid == True,  # noqa: E712
        ).order_by(WeakSignalAnalysis.created_at.desc())
    )
    return list(result.scalars().all())


async def get_weak_signals_by_disruption_potential(
    db_session: AsyncSession,
    min_potential: float = 0.7,
    limit: Optional[int] = None,
) -> List[WeakSignalAnalysis]:
    """
    Get weak signals with high disruption potential.
    
    Args:
        db_session: Database session
        min_potential: Minimum disruption potential score
        limit: Optional limit on number of results
        
    Returns:
        List of WeakSignalAnalysis instances sorted by disruption potential
    """
    query = select(WeakSignalAnalysis).where(
        WeakSignalAnalysis.disruption_potential >= min_potential,
        WeakSignalAnalysis.is_valid == True,  # noqa: E712
    ).order_by(WeakSignalAnalysis.disruption_potential.desc())
    
    if limit:
        query = query.limit(limit)
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


















