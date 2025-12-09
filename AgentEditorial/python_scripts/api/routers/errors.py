"""API routes for error logs management."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.crud_error_logs import (
    get_error_statistics,
    get_errors_by_component,
    get_errors_by_domain,
    get_unresolved_errors,
    log_error_from_exception,
    mark_error_resolved,
)
from python_scripts.database.db_session import get_db
from python_scripts.database.models import ErrorLog
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/errors", tags=["errors"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Get error logs",
    description="Récupérer les logs d'erreurs avec filtres optionnels.",
)
async def get_errors(
    component: Optional[str] = Query(None, description="Filtrer par composant"),
    severity: Optional[str] = Query(None, description="Filtrer par sévérité (critical, error, warning)"),
    domain: Optional[str] = Query(None, description="Filtrer par domaine"),
    agent_name: Optional[str] = Query(None, description="Filtrer par agent"),
    execution_id: Optional[UUID] = Query(None, description="Filtrer par execution_id"),
    is_resolved: Optional[bool] = Query(None, description="Filtrer par statut de résolution"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum d'erreurs à retourner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Récupérer les logs d'erreurs avec filtres optionnels.
    
    Returns:
        Dict avec la liste des erreurs et le total
    """
    from sqlalchemy import select, and_, func
    
    query = select(ErrorLog)
    conditions = []
    
    if component:
        conditions.append(ErrorLog.component == component)
    if severity:
        conditions.append(ErrorLog.severity == severity)
    if domain:
        conditions.append(ErrorLog.domain == domain)
    if agent_name:
        conditions.append(ErrorLog.agent_name == agent_name)
    if execution_id:
        conditions.append(ErrorLog.execution_id == execution_id)
    if is_resolved is not None:
        conditions.append(ErrorLog.is_resolved == is_resolved)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(ErrorLog.last_occurrence.desc()).limit(limit)
    
    result = await db.execute(query)
    errors = result.scalars().all()
    
    # Count total
    count_query = select(ErrorLog)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    count_result = await db.execute(select(func.count()).select_from(count_query.subquery()))
    total = count_result.scalar() or 0
    
    return {
        "errors": [
            {
                "id": error.id,
                "execution_id": str(error.execution_id) if error.execution_id else None,
                "domain": error.domain,
                "agent_name": error.agent_name,
                "component": error.component,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "error_traceback": error.error_traceback,
                "context": error.context,
                "severity": error.severity,
                "is_resolved": error.is_resolved,
                "resolution_note": error.resolution_note,
                "occurrence_count": error.occurrence_count,
                "first_occurrence": error.first_occurrence.isoformat() if error.first_occurrence else None,
                "last_occurrence": error.last_occurrence.isoformat() if error.last_occurrence else None,
            }
            for error in errors
        ],
        "total": total,
        "limit": limit,
    }


@router.get(
    "/unresolved",
    status_code=status.HTTP_200_OK,
    summary="Get unresolved errors",
    description="Récupérer les erreurs non résolues.",
)
async def get_unresolved(
    component: Optional[str] = Query(None, description="Filtrer par composant"),
    severity: Optional[str] = Query(None, description="Filtrer par sévérité"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum d'erreurs"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Récupérer les erreurs non résolues.
    
    Returns:
        Dict avec la liste des erreurs non résolues
    """
    errors = await get_unresolved_errors(
        db_session=db,
        component=component,
        severity=severity,
        limit=limit,
    )
    
    return {
        "errors": [
            {
                "id": error.id,
                "execution_id": str(error.execution_id) if error.execution_id else None,
                "domain": error.domain,
                "agent_name": error.agent_name,
                "component": error.component,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "error_traceback": error.error_traceback,
                "context": error.context,
                "severity": error.severity,
                "occurrence_count": error.occurrence_count,
                "first_occurrence": error.first_occurrence.isoformat() if error.first_occurrence else None,
                "last_occurrence": error.last_occurrence.isoformat() if error.last_occurrence else None,
            }
            for error in errors
        ],
        "count": len(errors),
    }


@router.get(
    "/by-component/{component}",
    status_code=status.HTTP_200_OK,
    summary="Get errors by component",
    description="Récupérer les erreurs d'un composant spécifique.",
)
async def get_errors_by_component_route(
    component: str,
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum d'erreurs"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Récupérer les erreurs d'un composant spécifique.
    
    Args:
        component: Nom du composant (ex: 'qdrant', 'scraping', 'llm')
        limit: Nombre maximum d'erreurs
        
    Returns:
        Dict avec la liste des erreurs
    """
    errors = await get_errors_by_component(
        db_session=db,
        component=component,
        limit=limit,
    )
    
    return {
        "component": component,
        "errors": [
            {
                "id": error.id,
                "execution_id": str(error.execution_id) if error.execution_id else None,
                "domain": error.domain,
                "agent_name": error.agent_name,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "severity": error.severity,
                "is_resolved": error.is_resolved,
                "occurrence_count": error.occurrence_count,
                "first_occurrence": error.first_occurrence.isoformat() if error.first_occurrence else None,
                "last_occurrence": error.last_occurrence.isoformat() if error.last_occurrence else None,
            }
            for error in errors
        ],
        "count": len(errors),
    }


@router.get(
    "/by-domain/{domain}",
    status_code=status.HTTP_200_OK,
    summary="Get errors by domain",
    description="Récupérer les erreurs pour un domaine spécifique.",
)
async def get_errors_by_domain_route(
    domain: str,
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum d'erreurs"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Récupérer les erreurs pour un domaine spécifique.
    
    Args:
        domain: Nom du domaine
        limit: Nombre maximum d'erreurs
        
    Returns:
        Dict avec la liste des erreurs
    """
    errors = await get_errors_by_domain(
        db_session=db,
        domain=domain,
        limit=limit,
    )
    
    return {
        "domain": domain,
        "errors": [
            {
                "id": error.id,
                "execution_id": str(error.execution_id) if error.execution_id else None,
                "agent_name": error.agent_name,
                "component": error.component,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "severity": error.severity,
                "is_resolved": error.is_resolved,
                "occurrence_count": error.occurrence_count,
                "first_occurrence": error.first_occurrence.isoformat() if error.first_occurrence else None,
                "last_occurrence": error.last_occurrence.isoformat() if error.last_occurrence else None,
            }
            for error in errors
        ],
        "count": len(errors),
    }


@router.get(
    "/statistics",
    status_code=status.HTTP_200_OK,
    summary="Get error statistics",
    description="Obtenir des statistiques sur les erreurs.",
)
async def get_statistics(
    component: Optional[str] = Query(None, description="Filtrer par composant"),
    days: int = Query(7, ge=1, le=365, description="Nombre de jours à analyser"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Obtenir des statistiques sur les erreurs.
    
    Args:
        component: Filtrer par composant (optionnel)
        days: Nombre de jours à analyser
        
    Returns:
        Dict avec les statistiques
    """
    stats = await get_error_statistics(
        db_session=db,
        component=component,
        days=days,
    )
    
    return {
        "period_days": days,
        "component": component,
        "statistics": stats,
    }


@router.get(
    "/{error_id}",
    status_code=status.HTTP_200_OK,
    summary="Get error by ID",
    description="Récupérer une erreur spécifique par son ID.",
)
async def get_error_by_id(
    error_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Récupérer une erreur spécifique par son ID.
    
    Args:
        error_id: ID de l'erreur
        
    Returns:
        Dict avec les détails de l'erreur
    """
    error = await db.get(ErrorLog, error_id)
    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Error with ID {error_id} not found",
        )
    
    return {
        "id": error.id,
        "execution_id": str(error.execution_id) if error.execution_id else None,
        "domain": error.domain,
        "agent_name": error.agent_name,
        "component": error.component,
        "error_type": error.error_type,
        "error_message": error.error_message,
        "error_traceback": error.error_traceback,
        "context": error.context,
        "severity": error.severity,
        "is_resolved": error.is_resolved,
        "resolution_note": error.resolution_note,
        "occurrence_count": error.occurrence_count,
        "first_occurrence": error.first_occurrence.isoformat() if error.first_occurrence else None,
        "last_occurrence": error.last_occurrence.isoformat() if error.last_occurrence else None,
    }


@router.post(
    "/{error_id}/resolve",
    status_code=status.HTTP_200_OK,
    summary="Mark error as resolved",
    description="Marquer une erreur comme résolue.",
)
async def resolve_error(
    error_id: int,
    resolution_note: Optional[str] = Query(None, description="Note de résolution"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Marquer une erreur comme résolue.
    
    Args:
        error_id: ID de l'erreur
        resolution_note: Note de résolution (optionnel)
        
    Returns:
        Dict avec le statut de la mise à jour
    """
    success = await mark_error_resolved(
        db_session=db,
        error_id=error_id,
        resolution_note=resolution_note,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Error with ID {error_id} not found",
        )
    
    return {
        "error_id": error_id,
        "is_resolved": True,
        "resolution_note": resolution_note,
        "message": "Error marked as resolved",
    }

