"""CrewOrchestrator for end-to-end article generation pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.article_generation.crew import (
    PlanningCrew,
    ResearchCrew,
    ReviewCrew,
    VisualizationCrew,
    WritingCrew,
)
from python_scripts.agents.article_generation.tools.web_search import WebSearchClient
from python_scripts.agents.base_agent import BaseAgent
from python_scripts.config.settings import settings
from python_scripts.database.crud_generated_articles import (
    get_article_by_plan_id,
    update_article_content,
    update_article_plan,
    update_article_status,
)
from python_scripts.utils.logging import get_logger


logger = get_logger(__name__)


class CrewOrchestrator(BaseAgent):
    """High-level orchestrator for multi-phase article generation."""

    def __init__(self) -> None:
        super().__init__("article_generation")
        self._planning_crew = PlanningCrew()
        self._research_crew = ResearchCrew(web_search=WebSearchClient())
        self._writing_crew = WritingCrew()
        self._visualization_crew = VisualizationCrew()
        self._review_crew = ReviewCrew()

    async def execute(
        self,
        execution_id: UUID,
        input_data: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute the end-to-end generation pipeline for an article."""
        self.set_execution_context(execution_id)
        db: AsyncSession = kwargs["db_session"]

        # On attend désormais un plan_id existant (article déjà créé par l'API)
        plan_id_str: Optional[str] = input_data.get("plan_id")
        if not plan_id_str:
            raise ValueError("Missing plan_id in input_data for CrewOrchestrator")

        try:
            plan_id = UUID(plan_id_str)
        except ValueError as exc:  # noqa: BLE001
            raise ValueError(f"Invalid plan_id provided to CrewOrchestrator: {plan_id_str}") from exc

        article = await get_article_by_plan_id(db, plan_id=plan_id)
        if not article:
            raise ValueError(f"GeneratedArticle with plan_id={plan_id} not found")

        topic: str = input_data["topic"]
        keywords_str: str = input_data.get("keywords", "")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        tone: str = input_data.get("tone", "professional")
        target_words: int = int(input_data.get("target_words", 2000))
        language: str = input_data.get("language", "fr")
        site_profile_id: Optional[int] = input_data.get("site_profile_id")
        generate_images: bool = bool(input_data.get("generate_images", True))

        # 1. Planning
        await update_article_status(
            db_session=db,
            plan_id=article.plan_id,
            status="planning",
            current_step="planning",
            progress_percentage=10,
        )
        await db.commit()
        self.log_step_start("planning", "Running planning crew")
        planning_result = await self._planning_crew.run(topic=topic, keywords=keywords)
        await update_article_plan(
            db_session=db,
            plan_id=article.plan_id,
            plan_json=planning_result,
        )
        await update_article_status(
            db_session=db,
            plan_id=article.plan_id,
            status="planning",
            current_step="planning_completed",
            progress_percentage=25,
        )
        await db.commit()
        self.log_step_complete("planning", "Planning completed")

        # 3. Research (facultatif mais utile pour futur enrichissement)
        self.log_step_start("research", "Running research crew")
        research_result = await self._research_crew.run(topic=topic, keywords=keywords)
        await update_article_status(
            db_session=db,
            plan_id=article.plan_id,
            status="researching",
            current_step="research_completed",
            progress_percentage=35,
        )
        await db.commit()
        self.log_step_complete("research", "Research completed")

        # 4. Writing
        self.log_step_start("writing", "Running writing crew")
        outline_str = json.dumps(planning_result, ensure_ascii=False)
        content_markdown = await self._writing_crew.run(
            topic=topic,
            tone=tone,
            target_words=target_words,
            language=language,
            outline=outline_str,
        )
        await update_article_content(
            db_session=db,
            plan_id=article.plan_id,
            content_markdown=content_markdown,
        )
        await update_article_status(
            db_session=db,
            plan_id=article.plan_id,
            status="writing",
            current_step="writing_completed",
            progress_percentage=65,
        )
        await db.commit()
        self.log_step_complete("writing", "Writing completed")

        # 5. Visualization (images)
        image_info: Optional[Dict[str, Any]] = None
        if generate_images:
            self.log_step_start("visualization", "Running visualization crew")
            base_output_dir = Path(settings.article_images_dir)
            
            # Récupérer le site_profile si site_profile_id est disponible
            site_profile_for_image = None
            if site_profile_id:
                from python_scripts.database.crud_profiles import get_site_profile_by_id
                site_profile_obj = await get_site_profile_by_id(db, profile_id=site_profile_id)
                if site_profile_obj:
                    # Convertir le site_profile en dict pour generate_article_image
                    site_profile_for_image = {
                        "editorial_tone": site_profile_obj.editorial_tone or "professional",
                        "target_audience": site_profile_obj.target_audience or {},
                        "activity_domains": site_profile_obj.activity_domains or [],
                        "keywords": site_profile_obj.keywords or {},
                        "style_features": site_profile_obj.style_features or {},
                    }
            
            image_info = await self._visualization_crew.run(
                article_title=topic,
                topic=topic,
                base_output_dir=base_output_dir,
                site_profile=site_profile_for_image,
                article_id=article.id,
            )
            
            # Sauvegarder l'image dans la base de données si génération réussie
            # Debug: logger pour comprendre ce qui se passe
            logger.info(
                "Visualization crew returned",
                image_path=image_info.get("image_path"),
                has_error=bool(image_info.get("error")),
                keys=list(image_info.keys()),
            )
            
            if image_info.get("image_path") and not image_info.get("error"):
                try:
                    from python_scripts.database.crud_images import save_image_generation
                    
                    saved_image = await save_image_generation(
                        db=db,
                        site_profile_id=site_profile_id,
                        article_topic=topic,
                        prompt_used=image_info.get("prompt", ""),
                        output_path=image_info.get("image_path", ""),
                        generation_params=image_info.get("generation_params", {}),
                        quality_score=image_info.get("quality_score"),
                        negative_prompt=image_info.get("negative_prompt"),
                        critique_details=image_info.get("critique_details"),
                        retry_count=image_info.get("retry_count", 0),
                        final_status=image_info.get("final_status", "success"),
                        generation_time_seconds=image_info.get("generation_time_seconds"),
                        article_id=article.id,
                    )
                    await db.flush()  # Flush pour avoir l'ID de l'image
                    logger.info(
                        "Image generation saved to database",
                        image_id=saved_image.id,
                        article_id=article.id,
                    )
                except Exception as db_error:
                    logger.error(
                        "Failed to save image generation to database",
                        error=str(db_error),
                        article_id=article.id,
                    )
                    # Continuer même si la sauvegarde échoue
            
            await update_article_status(
                db_session=db,
                plan_id=article.plan_id,
                status="generating_images",
                current_step="visualization_completed",
                progress_percentage=80,
            )
            await db.commit()
            self.log_step_complete("visualization", "Visualization completed", details=image_info)

        # 6. Review
        self.log_step_start("review", "Running review crew")
        review_result = await self._review_crew.run(content_markdown=content_markdown)
        await update_article_content(
            db_session=db,
            plan_id=article.plan_id,
            quality_metrics={"review": review_result, "research": research_result},
        )
        await update_article_status(
            db_session=db,
            plan_id=article.plan_id,
            status="validated",
            current_step="completed",
            progress_percentage=100,
        )
        await db.commit()
        self.log_step_complete("review", "Review completed")

        return {
            "plan_id": str(article.plan_id),
            "status": "validated",
            "topic": topic,
            "generate_images": generate_images,
        }


