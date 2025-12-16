"""CRUD operations for ErrorLog model."""

import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import ErrorLog
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def log_error(
    db_session: AsyncSession,
    error_type: str,
    error_message: str,
    component: str,
    context: Optional[Dict[str, Any]] = None,
    error_traceback: Optional[str] = None,
    severity: str = "error",
    execution_id: Optional[UUID] = None,
    domain: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> ErrorLog:
    """
    Enregistrer une erreur dans la table error_logs.
    
    Si une erreur similaire existe déjà (même type, message, composant),
    on incrémente occurrence_count au lieu de créer un nouveau log.
    
    Args:
        db_session: Database session
        error_type: Type d'erreur (ex: 'AttributeError', 'ValueError')
        error_message: Message d'erreur
        component: Composant où l'erreur s'est produite (ex: 'qdrant', 'scraping', 'llm')
        context: Contexte additionnel (dict)
        error_traceback: Stack trace complet
        severity: Sévérité ('critical', 'error', 'warning')
        execution_id: ID de l'exécution workflow (optionnel)
        domain: Domaine concerné (optionnel)
        agent_name: Nom de l'agent (optionnel)
        
    Returns:
        ErrorLog instance créée ou mise à jour
    """
    try:
        # Chercher une erreur similaire non résolue
        existing = await db_session.execute(
            select(ErrorLog).where(
                and_(
                    ErrorLog.error_type == error_type,
                    ErrorLog.error_message == error_message,
                    ErrorLog.component == component,
                    ErrorLog.is_resolved == False,  # noqa: E712
                )
            ).order_by(ErrorLog.last_occurrence.desc())
        )
        existing_error = existing.scalar_one_or_none()
        
        if existing_error:
            # Incrémenter le compteur
            existing_error.occurrence_count += 1
            existing_error.last_occurrence = datetime.now(timezone.utc)
            if context:
                # Fusionner les contextes (garder les anciennes valeurs, ajouter les nouvelles)
                existing_context = existing_error.context or {}
                existing_context.update(context)
                existing_error.context = existing_context
            await db_session.commit()
            await db_session.refresh(existing_error)
            logger.debug(
                "Error occurrence incremented",
                error_id=existing_error.id,
                count=existing_error.occurrence_count,
            )
            return existing_error
        
        # Créer une nouvelle entrée
        error_log = ErrorLog(
            error_type=error_type,
            error_message=error_message,
            component=component,
            context=context or {},
            error_traceback=error_traceback,
            severity=severity,
            execution_id=execution_id,
            domain=domain,
            agent_name=agent_name,
            first_occurrence=datetime.now(timezone.utc),
            last_occurrence=datetime.now(timezone.utc),
        )
        db_session.add(error_log)
        await db_session.commit()
        await db_session.refresh(error_log)
        logger.info(
            "Error logged",
            error_id=error_log.id,
            component=component,
            error_type=error_type,
            severity=severity,
        )
        return error_log
    except Exception as e:
        # Si on ne peut pas logger l'erreur, on log dans les logs standards
        logger.error(
            "Failed to log error to database",
            error=str(e),
            original_error_type=error_type,
            original_component=component,
        )
        # On ne raise pas pour ne pas interrompre le flux principal
        # On retourne None pour indiquer l'échec
        return None


async def log_error_from_exception(
    db_session: AsyncSession,
    exception: Exception,
    component: str,
    context: Optional[Dict[str, Any]] = None,
    severity: str = "error",
    execution_id: Optional[UUID] = None,
    domain: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Optional[ErrorLog]:
    """
    Enregistrer une erreur à partir d'une exception Python.
    
    Args:
        db_session: Database session
        exception: Exception Python
        component: Composant où l'erreur s'est produite
        context: Contexte additionnel
        severity: Sévérité
        execution_id: ID de l'exécution workflow
        domain: Domaine concerné
        agent_name: Nom de l'agent
        
    Returns:
        ErrorLog instance ou None si échec
    """
    error_type = type(exception).__name__
    error_message = str(exception)
    error_traceback = traceback.format_exc()
    
    return await log_error(
        db_session=db_session,
        error_type=error_type,
        error_message=error_message,
        component=component,
        context=context,
        error_traceback=error_traceback,
        severity=severity,
        execution_id=execution_id,
        domain=domain,
        agent_name=agent_name,
    )


async def get_unresolved_errors(
    db_session: AsyncSession,
    component: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
) -> List[ErrorLog]:
    """
    Récupérer les erreurs non résolues.
    
    Args:
        db_session: Database session
        component: Filtrer par composant (optionnel)
        severity: Filtrer par sévérité (optionnel)
        limit: Nombre maximum d'erreurs à retourner
        
    Returns:
        Liste d'ErrorLog non résolues
    """
    query = select(ErrorLog).where(ErrorLog.is_resolved == False)  # noqa: E712
    
    if component:
        query = query.where(ErrorLog.component == component)
    if severity:
        query = query.where(ErrorLog.severity == severity)
    
    query = query.order_by(ErrorLog.last_occurrence.desc()).limit(limit)
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def get_errors_by_component(
    db_session: AsyncSession,
    component: str,
    limit: int = 100,
) -> List[ErrorLog]:
    """
    Récupérer les erreurs d'un composant spécifique.
    
    Args:
        db_session: Database session
        component: Nom du composant
        limit: Nombre maximum d'erreurs à retourner
        
    Returns:
        Liste d'ErrorLog pour ce composant
    """
    query = (
        select(ErrorLog)
        .where(ErrorLog.component == component)
        .order_by(ErrorLog.last_occurrence.desc())
        .limit(limit)
    )
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def get_errors_by_domain(
    db_session: AsyncSession,
    domain: str,
    limit: int = 100,
) -> List[ErrorLog]:
    """
    Récupérer les erreurs pour un domaine spécifique.
    
    Args:
        db_session: Database session
        domain: Nom du domaine
        limit: Nombre maximum d'erreurs à retourner
        
    Returns:
        Liste d'ErrorLog pour ce domaine
    """
    query = (
        select(ErrorLog)
        .where(ErrorLog.domain == domain)
        .order_by(ErrorLog.last_occurrence.desc())
        .limit(limit)
    )
    
    result = await db_session.execute(query)
    return list(result.scalars().all())


async def mark_error_resolved(
    db_session: AsyncSession,
    error_id: int,
    resolution_note: Optional[str] = None,
) -> bool:
    """
    Marquer une erreur comme résolue.
    
    Args:
        db_session: Database session
        error_id: ID de l'erreur
        resolution_note: Note de résolution (optionnel)
        
    Returns:
        True si succès, False si erreur non trouvée
    """
    error = await db_session.get(ErrorLog, error_id)
    if error:
        error.is_resolved = True
        error.resolution_note = resolution_note
        await db_session.commit()
        logger.info("Error marked as resolved", error_id=error_id)
        return True
    return False


async def get_error_statistics(
    db_session: AsyncSession,
    component: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Obtenir des statistiques sur les erreurs.
    
    Args:
        db_session: Database session
        component: Filtrer par composant (optionnel)
        days: Nombre de jours à analyser
        
    Returns:
        Dict avec statistiques
    """
    from datetime import timedelta
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = select(
        ErrorLog.component,
        ErrorLog.severity,
        ErrorLog.is_resolved,
        func.count(ErrorLog.id).label("count"),
    ).where(
        ErrorLog.first_occurrence >= cutoff_date
    )
    
    if component:
        query = query.where(ErrorLog.component == component)
    
    query = query.group_by(
        ErrorLog.component,
        ErrorLog.severity,
        ErrorLog.is_resolved,
    )
    
    result = await db_session.execute(query)
    rows = result.all()
    
    stats = {
        "total_errors": sum(row.count for row in rows),
        "by_component": {},
        "by_severity": {},
        "resolved": 0,
        "unresolved": 0,
    }
    
    for row in rows:
        component_name = row.component
        severity = row.severity
        is_resolved = row.is_resolved
        count = row.count
        
        # Par composant
        if component_name not in stats["by_component"]:
            stats["by_component"][component_name] = 0
        stats["by_component"][component_name] += count
        
        # Par sévérité
        if severity not in stats["by_severity"]:
            stats["by_severity"][severity] = 0
        stats["by_severity"][severity] += count
        
        # Résolu/Non résolu
        if is_resolved:
            stats["resolved"] += count
        else:
            stats["unresolved"] += count
    
    return stats









