"""Module de génération d'images avec Z-Image Turbo et Ideogram."""

from python_scripts.image_generation.exceptions import (
    ImageGenerationError,
    VRAMError,
    ModelLoadError,
    PromptError,
    CacheError,
    IdeogramAPIError,
)
from python_scripts.image_generation.ideogram_client import (
    IdeogramClient,
    IdeogramResult,
    get_ideogram_client,
    IDEOGRAM_STYLE_TYPES,
    IDEOGRAM_ASPECT_RATIOS,
)
from python_scripts.image_generation.image_generator import (
    ImageGenerator,
    GenerationResult,
    VariantGenerationResult,
    get_image_generator,
)
from python_scripts.image_generation.z_image_generator import (
    ZImageGenerator,
    ImageModel,
)
from python_scripts.image_generation.prompt_builder import (
    ImagePromptBuilderV2,
    IdeogramPromptResult,
)

# Alias pour compatibilité avec le code existant
ImagePromptBuilder = ImagePromptBuilderV2
from python_scripts.image_generation.image_cache import ImageCache
from python_scripts.image_generation.vram_manager import (
    VRAMManager,
    VRAMInfo,
    GPUProcess,
    get_vram_manager,
)
from python_scripts.image_generation.vram_resource_manager import (
    VRAMResourceManager,
    VRAMStatus,
    get_vram_resource_manager,
)
from python_scripts.image_generation.image_critic import (
    ImageCritic,
    CritiqueResult,
    CritiqueScores,
)

__all__ = [
    # Z-Image (local, deprecated but kept for fallback)
    "ZImageGenerator",
    "ImageModel",
    # Ideogram (cloud)
    "IdeogramClient",
    "IdeogramResult",
    "get_ideogram_client",
    "IDEOGRAM_STYLE_TYPES",
    "IDEOGRAM_ASPECT_RATIOS",
    # Image Generator (unified)
    "ImageGenerator",
    "GenerationResult",
    "VariantGenerationResult",
    "get_image_generator",
    # Prompt builders
    "ImagePromptBuilder",
    "ImagePromptBuilderV2",
    "IdeogramPromptResult",
    # Cache
    "ImageCache",
    # VRAM management
    "VRAMManager",
    "VRAMInfo",
    "GPUProcess",
    "get_vram_manager",
    "VRAMResourceManager",
    "VRAMStatus",
    "get_vram_resource_manager",
    # Image critic
    "ImageCritic",
    "CritiqueResult",
    "CritiqueScores",
    # Exceptions
    "ImageGenerationError",
    "VRAMError",
    "ModelLoadError",
    "PromptError",
    "CacheError",
    "IdeogramAPIError",
]


