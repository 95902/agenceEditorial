"""Générateur d'images Z-Image Turbo avec gestion VRAM et singleton pattern."""

from __future__ import annotations

import hashlib
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from loguru import logger

from python_scripts.config.image_config import IMAGE_CONFIG
from python_scripts.image_generation.exceptions import (
    ModelLoadError,
    PromptError,
    VRAMError,
)
from python_scripts.image_generation.vram_manager import get_vram_manager
from python_scripts.image_generation.vram_resource_manager import get_vram_resource_manager
from python_scripts.image_generation.prompt_builder import ImagePromptBuilderV2

try:
    from diffusers import DiffusionPipeline
    # Import conditionnel pour FLUX (évite les erreurs avec Qwen si transformers est trop ancien)
    try:
        from diffusers import FluxPipeline
    except (ImportError, RuntimeError):
        FluxPipeline = None  # type: ignore
        # Fallback: utiliser AutoPipelineForText2Image en lazy import si nécessaire
        AutoPipelineForText2Image = None  # type: ignore
except ImportError:
    DiffusionPipeline = None  # type: ignore
    FluxPipeline = None  # type: ignore
    AutoPipelineForText2Image = None  # type: ignore
    logger.warning("diffusers not installed - image generation will not work")

# FLUX Schnell utilise FluxPipeline, importé de manière conditionnelle
# pour éviter les erreurs d'import si transformers n'a pas toutes les classes Qwen
try:
    from diffusers import FluxPipeline
except (ImportError, RuntimeError):
    FluxPipeline = None  # type: ignore


class ImageModel(str, Enum):
    """Modèles d'images disponibles."""

    Z_IMAGE_TURBO = "z-image-turbo"  # Par défaut, 8 steps
    Z_IMAGE_BASE = "z-image-base"  # Pour fine-tuning
    FLUX_SCHNELL = "flux-schnell"  # Fallback, 4 steps


class ZImageGenerator:
    """
    Générateur d'images basé sur Z-Image Turbo.
    Singleton pour éviter de recharger le modèle à chaque appel.
    
    DEPRECATED: Ce générateur local est remplacé par Ideogram cloud.
    Conservé pour fallback uniquement si IMAGE_PROVIDER=local.
    
    Utilisez ImageGenerator (qui utilise Ideogram par défaut) pour de nouvelles implémentations.
    """

    _instance: Optional[ZImageGenerator] = None
    _lock = threading.Lock()

    def __init__(self, model: ImageModel = ImageModel.Z_IMAGE_TURBO) -> None:
        """
        Initialise le générateur avec le modèle spécifié.

        Args:
            model: Modèle à utiliser (Z_IMAGE_TURBO par défaut, plus léger que FLUX)
        """
        if ZImageGenerator._instance is not None:
            raise RuntimeError(
                "ZImageGenerator is a singleton. Use get_instance() instead."
            )

        self.model_type = model
        self._pipeline: Optional[Any] = None
        self._is_loaded = False
        self._last_prompt_hash: Optional[str] = None
        self._last_generation_time: Optional[float] = None
        self._output_dir = Path(IMAGE_CONFIG.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Configuration du modèle selon le type
        self._model_configs = {
            ImageModel.Z_IMAGE_TURBO: {
                "model_id": "Tongyi-MAI/Z-Image-Turbo",
                "default_steps": 8,
            },
            ImageModel.Z_IMAGE_BASE: {
                "model_id": "Tongyi-MAI/Z-Image-Base",
                "default_steps": 20,
            },
            ImageModel.FLUX_SCHNELL: {
                "model_id": "black-forest-labs/FLUX.1-schnell",
                "default_steps": 4,
            },
        }

        ZImageGenerator._instance = self

    @classmethod
    def get_instance(
        cls, model: ImageModel = ImageModel.Z_IMAGE_TURBO
    ) -> ZImageGenerator:
        """
        Récupère l'instance singleton du générateur.

        Args:
            model: Modèle à utiliser (ignoré si instance existe déjà)

        Returns:
            Instance unique de ZImageGenerator
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(model)
        return cls._instance

    def _ensure_sufficient_vram(self) -> None:
        """
        Vérifie et libère la VRAM si nécessaire avant de charger le modèle.
        """
        vram_manager = get_vram_manager()
        vram_info = vram_manager.check_available_vram()

        if vram_info is None:
            logger.warning("Cannot check VRAM - proceeding anyway")
            return

        # Estimer la mémoire nécessaire pour ce modèle
        estimated_memory = vram_manager.estimate_model_memory(
            self.model_type, width=1024, height=1024
        )

        # Marge de sécurité : besoin de 1 GB supplémentaire
        min_required = estimated_memory + 1.0

        logger.info(
            "Checking VRAM before model load",
            model_type=self.model_type.value,
            estimated_memory_gb=estimated_memory,
            free_vram_gb=vram_info.free_gb,
            min_required_gb=min_required,
        )

        if vram_info.free_gb < min_required:
            logger.warning(
                "Insufficient VRAM - attempting to free memory",
                free_gb=vram_info.free_gb,
                required_gb=min_required,
            )

            # Libérer la VRAM automatiquement
            killed = vram_manager.free_vram_if_needed(
                min_free_gb=min_required, kill_ollama=True
            )

            if killed > 0:
                # Attendre un peu pour que la VRAM soit libérée
                import time

                time.sleep(2)

                # Vérifier à nouveau
                vram_info = vram_manager.check_available_vram()
                if vram_info and vram_info.free_gb < min_required:
                    logger.warning(
                        "Still insufficient VRAM after cleanup",
                        free_gb=vram_info.free_gb,
                        required_gb=min_required,
                    )
            else:
                logger.warning(
                    "Could not free enough VRAM - generation may fail",
                    free_gb=vram_info.free_gb,
                    required_gb=min_required,
                )

    def _load_model(self) -> None:
        """Charge le modèle en mémoire GPU."""
        if self._is_loaded:
            return

        if DiffusionPipeline is None:
            raise ModelLoadError(
                "diffusers library not installed. Install with: pip install diffusers"
            )

        if not torch.cuda.is_available():
            raise ModelLoadError("CUDA not available. GPU required for Z-Image.")

        # Vérifier et libérer la VRAM avant de charger
        self._ensure_sufficient_vram()
        
        # Acquérir la VRAM via VRAMResourceManager (décharge Ollama si nécessaire)
        # Utiliser une nouvelle boucle dans un thread pour éviter les conflits avec la boucle existante
        import asyncio
        
        def run_in_new_loop():
            """Exécute la coroutine dans une nouvelle boucle d'événements."""
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result = new_loop.run_until_complete(
                    get_vram_resource_manager().acquire_for_zimage()
                )
                return result
            finally:
                new_loop.close()
        
        # Exécuter dans un thread pour éviter de bloquer ou de causer des conflits
        result_container = {"result": None, "exception": None}
        
        def run_async():
            try:
                result_container["result"] = run_in_new_loop()
            except Exception as e:
                result_container["exception"] = e
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        thread.join(timeout=30)  # Timeout de 30 secondes
        
        if thread.is_alive():
            logger.warning("VRAM acquisition thread still running after timeout - proceeding anyway")
        
        if result_container["exception"]:
            raise RuntimeError(f"Failed to acquire VRAM: {result_container['exception']}")
        
        if result_container["result"] is None:
            raise RuntimeError("Failed to acquire VRAM for Z-Image (timeout or failed)")
        
        if not result_container["result"]:
            raise RuntimeError("Failed to acquire VRAM for Z-Image (VRAMResourceManager returned False)")

        try:
            config = self._model_configs[self.model_type]
            model_id = config["model_id"]

            logger.info("Loading image generation model", model_id=model_id, model_type=self.model_type.value)

            # Déterminer le dtype
            dtype_map = {
                "bfloat16": torch.bfloat16,
                "float16": torch.float16,
                "float32": torch.float32,
            }
            torch_dtype = dtype_map.get(IMAGE_CONFIG.torch_dtype, torch.bfloat16)

            # Charger le pipeline
            # FLUX Schnell utilise AutoPipelineForText2Image, Z-Image utilise DiffusionPipeline
            variant: Any = None
            if torch_dtype is torch.float16:
                variant = "fp16"

            # Nettoyer la VRAM avant de charger un nouveau modèle
            torch.cuda.empty_cache()
            
            if self.model_type == ImageModel.FLUX_SCHNELL:
                # FLUX Schnell utilise FluxPipeline (import lazy pour éviter erreurs Qwen)
                if FluxPipeline is not None:
                    self._pipeline = FluxPipeline.from_pretrained(
                        model_id,
                        torch_dtype=torch_dtype,
                    )
                else:
                    # Fallback: import lazy de AutoPipelineForText2Image
                    try:
                        from diffusers import AutoPipelineForText2Image
                        self._pipeline = AutoPipelineForText2Image.from_pretrained(
                            model_id,
                            torch_dtype=torch_dtype,
                        )
                    except (ImportError, RuntimeError) as e:
                        raise ModelLoadError(
                            f"FluxPipeline not available and AutoPipelineForText2Image failed: {e}. "
                            "Install diffusers >= 0.30.0 with FLUX support"
                        ) from e
            else:
                # Z-Image utilise DiffusionPipeline standard
                if DiffusionPipeline is None:
                    raise ModelLoadError("DiffusionPipeline not available. Install diffusers >= 0.30.0")
                
                # Charger le modèle (sans le déplacer sur GPU immédiatement si CPU offload est activé)
                self._pipeline = DiffusionPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch_dtype,
                    variant=variant,
                )

            # Optimisations pour GPU (appliquées après chargement)
            if IMAGE_CONFIG.enable_model_cpu_offload:
                # Utiliser sequential CPU offload (plus efficace que model CPU offload)
                # Il charge les composants sur GPU un par un pendant la génération, puis les remet sur CPU
                try:
                    self._pipeline.enable_sequential_cpu_offload()
                    logger.info(
                        "Sequential CPU offload enabled",
                        model_type=self.model_type.value,
                        note="Models will be loaded on CPU and moved to GPU only during generation",
                    )
                except (AttributeError, TypeError) as e:
                    # Fallback sur model CPU offload si sequential n'est pas disponible
                    logger.warning(
                        "Sequential CPU offload not available, using model CPU offload",
                        error=str(e),
                    )
                    try:
                        self._pipeline.enable_model_cpu_offload()
                        logger.info("Model CPU offload enabled")
                    except (AttributeError, TypeError) as e2:
                        logger.error(
                            "CPU offload not available for this pipeline",
                            error=str(e2),
                        )
                        # En dernier recours, déplacer sur GPU mais avec attention slicing
                        self._pipeline = self._pipeline.to("cuda")
            else:
                # Si pas de CPU offload, déplacer sur GPU
                self._pipeline = self._pipeline.to("cuda")
                
            if IMAGE_CONFIG.enable_attention_slicing:
                self._pipeline.enable_attention_slicing(slice_size="max")
            if IMAGE_CONFIG.enable_vae_tiling:
                self._pipeline.enable_vae_slicing()

            self._is_loaded = True
            logger.info("Image generation model loaded successfully", model_id=model_id, model_type=self.model_type.value)

        except Exception as e:
            logger.error("Failed to load image generation model", error=str(e), model_id=model_id, model_type=self.model_type.value)
            raise ModelLoadError(f"Failed to load model {model_id}: {e}") from e

    def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: Optional[int] = None,
        guidance_scale: float = 4.5,
        seed: Optional[int] = None,
        filename: Optional[str] = None,
        return_metadata: bool = False,
    ) -> Path | tuple[Path, dict[str, Any]]:
        """
        Génère une image depuis un prompt.

        Args:
            prompt: Description de l'image à générer
            negative_prompt: Éléments à éviter (optionnel)
            width: Largeur en pixels (défaut 1024)
            height: Hauteur en pixels (défaut 1024)
            steps: Nombre d'étapes (défaut selon modèle)
            guidance_scale: Échelle de guidage (défaut 4.5)
            seed: Graine pour reproductibilité (optionnel)
            filename: Nom du fichier de sortie (optionnel)

        Returns:
            Path vers l'image générée

        Raises:
            VRAMError: Si mémoire GPU insuffisante
            PromptError: Si prompt invalide
        """
        # Validation
        if not prompt or not prompt.strip():
            raise PromptError("Prompt cannot be empty")

        # Valider dimensions (multiples de 8)
        if width % 8 != 0 or height % 8 != 0:
            raise PromptError(f"Width and height must be multiples of 8 (got {width}x{height})")

        # Charger le modèle si nécessaire
        if not self._is_loaded:
            self._load_model()

        # Steps par défaut selon modèle
        if steps is None:
            config = self._model_configs[self.model_type]
            steps = config["default_steps"]

        # Générer hash du prompt pour nom de fichier
        prompt_hash = hashlib.md5(
            f"{prompt}_{width}_{height}_{steps}_{guidance_scale}_{seed}".encode()
        ).hexdigest()[:8]
        self._last_prompt_hash = prompt_hash

        # Nom de fichier
        if filename is None:
            filename = f"z_image_{prompt_hash}.png"
        if not filename.endswith(".png"):
            filename += ".png"

        output_path = self._output_dir / filename

        # Générer l'image
        start_time = time.time()
        try:
            # Générer avec le pipeline
            generator = None
            if seed is not None:
                generator = torch.Generator(device="cuda").manual_seed(seed)

            result = self._pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )

            # Sauvegarder l'image
            image = result.images[0]
            image.save(output_path)

            generation_time = time.time() - start_time
            self._last_generation_time = generation_time

            if IMAGE_CONFIG.log_generation_time:
                logger.info(
                    "Image generated successfully",
                    path=str(output_path),
                    prompt=prompt[:50],
                    generation_time_seconds=generation_time,
                    width=width,
                    height=height,
                    steps=steps,
                )

            # Nettoyer la VRAM après génération
            torch.cuda.empty_cache()
            
            # Si CPU offload est activé, forcer le nettoyage des activations
            if IMAGE_CONFIG.enable_model_cpu_offload:
                # Avec sequential CPU offload, les modèles sont déjà sur CPU
                # Mais on peut forcer un nettoyage plus agressif
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Attendre que toutes les opérations CUDA soient terminées

            if return_metadata:
                metadata = {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "guidance_scale": guidance_scale,
                    "seed": seed,
                    "generation_time_seconds": generation_time,
                    "model_type": self.model_type.value,
                }
                return output_path, metadata

            return output_path

        except torch.cuda.OutOfMemoryError as e:
            logger.error("VRAM out of memory", error=str(e))
            torch.cuda.empty_cache()
            raise VRAMError(
                f"GPU out of memory. Try reducing width/height or steps. Error: {e}"
            ) from e
        except Exception as e:
            logger.error("Image generation failed", error=str(e), prompt=prompt[:50])
            torch.cuda.empty_cache()
            raise

    def generate_batch(
        self, prompts: list[str], **kwargs: Any
    ) -> list[Path]:
        """
        Génère plusieurs images en batch.

        Args:
            prompts: Liste de prompts
            **kwargs: Paramètres passés à generate()

        Returns:
            Liste de paths vers les images générées
        """
        results = []
        for prompt in prompts:
            try:
                image_path = self.generate(prompt, **kwargs)
                results.append(image_path)
            except Exception as e:
                logger.error("Batch generation failed for prompt", prompt=prompt[:50], error=str(e))
                # Continue avec les autres prompts
        return results

    def generate_with_retry(
        self,
        prompt: str,
        max_retries: int = 4,
        **kwargs: Any,
    ) -> Path:
        """
        Génère avec retry automatique en cas d'échec VRAM.
        Utilise VRAMManager pour déterminer les résolutions optimales.

        Args:
            prompt: Prompt de l'image
            max_retries: Nombre maximum de tentatives
            **kwargs: Paramètres passés à generate()

        Returns:
            Path vers l'image générée

        Raises:
            VRAMError: Si toutes les tentatives échouent
        """
        vram_manager = get_vram_manager()

        # Obtenir la résolution recommandée basée sur la VRAM disponible
        initial_width = kwargs.get("width", 768)
        initial_height = kwargs.get("height", 768)
        recommended = vram_manager.get_recommended_resolution(
            self.model_type, (initial_width, initial_height)
        )

        # Tentatives avec réduction progressive de résolution
        retry_configs = [
            {"width": recommended[0], "height": recommended[1]},
            {"width": 512, "height": 512},
            {"width": 384, "height": 384},
            {"width": 256, "height": 256},  # Dernière tentative très basse
        ]

        last_error = None
        for attempt in range(min(max_retries, len(retry_configs))):
            try:
                # Utiliser la config de retry
                if attempt > 0:
                    kwargs.update(retry_configs[attempt])
                    logger.warning(
                        "Retrying with reduced resolution",
                        attempt=attempt + 1,
                        width=kwargs["width"],
                        height=kwargs["height"],
                    )
                else:
                    # Première tentative avec la résolution recommandée
                    kwargs.update(retry_configs[0])
                    logger.info(
                        "Starting generation with recommended resolution",
                        width=kwargs["width"],
                        height=kwargs["height"],
                    )

                # Nettoyer la VRAM avant chaque tentative
                torch.cuda.empty_cache()
                time.sleep(1)  # Laisser le temps à CUDA de libérer

                return self.generate(prompt, **kwargs)

            except VRAMError as e:
                last_error = e
                logger.warning(
                    "VRAM error on attempt",
                    attempt=attempt + 1,
                    width=kwargs.get("width"),
                    height=kwargs.get("height"),
                    error=str(e)[:100],
                )

                # Essayer de libérer plus de VRAM avant le prochain retry
                if attempt < min(max_retries, len(retry_configs)) - 1:
                    vram_manager.free_vram_if_needed(min_free_gb=2.0, kill_ollama=True)
                    torch.cuda.empty_cache()
                    time.sleep(2)  # Attendre un peu avant retry
                else:
                    raise

        raise last_error or VRAMError("All retry attempts failed")

    def generate_with_profile(
        self,
        site_profile: dict[str, Any],
        topic: str,
        style: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Génère une image basée sur le profil éditorial d'un site.

        Args:
            site_profile: Dictionnaire contenant le profil éditorial du site
            topic: Sujet de l'article pour lequel générer l'image
            style: Style optionnel (sinon déterminé depuis le profil)
            filename: Nom du fichier de sortie (optionnel)

        Returns:
            Path vers l'image générée
        """
        # Construire le prompt depuis le profil éditorial
        prompt_builder = ImagePromptBuilderV2()
        prompt_result = prompt_builder.build_from_editorial_profile(
            site_profile=site_profile,
            article_topic=topic,
        )

        # Si un style est spécifié, l'utiliser
        if style:
            from python_scripts.image_generation.prompt_builder import ImageStyle
            style_enum = ImageStyle(style) if style in [s.value for s in ImageStyle] else None
            if style_enum:
                prompt_result = prompt_builder.build_professional_prompt(
                    subject=f"{topic} concept illustration",
                    style=style_enum,
                    avoid_text=True,
                )

        # Générer l'image avec les paramètres du prompt
        result = self.generate(
            prompt=prompt_result["prompt"],
            negative_prompt=prompt_result.get("negative_prompt"),
            width=prompt_result.get("recommended_size", (768, 768))[0],
            height=prompt_result.get("recommended_size", (768, 768))[1],
            steps=prompt_result.get("steps", 12),
            guidance_scale=prompt_result.get("guidance_scale", 7.5),
            filename=filename,
        )

        return result

    def unload_model(self) -> None:
        """Décharge le modèle de la VRAM pour libérer la mémoire."""
        if self._pipeline is not None:
            # Si CPU offload est activé, les modèles sont déjà sur CPU
            # Mais on doit quand même nettoyer les références
            try:
                # Essayer de déplacer explicitement sur CPU si possible
                if hasattr(self._pipeline, 'to'):
                    self._pipeline = self._pipeline.to("cpu")
            except Exception:
                pass  # Ignorer les erreurs si le modèle est déjà sur CPU
            
            del self._pipeline
            self._pipeline = None
            self._is_loaded = False
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.info("Z-Image model unloaded from VRAM")
            
            # Notifier VRAMResourceManager que Z-Image est déchargé
            # (optionnel, car release_all peut être appelé explicitement)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Retourne les informations sur le modèle chargé.

        Returns:
            Dictionnaire avec infos du modèle
        """
        config = self._model_configs[self.model_type]
        return {
            "model_type": self.model_type.value,
            "model_id": config["model_id"],
            "is_loaded": self._is_loaded,
            "default_steps": config["default_steps"],
            "cuda_available": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }

    @property
    def is_loaded(self) -> bool:
        """Vérifie si le modèle est chargé."""
        return self._is_loaded

    @property
    def last_prompt_hash(self) -> Optional[str]:
        """Retourne le hash du dernier prompt généré."""
        return self._last_prompt_hash

    @property
    def last_generation_time(self) -> Optional[float]:
        """Retourne le temps de génération de la dernière image."""
        return self._last_generation_time

