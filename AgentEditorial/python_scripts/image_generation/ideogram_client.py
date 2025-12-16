"""Client API pour Ideogram 3.0."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from python_scripts.config.settings import settings


# Constantes Ideogram v3
IDEOGRAM_STYLE_TYPES = {
    "AUTO": "AUTO",
    "DESIGN": "DESIGN",
    "ILLUSTRATION": "ILLUSTRATION",
    "REALISTIC": "REALISTIC",
    "GENERAL": "GENERAL",
}

IDEOGRAM_ASPECT_RATIOS = {
    "1:1": "1x1",
    "4:3": "4x3",
    "3:4": "3x4",
    "16:9": "16x9",
    "9:16": "9x16",
}

RENDERING_SPEED = {
    "TURBO": "TURBO",
    "STANDARD": "STANDARD",
}

MAGIC_PROMPT_OPTIONS = {
    "AUTO": "AUTO",
    "ON": "ON",
    "OFF": "OFF",
}


@dataclass
class IdeogramResult:
    """Résultat d'une génération Ideogram."""

    url: str  # URL Ideogram (expire après ~24h)
    prompt: str  # Prompt amélioré par magic_prompt
    resolution: str  # "1024x1024"
    local_path: Optional[Path] = None  # Après téléchargement
    generation_time: float = 0.0


class IdeogramAPIError(Exception):
    """Erreur lors de l'appel à l'API Ideogram."""

    pass


class IdeogramClient:
    """
    Client HTTP pour l'API Ideogram 3.0.

    Singleton pour éviter de créer plusieurs instances du client HTTP.
    """

    _instance: Optional[IdeogramClient] = None
    _lock = None

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialise le client Ideogram.

        Args:
            api_key: Clé API Ideogram. Si None, récupère depuis settings.
        """
        if IdeogramClient._instance is not None:
            raise RuntimeError(
                "IdeogramClient is a singleton. Use get_instance() instead."
            )

        self.api_key = api_key or settings.ideogram_api_key
        if not self.api_key:
            raise ValueError(
                "Ideogram API key is required. Set IDEOGRAM_API_KEY environment variable."
            )

        self.base_url = "https://api.ideogram.ai/v1/ideogram-v3"
        self._client: Optional[httpx.AsyncClient] = None
        IdeogramClient._instance = self

    @classmethod
    def get_instance(cls, api_key: Optional[str] = None, force_reload: bool = False) -> IdeogramClient:
        """
        Retourne l'instance singleton du client.

        Args:
            api_key: Clé API (utilisée uniquement à la première création ou si force_reload=True)
            force_reload: Si True, réinitialise le singleton avec la nouvelle clé

        Returns:
            Instance du client Ideogram
        """
        if force_reload or cls._instance is None:
            if cls._instance is not None:
                # Fermer l'ancien client HTTP si présent
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si la boucle tourne, on ne peut pas attendre la fermeture synchrone
                        # Le client sera fermé lors de la création du nouveau
                        pass
                    else:
                        loop.run_until_complete(cls._instance.close())
                except Exception:
                    pass
            cls._instance = None
            cls._instance = cls(api_key=api_key)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Réinitialise le singleton (utile quand la clé API change dans .env).
        
        Appelez cette méthode après avoir modifié IDEOGRAM_API_KEY dans .env
        pour forcer la recréation du client avec la nouvelle clé.
        """
        if cls._instance is not None:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    loop.run_until_complete(cls._instance.close())
            except Exception:
                pass
        cls._instance = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Retourne le client HTTP async, en le créant si nécessaire."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"Api-Key": self.api_key},
            )
        return self._client

    async def close(self) -> None:
        """Ferme le client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        style_type: str = "AUTO",
        aspect_ratio: str = "1x1",
        rendering_speed: str = "DEFAULT",
        magic_prompt: str = "AUTO",
        resolution: Optional[str] = None,
    ) -> IdeogramResult:
        """
        Génère une image via l'API Ideogram v3.

        Args:
            prompt: Description de l'image à générer
            negative_prompt: Prompt négatif (optionnel)
            style_type: Style Ideogram (AUTO, DESIGN, ILLUSTRATION, REALISTIC, GENERAL)
            aspect_ratio: Ratio d'aspect Ideogram (1x1, 4x3, 3x4, 16x9, 9x16)
            rendering_speed: Vitesse de rendu (TURBO ou STANDARD)
            magic_prompt: Option magic prompt (AUTO, ON, OFF)
            resolution: Résolution spécifique (optionnel, sinon utilise aspect_ratio)

        Returns:
            IdeogramResult avec l'URL de l'image et les métadonnées

        Raises:
            IdeogramAPIError: Si l'API retourne une erreur
        """
        start_time = time.time()

        if style_type not in IDEOGRAM_STYLE_TYPES.values():
            raise ValueError(
                f"Invalid style_type: {style_type}. Must be one of {list(IDEOGRAM_STYLE_TYPES.values())}"
            )

        if aspect_ratio not in IDEOGRAM_ASPECT_RATIOS.values():
            raise ValueError(
                f"Invalid aspect_ratio: {aspect_ratio}. Must be one of {list(IDEOGRAM_ASPECT_RATIOS.values())}"
            )

        if rendering_speed not in RENDERING_SPEED.values():
            raise ValueError(
                f"Invalid rendering_speed: {rendering_speed}. Must be one of {list(RENDERING_SPEED.values())}"
            )

        if magic_prompt not in MAGIC_PROMPT_OPTIONS.values():
            raise ValueError(
                f"Invalid magic_prompt: {magic_prompt}. Must be one of {list(MAGIC_PROMPT_OPTIONS.values())}"
            )

        url = f"{self.base_url}/generate"

        # Construire le formulaire multipart/form-data
        # httpx utilise files avec des tuples pour multipart/form-data
        # Format: {"field_name": (filename, content)} ou {"field_name": (None, content)} pour texte
        files = {
            "prompt": (None, prompt),
            "aspect_ratio": (None, aspect_ratio),
            "rendering_speed": (None, rendering_speed),
            "style_type": (None, style_type),
            "magic_prompt": (None, magic_prompt),
        }

        if negative_prompt:
            files["negative_prompt"] = (None, negative_prompt)

        if resolution:
            files["resolution"] = (None, resolution)

        client = await self._get_client()

        logger.info(
            "Calling Ideogram API v3",
            prompt=prompt[:100],
            style_type=style_type,
            aspect_ratio=aspect_ratio,
            rendering_speed=rendering_speed,
        )

        try:
            # Utiliser files pour envoyer en multipart/form-data
            response = await client.post(url, files=files)
            response.raise_for_status()

            data_response = response.json()

            # Structure de réponse Ideogram v3: {"data": [{"url": "...", "prompt": "...", ...}]}
            if not data_response.get("data") or len(data_response["data"]) == 0:
                raise IdeogramAPIError("No image data in Ideogram response")

            image_data = data_response["data"][0]
            image_url = image_data.get("url")
            
            # Le prompt amélioré par magic_prompt est dans image_data["prompt"]
            improved_prompt = image_data.get("prompt", prompt)
            resolution_result = image_data.get("resolution", resolution or "1024x1024")

            if not image_url:
                raise IdeogramAPIError("No image URL in Ideogram response")

            generation_time = time.time() - start_time

            logger.info(
                "Ideogram image generated successfully",
                url=image_url,
                prompt_improved=improved_prompt != prompt,
                resolution=resolution_result,
                generation_time=generation_time,
            )

            return IdeogramResult(
                url=image_url,
                prompt=improved_prompt,
                resolution=resolution_result,
                generation_time=generation_time,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Ideogram API error: {e.response.status_code}"
            if e.response.status_code == 429:
                error_msg += " (Rate limit exceeded)"
            elif e.response.status_code == 401:
                error_msg += " (Invalid API key)"
            elif e.response.status_code == 422:
                error_msg += " (Prompt failed safety check)"

            # Log le détail de l'erreur si disponible
            try:
                error_detail = e.response.json()
                logger.error(
                    "Ideogram API error",
                    status_code=e.response.status_code,
                    error_detail=error_detail,
                )
            except Exception:
                logger.error(
                    "Ideogram API error",
                    status_code=e.response.status_code,
                    error=str(e),
                )

            raise IdeogramAPIError(error_msg) from e

        except httpx.TimeoutException:
            logger.error("Ideogram API timeout")
            raise IdeogramAPIError("Request timeout") from None

        except Exception as e:
            logger.error("Unexpected error calling Ideogram API", error=str(e))
            raise IdeogramAPIError(f"Unexpected error: {str(e)}") from e

    async def generate_variants(
        self,
        prompt: str,
        num_variants: int = 3,
        negative_prompt: Optional[str] = None,
        style_type: str = "AUTO",
        aspect_ratio: str = "1x1",
        rendering_speed: str = "TURBO",
        magic_prompt: str = "AUTO",
        resolution: Optional[str] = None,
    ) -> list[IdeogramResult]:
        """
        Génère plusieurs variantes d'une image en parallèle.

        Args:
            prompt: Prompt de base
            num_variants: Nombre de variantes (défaut: 3)
            negative_prompt: Prompt négatif (optionnel)
            style_type: Style Ideogram (AUTO, DESIGN, ILLUSTRATION, REALISTIC, GENERAL)
            aspect_ratio: Ratio d'aspect Ideogram (1x1, 4x3, 3x4, 16x9, 9x16)
            rendering_speed: Vitesse de rendu (TURBO ou STANDARD)
            magic_prompt: Option magic prompt (AUTO, ON, OFF)
            resolution: Résolution spécifique (optionnel, sinon utilise aspect_ratio)

        Returns:
            Liste de IdeogramResult, incluant les résultats réussis.
        """
        import asyncio

        logger.info(
            "Generating image variants with Ideogram API v3",
            prompt=prompt[:100],
            num_variants=num_variants,
            style_type=style_type,
            aspect_ratio=aspect_ratio,
        )

        # Créer les tâches pour générer chaque variante
        tasks = [
            self.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                style_type=style_type,
                aspect_ratio=aspect_ratio,
                rendering_speed=rendering_speed,
                magic_prompt=magic_prompt,
                resolution=resolution,
            )
            for _ in range(num_variants)
        ]

        # Exécuter les tâches en parallèle et collecter les résultats
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results: list[IdeogramResult] = []
        for i, res in enumerate(results):
            if isinstance(res, IdeogramResult):
                valid_results.append(res)
            else:
                logger.error(
                    "Failed to generate image variant",
                    variant_number=i + 1,
                    error=str(res),
                    prompt=prompt[:100],
                )

        if not valid_results:
            raise IdeogramAPIError("All image variant generations failed.")

        logger.info(
            "Successfully generated image variants",
            num_successful_variants=len(valid_results),
            total_variants_requested=num_variants,
        )
        return valid_results

    async def download_image(self, url: str, output_path: Path) -> Path:
        """
        Télécharge une image depuis l'URL Ideogram.

        Args:
            url: URL de l'image Ideogram
            output_path: Chemin où sauvegarder l'image

        Returns:
            Chemin vers l'image téléchargée

        Raises:
            IdeogramAPIError: Si le téléchargement échoue
        """
        # Créer le répertoire parent si nécessaire
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading image from Ideogram", url=url, output_path=str(output_path))

        try:
            # Télécharger l'image (sans header Api-Key pour les images publiques)
            response = await httpx.AsyncClient(timeout=60.0).get(url)
            response.raise_for_status()

            # Sauvegarder l'image
            output_path.write_bytes(response.content)

            logger.info("Image downloaded successfully", output_path=str(output_path))

            return output_path

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to download image",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise IdeogramAPIError(f"Failed to download image: {e.response.status_code}") from e

        except httpx.TimeoutException:
            logger.error("Image download timeout")
            raise IdeogramAPIError("Download timeout") from None

        except Exception as e:
            logger.error("Unexpected error downloading image", error=str(e))
            raise IdeogramAPIError(f"Download error: {str(e)}") from e


def get_ideogram_client(api_key: Optional[str] = None) -> IdeogramClient:
    """
    Helper function pour obtenir l'instance singleton du client.

    Args:
        api_key: Clé API (utilisée uniquement à la première création)

    Returns:
        Instance du client Ideogram
    """
    return IdeogramClient.get_instance(api_key=api_key)
