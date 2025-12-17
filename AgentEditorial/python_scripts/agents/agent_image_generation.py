"""Agent CrewAI pour génération d'images avec validation qualité."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from python_scripts.config.settings import settings
from python_scripts.image_generation import CritiqueResult, ImageCritic

# Note: Les imports CrewAI sont commentés car on utilise une approche directe plus fiable
# from crewai import Agent, Crew, Process, Task
# from langchain_ollama import ChatOllama
# from python_scripts.agents.tools.image_critic_tool import ImageCriticTool
# from python_scripts.agents.tools.image_generator_tool import ImageGeneratorTool


@dataclass
class ImageGenerationResult:
    """Résultat de la génération d'image avec validation."""

    image_path: Path
    prompt_used: str
    negative_prompt: str
    generation_params: dict[str, Any]
    quality_score: Optional[float] = None
    critique_details: Optional[dict[str, Any]] = None
    retry_count: int = 0
    final_status: str = "success"  # "success", "failed", "retry_exhausted"


# Fonction commentée car on n'utilise plus CrewAI pour l'instant
# def _create_crewai_llm(model_name: str = "llama3:8b") -> ChatOllama:
#     """
#     Crée un LLM compatible CrewAI depuis Ollama.
#     """
#     from langchain_ollama import ChatOllama
#     return ChatOllama(
#         model=model_name,
#         base_url=settings.ollama_base_url,
#         temperature=0.7,
#     )


async def generate_article_image(
    site_profile: dict[str, Any],
    article_topic: str,
    style: str = "corporate_flat",
    max_retries: int = 3,
    # Nouveaux paramètres pour utiliser AdvancedPromptBuilder
    article_title: Optional[str] = None,
    content_summary: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> ImageGenerationResult:
    """
    Génère une image avec validation et retry automatique.
    
    NOUVELLE LOGIQUE : Génère 1 image à la fois jusqu'à avoir 3 images valides (max 5 total).

    Args:
        site_profile: Profil éditorial du site
        article_topic: Sujet de l'article
        style: Style d'image (corporate_flat, corporate_3d, tech_isometric, etc.)
        max_retries: Nombre maximum de tentatives (déprécié, utilise max_total_images=5)
        article_title: Titre de l'article (optionnel, pour utiliser AdvancedPromptBuilder)
        content_summary: Résumé du contenu (optionnel, pour utiliser AdvancedPromptBuilder)
        keywords: Mots-clés de l'article (optionnel, pour utiliser AdvancedPromptBuilder)

    Returns:
        ImageGenerationResult avec détails de la génération (meilleure image parmi les 3 valides)
    """
    from python_scripts.image_generation import ImageGenerator
    from python_scripts.image_generation.image_critic import ImageCritic
    from python_scripts.image_generation.image_generator import GenerationResult
    
    # Configuration
    max_total_images = 5  # Générer exactement 5 images
    keep_best_n = 3  # Garder les 3 meilleures images
    
    generator = ImageGenerator.get_instance()
    critic = ImageCritic()
    
    # Déterminer le style depuis le profil si non fourni
    if style == "corporate_flat":
        editorial_tone = site_profile.get("editorial_tone", "professional")
        style_mapping = {
            "professional": "corporate_flat",
            "technical": "tech_isometric",
            "innovative": "tech_gradient",
            "modern": "modern_minimal",
            "corporate": "corporate_3d",
        }
        style = style_mapping.get(editorial_tone.lower(), "corporate_flat")
    
    # Construire le prompt avec AdvancedPromptBuilder si infos disponibles
    prompt_to_use = article_topic
    use_advanced_prompt = (
        site_profile is not None
        and (article_title or content_summary or keywords or article_topic)
    )
    
    if use_advanced_prompt:
        from python_scripts.image_generation.prompt_builder_v3 import AdvancedPromptBuilder, ImageFormat
        advanced_builder = AdvancedPromptBuilder()
        
        # Extraire des keywords depuis le topic si non fournis
        extracted_keywords = keywords or []
        if not extracted_keywords and article_topic:
            extracted_keywords = [
                word.strip() 
                for word in article_topic.split() 
                if len(word.strip()) >= 3 and word.strip().isalnum()
            ][:5]
        
        try:
            advanced_result = await advanced_builder.build_from_article(
                title=article_title or article_topic,
                content_summary=content_summary or "",
                keywords=extracted_keywords,
                site_profile=site_profile,
                format=ImageFormat.SOCIAL_SQUARE,  # 1:1 pour articles
            )
            prompt_to_use = advanced_result.prompt
            logger.info(
                "Using AdvancedPromptBuilder for batch generation",
                domain=advanced_result.metadata.get("domain"),
                style=advanced_result.metadata.get("style"),
            )
        except Exception as e:
            logger.warning(
                "AdvancedPromptBuilder failed, using basic prompt",
                error=str(e),
            )
    
    # Stocker TOUTES les images générées avec leur critique (valides ou non)
    all_images: list[tuple[GenerationResult, CritiqueResult]] = []
    total_generated = 0
    
    logger.info(
        "Starting batch image generation",
        max_total=max_total_images,
        keep_best=keep_best_n,
        topic=article_topic,
    )
    
    # Générer exactement 5 images
    while total_generated < max_total_images:
        try:
            total_generated += 1
            
            logger.info(
                "Generating image",
                image_number=total_generated,
                total=max_total_images,
            )
            
            # Générer UNE image
            # Si le prompt a été construit avec AdvancedPromptBuilder, utiliser skip_prompt_building
            generation_result = await generator.generate(
                prompt=prompt_to_use,
                negative_prompt=None,
                style=style,
                aspect_ratio="1:1",
                skip_prompt_building=use_advanced_prompt,  # Utiliser le prompt enrichi tel quel
            )
            
            if not generation_result.success:
                logger.warning(
                    "Image generation failed, continuing",
                    image_number=total_generated,
                    error=generation_result.error,
                )
                # Si une image a été générée mais a échoué, la supprimer
                if generation_result.image_path and generation_result.image_path.exists():
                    try:
                        generation_result.image_path.unlink()
                        logger.info("Failed image deleted", image_path=str(generation_result.image_path))
                    except Exception as delete_error:
                        logger.warning("Failed to delete failed image", error=str(delete_error))
                continue
            
            # Critiquer l'image (même si elle ne passe pas le seuil, on la garde pour le tri)
            try:
                critique_result = await critic.evaluate(generation_result.image_path)
            except Exception as critique_error:
                logger.warning(
                    "Image critique failed, continuing",
                    error=str(critique_error),
                    image_path=str(generation_result.image_path),
                )
                # Créer un résultat par défaut avec score 0
                from python_scripts.image_generation.image_critic import CritiqueResult, CritiqueScores
                critique_result = CritiqueResult(
                    scores=CritiqueScores(
                        sharpness=0,
                        composition=0,
                        no_text=0,
                        coherence=0,
                        professionalism=0,
                    ),
                    score_total=0,
                    verdict="REGENERER",
                    problems=["Critique failed"],
                    suggestions=[],
                    has_unwanted_text=False,
                )
            
            # Ajouter l'image à la liste (même si elle ne passe pas le seuil)
            all_images.append((generation_result, critique_result))
            logger.info(
                "Image generated and critiqued",
                image_number=total_generated,
                score_total=critique_result.score_total,
                verdict=critique_result.verdict,
            )
            
        except Exception as e:
            import traceback
            logger.error(
                "Error generating image",
                error=str(e),
                attempt=attempt,
                total_generated=total_generated,
                traceback=traceback.format_exc(),
            )
            attempt += 1
            continue
    
    # Résultat final
    if not all_images:
        # Aucune image générée
        logger.warning(
            "No images generated",
            total_generated=total_generated,
            max_total=max_total_images,
        )
        return ImageGenerationResult(
            image_path=Path(""),
            prompt_used=prompt_to_use,
            negative_prompt="",
            generation_params={},
            quality_score=0.0,
            critique_details={
                "scores": {"sharpness": 0, "composition": 0, "no_text": 0, "coherence": 0, "professionalism": 0},
                "verdict": "REGENERER",
                "problems": ["No images generated"],
                "suggestions": [],
                "has_unwanted_text": False,
            },
            retry_count=total_generated,
            final_status="failed",
        )
    
    # Trier toutes les images par score (meilleures en premier)
    all_images_sorted = sorted(all_images, key=lambda x: x[1].score_total, reverse=True)
    
    # Garder les N meilleures images
    best_images = all_images_sorted[:keep_best_n]
    
    # Supprimer les images qui ne sont pas dans le top N
    images_to_delete = all_images_sorted[keep_best_n:]
    for img_result, critique_result in images_to_delete:
        try:
            if img_result.image_path and img_result.image_path.exists():
                img_result.image_path.unlink()
                logger.info(
                    "Image deleted (not in top N)",
                    image_path=str(img_result.image_path),
                    score=critique_result.score_total,
                    rank=all_images_sorted.index((img_result, critique_result)) + 1,
                )
        except Exception as delete_error:
            logger.warning(
                "Failed to delete image",
                image_path=str(img_result.image_path) if img_result.image_path else None,
                error=str(delete_error),
            )
    
    # Sélectionner la meilleure image parmi les N gardées (pour le retour)
    best_image, best_critique = best_images[0]
    
    logger.info(
        "Top images selected",
        total_generated=total_generated,
        kept=len(best_images),
        best_score=best_critique.score_total,
        scores=[critique.score_total for _, critique in best_images],
    )
    
    # Préparer les métadonnées
    if best_image.provider == "ideogram":
        generation_params = {
            "provider": "ideogram",
            "model": best_image.metadata.get("model", "V_2"),
            "style_type": best_image.metadata.get("style_type", "DESIGN"),
            "aspect_ratio": best_image.metadata.get("aspect_ratio", "1:1"),
            "resolution": best_image.metadata.get("resolution", "1024x1024"),
            "ideogram_url": best_image.metadata.get("ideogram_url"),
            "magic_prompt": best_image.metadata.get("magic_prompt"),
            "total_generated": total_generated,
            "kept_images_count": len(best_images),
            "all_images_scores": [critique.score_total for _, critique in all_images_sorted],
        }
    else:
        generation_params = {
            "provider": "local",
            "width": best_image.metadata.get("width", 768),
            "height": best_image.metadata.get("height", 768),
            "steps": best_image.metadata.get("steps", 12),
            "guidance_scale": best_image.metadata.get("guidance_scale", 7.5),
            "total_generated": total_generated,
            "kept_images_count": len(best_images),
            "all_images_scores": [critique.score_total for _, critique in all_images_sorted],
        }
    
    logger.info(
        "Image generation completed",
        total_generated=total_generated,
        kept_images=len(best_images),
        best_score=best_critique.score_total,
        final_status="success" if len(best_images) >= keep_best_n else "partial",
    )
    
    return ImageGenerationResult(
        image_path=best_image.image_path,
        prompt_used=best_image.prompt_used,
        negative_prompt=best_image.negative_prompt or "",
        generation_params=generation_params,
        quality_score=float(best_critique.score_total),
        critique_details={
            "scores": {
                "sharpness": best_critique.scores.sharpness,
                "composition": best_critique.scores.composition,
                "no_text": best_critique.scores.no_text,
                "coherence": best_critique.scores.coherence,
                "professionalism": best_critique.scores.professionalism,
            },
            "verdict": best_critique.verdict,
            "problems": best_critique.problems,
            "suggestions": best_critique.suggestions,
            "has_unwanted_text": best_critique.has_unwanted_text,
        },
        retry_count=total_generated,
        final_status="success" if len(best_images) >= keep_best_n else "partial",
    )

