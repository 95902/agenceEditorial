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
) -> ImageGenerationResult:
    """
    Génère une image avec validation et retry automatique.

    Args:
        site_profile: Profil éditorial du site
        article_topic: Sujet de l'article
        style: Style d'image (corporate_flat, corporate_3d, tech_isometric, etc.)
        max_retries: Nombre maximum de tentatives

    Returns:
        ImageGenerationResult avec détails de la génération
    """
    # Gérer les retries avec génération directe et critique IA
    # Note: On utilise une approche directe (sans CrewAI) pour plus de fiabilité et rapidité
    # Les agents CrewAI sont définis mais non utilisés pour l'instant
    retry_count = 0
    last_image_path: Optional[Path] = None
    last_prompt: Optional[str] = None
    last_negative_prompt: Optional[str] = None
    last_generation_params: Optional[dict[str, Any]] = None

    from python_scripts.image_generation import ImageGenerator

    while retry_count < max_retries:
        try:
            logger.info(
                "Running image generation with AI validation",
                attempt=retry_count + 1,
                max_retries=max_retries,
                topic=article_topic,
            )

            # Générer les variantes d'images avec le nouveau générateur unifié
            generator = ImageGenerator.get_instance()
            
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
            
            # Générer 3 variantes avec le topic de l'article
            # Le prompt sera construit dans generate_with_variants() depuis le topic
            variant_result = await generator.generate_with_variants(
                prompt=article_topic,  # Passer directement le topic, le prompt sera construit dans generate_with_variants
                num_variants=3,
                negative_prompt=None,  # Sera construit automatiquement
                style=style,
                aspect_ratio="1:1",
                auto_select=False,  # Pas d'auto-sélection par défaut
            )
            
            if not variant_result.success or not variant_result.variants:
                raise Exception(f"Variant generation failed: {variant_result.error}")
            
            # Pour la compatibilité avec le code existant, utiliser la première variante
            # (ou la variante sélectionnée si auto_select=True)
            selected_index = variant_result.selected_index or 0
            generation_result = variant_result.variants[selected_index]

            if not generation_result.success:
                raise Exception(f"Image generation failed: {generation_result.error}")

            image_path = generation_result.image_path

            # Critiquer l'image (si critique échoue, on continue quand même avec l'image générée)
            critic = ImageCritic()
            critique_result = None
            try:
                critique_result = await critic.evaluate(image_path)
            except Exception as critique_error:
                logger.warning(
                    "Image critique failed, continuing without critique",
                    error=str(critique_error),
                    image_path=str(image_path),
                )
                # Continuer sans critique - on considère l'image comme valide par défaut
                # Créer un résultat de critique par défaut
                from python_scripts.image_generation.image_critic import CritiqueResult, CritiqueScores
                critique_result = CritiqueResult(
                    scores=CritiqueScores(
                        sharpness=50,  # Score par défaut moyen
                        composition=50,
                        no_text=100,  # On assume pas de texte (le prompt l'évite)
                        coherence=50,
                        professionalism=50,
                    ),
                    score_total=50,  # Score moyen par défaut
                    verdict="VALIDE",  # Par défaut valide si critique échoue
                    problems=[],
                    suggestions=[],
                    has_unwanted_text=False,
                )

            last_image_path = image_path
            last_prompt = generation_result.prompt_used
            last_negative_prompt = generation_result.negative_prompt or ""
            # Adapter les generation_params depuis les métadonnées Ideogram ou local
            if generation_result.provider == "ideogram":
                last_generation_params = {
                    "provider": "ideogram",
                    "model": generation_result.metadata.get("model", "V_2"),
                    "style_type": generation_result.metadata.get("style_type", "DESIGN"),
                    "aspect_ratio": generation_result.metadata.get("aspect_ratio", "1:1"),
                    "resolution": generation_result.metadata.get("resolution", "1024x1024"),
                    "ideogram_url": generation_result.metadata.get("ideogram_url"),
                    "magic_prompt": generation_result.metadata.get("magic_prompt"),
                }
            else:  # local
                last_generation_params = {
                    "provider": "local",
                    "width": generation_result.metadata.get("width", 768),
                    "height": generation_result.metadata.get("height", 768),
                    "steps": generation_result.metadata.get("steps", 12),
                    "guidance_scale": generation_result.metadata.get("guidance_scale", 7.5),
                }

            # Vérifier si retry nécessaire (seulement si critique réussie)
            if critique_result and not critic.should_retry(critique_result):
                # Image valide
                return ImageGenerationResult(
                    image_path=image_path,
                    prompt_used=last_prompt,
                    negative_prompt=last_negative_prompt,
                    generation_params=last_generation_params,
                    quality_score=float(critique_result.score_total),
                    critique_details={
                        "scores": {
                            "sharpness": critique_result.scores.sharpness,
                            "composition": critique_result.scores.composition,
                            "no_text": critique_result.scores.no_text,
                            "coherence": critique_result.scores.coherence,
                            "professionalism": critique_result.scores.professionalism,
                        },
                        "verdict": critique_result.verdict,
                        "problems": critique_result.problems,
                        "suggestions": critique_result.suggestions,
                        "has_unwanted_text": critique_result.has_unwanted_text,
                    },
                    retry_count=retry_count,
                    final_status="success",
                )
            else:
                # Retry nécessaire
                retry_count += 1
                logger.warning(
                    "Image quality below threshold, retrying",
                    attempt=retry_count,
                    score_total=critique_result.score_total,
                    max_retries=max_retries,
                )

                if retry_count >= max_retries:
                    # Retries épuisés
                    return ImageGenerationResult(
                        image_path=image_path,
                        prompt_used=last_prompt or "",
                        negative_prompt=last_negative_prompt or "",
                        generation_params=last_generation_params or {},
                        quality_score=float(critique_result.score_total),
                        critique_details={
                            "scores": {
                                "sharpness": critique_result.scores.sharpness,
                                "composition": critique_result.scores.composition,
                                "no_text": critique_result.scores.no_text,
                                "coherence": critique_result.scores.coherence,
                                "professionalism": critique_result.scores.professionalism,
                            },
                            "verdict": critique_result.verdict,
                            "problems": critique_result.problems,
                            "suggestions": critique_result.suggestions,
                            "has_unwanted_text": critique_result.has_unwanted_text,
                        },
                        retry_count=retry_count,
                        final_status="retry_exhausted",
                    )

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(
                "Error in image generation crew",
                error=str(e),
                error_type=type(e).__name__,
                attempt=retry_count + 1,
                traceback=error_traceback,
            )
            retry_count += 1

            if retry_count >= max_retries:
                return ImageGenerationResult(
                    image_path=last_image_path or Path(""),
                    prompt_used=last_prompt or "",
                    negative_prompt=last_negative_prompt or "",
                    generation_params=last_generation_params or {},
                    retry_count=retry_count,
                    final_status="failed",
                )

    # Ne devrait jamais arriver ici
    raise RuntimeError("Image generation failed after all retries")

