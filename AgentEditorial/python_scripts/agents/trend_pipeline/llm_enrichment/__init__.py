"""LLM enrichment module (ETAGE 3)."""

from python_scripts.agents.trend_pipeline.llm_enrichment.config import LLMEnrichmentConfig
from python_scripts.agents.trend_pipeline.llm_enrichment.llm_enricher import LLMEnricher

__all__ = [
    "LLMEnrichmentConfig",
    "LLMEnricher",
]

