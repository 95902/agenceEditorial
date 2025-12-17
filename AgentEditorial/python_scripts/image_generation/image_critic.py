"""Critique d'images générées avec LLM Vision pour évaluation qualité."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger

from python_scripts.config.settings import settings
from python_scripts.image_generation.vram_resource_manager import get_vram_resource_manager


@dataclass
class CritiqueScores:
    """Scores d'évaluation pour chaque critère (0-10 chacun)."""

    sharpness: int  # /10 - Netteté
    composition: int  # /10 - Composition
    no_text: int  # /10 - Absence de texte
    coherence: int  # /10 - Cohérence style
    professionalism: int  # /10 - Professionnalisme


@dataclass
class CritiqueResult:
    """Résultat complet de l'évaluation d'une image."""

    scores: CritiqueScores
    score_total: int  # /50
    verdict: str  # "VALIDE" ou "REGENERER"
    problems: list[str]
    suggestions: list[str]
    has_unwanted_text: bool


CRITIQUE_PROMPT = """
Analyse cette image générée pour un blog B2B tech.

Évalue selon ces critères (score 1-10 chacun) :

1. NETTETÉ : Bords nets, pas de flou, détails visibles ?
2. COMPOSITION : Éléments bien centrés et équilibrés ?
3. ABSENCE DE TEXTE : Y a-t-il du texte visible ou caractères ?
4. COHÉRENCE STYLE : Style uniforme, pas d'artefacts ?
5. PROFESSIONNALISME : Utilisable pour communication B2B ?

Réponds UNIQUEMENT en JSON valide :
{{
  "scores": {{
    "sharpness": X,
    "composition": X,
    "no_text": X,
    "coherence": X,
    "professionalism": X
  }},
  "score_total": X,
  "verdict": "VALIDE" ou "REGENERER",
  "has_unwanted_text": true/false,
  "problems": ["liste", "des", "problèmes"],
  "suggestions": ["amélioration", "du", "prompt"]
}}
"""


class ImageCritic:
    """
    Critique d'images générées via LLM Vision (Qwen2-VL via Ollama).
    
    Évalue la qualité des images selon 5 critères et retourne un verdict.
    """

    def __init__(
        self,
        model: str = "qwen2.5vl:latest",
        ollama_url: Optional[str] = None,
    ) -> None:
        """
        Initialise le critique d'images.

        Args:
            model: Nom du modèle vision à utiliser
            ollama_url: URL de l'API Ollama (utilise settings.ollama_base_url par défaut)
        """
        self.model = model
        self.ollama_url = ollama_url or settings.ollama_base_url

    def _encode_image_to_base64(self, image_path: Path) -> str:
        """
        Encode une image en base64 pour l'API Ollama.

        Args:
            image_path: Chemin vers l'image

        Returns:
            String base64 encodée
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse une réponse JSON depuis le LLM avec stratégies de fallback.

        Args:
            response_text: Texte de la réponse

        Returns:
            Dictionnaire parsé

        Raises:
            ValueError: Si le JSON ne peut pas être parsé
        """
        # Strategy 1: Try to find JSON block between ```json and ```
        json_block_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 2: Try to find JSON block between ``` and ```
        code_block_match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find first { and last } and extract
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]

            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # Strategy 4: Try to fix common JSON issues
                fixed_json = self._fix_json_common_issues(json_text)
                try:
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    pass

        # Strategy 5: Try parsing entire response
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse JSON response: {response_text[:200]}")

    def _fix_json_common_issues(self, json_text: str) -> str:
        """
        Corrige les problèmes JSON communs dans les réponses LLM.

        Args:
            json_text: JSON avec problèmes potentiels

        Returns:
            JSON corrigé
        """
        # Remove trailing commas before } or ]
        json_text = re.sub(r",\s*}", "}", json_text)
        json_text = re.sub(r",\s*]", "]", json_text)

        return json_text

    async def _check_model_available(self) -> bool:
        """
        Vérifie que le modèle vision est disponible dans Ollama.

        Returns:
            True si le modèle est disponible, False sinon
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                response.raise_for_status()
                models_data = response.json()
                model_names = [model.get("name", "") for model in models_data.get("models", [])]
                is_available = self.model in model_names
                if not is_available:
                    logger.warning(
                        "Vision model not found in Ollama",
                        model=self.model,
                        available_models=model_names[:10],  # Logger les 10 premiers pour debug
                    )
                return is_available
        except Exception as e:
            logger.error(
                "Failed to check model availability",
                error=str(e),
                ollama_url=self.ollama_url,
            )
            return False

    async def evaluate(self, image_path: Path) -> CritiqueResult:
        """
        Évalue la qualité d'une image générée.

        Args:
            image_path: Chemin vers l'image à évaluer

        Returns:
            CritiqueResult avec scores et verdict

        Raises:
            ValueError: Si l'évaluation échoue
        """
        # Vérifier que le modèle est disponible
        if not await self._check_model_available():
            logger.warning(
                "Vision model not available, proceeding anyway",
                model=self.model,
                ollama_url=self.ollama_url,
            )

        # Encoder l'image en base64
        image_base64 = self._encode_image_to_base64(image_path)

        # Acquérir la VRAM pour le modèle vision
        vram_manager = get_vram_resource_manager()
        await vram_manager.acquire_for_vision(self.model)

        try:
            # Appeler Ollama avec l'image (utiliser /api/chat pour les modèles vision)
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": CRITIQUE_PROMPT,
                                "images": [image_base64],
                            }
                        ],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                response_data = response.json()

                # Extraire le texte de la réponse (format /api/chat)
                if isinstance(response_data, dict):
                    # Format /api/chat retourne {"message": {"content": "..."}}
                    message = response_data.get("message", {})
                    response_text = message.get("content", "") if isinstance(message, dict) else str(message)
                elif isinstance(response_data, str):
                    response_text = response_data
                else:
                    response_text = str(response_data)

                # Parser le JSON
                parsed = self._parse_json_response(response_text)

                # Construire CritiqueResult
                scores_dict = parsed.get("scores", {})
                scores = CritiqueScores(
                    sharpness=int(scores_dict.get("sharpness", 5)),
                    composition=int(scores_dict.get("composition", 5)),
                    no_text=int(scores_dict.get("no_text", 5)),
                    coherence=int(scores_dict.get("coherence", 5)),
                    professionalism=int(scores_dict.get("professionalism", 5)),
                )

                score_total = parsed.get("score_total")
                if score_total is None:
                    # Calculer si manquant
                    score_total = (
                        scores.sharpness
                        + scores.composition
                        + scores.no_text
                        + scores.coherence
                        + scores.professionalism
                    )

                verdict = parsed.get("verdict", "REGENERER")
                if verdict not in ("VALIDE", "REGENERER"):
                    # Déterminer automatiquement si score_total >= 35
                    verdict = "VALIDE" if score_total >= 35 else "REGENERER"

                result = CritiqueResult(
                    scores=scores,
                    score_total=int(score_total),
                    verdict=verdict,
                    problems=parsed.get("problems", []),
                    suggestions=parsed.get("suggestions", []),
                    has_unwanted_text=parsed.get("has_unwanted_text", False),
                )

                logger.info(
                    "Image critique completed",
                    image_path=str(image_path),
                    score_total=result.score_total,
                    verdict=result.verdict,
                )

                return result

        except httpx.HTTPError as e:
            # Logger les détails de l'erreur HTTP
            error_detail = {
                "error": str(e),
                "error_type": type(e).__name__,
            }

            if hasattr(e, "response") and e.response is not None:
                error_detail["status_code"] = e.response.status_code
                try:
                    response_text = e.response.text
                    error_detail["response_text"] = response_text[:500] if response_text else None
                except Exception:
                    pass

            logger.error(
                "Ollama API error during image critique",
                **error_detail,
                model=self.model,
                ollama_url=self.ollama_url,
            )
            raise ValueError(f"Image critique failed: {error_detail}") from e
        except (ValueError, KeyError) as e:
            logger.error("Error parsing critique response", error=str(e))
            raise ValueError(f"Failed to parse critique response: {e}") from e
        except Exception as e:
            logger.error("Unexpected error during image critique", error=str(e))
            raise ValueError(f"Image critique failed: {e}") from e

    def should_retry(
        self, 
        result: CritiqueResult, 
        attempt: int = 1,
        min_score_threshold: int = 35,
        accept_if_essential_ok: bool = True,
    ) -> bool:
        """
        Validation hybride avec seuil adaptatif et critères essentiels.
        
        Args:
            result: Résultat de l'évaluation
            attempt: Numéro de la tentative (1, 2, 3...)
            min_score_threshold: Seuil minimum de score total (défaut: 35)
            accept_if_essential_ok: Si True, accepter si critères essentiels OK même si score bas
            
        Returns:
            True si une nouvelle génération est recommandée
        """
        # Critères absolus : toujours retry
        if result.has_unwanted_text:
            return True
        
        if result.verdict == "REGENERER":
            return True
        
        # Seuil adaptatif selon la tentative
        # Tentative 1: min_score_threshold, Tentative 2: -5, Tentative 3+: -10
        adaptive_threshold = min_score_threshold - (attempt - 1) * 5
        adaptive_threshold = max(adaptive_threshold, 15)  # Minimum 15/50 (réduit de 20)
        
        # Si critères essentiels OK, accepter même avec score légèrement inférieur
        if accept_if_essential_ok:
            essential_ok = (
                result.scores.no_text >= 7 and  # Pas de texte (réduit de 8 à 7)
                result.scores.professionalism >= 5 and  # Professionnel (réduit de 6 à 5)
                result.scores.sharpness >= 4  # Netteté acceptable (réduit de 5 à 4)
            )
            
            # Accepter si critères essentiels OK et score proche du seuil (marge augmentée)
            if essential_ok and result.score_total >= (adaptive_threshold - 8):
                return False
        
        # Validation par score total
        return result.score_total < adaptive_threshold

