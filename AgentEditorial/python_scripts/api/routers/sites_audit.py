"""API router for audit endpoints."""

import asyncio
import re
from typing import Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.responses import (
    AuditStatusResponse,
    DataStatus,
    PendingAuditResponse,
    SiteAuditResponse,
    WorkflowStep,
)
from python_scripts.api.services.audit_service import (
    _check_client_articles,
    _check_competitor_articles,
    _check_competitors,
    _check_site_profile,
    _check_trend_pipeline,
    _get_audit_status,
    build_complete_audit_from_database,
    run_missing_workflows_chain,
)
from python_scripts.database.crud_executions import create_workflow_execution
from python_scripts.database.models import WorkflowExecution
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sites", tags=["sites"])

# Regex pour valider le format d'un domaine
DOMAIN_REGEX = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
)


@router.get(
    "/{domain}/audit",
    response_model=Union[SiteAuditResponse, PendingAuditResponse],
    summary="Get complete site audit (auto-launches missing workflows)",
    description="""
    Get complete site audit data.
    
    Strategy:
    1. Check if data exists in database
    2. If exists: retrieve and use it
    3. If missing: launch only the missing workflows
    
    Checks in order:
    - Site profile (site_profiles)
    - Competitors (workflow_executions with competitor_search)
    - Scraped articles (competitor_articles count)
    - Trend pipeline (trend_pipeline_executions)
    
    Returns either:
    - Complete audit data if all data is available
    - Pending response with execution_id if workflows are launched
    """,
)
async def get_site_audit(
    domain: str = Path(
        ...,
        description="Valid domain name (e.g., example.com, innosys.fr)",
        examples=["innosys.fr", "example.com"],
    ),
    include_topics: bool = Query(False, description="Include detailed topics in domains"),
    include_trending: bool = Query(True, description="Include trending topics section"),
    include_analyses: bool = Query(True, description="Include trend analyses section"),
    include_temporal: bool = Query(True, description="Include temporal insights section"),
    include_opportunities: bool = Query(True, description="Include editorial opportunities section"),
    topics_limit: int = Query(10, ge=1, le=50, description="Maximum number of topics per domain"),
    trending_limit: int = Query(15, ge=1, le=100, description="Maximum number of trending topics"),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Union[SiteAuditResponse, PendingAuditResponse]:
    """
    Get site audit with smart data retrieval.
    
    Vérifie chaque source de données et lance seulement ce qui manque.
    
    Args:
        domain: Domain name (validated format)
        include_topics: Include detailed topics in domains (default: False)
        include_trending: Include trending topics section (default: True)
        include_analyses: Include trend analyses section (default: True)
        include_temporal: Include temporal insights section (default: True)
        include_opportunities: Include editorial opportunities section (default: True)
        topics_limit: Maximum number of topics per domain (default: 10, max: 50)
        trending_limit: Maximum number of trending topics (default: 15, max: 100)
        db: Database session
        background_tasks: FastAPI background tasks
        
    Returns:
        Complete audit data or pending response
        
    Raises:
        HTTPException: 422 if domain format is invalid
    """
    # Validation du domaine (P2-8)
    if not DOMAIN_REGEX.match(domain):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid domain format: {domain}. Expected format: example.com",
        )
    
    # ============================================================
    # ÉTAPE 1: Vérifier site_profile (P0-4: gestion d'erreur)
    # ============================================================
    try:
        profile = await _check_site_profile(db, domain)
    except Exception as e:
        logger.warning(
            "Error checking site profile, assuming missing",
            domain=domain,
            error=str(e),
        )
        profile = None
    needs_analysis = not profile
    
    # ============================================================
    # ÉTAPE 2-5: Vérifications en parallèle (P1-1: parallélisation)
    # ============================================================
    # Paralléliser les vérifications indépendantes pour améliorer les performances
    competitors_execution = None
    trend_execution = None
    competitor_articles_count = 0
    client_articles_count = 0
    
    if profile:
        # Lancer les vérifications en parallèle
        try:
            results = await asyncio.gather(
                _check_competitors(db, domain),
                _check_trend_pipeline(db, domain),
                _check_client_articles(db, profile.id),
                return_exceptions=True,
            )
            
            competitors_execution, trend_execution, client_articles_result = results
            
            # Gérer les exceptions (P0-4: gestion d'erreur)
            if isinstance(competitors_execution, Exception):
                logger.warning(
                    "Error checking competitors, assuming missing",
                    domain=domain,
                    error=str(competitors_execution),
                )
                competitors_execution = None
            if isinstance(trend_execution, Exception):
                logger.warning(
                    "Error checking trend pipeline, assuming missing",
                    domain=domain,
                    error=str(trend_execution),
                )
                trend_execution = None
            if isinstance(client_articles_result, Exception):
                logger.warning(
                    "Error checking client articles, assuming missing",
                    domain=domain,
                    error=str(client_articles_result),
                )
                client_articles_count = 0
            else:
                # client_articles_result est un tuple (count, is_sufficient)
                client_articles_count, _ = client_articles_result
        except Exception as e:
            logger.error(
                "Error during parallel checks",
                domain=domain,
                error=str(e),
            )
            # En cas d'erreur globale, considérer que tout manque
            competitors_execution = None
            trend_execution = None
            client_articles_count = 0
    else:
        # Pas de profile : vérifier seulement les concurrents (sans dépendance)
        try:
            competitors_execution = await _check_competitors(db, domain)
            if isinstance(competitors_execution, Exception):
                logger.warning(
                    "Error checking competitors, assuming missing",
                    domain=domain,
                    error=str(competitors_execution),
                )
                competitors_execution = None
        except Exception as e:
            logger.warning(
                "Error checking competitors, assuming missing",
                domain=domain,
                error=str(e),
            )
            competitors_execution = None
    
    needs_competitors = not competitors_execution
    needs_trend_pipeline = not trend_execution
    
    # ============================================================
    # ÉTAPE 3: Vérifier articles scrapés (competitors)
    # ============================================================
    needs_scraping = False
    
    if competitors_execution:
        # Récupérer les domaines des concurrents validés (P0-5: vérification null)
        if competitors_execution.output_data is None:
            competitors_data = []
        else:
            competitors_data = competitors_execution.output_data.get("competitors", [])
        competitor_domains = [
            c.get("domain")
            for c in competitors_data
            if c.get("domain")
            and not c.get("excluded", False)
            and (c.get("validated", False) or c.get("manual", False))
        ]
        
        if competitor_domains:
            # Compter les articles pour ces domaines (PostgreSQL + Qdrant)
            try:
                count, is_sufficient = await _check_competitor_articles(
                    db, competitor_domains, client_domain=domain
                )
                competitor_articles_count = count
                needs_scraping = not is_sufficient
            except Exception as e:
                logger.warning(
                    "Error checking competitor articles, assuming insufficient",
                    domain=domain,
                    error=str(e),
                )
                competitor_articles_count = 0
                needs_scraping = True
        else:
            needs_scraping = True
    else:
        needs_scraping = True
    
    # ============================================================
    # ÉTAPE 4: Vérifier articles client (client_articles)
    # ============================================================
    needs_client_scraping = False
    
    if profile:
        # client_articles_count a déjà été récupéré dans le gather ci-dessus
        # Vérifier si suffisant (seuil: 5 articles)
        needs_client_scraping = client_articles_count < 5
    else:
        needs_client_scraping = True
    
    # ============================================================
    # DÉCISION: Lancer les workflows manquants ou retourner les données
    # ============================================================
    
    # AVANT de décider de lancer des workflows, vérifier s'il existe un orchestrator "completed" récent
    # Si oui et que les données essentielles sont disponibles, retourner les données directement
    completed_orchestrator_stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_type == "audit_orchestrator",
            WorkflowExecution.status == "completed",
            WorkflowExecution.input_data["domain"].astext == domain,
            WorkflowExecution.is_valid == True,  # noqa: E712
            WorkflowExecution.was_success == True,  # noqa: E712
        )
        .order_by(desc(WorkflowExecution.end_time))
        .limit(1)
    )
    completed_result = await db.execute(completed_orchestrator_stmt)
    completed_orchestrator = completed_result.scalar_one_or_none()
    
    # Si un orchestrator complet existe et que les données essentielles sont disponibles
    # (profile, competitors, trend_pipeline), retourner les données même s'il manque quelques articles
    # Note: needs_scraping peut être True si aucun concurrent n'est validé, mais on peut quand même retourner les données
    if completed_orchestrator and profile and not needs_analysis and not needs_competitors and not needs_trend_pipeline:
        logger.info(
            "Completed orchestrator found with essential data available, returning audit",
            execution_id=str(completed_orchestrator.execution_id),
            domain=domain,
            missing_scraping=needs_scraping,
            missing_client_scraping=needs_client_scraping,
        )
        # Les données essentielles sont disponibles : construire et retourner la réponse
        return await build_complete_audit_from_database(
            db,
            domain,
            profile,
            competitors_execution,
            trend_execution,
            include_topics=include_topics,
            include_trending=include_trending,
            include_analyses=include_analyses,
            include_temporal=include_temporal,
            include_opportunities=include_opportunities,
            topics_limit=topics_limit,
            trending_limit=trending_limit,
        )
    
    # Si les données essentielles sont disponibles SANS orchestrator complet, retourner aussi les données
    # (cas où l'orchestrator n'existe pas mais toutes les données sont là)
    if profile and not needs_analysis and not needs_competitors and not needs_trend_pipeline:
        logger.info(
            "Essential data available without completed orchestrator, returning audit",
            domain=domain,
            missing_scraping=needs_scraping,
            missing_client_scraping=needs_client_scraping,
        )
        # Les données essentielles sont disponibles : construire et retourner la réponse
        return await build_complete_audit_from_database(
            db,
            domain,
            profile,
            competitors_execution,
            trend_execution,
            include_topics=include_topics,
            include_trending=include_trending,
            include_analyses=include_analyses,
            include_temporal=include_temporal,
            include_opportunities=include_opportunities,
            topics_limit=topics_limit,
            trending_limit=trending_limit,
        )
    
    if (
        needs_analysis
        or needs_competitors
        or needs_scraping
        or needs_client_scraping
        or needs_trend_pipeline
    ):
        # Il manque des données : lancer les workflows nécessaires
        # Vérifier d'abord si un orchestrator existe déjà pour ce domaine (P0-1: Race condition fix)
        existing_orchestrator_stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "audit_orchestrator",
                WorkflowExecution.status.in_(["pending", "running"]),
                WorkflowExecution.input_data["domain"].astext == domain,
                WorkflowExecution.is_valid == True,  # noqa: E712
            )
            .order_by(desc(WorkflowExecution.created_at))
            .limit(1)
        )
        existing_result = await db.execute(existing_orchestrator_stmt)
        existing_orchestrator = existing_result.scalar_one_or_none()
        
        if existing_orchestrator:
            # Un orchestrator existe déjà : retourner celui-ci
            logger.info(
                "Existing orchestrator found, reusing",
                execution_id=str(existing_orchestrator.execution_id),
                domain=domain,
            )
            
            # Construire la liste des étapes depuis input_data
            input_data = existing_orchestrator.input_data or {}
            workflow_steps = []
            step_num = 1
            
            if input_data.get("needs_analysis", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Editorial Analysis",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_competitors", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Competitor Search",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_client_scraping", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Client Site Scraping",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_scraping", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Competitor Scraping",
                        status="pending",
                    )
                )
                step_num += 1
            
            if input_data.get("needs_trend_pipeline", False):
                workflow_steps.append(
                    WorkflowStep(
                        step=step_num,
                        name="Trend Pipeline",
                        status="pending",
                    )
                )
            
            return PendingAuditResponse(
                status="pending",
                execution_id=str(existing_orchestrator.execution_id),
                message="Audit already in progress. Use the execution_id to check status.",
                workflow_steps=workflow_steps,
                data_status=DataStatus(
                    has_profile=not needs_analysis,
                    has_competitors=not needs_competitors,
                    has_client_articles=not needs_client_scraping,
                    has_competitor_articles=not needs_scraping,
                    has_trend_pipeline=not needs_trend_pipeline,
                ),
            )
        
        # Aucun orchestrator existant : créer un nouveau
        orchestrator_execution = await create_workflow_execution(
            db,
            workflow_type="audit_orchestrator",
            input_data={
                "domain": domain,
                "needs_analysis": needs_analysis,
                "needs_competitors": needs_competitors,
                "needs_scraping": needs_scraping,
                "needs_client_scraping": needs_client_scraping,
                "needs_trend_pipeline": needs_trend_pipeline,
            },
            status="running",
        )
        
        # Lancer les workflows manquants en chaîne
        background_tasks.add_task(
            run_missing_workflows_chain,
            domain,
            orchestrator_execution.execution_id,
            needs_analysis=needs_analysis,
            needs_competitors=needs_competitors,
            needs_scraping=needs_scraping,
            needs_client_scraping=needs_client_scraping,
            needs_trend_pipeline=needs_trend_pipeline,
            profile_id=profile.id if profile else None,
        )
        
        # Construire la liste des étapes
        workflow_steps = []
        step_num = 1
        
        if needs_analysis:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Editorial Analysis",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_competitors:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Competitor Search",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_client_scraping:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Client Site Scraping",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_scraping:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Competitor Scraping",
                    status="pending",
                )
            )
            step_num += 1
        
        if needs_trend_pipeline:
            workflow_steps.append(
                WorkflowStep(
                    step=step_num,
                    name="Trend Pipeline",
                    status="pending",
                )
            )
        
        return PendingAuditResponse(
            status="pending",
            execution_id=str(orchestrator_execution.execution_id),
            message="Some data is missing. Launching required workflows...",
            workflow_steps=workflow_steps,
            data_status=DataStatus(
                has_profile=not needs_analysis,
                has_competitors=not needs_competitors,
                has_client_articles=not needs_client_scraping,
                has_competitor_articles=not needs_scraping,
                has_trend_pipeline=not needs_trend_pipeline,
            ),
        )
    
    # ============================================================
    # TOUTES LES DONNÉES SONT DISPONIBLES : Construire la réponse
    # ============================================================
    
    # Récupérer les données complètes depuis la base
    return await build_complete_audit_from_database(
        db,
        domain,
        profile,
        competitors_execution,
        trend_execution,
        include_topics=include_topics,
        include_trending=include_trending,
        include_analyses=include_analyses,
        include_temporal=include_temporal,
        include_opportunities=include_opportunities,
        topics_limit=topics_limit,
        trending_limit=trending_limit,
    )


@router.get(
    "/{domain}/audit/status/{execution_id}",
    response_model=AuditStatusResponse,
    summary="Get audit execution status",
    description="""
    Récupère le statut global de l'audit avec tous les workflows enfants.
    
    Cette route permet de suivre la progression de l'audit en temps réel,
    avec le statut détaillé de chaque étape et une progression globale.
    
    Utilisez cette route pour poller le statut de l'audit après avoir reçu
    un `PendingAuditResponse` avec un `execution_id`.
    
    Note: Si l'audit est déjà complété et que toutes les données sont disponibles,
    utilisez directement GET /{domain}/audit pour obtenir les données complètes.
    """,
    tags=["sites"],
)
async def get_audit_status(
    domain: str,
    execution_id: str,  # Accepter string pour gérer les cas spéciaux
    db: AsyncSession = Depends(get_db),
) -> AuditStatusResponse:
    """
    Récupère le statut global de l'audit.
    
    Args:
        domain: Domaine analysé
        execution_id: ID de l'orchestrator execution (UUID ou "already-completed")
        db: Session de base de données
        
    Returns:
        Statut global de l'audit avec détails de chaque étape
        
    Raises:
        HTTPException: 404 si l'orchestrator n'est pas trouvé, 422 si execution_id invalide
    """
    # Gérer le cas spécial "already-completed"
    if execution_id == "already-completed":
        # Chercher l'orchestrator "completed" le plus récent pour ce domaine
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_type == "audit_orchestrator",
                WorkflowExecution.status == "completed",
                WorkflowExecution.input_data["domain"].astext == domain,
                WorkflowExecution.is_valid == True,  # noqa: E712
                WorkflowExecution.was_success == True,  # noqa: E712
            )
            .order_by(desc(WorkflowExecution.end_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        orchestrator = result.scalar_one_or_none()
        
        if not orchestrator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No completed orchestrator found for domain: {domain}",
            )
        
        execution_id_uuid = orchestrator.execution_id
    else:
        # Valider que c'est un UUID valide
        try:
            execution_id_uuid = UUID(execution_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid execution_id format: {execution_id}. Expected UUID or 'already-completed'",
            )
    
    status_response = await _get_audit_status(db, execution_id_uuid, domain)
    
    # Log pour déboguer le polling continu
    if status_response.overall_status in ("completed", "failed"):
        logger.debug(
            "Audit status requested for completed/failed audit",
            execution_id=str(execution_id_uuid),
            domain=domain,
            overall_status=status_response.overall_status,
            overall_progress=status_response.overall_progress,
        )
    
    return status_response

