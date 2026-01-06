"""CrewAI tool for image quality critique."""

from __future__ import annotations

import json
from pathlib import Path

from crewai.tools import BaseTool
from loguru import logger

from python_scripts.image_generation import ImageCritic


class ImageCriticTool(BaseTool):
    """Tool CrewAI pour évaluation qualité d'images générées."""

    name: str = "critique_image"
    description: str = (
        "Évalue la qualité d'une image générée selon 5 critères (netteté, composition, "
        "absence de texte, cohérence style, professionnalisme). "
        "Input: Chemin vers l'image (string). "
        "Output: JSON string avec scores (0-10 chacun), score_total (/50), "
        "verdict (VALIDE ou REGENERER), problems (liste), suggestions (liste), "
        "has_unwanted_text (bool)."
    )

    def _run(self, image_path: str) -> str:
        """
        Évalue la qualité d'une image.

        Args:
            image_path: Chemin vers l'image à évaluer

        Returns:
            JSON string avec résultats de l'évaluation
        """
        try:
            path = Path(image_path)
            if not path.exists():
                raise ValueError(f"Image file not found: {image_path}")

            # Créer le critique et évaluer
            critic = ImageCritic()

            # Appel async dans un contexte synchrone
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si la boucle tourne déjà, créer une task
                    # Pour l'instant, utiliser asyncio.run dans un nouveau contexte
                    result = asyncio.run(critic.evaluate(path))
                else:
                    result = loop.run_until_complete(critic.evaluate(path))
            except RuntimeError:
                # Pas de boucle d'événements, créer une nouvelle
                result = asyncio.run(critic.evaluate(path))

            # Construire le résultat JSON
            result_dict = {
                "scores": {
                    "sharpness": result.scores.sharpness,
                    "composition": result.scores.composition,
                    "no_text": result.scores.no_text,
                    "coherence": result.scores.coherence,
                    "professionalism": result.scores.professionalism,
                },
                "score_total": result.score_total,
                "verdict": result.verdict,
                "has_unwanted_text": result.has_unwanted_text,
                "problems": result.problems,
                "suggestions": result.suggestions,
            }

            logger.info(
                "Image critique completed via CrewAI tool",
                image_path=str(image_path),
                score_total=result.score_total,
                verdict=result.verdict,
            )

            return json.dumps(result_dict, ensure_ascii=False)

        except Exception as e:
            error_msg = f"Image critique failed: {e}"
            logger.error(error_msg, image_path=image_path, error=str(e))
            raise ValueError(error_msg) from e














