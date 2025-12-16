"""Crew definitions for article generation (planning, writing, visualization, review)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from python_scripts.agents.article_generation.tools.web_search import WebSearchClient
from python_scripts.agents.utils.llm_factory import create_llm
from python_scripts.config.settings import settings
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class PlanningCrew:
    """Crew responsible for planning and outlining the article."""

    model_name: str = settings.ollama_model

    async def run(self, topic: str, keywords: list[str]) -> Dict[str, Any]:
        llm = create_llm(self.model_name)
        prompt = (
            "Tu es un stratège éditorial senior.\n"
            "Génère un plan détaillé d'article de blog en français à partir du sujet et des mots-clés.\n"
            f"Sujet: {topic}\n"
            f"Mots-clés: {', '.join(keywords)}\n"
            "Structure la réponse en JSON avec les champs: title, h1, sections (liste avec h2, objectifs, points clés).\n"
        )
        outline = await llm.ainvoke(prompt)
        return {"raw_outline": str(outline)}


@dataclass
class WritingCrew:
    """Crew responsible for writing the full article."""

    model_name: str = settings.ollama_model

    async def run(
        self,
        topic: str,
        tone: str,
        target_words: int,
        language: str,
        outline: str,
    ) -> str:
        llm = create_llm(self.model_name)
        prompt = (
            "Tu es un rédacteur senior.\n"
            "Rédige un article complet en markdown en suivant le plan fourni.\n"
            f"Sujet: {topic}\n"
            f"Ton: {tone}\n"
            f"Longueur cible (mots): {target_words}\n"
            f"Langue: {language}\n"
            f"Plan JSON: {outline}\n"
        )
        content = await llm.ainvoke(prompt)
        return str(content)


@dataclass
class VisualizationCrew:
    """Crew responsible for proposing and generating images with AI validation."""

    def __init__(self) -> None:
        """Initialise le crew avec les nouveaux agents de génération d'image."""
        # Les nouveaux agents (generate_article_image) gèrent tout en interne
        pass

    async def run(
        self,
        article_title: str,
        topic: str,
        base_output_dir: Path,
        site_profile: Optional[Dict[str, Any]] = None,
        article_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Génère une image illustrative pour l'article avec validation IA.

        Args:
            article_title: Titre de l'article
            topic: Sujet de l'article
            base_output_dir: Répertoire de sortie (non utilisé, conservé pour compatibilité)
            site_profile: Profil éditorial du site (optionnel)
            article_id: ID de l'article pour sauvegarde en BDD (optionnel)

        Returns:
            Dictionnaire avec prompt, chemin de l'image, et métadonnées
        """
        if not settings.z_image_enabled:
            logger.warning("z_image_disabled", topic=topic)
            return {"prompt": None, "image_path": None}

        try:
            from python_scripts.agents.agent_image_generation import generate_article_image
            import time

            start_time = time.time()

            # Utiliser le site_profile si fourni, sinon créer un profil minimal
            if not site_profile:
                site_profile = {
                    "editorial_tone": "professional",
                    "target_audience": {},
                    "activity_domains": [],
                }

            # Générer l'image avec les nouveaux agents (validation IA + retry)
            image_result = await generate_article_image(
                site_profile=site_profile,
                article_topic=topic,
                style="corporate_flat",  # Style par défaut
                max_retries=3,
            )

            generation_time = time.time() - start_time

            logger.info(
                "article_image_generated",
                topic=topic,
                image_path=str(image_result.image_path),
                quality_score=image_result.quality_score,
                retry_count=image_result.retry_count,
                final_status=image_result.final_status,
            )

            # Vérifier que l'image a été générée (image_path ne doit pas être vide)
            image_path_str = str(image_result.image_path) if image_result.image_path else None
            if not image_path_str or image_path_str == "." or not image_result.image_path.exists():
                logger.warning(
                    "Image generation returned empty or invalid path",
                    image_path=image_path_str,
                    final_status=image_result.final_status,
                )
                return {"prompt": None, "image_path": None, "error": f"Invalid image path: {image_path_str}"}
            
            return {
                "prompt": image_result.prompt_used,
                "image_path": image_path_str,
                "negative_prompt": image_result.negative_prompt,
                "quality_score": image_result.quality_score,
                "critique_details": image_result.critique_details,
                "retry_count": image_result.retry_count,
                "final_status": image_result.final_status,
                "generation_params": image_result.generation_params,
                "generation_time_seconds": generation_time,
            }

        except Exception as e:
            logger.error(
                "image_generation_failed",
                error=str(e),
                topic=topic,
            )
            return {"prompt": None, "image_path": None, "error": str(e)}


@dataclass
class ReviewCrew:
    """Crew responsible for reviewing and scoring the article."""

    model_name: str = settings.ollama_model

    async def run(self, content_markdown: str) -> Dict[str, Any]:
        llm = create_llm(self.model_name)
        prompt = (
            "Tu es un rédacteur en chef.\n"
            "Évalue la qualité de l'article suivant en termes de clarté, structure, valeur et lisibilité.\n"
            "Retourne un JSON avec les champs: global_score (0-100), readability_score (0-100), "
            "seo_score (0-100), strengths (liste), improvements (liste).\n"
            f"Article markdown:\n{content_markdown}\n"
        )
        review = await llm.ainvoke(prompt)
        return {"raw_review": str(review)}


@dataclass
class ResearchCrew:
    """Crew responsible for collecting external references and statistics."""

    web_search: WebSearchClient

    async def run(self, topic: str, keywords: list[str]) -> Dict[str, Any]:
        query = f"{topic} {' '.join(keywords)} statistiques étude"
        results = self.web_search.search(query, max_results=5)
        return {"query": query, "results": results}


