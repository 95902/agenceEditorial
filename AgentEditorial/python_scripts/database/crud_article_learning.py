"""CRUD operations for article learning data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Select, and_, desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.database.models import ArticleLearningData
from python_scripts.utils.json_utils import make_json_serializable
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)


async def create_learning_data(
    db_session: AsyncSession,
    *,
    article_id: int,
    generation_params: Dict[str, Any],
    prompt_used: str,
    quality_scores: Dict[str, Any],
    feedback_type: str = "automatic",
    is_positive: bool = True,
    site_profile_id: Optional[int] = None,
    learned_patterns: Optional[Dict[str, Any]] = None,
) -> ArticleLearningData:
    """
    Crée une entrée de données d'apprentissage.

    Args:
        db_session: Session de base de données
        article_id: ID de l'article généré
        generation_params: Paramètres de génération (topic, keywords, tone, etc.)
        prompt_used: Prompt exact utilisé
        quality_scores: Scores de qualité (global_score, readability_score, seo_score)
        feedback_type: Type de feedback ("automatic" ou "manual")
        is_positive: Si c'est un bon exemple
        site_profile_id: ID du profil de site (optionnel)
        learned_patterns: Patterns identifiés (optionnel)

    Returns:
        ArticleLearningData créé
    """
    try:
        learning_data = ArticleLearningData(
            article_id=article_id,
            site_profile_id=site_profile_id,
            generation_params=make_json_serializable(generation_params),
            prompt_used=prompt_used,
            quality_scores=make_json_serializable(quality_scores),
            feedback_type=feedback_type,
            is_positive=is_positive,
            learned_patterns=make_json_serializable(learned_patterns) if learned_patterns else None,
        )
        db_session.add(learning_data)
        await db_session.flush()

        logger.info(
            "article_learning_data_created",
            learning_data_id=learning_data.id,
            article_id=article_id,
            feedback_type=feedback_type,
            is_positive=is_positive,
        )

        return learning_data
    except SQLAlchemyError as e:
        logger.error(
            "failed_to_create_learning_data",
            article_id=article_id,
            error=str(e),
        )
        await db_session.rollback()
        raise


async def get_learning_data_by_article_id(
    db_session: AsyncSession,
    article_id: int,
) -> Optional[ArticleLearningData]:
    """Récupère les données d'apprentissage pour un article."""
    try:
        stmt = select(ArticleLearningData).where(
            ArticleLearningData.article_id == article_id
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(
            "failed_to_get_learning_data",
            article_id=article_id,
            error=str(e),
        )
        raise


async def list_learning_data(
    db_session: AsyncSession,
    *,
    site_profile_id: Optional[int] = None,
    is_positive: Optional[bool] = None,
    feedback_type: Optional[str] = None,
    min_global_score: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[ArticleLearningData]:
    """
    Liste les données d'apprentissage avec filtres.

    Args:
        db_session: Session de base de données
        site_profile_id: Filtrer par profil de site
        is_positive: Filtrer par type (positif/négatif)
        feedback_type: Filtrer par type de feedback
        min_global_score: Score global minimum
        limit: Nombre maximum de résultats
        offset: Offset pour la pagination

    Returns:
        Liste des données d'apprentissage
    """
    try:
        stmt = select(ArticleLearningData)

        conditions = []
        if site_profile_id is not None:
            conditions.append(ArticleLearningData.site_profile_id == site_profile_id)
        if is_positive is not None:
            conditions.append(ArticleLearningData.is_positive == is_positive)
        if feedback_type is not None:
            conditions.append(ArticleLearningData.feedback_type == feedback_type)
        if min_global_score is not None:
            # Filtrer par score global dans quality_scores JSONB
            conditions.append(
                ArticleLearningData.quality_scores["review"]["raw_review"].astext.contains(
                    f'"global_score": {min_global_score}'
                )
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(ArticleLearningData.created_at)).limit(limit).offset(offset)

        result = await db_session.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as e:
        logger.error("failed_to_list_learning_data", error=str(e))
        raise


async def get_positive_examples(
    db_session: AsyncSession,
    *,
    site_profile_id: Optional[int] = None,
    min_global_score: float = 80.0,
    limit: int = 50,
) -> List[ArticleLearningData]:
    """
    Récupère les exemples positifs (bons articles) pour l'apprentissage.

    Args:
        db_session: Session de base de données
        site_profile_id: Filtrer par profil de site
        min_global_score: Score global minimum
        limit: Nombre maximum de résultats

    Returns:
        Liste des exemples positifs
    """
    return await list_learning_data(
        db_session,
        site_profile_id=site_profile_id,
        is_positive=True,
        min_global_score=min_global_score,
        limit=limit,
    )


async def update_learned_patterns(
    db_session: AsyncSession,
    learning_data_id: int,
    learned_patterns: Dict[str, Any],
) -> Optional[ArticleLearningData]:
    """Met à jour les patterns appris pour une entrée d'apprentissage."""
    try:
        stmt = select(ArticleLearningData).where(ArticleLearningData.id == learning_data_id)
        result = await db_session.execute(stmt)
        learning_data = result.scalar_one_or_none()

        if not learning_data:
            return None

        learning_data.learned_patterns = make_json_serializable(learned_patterns)
        await db_session.flush()

        logger.info(
            "learned_patterns_updated",
            learning_data_id=learning_data_id,
        )

        return learning_data
    except SQLAlchemyError as e:
        logger.error(
            "failed_to_update_learned_patterns",
            learning_data_id=learning_data_id,
            error=str(e),
        )
        await db_session.rollback()
        raise


async def get_learning_stats(
    db_session: AsyncSession,
    *,
    site_profile_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Récupère les statistiques d'apprentissage.

    Returns:
        Dictionnaire avec les statistiques
    """
    try:
        stmt = select(ArticleLearningData)
        if site_profile_id is not None:
            stmt = stmt.where(ArticleLearningData.site_profile_id == site_profile_id)

        result = await db_session.execute(stmt)
        all_data = list(result.scalars().all())

        total = len(all_data)
        positive = sum(1 for d in all_data if d.is_positive)
        negative = total - positive
        automatic = sum(1 for d in all_data if d.feedback_type == "automatic")
        manual = total - automatic
        with_patterns = sum(1 for d in all_data if d.learned_patterns is not None)

        # Calculer le score moyen (si disponible dans quality_scores)
        scores = []
        for data in all_data:
            if isinstance(data.quality_scores, dict):
                review = data.quality_scores.get("review", {})
                if isinstance(review, dict):
                    raw_review = review.get("raw_review", "")
                    # Essayer d'extraire global_score du texte JSON
                    try:
                        import json
                        import re
                        # Chercher "global_score": X dans le texte
                        match = re.search(r'"global_score":\s*(\d+)', raw_review)
                        if match:
                            scores.append(float(match.group(1)))
                    except Exception:
                        pass

        avg_score = sum(scores) / len(scores) if scores else None

        return {
            "total_articles": total,
            "positive_examples": positive,
            "negative_examples": negative,
            "automatic_feedback": automatic,
            "manual_feedback": manual,
            "with_learned_patterns": with_patterns,
            "average_global_score": round(avg_score, 2) if avg_score else None,
        }
    except SQLAlchemyError as e:
        logger.error("failed_to_get_learning_stats", error=str(e))
        raise

