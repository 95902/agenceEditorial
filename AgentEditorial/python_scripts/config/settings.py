"""Configuration settings using Pydantic Settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Find .env file - look in project root (AgentEditorial/)
# Go up from python_scripts/config/settings.py -> python_scripts/config -> python_scripts -> AgentEditorial
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"

# Also check current working directory as fallback
_cwd_env_file = Path.cwd() / ".env"
if not _env_file.exists() and _cwd_env_file.exists():
    _env_file = _cwd_env_file


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_env_file) if _env_file.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Also load from environment variables directly
        env_prefix="",
    )

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "editorial_db"
    postgres_user: str = "editorial_user"
    postgres_password: str = "change_me_strong_password"

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL async database URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Construct PostgreSQL sync database URL (for Alembic)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None

    # Ollama
    # Default to 11435 if using Docker Compose (to avoid conflict with local Ollama on 11434)
    # Set OLLAMA_BASE_URL=http://localhost:11434 in .env if using local Ollama
    ollama_base_url: str = "http://localhost:11435"
    # Default model for article generation / LLM-based features
    # Utilise un modèle plus standard déjà utilisé ailleurs dans le projet
    ollama_model: str = "llama3:8b"

    # API Keys (optional)
    tavily_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Scraping
    user_agent: str = "EditorialBot/1.0 (+https://your-site.com/bot)"
    crawl_delay_default: int = 2
    max_pages_per_domain: int = 100

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_analysis_per_minute: int = 10

    # Data Retention
    data_retention_days: int = 90

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Output Paths
    output_base_path: str = "/mnt/user-data/outputs"
    visualizations_path: str = "/mnt/user-data/outputs/visualizations"

    # Article Generation Output Paths
    # Base directory for generated article files (markdown, html, metadata)
    article_output_dir: str = "outputs/articles"
    # Directory for generated images associated with articles
    article_images_dir: str = "outputs/articles/images"

    # Z-Image configuration
    # Enable/disable image generation (can be disabled in environments without GPU)
    z_image_enabled: bool = True
    # Image generation model to use (z-image-turbo, z-image-base, flux-schnell)
    # Note: z-image-turbo is the default (lighter than FLUX, requires transformers >= 4.47.0)
    z_image_model: str = "z-image-turbo"

    # Ideogram API configuration
    ideogram_api_key: Optional[str] = None
    ideogram_model: str = "V_2"  # V_2 ou V_2_TURBO
    ideogram_default_style: str = "DESIGN"  # DESIGN, ILLUSTRATION, REALISTIC, GENERAL
    image_provider: str = "ideogram"  # "ideogram" ou "local"
    image_fallback_to_local: bool = False  # Fallback vers Z-Image si API Ideogram échoue


# Global settings instance
settings = Settings()

