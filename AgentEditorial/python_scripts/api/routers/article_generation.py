"""API router for article generation based on CrewOrchestrator."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.article_generation.orchestrator import CrewOrchestrator
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.article_generation import (
    ArticleDetailResponse,
    ArticleGenerationRequest,
    ArticleGenerationResponse,
    ArticleListItemResponse,
    ArticleListResponse,
    ArticleStatus,
    ArticleStatusResponse,
)
from python_scripts.database.crud_generated_articles import (
    create_article,
    delete_article,
    get_article_by_plan_id,
    get_article_images,
    list_articles,
)
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/articles", tags=["Article Generation"])


async def _run_generation_background(
    execution_id: UUID,
    plan_id: UUID,
    request: ArticleGenerationRequest,
    db: AsyncSession,
) -> None:
    """Background task to run the article generation orchestrator."""
    orchestrator = CrewOrchestrator()
    try:
        input_data = request.model_dump()
        # Injecter le plan_id pour que l'orchestrateur réutilise l'article existant
        input_data["plan_id"] = str(plan_id)
        await orchestrator.execute(
            execution_id=execution_id,
            input_data=input_data,
            db_session=db,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "article_generation_background_failed",
            error=str(exc),
        )
        await db.rollback()


@router.post(
    "/generate",
    response_model=ArticleGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_article(
    request: ArticleGenerationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ArticleGenerationResponse:
    """Initialiser et lancer la génération d'un article."""
    from uuid import uuid4

    # 1) Créer immédiatement l'article en base pour disposer d'un plan_id réel
    keywords_list = [k.strip() for k in request.keywords.split(",") if k.strip()]
    article = await create_article(
        db_session=db,
        topic=request.topic,
        keywords=keywords_list,
        tone=request.tone.value,
        target_words=request.target_words,
        language=request.language,
        site_profile_id=request.site_profile_id,
    )
    await db.commit()

    # 2) Lancer l'orchestrateur en tâche de fond sur ce plan_id
    execution_id = uuid4()
    background_tasks.add_task(_run_generation_background, execution_id, article.plan_id, request, db)

    # 3) Retourner le vrai plan_id au client
    return ArticleGenerationResponse(
        plan_id=str(article.plan_id),
        status=ArticleStatus.INITIALIZED,
        topic=request.topic,
        message="Génération d'article initialisée. Suivez le statut via l'endpoint /status.",
    )


@router.get(
    "/{plan_id}/status",
    response_model=ArticleStatusResponse,
)
async def get_article_status(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
) -> ArticleStatusResponse:
    """Récupérer le statut de génération d'un article."""
    try:
        plan_uuid = UUID(plan_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="plan_id invalide",
        ) from exc

    article = await get_article_by_plan_id(db, plan_id=plan_uuid)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article non trouvé",
        )

    return ArticleStatusResponse(
        plan_id=str(article.plan_id),
        status=ArticleStatus(article.status),
        current_step=article.current_step,
        progress_percentage=article.progress_percentage,
        error_message=article.error_message,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


@router.get(
    "/{plan_id}",
    response_model=ArticleDetailResponse,
)
async def get_article_detail(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
) -> ArticleDetailResponse:
    """Obtenir le détail complet d'un article généré."""
    try:
        plan_uuid = UUID(plan_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="plan_id invalide",
        ) from exc

    article = await get_article_by_plan_id(db, plan_id=plan_uuid)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article non trouvé",
        )

    # Important: ne pas accéder à article.images directement (lazy-load sync) en contexte async,
    # utiliser le CRUD dédié pour éviter l'erreur MissingGreenlet.
    db_images = await get_article_images(db, article_id=article.id)
    images = [
        {
            "id": img.id,
            "image_type": img.image_type,
            "local_path": img.local_path,
            "alt_text": img.alt_text,
        }
        for img in db_images
    ]

    return ArticleDetailResponse(
        plan_id=str(article.plan_id),
        status=ArticleStatus(article.status),
        topic=article.topic,
        keywords=article.keywords if isinstance(article.keywords, list) else [],
        plan=article.plan_json,
        content_markdown=article.content_markdown,
        content_html=article.content_html,
        quality_metrics=article.quality_metrics,
        images=images,
        created_at=article.created_at,
        validated_at=article.validated_at,
    )


@router.get(
    "",
    response_model=ArticleListResponse,
)
async def list_generated_articles(
    db: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    """Lister les articles générés."""
    articles = await list_articles(db)
    items: List[ArticleListItemResponse] = [
        ArticleListItemResponse(
            plan_id=str(a.plan_id),
            status=ArticleStatus(a.status),
            topic=a.topic,
            created_at=a.created_at,
            site_profile_id=a.site_profile_id,
        )
        for a in articles
    ]
    return ArticleListResponse(items=items, total=len(items))


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_generated_article(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Supprimer (soft delete) un article généré."""
    try:
        plan_uuid = UUID(plan_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="plan_id invalide",
        ) from exc

    deleted = await delete_article(db, plan_id=plan_uuid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article non trouvé",
        )
    await db.commit()


