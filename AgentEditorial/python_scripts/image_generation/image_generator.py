"""Générateur d'images unifié utilisant Ideogram (cloud) ou Z-Image (local)."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from python_scripts.config.settings import settings
from python_scripts.image_generation.exceptions import IdeogramAPIError
from python_scripts.image_generation.ideogram_client import (
    IDEOGRAM_ASPECT_RATIOS,
    IdeogramClient,
)
from python_scripts.image_generation.prompt_builder import (
    ImagePromptBuilderV2,
    ImageStyle,
    IdeogramPromptResult,
)


@dataclass
class GenerationResult:
    """Résultat d'une génération d'image."""

    success: bool
    image_path: Path
    prompt_used: str  # Prompt final utilisé (amélioré par magic_prompt si Ideogram)
    negative_prompt: Optional[str]
    generation_time: float
    provider: str  # "ideogram" ou "local"
    metadata: dict[str, Any]  # Infos supplémentaires (resolution, style_type, aspect_ratio, model, magic_prompt)
    error: Optional[str] = None


@dataclass
class VariantGenerationResult:
    """Résultat d'une génération avec variantes."""

    success: bool
    variants: list[GenerationResult]  # Liste des N images
    selected_index: Optional[int] = None  # Index sélectionné (si auto-select)
    total_generation_time: float = 0.0
    prompt_used: str = ""
    variant_group_id: str = ""  # UUID pour grouper les variantes en BDD
    error: Optional[str] = None


class ImageGenerator:
    """
    Générateur d'images unifié.
    
    Utilise Ideogram (cloud) par défaut, avec fallback optionnel vers Z-Image (local).
    """

    _instance: Optional[ImageGenerator] = None
    _lock = threading.Lock()

    def __init__(self, provider: str = "ideogram") -> None:
        """
        Initialise le générateur.

        Args:
            provider: Provider à utiliser ("ideogram" ou "local")
        """
        if ImageGenerator._instance is not None:
            raise RuntimeError(
                "ImageGenerator is a singleton. Use get_instance() instead."
            )

        self.provider = provider or settings.image_provider
        if self.provider not in ("ideogram", "local"):
            raise ValueError(f"Invalid provider: {self.provider}. Must be 'ideogram' or 'local'")

        self._ideogram_client: Optional[IdeogramClient] = None
        self._prompt_builder = ImagePromptBuilderV2()
        self._output_dir = Path(settings.article_images_dir or "outputs/images")
        self._output_dir.mkdir(parents=True, exist_ok=True)

        ImageGenerator._instance = self

    @classmethod
    def get_instance(cls, provider: Optional[str] = None) -> ImageGenerator:
        """
        Retourne l'instance singleton du générateur.

        Args:
            provider: Provider à utiliser (utilisé uniquement à la première création)

        Returns:
            Instance du générateur
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(provider=provider or settings.image_provider)
        return cls._instance

    def _get_ideogram_client(self) -> IdeogramClient:
        """
        Retourne le client Ideogram, en le créant si nécessaire.
        
        Si la clé API a changé dans settings, réinitialise le singleton.
        """
        # Vérifier si la clé API a changé
        current_key = settings.ideogram_api_key
        if self._ideogram_client is not None and self._ideogram_client.api_key != current_key:
            # La clé a changé, réinitialiser
            logger.info("API key changed, resetting IdeogramClient singleton")
            IdeogramClient.reset_instance()
            self._ideogram_client = None
        
        if self._ideogram_client is None:
            self._ideogram_client = IdeogramClient.get_instance()
        return self._ideogram_client

    def _generate_filename(self, prompt: str, provider: str) -> str:
        """Génère un nom de fichier unique basé sur le prompt."""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        timestamp = int(time.time())
        return f"{provider}_image_{prompt_hash}_{timestamp}.png"

    async def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        style: str = "corporate_flat",
        aspect_ratio: str = "1:1",
        output_filename: Optional[str] = None,
    ) -> GenerationResult:
        """
        Génère une image depuis un prompt.

        Args:
            prompt: Description de l'image
            negative_prompt: Prompt négatif (optionnel)
            style: Style visuel (corporate_flat, corporate_3d, etc.)
            aspect_ratio: Ratio d'aspect ("1:1", "4:3", "16:9", etc.)
            output_filename: Nom du fichier de sortie (auto-généré si None)

        Returns:
            GenerationResult avec les détails de la génération
        """
        start_time = time.time()

        try:
            if self.provider == "ideogram":
                return await self._generate_with_ideogram(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    style=style,
                    aspect_ratio=aspect_ratio,
                    output_filename=output_filename,
                    start_time=start_time,
                )
            else:  # local
                return await self._generate_with_local(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    style=style,
                    output_filename=output_filename,
                    start_time=start_time,
                )

        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(
                "Image generation failed",
                provider=self.provider,
                error=str(e),
                generation_time=generation_time,
            )

            # Fallback vers local si Ideogram échoue et fallback activé
            # ou si la clé API est manquante (convertisse en IdeogramAPIError)
            is_ideogram_error = isinstance(e, IdeogramAPIError) or (
                isinstance(e, ValueError) and "API key" in str(e)
            )
            
            # Fallback automatique si clé API manquante ET fallback activé
            should_fallback = (
                self.provider == "ideogram"
                and settings.image_fallback_to_local
                and is_ideogram_error
            )
            
            if should_fallback:
                logger.info(
                    "Falling back to local provider after Ideogram failure",
                    error=str(e),
                )
                try:
                    return await self._generate_with_local(
                        prompt=prompt,
                        negative_prompt=negative_prompt,
                        style=style,
                        output_filename=output_filename,
                        start_time=start_time,
                    )
                except Exception as fallback_error:
                    logger.error("Local fallback also failed", error=str(fallback_error))
                    return GenerationResult(
                        success=False,
                        image_path=Path(""),
                        prompt_used=prompt,
                        negative_prompt=negative_prompt,
                        generation_time=generation_time,
                        provider="local",
                        metadata={},
                        error=f"Ideogram failed: {str(e)}, Local fallback failed: {str(fallback_error)}",
                    )

            # Construire un message d'erreur plus informatif
            error_message = str(e)
            # Ajouter suggestion de fallback si clé API manquante et fallback désactivé
            # Éviter la redondance si le message contient déjà ces instructions
            if "API key" in error_message and not settings.image_fallback_to_local:
                if "IMAGE_FALLBACK_TO_LOCAL" not in error_message:
                    # Le message n'a pas encore de suggestion de fallback, l'ajouter
                    if "Set IDEOGRAM_API_KEY" not in error_message:
                        error_message += (
                            f". Set IDEOGRAM_API_KEY environment variable or "
                            f"enable fallback with IMAGE_FALLBACK_TO_LOCAL=true"
                        )
                    else:
                        # Le message mentionne déjà IDEOGRAM_API_KEY, juste ajouter l'option fallback
                        # Nettoyer les points multiples en fin de phrase avant d'ajouter
                        error_message = error_message.rstrip('. ')
                        error_message += (
                            f", or enable fallback with IMAGE_FALLBACK_TO_LOCAL=true"
                        )
            
            return GenerationResult(
                success=False,
                image_path=Path(""),
                prompt_used=prompt,
                negative_prompt=negative_prompt,
                generation_time=generation_time,
                provider=self.provider,
                metadata={},
                error=error_message,
            )

    async def generate_with_variants(
        self,
        prompt: str,
        num_variants: int = 3,
        negative_prompt: Optional[str] = None,
        style: str = "corporate_flat",
        aspect_ratio: str = "1:1",
        output_prefix: Optional[str] = None,
        auto_select: bool = False,
    ) -> VariantGenerationResult:
        """
        Génère plusieurs variantes d'une image.

        Args:
            prompt: Prompt de base
            num_variants: Nombre de variantes à générer (défaut: 3)
            negative_prompt: Prompt négatif optionnel
            style: Style visuel (défaut: corporate_flat)
            aspect_ratio: Ratio d'aspect (défaut: 1:1)
            output_prefix: Préfixe pour les noms de fichiers (optionnel)
            auto_select: Si True, sélectionne automatiquement la meilleure via critique IA

        Returns:
            VariantGenerationResult avec toutes les variantes
        """
        start_time = time.time()
        variant_group_id = str(uuid.uuid4())

        logger.info(
            "Generating image variants",
            prompt=prompt[:100],
            num_variants=num_variants,
            style=style,
            variant_group_id=variant_group_id,
        )

        try:
            # Générer un nom de base pour les fichiers
            if output_prefix is None:
                prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
                timestamp = int(time.time())
                output_prefix = f"ideogram_image_{prompt_hash}_{timestamp}"

            # Construire le prompt optimisé pour Ideogram
            try:
                style_enum = ImageStyle(style)
            except ValueError:
                logger.warning(f"Unknown style '{style}', using CORPORATE_FLAT")
                style_enum = ImageStyle.CORPORATE_FLAT

            ideogram_aspect = IDEOGRAM_ASPECT_RATIOS.get(aspect_ratio, "1x1")

            ideogram_prompt_result: IdeogramPromptResult = (
                self._prompt_builder.build_ideogram_prompt(
                    subject=prompt,
                    style=style_enum,
                    include_negative=negative_prompt is None,
                    aspect_ratio=ideogram_aspect,
                )
            )

            final_negative_prompt = negative_prompt or ideogram_prompt_result.negative_prompt

            # Générer les variantes en parallèle
            if self.provider == "ideogram":
                client = self._get_ideogram_client()
                ideogram_results = await client.generate_variants(
                    prompt=ideogram_prompt_result.prompt,
                    num_variants=num_variants,
                    negative_prompt=final_negative_prompt,
                    style_type=ideogram_prompt_result.style_type,
                    aspect_ratio=ideogram_aspect,
                    rendering_speed="TURBO",
                    magic_prompt="AUTO",
                )

                # Télécharger et sauvegarder chaque variante
                variants: list[GenerationResult] = []
                output_dir = Path(settings.article_images_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                for i, ideogram_result in enumerate(ideogram_results):
                    variant_number = i + 1
                    filename = f"{output_prefix}_v{variant_number}.png"
                    output_path = output_dir / filename

                    try:
                        # Télécharger l'image
                        downloaded_path = await client.download_image(
                            ideogram_result.url, output_path
                        )

                        metadata = {
                            "provider": "ideogram",
                            "style_type": ideogram_prompt_result.style_type,
                            "aspect_ratio": aspect_ratio,
                            "resolution": ideogram_result.resolution,
                            "ideogram_url": ideogram_result.url,
                            "magic_prompt": ideogram_result.prompt,
                            "variant_number": variant_number,
                        }

                        variants.append(
                            GenerationResult(
                                success=True,
                                image_path=downloaded_path,
                                prompt_used=ideogram_result.prompt,
                                negative_prompt=final_negative_prompt,
                                generation_time=ideogram_result.generation_time,
                                provider="ideogram",
                                metadata=metadata,
                            )
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to download variant",
                            variant_number=variant_number,
                            error=str(e),
                        )
                        variants.append(
                            GenerationResult(
                                success=False,
                                image_path=Path(""),
                                prompt_used=ideogram_prompt_result.prompt,
                                negative_prompt=final_negative_prompt,
                                generation_time=0.0,
                                provider="ideogram",
                                metadata={"variant_number": variant_number},
                                error=f"Download failed: {str(e)}",
                            )
                        )

                # Filtrer les variantes réussies
                successful_variants = [v for v in variants if v.success]

                if not successful_variants:
                    raise Exception("All variant generations failed")

                # Auto-sélection via critique IA si demandée
                selected_index: Optional[int] = None
                if auto_select and successful_variants:
                    from python_scripts.image_generation.image_critic import ImageCritic

                    critic = ImageCritic()
                    best_score = -1
                    best_index = 0

                    for i, variant in enumerate(successful_variants):
                        try:
                            critique_result = await critic.evaluate(variant.image_path)
                            if critique_result.score_total > best_score:
                                best_score = critique_result.score_total
                                best_index = i
                        except Exception as e:
                            logger.warning(
                                "Failed to critique variant",
                                variant_index=i,
                                error=str(e),
                            )

                    selected_index = best_index
                    logger.info(
                        "Auto-selected best variant",
                        selected_index=selected_index,
                        score=best_score,
                    )

                total_time = time.time() - start_time

                return VariantGenerationResult(
                    success=True,
                    variants=variants,
                    selected_index=selected_index,
                    total_generation_time=total_time,
                    prompt_used=ideogram_prompt_result.prompt,
                    variant_group_id=variant_group_id,
                )
            else:
                # Fallback local non supporté pour les variantes
                raise NotImplementedError(
                    "Variant generation is only supported with Ideogram provider"
                )

        except Exception as e:
            import traceback
            total_time = time.time() - start_time
            error_traceback = traceback.format_exc()
            logger.error(
                "Variant generation failed",
                error=str(e),
                error_type=type(e).__name__,
                generation_time=total_time,
                traceback=error_traceback,
            )
            return VariantGenerationResult(
                success=False,
                variants=[],
                total_generation_time=total_time,
                prompt_used=prompt,
                variant_group_id=variant_group_id,
                error=str(e),
            )

    async def _generate_with_ideogram(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        style: str,
        aspect_ratio: str,
        output_filename: Optional[str],
        start_time: float,
    ) -> GenerationResult:
        """Génère une image avec Ideogram."""
        # Vérifier si la clé API est disponible avant de continuer
        try:
            client = self._get_ideogram_client()
        except ValueError as e:
            # Clé API manquante - convertir en IdeogramAPIError pour déclencher le fallback
            raise IdeogramAPIError(f"Missing API key: {str(e)}") from e
        
        # Convertir le style string en ImageStyle enum
        try:
            style_enum = ImageStyle(style)
        except ValueError:
            logger.warning(f"Unknown style '{style}', using CORPORATE_FLAT")
            style_enum = ImageStyle.CORPORATE_FLAT

        # Convertir aspect_ratio string en format Ideogram v3 (1x1, 4x3, etc.)
        ideogram_aspect = IDEOGRAM_ASPECT_RATIOS.get(aspect_ratio, "1x1")

        # Construire le prompt optimisé pour Ideogram
        ideogram_prompt_result: IdeogramPromptResult = (
            self._prompt_builder.build_ideogram_prompt(
                subject=prompt,
                style=style_enum,
                include_negative=negative_prompt is None,
                aspect_ratio=ideogram_aspect,
            )
        )

        # Utiliser le negative_prompt fourni ou celui du builder
        final_negative_prompt = negative_prompt or ideogram_prompt_result.negative_prompt

        # Générer l'image avec Ideogram v3
        # Note: v3 n'a plus de paramètre "model", utilise rendering_speed à la place
        ideogram_result = await client.generate(
            prompt=ideogram_prompt_result.prompt,
            negative_prompt=final_negative_prompt,
            style_type=ideogram_prompt_result.style_type,
            aspect_ratio=ideogram_aspect,
            rendering_speed="TURBO",  # TURBO pour rapide, STANDARD pour meilleure qualité
            magic_prompt="AUTO",  # Auto-amélioration du prompt
        )

        # Générer le nom de fichier si non fourni
        if output_filename is None:
            output_filename = self._generate_filename(
                ideogram_result.prompt, provider="ideogram"
            )

        output_path = self._output_dir / output_filename

        # Télécharger l'image
        await client.download_image(ideogram_result.url, output_path)

        generation_time = time.time() - start_time

        return GenerationResult(
            success=True,
            image_path=output_path,
            prompt_used=ideogram_result.prompt,  # Prompt amélioré par magic_prompt
            negative_prompt=final_negative_prompt,
            generation_time=generation_time,
            provider="ideogram",
            metadata={
                "resolution": ideogram_result.resolution,
                "style_type": ideogram_prompt_result.style_type,
                "aspect_ratio": aspect_ratio,
                "rendering_speed": "TURBO",  # v3 utilise rendering_speed au lieu de model
                "magic_prompt": ideogram_result.prompt,  # Prompt amélioré
                "original_prompt": prompt,  # Prompt original
                "ideogram_url": ideogram_result.url,  # URL originale Ideogram
            },
        )

    async def _generate_with_local(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        style: str,
        output_filename: Optional[str],
        start_time: float,
    ) -> GenerationResult:
        """Génère une image avec Z-Image local (fallback)."""
        from python_scripts.image_generation import ZImageGenerator, ImageModel

        # Construire le prompt pour Z-Image
        try:
            style_enum = ImageStyle(style)
        except ValueError:
            style_enum = ImageStyle.CORPORATE_FLAT

        prompt_result = self._prompt_builder.build_professional_prompt(
            subject=prompt,
            style=style_enum,
        )

        # Utiliser le negative_prompt fourni ou celui du builder
        final_negative_prompt = negative_prompt or prompt_result["negative_prompt"]

        # Générer l'image avec Z-Image
        generator = ZImageGenerator.get_instance(ImageModel.Z_IMAGE_TURBO)

        # Générer le nom de fichier si non fourni
        if output_filename is None:
            output_filename = self._generate_filename(prompt, provider="local")

        output_path = self._output_dir / output_filename

        # Z-Image.generate() est synchrone, donc on l'exécute dans un thread
        # ou on attend qu'il devienne async. Pour l'instant, on suppose qu'il est sync.
        try:
            # Note: ZImageGenerator.generate() retourne un Path
            generated_path = generator.generate(
                prompt=prompt_result["prompt"],
                negative_prompt=final_negative_prompt,
                width=768,
                height=768,
                steps=prompt_result["steps"],
                guidance_scale=prompt_result["guidance_scale"],
            )

            # Si le chemin généré est différent, copier ou renommer
            if generated_path != output_path:
                import shutil
                shutil.copy2(generated_path, output_path)

        except Exception as e:
            generation_time = time.time() - start_time
            raise Exception(f"Z-Image generation failed: {str(e)}") from e

        generation_time = time.time() - start_time

        return GenerationResult(
            success=True,
            image_path=output_path,
            prompt_used=prompt_result["prompt"],
            negative_prompt=final_negative_prompt,
            generation_time=generation_time,
            provider="local",
            metadata={
                "width": 768,
                "height": 768,
                "steps": prompt_result["steps"],
                "guidance_scale": prompt_result["guidance_scale"],
                "style": style,
            },
        )

    async def generate_from_profile(
        self,
        site_profile: dict[str, Any],
        article_topic: str,
        style: Optional[str] = None,
    ) -> GenerationResult:
        """
        Génère une image depuis un profil éditorial.

        Args:
            site_profile: Profil éditorial du site
            article_topic: Sujet de l'article
            style: Style visuel (optionnel, déterminé depuis le profil si None)

        Returns:
            GenerationResult avec les détails de la génération
        """
        # Construire le prompt depuis le profil
        prompt_result = self._prompt_builder.build_from_editorial_profile(
            site_profile=site_profile,
            article_topic=article_topic,
        )

        # Déterminer le style depuis le profil si non fourni
        if style is None:
            editorial_tone = site_profile.get("editorial_tone", "professional")
            style_mapping = {
                "professional": "corporate_flat",
                "technical": "tech_isometric",
                "innovative": "tech_gradient",
                "modern": "modern_minimal",
                "corporate": "corporate_3d",
            }
            style = style_mapping.get(editorial_tone.lower(), "corporate_flat")

        # Générer l'image
        return await self.generate(
            prompt=prompt_result["prompt"],
            negative_prompt=prompt_result["negative_prompt"],
            style=style,
            aspect_ratio="1:1",
        )

    async def generate_from_topic(
        self,
        topic: str,
        style: str = "corporate_flat",
        aspect_ratio: str = "1:1",
    ) -> GenerationResult:
        """
        Génère une image depuis un topic simple.

        Args:
            topic: Sujet de l'image
            style: Style visuel
            aspect_ratio: Ratio d'aspect

        Returns:
            GenerationResult avec les détails de la génération
        """
        return await self.generate(
            prompt=topic,
            style=style,
            aspect_ratio=aspect_ratio,
        )


def get_image_generator(provider: Optional[str] = None) -> ImageGenerator:
    """
    Helper function pour obtenir l'instance singleton du générateur.

    Args:
        provider: Provider à utiliser (utilisé uniquement à la première création)

    Returns:
        Instance du générateur
    """
    return ImageGenerator.get_instance(provider=provider)

