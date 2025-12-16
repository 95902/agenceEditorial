"""Gestionnaire VRAM avec orchestration Ollama/Z-Image."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from threading import Lock

import httpx
import torch
from loguru import logger

from python_scripts.config.image_config import IMAGE_CONFIG
from python_scripts.config.settings import settings
from python_scripts.image_generation.vram_manager import get_vram_manager, VRAMInfo


@dataclass
class VRAMStatus:
    """Statut actuel de la VRAM et de son propriétaire."""

    current_owner: str  # "ollama", "zimage", "vision", "none"
    vram_free_gb: float
    vram_total_gb: float
    ollama_model_loaded: Optional[str]


class VRAMResourceManager:
    """
    Gestionnaire VRAM avec orchestration Ollama.
    
    Singleton qui coordonne l'accès VRAM entre différents modèles GPU Ollama.
    
    Note: Avec Ideogram en cloud, plus besoin de décharger Ollama pour générer des images.
    La VRAM est maintenant uniquement pour Ollama (LLM et Vision).
    """

    _instance: Optional[VRAMResourceManager] = None
    _lock = Lock()

    def __init__(self, ollama_url: Optional[str] = None) -> None:
        """
        Initialise le gestionnaire VRAM.

        Args:
            ollama_url: URL de l'API Ollama (utilise settings.ollama_base_url par défaut)
        """
        if VRAMResourceManager._instance is not None:
            raise RuntimeError(
                "VRAMResourceManager is a singleton. Use get_instance() instead."
            )

        self.ollama_url = ollama_url or settings.ollama_base_url
        self._current_owner: str = "none"  # "ollama", "zimage", "vision", "none"
        self._ollama_model_loaded: Optional[str] = None
        self._vram_manager = get_vram_manager()
        self._transition_delay = IMAGE_CONFIG.transition_delay_seconds

        VRAMResourceManager._instance = self

    @classmethod
    def get_instance(cls, ollama_url: Optional[str] = None) -> VRAMResourceManager:
        """
        Récupère l'instance singleton du gestionnaire VRAM.

        Args:
            ollama_url: URL de l'API Ollama (ignoré si instance existe déjà)

        Returns:
            Instance unique de VRAMResourceManager
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(ollama_url)
        return cls._instance

    async def _unload_ollama_model(self, model: Optional[str] = None) -> bool:
        """
        Décharge un modèle Ollama de la VRAM.

        Args:
            model: Nom du modèle à décharger (si None, décharge tous les modèles)

        Returns:
            True si succès, False sinon
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Pour décharger un modèle, on utilise /api/generate avec keep_alive=0
                # Si model est None, on décharge tous les modèles chargés
                if model:
                    models_to_unload = [model]
                else:
                    # Récupérer la liste des modèles chargés
                    models_to_unload = await self._get_ollama_loaded_models()

                if not models_to_unload:
                    logger.debug("No Ollama models to unload")
                    return True

                for model_name in models_to_unload:
                    try:
                        # Décharger en utilisant keep_alive=0
                        response = await client.post(
                            f"{self.ollama_url}/api/generate",
                            json={
                                "model": model_name,
                                "prompt": "test",
                                "keep_alive": 0,
                                "stream": False,
                            },
                        )
                        response.raise_for_status()
                        logger.info(
                            "Unloaded Ollama model",
                            model=model_name,
                            status_code=response.status_code,
                        )
                    except httpx.HTTPError as e:
                        logger.warning(
                            "Failed to unload Ollama model",
                            model=model_name,
                            error=str(e),
                        )

                # Attendre la libération VRAM
                await asyncio.sleep(self._transition_delay)
                torch.cuda.empty_cache()

                return True

        except Exception as e:
            logger.error("Error unloading Ollama model", error=str(e))
            return False

    async def _get_ollama_loaded_models(self) -> list[str]:
        """
        Récupère la liste des modèles Ollama actuellement chargés.

        Returns:
            Liste des noms de modèles chargés
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/ps")
                response.raise_for_status()
                data = response.json()

                models = []
                if isinstance(data, dict) and "models" in data:
                    for model_info in data["models"]:
                        if isinstance(model_info, dict) and "name" in model_info:
                            models.append(model_info["name"])
                        elif isinstance(model_info, str):
                            models.append(model_info)

                return models

        except Exception as e:
            logger.warning("Failed to get Ollama loaded models", error=str(e))
            return []

    async def acquire_for_ollama(self, model: str) -> bool:
        """
        Acquiert la VRAM pour Ollama (LLM).
        
        Avec Ideogram en cloud, Ollama peut rester chargé en permanence.
        On décharge uniquement si un autre modèle Ollama est chargé.

        Args:
            model: Nom du modèle Ollama à charger

        Returns:
            True si succès, False sinon
        """
        logger.info(
            "Acquiring VRAM for Ollama",
            model=model,
            current_owner=self._current_owner,
        )

        # Si un autre modèle Ollama est chargé, le décharger
        if self._current_owner in ("ollama", "vision") and self._ollama_model_loaded:
            if self._ollama_model_loaded != model:
                logger.info(
                    "Unloading previous Ollama model",
                    previous_model=self._ollama_model_loaded,
                    new_model=model,
                )
                await self._unload_ollama_model(self._ollama_model_loaded)
            else:
                # Même modèle déjà chargé, rien à faire
                logger.debug("Ollama model already loaded", model=model)
                return True

        self._current_owner = "ollama"
        self._ollama_model_loaded = model

        logger.info("VRAM acquired for Ollama", model=model)
        return True

    async def acquire_for_zimage(self) -> bool:
        """
        [DEPRECATED] Acquiert la VRAM pour Z-Image.
        
        Cette méthode est deprecated car Ideogram est maintenant utilisé en cloud.
        Z-Image n'est utilisé que comme fallback local si IMAGE_PROVIDER=local.
        
        Pour le fallback local, la gestion VRAM est gérée directement par ZImageGenerator.

        Returns:
            True si succès, False sinon
        """
        import warnings

        warnings.warn(
            "acquire_for_zimage() is deprecated. With Ideogram cloud, "
            "VRAM is only used for Ollama. Use acquire_for_ollama() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        logger.warning(
            "acquire_for_zimage() called but deprecated - "
            "Ideogram cloud no longer requires VRAM for images",
            current_owner=self._current_owner,
        )

        # Pour compatibilité, on décharge Ollama si nécessaire (fallback local)
        if self._current_owner in ("ollama", "vision"):
            logger.info("Unloading Ollama to free VRAM for Z-Image (fallback)")
            await self._unload_ollama_model(self._ollama_model_loaded)
            self._ollama_model_loaded = None

        self._current_owner = "zimage"

        # Nettoyer la VRAM
        torch.cuda.empty_cache()
        await asyncio.sleep(self._transition_delay)

        logger.info("VRAM acquired for Z-Image (fallback mode)")
        return True

    async def acquire_for_vision(self, model: str = "qwen2.5vl:latest") -> bool:
        """
        Acquiert la VRAM pour modèle vision (Ollama) en libérant le LLM Ollama si nécessaire.

        Args:
            model: Nom du modèle vision à charger

        Returns:
            True si succès, False sinon
        """
        logger.info(
            "Acquiring VRAM for Vision model",
            model=model,
            current_owner=self._current_owner,
        )

        # Décharger Ollama LLM si un autre modèle est chargé
        if self._current_owner == "ollama" and self._ollama_model_loaded:
            if self._ollama_model_loaded != model:
                logger.info(
                    "Unloading previous Ollama model",
                    previous_model=self._ollama_model_loaded,
                    new_model=model,
                )
                await self._unload_ollama_model(self._ollama_model_loaded)
            else:
                # Même modèle déjà chargé (vision), rien à faire
                logger.debug("Vision model already loaded", model=model)
                return True

        self._current_owner = "vision"
        self._ollama_model_loaded = model

        logger.info("VRAM acquired for Vision", model=model)
        return True

    def release_all(self) -> None:
        """
        Libère toutes les ressources VRAM.
        """
        logger.info("Releasing all VRAM resources", current_owner=self._current_owner)

        # Décharger Z-Image si chargé
        if self._current_owner == "zimage":
            # Import lazy pour éviter dépendance circulaire
            from python_scripts.image_generation.z_image_generator import ZImageGenerator
            generator = ZImageGenerator.get_instance()
            if generator.is_loaded:
                generator.unload_model()

        # Décharger Ollama si chargé (de manière synchrone pour release_all)
        if self._current_owner in ("ollama", "vision") and self._ollama_model_loaded:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si la boucle tourne déjà, on ne peut pas lancer une coroutine
                    # On log juste un avertissement
                    logger.warning(
                        "Cannot unload Ollama synchronously in async context",
                        model=self._ollama_model_loaded,
                    )
                else:
                    loop.run_until_complete(
                        self._unload_ollama_model(self._ollama_model_loaded)
                    )
            except RuntimeError:
                # Pas de boucle d'événements, créer une nouvelle
                asyncio.run(self._unload_ollama_model(self._ollama_model_loaded))

        self._current_owner = "none"
        self._ollama_model_loaded = None

        torch.cuda.empty_cache()

        logger.info("All VRAM resources released")

    def get_vram_status(self) -> VRAMStatus:
        """
        Retourne le statut actuel de la VRAM.

        Returns:
            VRAMStatus avec l'état actuel
        """
        vram_info = self._vram_manager.check_available_vram()

        if vram_info is None:
            # Retourner un statut par défaut si on ne peut pas vérifier
            return VRAMStatus(
                current_owner=self._current_owner,
                vram_free_gb=0.0,
                vram_total_gb=0.0,
                ollama_model_loaded=self._ollama_model_loaded,
            )

        return VRAMStatus(
            current_owner=self._current_owner,
            vram_free_gb=vram_info.free_gb,
            vram_total_gb=vram_info.total_gb,
            ollama_model_loaded=self._ollama_model_loaded,
        )


def get_vram_resource_manager(
    ollama_url: Optional[str] = None,
) -> VRAMResourceManager:
    """
    Récupère l'instance singleton du gestionnaire VRAM.

    Args:
        ollama_url: URL de l'API Ollama (ignoré si instance existe déjà)

    Returns:
        Instance unique de VRAMResourceManager
    """
    return VRAMResourceManager.get_instance(ollama_url)

