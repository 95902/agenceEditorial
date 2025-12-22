"""API router for article training and learning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.article_training import (
    AnalysisResponse,
    ArticleFeedbackRequest,
    ArticleFeedbackResponse,
    PatternResponse,
    PromptImprovementRequest,
    PromptImprovementResponse,
    TrainingStatsResponse,
)
from python_scripts.database.crud_article_learning import (
    create_learning_data,
    get_learning_data_by_article_id,
    get_learning_stats,
    list_learning_data,
    update_learned_patterns,
)
from python_scripts.database.crud_generated_articles import get_article_by_plan_id
from python_scripts.agents.article_generation.learning_service import (
    ArticleLearningService,
)
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/articles/training", tags=["Article Training"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze articles for learning patterns",
    description="""
    Analyse les articles générés récents pour identifier les patterns de succès.
    Identifie les combinaisons topic/keywords/tone qui fonctionnent bien.
    """,
)
async def analyze_articles(
    site_profile_id: Optional[int] = Query(None, description="Filter by site profile ID"),
    min_global_score: float = Query(80.0, ge=0.0, le=100.0, description="Minimum global score"),
    limit: int = Query(100, ge=1, le=500, description="Maximum articles to analyze"),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Analyse les articles pour identifier les patterns d'apprentissage."""
    try:
        service = ArticleLearningService(db_session=db)
        analysis_result = await service.analyze_articles(
            site_profile_id=site_profile_id,
            min_global_score=min_global_score,
            limit=limit,
        )

        patterns = [
            PatternResponse(**pattern) for pattern in analysis_result["patterns"]
        ]

        return AnalysisResponse(
            patterns=patterns,
            total_analyzed=analysis_result["total_analyzed"],
            patterns_found=analysis_result["patterns_found"],
            analysis_date=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error("Failed to analyze articles", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        ) from e


@router.post(
    "/feedback",
    response_model=ArticleFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit manual feedback on an article",
    description="""
    Permet d'ajouter un feedback manuel sur un article généré.
    Ce feedback sera utilisé pour améliorer les générations futures.
    """,
)
async def submit_feedback(
    request: ArticleFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> ArticleFeedbackResponse:
    """Soumet un feedback manuel sur un article."""
    try:
        from uuid import UUID

        # Récupérer l'article
        try:
            plan_id = UUID(request.plan_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan_id: {request.plan_id}",
            ) from e

        article = await get_article_by_plan_id(db, plan_id=plan_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article with plan_id {request.plan_id} not found",
            )

        # Vérifier si des données d'apprentissage existent déjà
        existing = await get_learning_data_by_article_id(db, article_id=article.id)

        # Extraire les quality_scores de l'article
        quality_scores = article.quality_metrics or {}
        if request.rating:
            # Ajouter le rating manuel aux quality_scores
            if "manual_feedback" not in quality_scores:
                quality_scores["manual_feedback"] = {}
            quality_scores["manual_feedback"]["rating"] = request.rating
            quality_scores["manual_feedback"]["comments"] = request.comments
            quality_scores["manual_feedback"]["submitted_at"] = datetime.now(
                timezone.utc
            ).isoformat()

        # Préparer les paramètres de génération
        generation_params = {
            "topic": article.topic,
            "keywords": article.keywords if isinstance(article.keywords, list) else [],
            "tone": article.tone or "professional",
            "target_words": article.target_words,
            "language": article.language,
        }

        # Construire le prompt utilisé (approximation depuis les paramètres)
        prompt_used = f"Topic: {article.topic}\nKeywords: {', '.join(generation_params['keywords'])}\nTone: {generation_params['tone']}"

        if existing:
            # Mettre à jour les données existantes
            existing.feedback_type = "manual"
            existing.is_positive = request.is_positive
            existing.quality_scores = quality_scores
            await db.flush()
            learning_data_id = existing.id
        else:
            # Créer de nouvelles données
            learning_data = await create_learning_data(
                db_session=db,
                article_id=article.id,
                generation_params=generation_params,
                prompt_used=prompt_used,
                quality_scores=quality_scores,
                feedback_type="manual",
                is_positive=request.is_positive,
                site_profile_id=article.site_profile_id,
            )
            learning_data_id = learning_data.id

        await db.commit()

        logger.info(
            "Manual feedback submitted",
            plan_id=request.plan_id,
            rating=request.rating,
            is_positive=request.is_positive,
        )

        return ArticleFeedbackResponse(
            success=True,
            learning_data_id=learning_data_id,
            message="Feedback submitted successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit feedback", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}",
        ) from e


@router.get(
    "/patterns",
    response_model=List[PatternResponse],
    status_code=status.HTTP_200_OK,
    summary="Get learned patterns",
    description="""
    Retourne les patterns appris à partir de l'analyse des articles.
    Peut être filtré par site_profile_id, min_score, etc.
    """,
)
async def get_patterns(
    site_profile_id: Optional[int] = Query(None, description="Filter by site profile ID"),
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0, description="Minimum global score"),
    limit: int = Query(50, ge=1, le=200, description="Maximum patterns to return"),
    db: AsyncSession = Depends(get_db),
) -> List[PatternResponse]:
    """Récupère les patterns appris."""
    try:
        service = ArticleLearningService(db_session=db)
        analysis_result = await service.analyze_articles(
            site_profile_id=site_profile_id,
            min_global_score=min_score or 80.0,
            limit=limit * 2,  # Analyser plus d'articles pour avoir plus de patterns
        )

        patterns = [
            PatternResponse(**pattern) for pattern in analysis_result["patterns"]
        ]

        return patterns[:limit]
    except Exception as e:
        logger.error("Failed to get patterns", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get patterns: {str(e)}",
        ) from e


@router.post(
    "/improve-prompts",
    response_model=PromptImprovementResponse,
    status_code=status.HTTP_200_OK,
    summary="Improve prompts based on learned patterns",
    description="""
    Lance l'amélioration des prompts basée sur les patterns appris.
    Retourne des suggestions d'amélioration pour les paramètres de génération.
    """,
)
async def improve_prompts(
    request: PromptImprovementRequest,
    db: AsyncSession = Depends(get_db),
) -> PromptImprovementResponse:
    """Améliore les prompts basés sur les patterns appris."""
    try:
        service = ArticleLearningService(db_session=db)
        improvement = await service.improve_prompt(
            topic=request.topic,
            keywords=request.keywords,
            tone=request.tone,
            target_words=request.target_words,
            site_profile_id=request.site_profile_id,
        )

        if not improvement:
            # Aucune amélioration disponible
            return PromptImprovementResponse(
                original_prompt=service._build_base_prompt(
                    request.topic, request.keywords, request.tone, request.target_words
                ),
                improved_prompt=service._build_base_prompt(
                    request.topic, request.keywords, request.tone, request.target_words
                ),
                improvements=[],
                confidence=0.0,
                patterns_used=[],
            )

        # Extraire les types de patterns utilisés
        analysis = await service.analyze_articles(
            site_profile_id=request.site_profile_id,
            min_global_score=80.0,
            limit=50,
        )
        patterns_used = [p["pattern_type"] for p in analysis.get("patterns", [])]

        return PromptImprovementResponse(
            original_prompt=improvement.original_prompt,
            improved_prompt=improvement.improved_prompt,
            improvements=improvement.improvements,
            confidence=improvement.confidence,
            patterns_used=patterns_used,
        )
    except Exception as e:
        logger.error("Failed to improve prompts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to improve prompts: {str(e)}",
        ) from e


@router.get(
    "/stats",
    response_model=TrainingStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get training statistics",
    description="""
    Retourne les statistiques sur l'apprentissage :
    nombre d'articles analysés, patterns identifiés, etc.
    """,
)
async def get_training_stats(
    site_profile_id: Optional[int] = Query(None, description="Filter by site profile ID"),
    db: AsyncSession = Depends(get_db),
) -> TrainingStatsResponse:
    """Récupère les statistiques d'apprentissage."""
    try:
        stats = await get_learning_stats(db_session=db, site_profile_id=site_profile_id)

        return TrainingStatsResponse(**stats)
    except Exception as e:
        logger.error("Failed to get training stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get training stats: {str(e)}",
        ) from e



