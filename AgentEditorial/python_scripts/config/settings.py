"""Configuration settings using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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


# Global settings instance
settings = Settings()

