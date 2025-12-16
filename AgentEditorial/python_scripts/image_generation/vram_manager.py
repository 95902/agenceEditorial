"""Gestionnaire VRAM hybride pour la génération d'images."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

import httpx
from loguru import logger

# Import conditionnel pour éviter l'import circulaire
if TYPE_CHECKING:
    from python_scripts.image_generation.z_image_generator import ImageModel
else:
    # Import lazy pour éviter l'import circulaire
    ImageModel = None


@dataclass
class VRAMInfo:
    """Informations sur la VRAM."""

    total_gb: float
    used_gb: float
    free_gb: float
    used_percent: float


@dataclass
class GPUProcess:
    """Information sur un processus utilisant la GPU."""

    pid: int
    name: str
    memory_mb: int
    memory_gb: float


class VRAMManager:
    """
    Gestionnaire VRAM hybride pour vérifier et libérer la mémoire GPU.
    """

    def __init__(self) -> None:
        """Initialise le gestionnaire VRAM."""
        self._nvidia_smi_available = self._check_nvidia_smi()

    def _check_nvidia_smi(self) -> bool:
        """Vérifie si nvidia-smi est disponible."""
        try:
            subprocess.run(
                ["nvidia-smi", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("nvidia-smi not available - VRAM management will be limited")
            return False

    def check_available_vram(self) -> Optional[VRAMInfo]:
        """
        Vérifie la VRAM disponible.

        Returns:
            VRAMInfo si nvidia-smi disponible, None sinon
        """
        if not self._nvidia_smi_available:
            return None

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                total_mb = int(parts[0])
                used_mb = int(parts[1])
                free_mb = int(parts[2])

                total_gb = total_mb / 1024
                used_gb = used_mb / 1024
                free_gb = free_mb / 1024
                used_percent = (used_mb / total_mb) * 100 if total_mb > 0 else 0

                return VRAMInfo(
                    total_gb=total_gb,
                    used_gb=used_gb,
                    free_gb=free_gb,
                    used_percent=used_percent,
                )

        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired) as e:
            logger.error("Failed to check VRAM", error=str(e))
            return None

        return None

    def get_gpu_processes(self) -> list[GPUProcess]:
        """
        Liste les processus utilisant la GPU.

        Returns:
            Liste des processus GPU
        """
        if not self._nvidia_smi_available:
            return []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,process_name,used_memory",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

            processes = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(", ")]
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0])
                        name = parts[1]
                        memory_str = parts[2].replace(" MiB", "").replace(" MB", "")
                        memory_mb = int(memory_str)
                        memory_gb = memory_mb / 1024

                        processes.append(
                            GPUProcess(
                                pid=pid,
                                name=name,
                                memory_mb=memory_mb,
                                memory_gb=memory_gb,
                            )
                        )
                    except (ValueError, IndexError):
                        continue

            return processes

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error("Failed to get GPU processes", error=str(e))
            return []

    def free_vram_if_needed(
        self, min_free_gb: float = 2.0, kill_ollama: bool = True
    ) -> int:
        """
        Libère automatiquement la VRAM si nécessaire.

        Args:
            min_free_gb: VRAM minimale libre requise en GB
            kill_ollama: Si True, arrête les processus Ollama qui utilisent beaucoup de VRAM

        Returns:
            Nombre de processus arrêtés
        """
        vram_info = self.check_available_vram()
        if vram_info is None:
            logger.warning("Cannot check VRAM - skipping automatic cleanup")
            return 0

        if vram_info.free_gb >= min_free_gb:
            logger.debug(
                "Sufficient VRAM available",
                free_gb=vram_info.free_gb,
                min_required_gb=min_free_gb,
            )
            return 0

        logger.warning(
            "Insufficient VRAM",
            free_gb=vram_info.free_gb,
            min_required_gb=min_free_gb,
        )

        if not kill_ollama:
            return 0

        # Trouver les processus Ollama qui utilisent beaucoup de VRAM
        processes = self.get_gpu_processes()
        ollama_processes = [
            p for p in processes if "ollama" in p.name.lower() and p.memory_gb >= 1.0
        ]

        if not ollama_processes:
            logger.info("No large Ollama processes found to kill")
            return 0

        killed = 0
        for proc in ollama_processes:
            try:
                # Essayer SIGTERM d'abord (arrêt propre)
                subprocess.run(
                    ["sudo", "kill", "-TERM", str(proc.pid)],
                    check=True,
                    timeout=5,
                    capture_output=True,
                )
                logger.info(
                    "Sent TERM signal to Ollama process",
                    pid=proc.pid,
                    memory_gb=proc.memory_gb,
                )
                killed += 1
            except subprocess.CalledProcessError:
                # Si TERM échoue, essayer KILL
                try:
                    subprocess.run(
                        ["sudo", "kill", "-KILL", str(proc.pid)],
                        check=True,
                        timeout=5,
                        capture_output=True,
                    )
                    logger.info(
                        "Killed Ollama process",
                        pid=proc.pid,
                        memory_gb=proc.memory_gb,
                    )
                    killed += 1
                except subprocess.CalledProcessError as e:
                    logger.warning(
                        "Failed to kill Ollama process",
                        pid=proc.pid,
                        error=str(e),
                    )
            except subprocess.TimeoutExpired:
                logger.warning("Timeout killing Ollama process", pid=proc.pid)

        if killed > 0:
            logger.info(
                "Freed VRAM by killing Ollama processes",
                killed_count=killed,
                expected_free_gb=sum(p.memory_gb for p in ollama_processes[:killed]),
            )

        return killed

    def estimate_model_memory(
        self, model_type, width: int, height: int
    ) -> float:
        """
        Estime la mémoire nécessaire pour générer une image.

        Args:
            model_type: Type de modèle (ImageModel enum)
            width: Largeur en pixels
            height: Hauteur en pixels

        Returns:
            Estimation de la mémoire nécessaire en GB
        """
        # Estimations basées sur l'expérience
        # Note: Avec sequential CPU offload activé, la VRAM utilisée est beaucoup plus faible
        # Ces estimations sont pour la VRAM maximale pendant la génération (pas au repos)
        base_memory = {
            "z-image-turbo": 0.7,  # Avec CPU offload : ~0.6-0.7 GB au repos, ~2-3 GB pendant génération
            "z-image-base": 1.0,  # Estimation similaire
            "flux-schnell": 5.8,  # FLUX sans CPU offload (mesuré précédemment)
        }

        # Extraire la valeur string si c'est un enum
        if hasattr(model_type, 'value'):
            model_key = model_type.value
        else:
            model_key = str(model_type)
        
        base = base_memory.get(model_key, 4.0)

        # Ajustement selon la résolution (approximation)
        # Avec CPU offload, la mémoire pendant génération dépend de la résolution
        resolution_factor = (width * height) / (1024 * 1024)

        # Mémoire additionnelle pour la génération (buffers, activations, temporaires)
        # Pour Z-Image avec CPU offload : ~1.5-2 GB supplémentaires pendant génération
        if model_key == "z-image-turbo" or model_key == "z-image-base":
            # Avec CPU offload, la base est faible mais la génération nécessite plus
            generation_overhead = 1.5 + (resolution_factor * 1.0)  # 1.5-2.5 GB selon résolution
        else:
            # Pour FLUX sans CPU offload, le modèle reste en VRAM
            generation_overhead = 0.5 + (resolution_factor * 0.5)

        total = base + generation_overhead

        return total

    def get_recommended_resolution(
        self, model_type, target_resolution: tuple[int, int] = (768, 768)
    ) -> tuple[int, int]:
        """
        Recommande une résolution basée sur la VRAM disponible.

        Args:
            model_type: Type de modèle à utiliser (ImageModel enum ou string)
            target_resolution: Résolution cible (width, height)

        Returns:
            Résolution recommandée (width, height)
        """
        vram_info = self.check_available_vram()
        if vram_info is None:
            # Si on ne peut pas vérifier, utiliser la résolution cible
            return target_resolution

        # Estimer la mémoire nécessaire pour différentes résolutions
        resolutions = [
            (1024, 1024),
            (768, 768),
            (512, 512),
            (384, 384),
            (256, 256),
        ]

        for width, height in resolutions:
            estimated = self.estimate_model_memory(model_type, width, height)
            # Garder 1 GB de marge
            if estimated + 1.0 <= vram_info.free_gb:
                logger.debug(
                    "Recommended resolution",
                    width=width,
                    height=height,
                    estimated_gb=estimated,
                    free_gb=vram_info.free_gb,
                )
                return (width, height)

        # Si même 256x256 ne passe pas, retourner le minimum
        logger.warning(
            "Very limited VRAM - using minimum resolution",
            free_gb=vram_info.free_gb,
        )
        return (256, 256)

    async def unload_ollama_model(
        self, model: str, ollama_url: str = "http://localhost:11435"
    ) -> bool:
        """
        Décharge un modèle Ollama de la VRAM.

        Args:
            model: Nom du modèle à décharger
            ollama_url: URL de l'API Ollama

        Returns:
            True si succès, False sinon
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Décharger en utilisant /api/generate avec keep_alive=0
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "test",
                        "keep_alive": 0,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                logger.info(
                    "Unloaded Ollama model",
                    model=model,
                    status_code=response.status_code,
                )
                return True

        except httpx.HTTPError as e:
            logger.warning(
                "Failed to unload Ollama model",
                model=model,
                ollama_url=ollama_url,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "Error unloading Ollama model",
                model=model,
                error=str(e),
            )
            return False

    async def get_ollama_loaded_models(
        self, ollama_url: str = "http://localhost:11435"
    ) -> list[str]:
        """
        Récupère la liste des modèles Ollama actuellement chargés.

        Args:
            ollama_url: URL de l'API Ollama

        Returns:
            Liste des noms de modèles chargés
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{ollama_url}/api/ps")
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

        except httpx.HTTPError as e:
            logger.warning(
                "Failed to get Ollama loaded models",
                ollama_url=ollama_url,
                error=str(e),
            )
            return []
        except Exception as e:
            logger.warning(
                "Error getting Ollama loaded models",
                ollama_url=ollama_url,
                error=str(e),
            )
            return []


# Instance globale
_vram_manager_instance: Optional[VRAMManager] = None


def get_vram_manager() -> VRAMManager:
    """Récupère l'instance singleton du gestionnaire VRAM."""
    global _vram_manager_instance
    if _vram_manager_instance is None:
        _vram_manager_instance = VRAMManager()
    return _vram_manager_instance

