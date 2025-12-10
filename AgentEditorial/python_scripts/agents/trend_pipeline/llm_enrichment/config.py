"""Configuration for LLM enrichment module (ETAGE 3)."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class LLMEnrichmentConfig:
    """LLM enrichment configuration."""
    
    # Model mapping by task
    models: Dict[str, str] = field(default_factory=lambda: {
            "trend_synthesis": "phi3:medium",
            "angle_generation": "mistral:7b",
            "outlier_analysis": "llama3:8b",
    })
    
    # Fallback model if primary not available
    fallback_model: str = "mistral:7b"
    
    # Timeouts
    synthesis_timeout_seconds: int = 120
    angle_timeout_seconds: int = 60
    outlier_timeout_seconds: int = 60
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 2
    
    # Output limits
    max_angles_per_topic: int = 5
    max_synthesis_length: int = 500
    max_outlier_clusters_to_analyze: int = 10
    
    # Topics enrichment limits
    # Augmenté de 10 à 50 pour enrichir plus de clusters
    # Valeur précédente était hardcodée à 10 dans agent.py
    max_topics_to_enrich: int = 50
    
    # Quality scoring
    min_quality_score: float = 0.6
    
    @classmethod
    def default(cls) -> "LLMEnrichmentConfig":
        """Create default configuration."""
        return cls()

