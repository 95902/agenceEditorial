"""Configuration for article enrichment module."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ArticleEnrichmentConfig:
    """Article enrichment configuration."""
    
    # Model mapping by task
    models: Dict[str, str] = field(default_factory=lambda: {
        "outline_enrichment": "llama3:8b",  # Best for structured content
        "angle_personalization": "mistral:7b",  # Good for creative adaptation
        "statistics_integration": "phi3:medium",  # Good for factual content
    })
    
    # Fallback model if primary not available
    fallback_model: str = "mistral:7b"
    
    # Timeouts
    outline_enrichment_timeout_seconds: int = 90
    angle_personalization_timeout_seconds: int = 60
    statistics_integration_timeout_seconds: int = 60
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 2
    
    # Output limits
    max_outline_sections: int = 5
    max_subsections_per_section: int = 4
    max_statistics_per_section: int = 3
    
    # Quality thresholds
    min_outline_detail_level: float = 0.7
    min_personalization_score: float = 0.6
    
    @classmethod
    def default(cls) -> "ArticleEnrichmentConfig":
        """Create default configuration."""
        return cls()



