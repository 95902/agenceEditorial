"""Configuration pour la génération d'images avec Z-Image."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from python_scripts.config.settings import settings


@dataclass
class ZImageConfig:
    """Configuration du générateur Z-Image."""

    # Modèle
    model_id: str = "Tongyi-MAI/Z-Image-Turbo"
    model_variant: str = "turbo"  # "turbo", "base", "edit"
    torch_dtype: str = "bfloat16"

    # Paramètres de génération par défaut
    default_width: int = 1024
    default_height: int = 1024
    default_steps: int = 8
    default_guidance_scale: float = 4.5

    # Chemins
    output_dir: Path = field(default_factory=lambda: Path("outputs/images"))
    cache_dir: Path = field(default_factory=lambda: Path("outputs/images/cache"))

    # Cache
    cache_enabled: bool = True
    max_cache_size_gb: float = 5.0

    # Performance
    enable_attention_slicing: bool = True  # Pour GPU < 12GB (activé par défaut pour RTX 5070)
    enable_vae_tiling: bool = False  # Pour très grandes images
    enable_model_cpu_offload: bool = True  # Pour GPU < 12GB (activé par défaut pour économiser VRAM)

    # Logging
    log_generation_time: bool = True
    save_generation_metadata: bool = True

    # VRAM Management
    vram_safety_margin_gb: float = 2.0  # Marge de sécurité pour la VRAM
    transition_delay_seconds: float = 2.0  # Délai entre transitions de modèles
    ollama_api_url: str = settings.ollama_base_url  # URL de l'API Ollama


# Instance globale de configuration
IMAGE_CONFIG = ZImageConfig()


# Presets de qualité
QUALITY_PRESETS = {
    "draft": {
        "steps": 4,
        "width": 512,
        "height": 512,
        "guidance_scale": 3.0,
    },
    "standard": {
        "steps": 8,
        "width": 1024,
        "height": 1024,
        "guidance_scale": 4.5,
    },
    "high": {
        "steps": 12,
        "width": 1024,
        "height": 1024,
        "guidance_scale": 5.0,
    },
    "max": {
        "steps": 20,
        "width": 1536,
        "height": 1536,
        "guidance_scale": 6.0,
    },
}


# Styles prédéfinis pour prompts
STYLE_PRESETS = {
    "photo": "professional photography, DSLR, 85mm lens, natural lighting",
    "cinematic": "cinematic lighting, movie still, dramatic atmosphere, 4k",
    "minimal": "minimalist design, clean background, simple composition",
    "corporate": "professional business style, modern office aesthetic, clean",
    "artistic": "artistic composition, creative lighting, unique perspective",
    "product": "product photography, studio lighting, white background, commercial",
}

