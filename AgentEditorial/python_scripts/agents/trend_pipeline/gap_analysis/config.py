"""Configuration for gap analysis module (ETAGE 4)."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GapAnalysisConfig:
    """Gap analysis configuration."""
    
    # Coverage thresholds
    coverage_excellent_threshold: float = 0.8  # >80% = excellent coverage
    coverage_good_threshold: float = 0.5       # >50% = good coverage
    coverage_weak_threshold: float = 0.2       # >20% = weak coverage
    # <20% = gap
    
    # Priority scoring weights
    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        "coverage_gap": 0.30,      # How big is the gap
        "topic_potential": 0.25,  # How promising is the topic
        "velocity": 0.20,          # How fast is it growing
        "competitor_presence": 0.15,  # How many competitors cover it
        "effort_estimate": 0.10,   # Inverse of effort (easier = higher)
    })
    
    # Strength thresholds
    strength_significant_threshold: float = 1.5  # Client 50%+ more than avg competitor
    
    # Roadmap settings
    max_roadmap_items: int = 20
    priority_distribution: Dict[str, int] = field(default_factory=lambda: {
        "high": 5,
        "medium": 10,
        "low": 5,
    })
    
    @classmethod
    def default(cls) -> "GapAnalysisConfig":
        """Create default configuration."""
        return cls()

