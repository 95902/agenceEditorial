"""CrewAI tool for image generation."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from crewai.tools import BaseTool
from loguru import logger

from python_scripts.image_generation import ImageGenerator, GenerationResult


class ImageGeneratorTool(BaseTool):
    """Tool CrewAI pour génération d'images professionnelles."""

    name: str = "generate_image"
    description: str = (
        "Génère une image professionnelle pour illustrer un article de blog. "
        "Input: JSON string avec 'topic' (sujet de l'article), "
        "'style' (optionnel: corporate_flat, corporate_3d, tech_isometric, etc.), "
        "et 'editorial_tone' (optionnel: professional, technical, etc.). "
        "Output: Chemin vers l'image générée."
    )

    def _run(self, input_data: str) -> str:
        """
        Génère une image depuis un prompt JSON.

        Args:
            input_data: JSON string avec topic, style (optionnel), aspect_ratio (optionnel)

        Returns:
            JSON string avec success, image_path, prompt_used, generation_time
        """
        try:
            # Parser l'input JSON
            data = json.loads(input_data) if isinstance(input_data, str) else input_data

            topic = data.get("topic", "")
            if not topic:
                raise ValueError("'topic' is required in input_data")

            style = data.get("style", "corporate_flat")
            aspect_ratio = data.get("aspect_ratio", "1:1")

            # Obtenir le générateur
            generator = ImageGenerator.get_instance()

            # Exécuter la génération async dans un contexte sync
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si la boucle tourne déjà, créer une nouvelle task
                    # Pour l'instant, utiliser run_coroutine_threadsafe ou créer une nouvelle boucle
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            generator.generate_from_topic(
                                topic=topic,
                                style=style,
                                aspect_ratio=aspect_ratio,
                            )
                        )
                        result = future.result()
                else:
                    result = loop.run_until_complete(
                        generator.generate_from_topic(
                            topic=topic,
                            style=style,
                            aspect_ratio=aspect_ratio,
                        )
                    )
            except RuntimeError:
                # Pas de boucle d'événements, créer une nouvelle
                result = asyncio.run(
                    generator.generate_from_topic(
                        topic=topic,
                        style=style,
                        aspect_ratio=aspect_ratio,
                    )
                )

            if result.success:
                logger.info(
                    "Image generated via CrewAI tool",
                    topic=topic,
                    image_path=str(result.image_path),
                    provider=result.provider,
                    generation_time=result.generation_time,
                )

                return json.dumps({
                    "success": True,
                    "image_path": str(result.image_path),
                    "prompt_used": result.prompt_used,
                    "generation_time": result.generation_time,
                    "provider": result.provider,
                })
            else:
                error_msg = f"Image generation failed: {result.error}"
                logger.error(error_msg)
                return json.dumps({
                    "success": False,
                    "error": result.error,
                })

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON input: {e}"
            logger.error(error_msg, input_data=input_data)
            return json.dumps({
                "success": False,
                "error": error_msg,
            })
        except Exception as e:
            error_msg = f"Image generation failed: {e}"
            logger.error(error_msg, error=str(e))
            return json.dumps({
                "success": False,
                "error": error_msg,
            })

