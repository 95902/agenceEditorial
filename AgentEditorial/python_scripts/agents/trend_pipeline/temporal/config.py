"""Configuration for temporal analysis module (ETAGE 2)."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TimeWindow:
    """Time window definition."""
    name: str
    days: int
    weight: float = 1.0


@dataclass
class TemporalConfig:
    """Temporal analysis configuration."""
    
    # Time windows for analysis
    windows: List[TimeWindow] = field(default_factory=lambda: [
        TimeWindow(name="7d", days=7, weight=0.4),
        TimeWindow(name="14d", days=14, weight=0.3),
        TimeWindow(name="30d", days=30, weight=0.2),
        TimeWindow(name="90d", days=90, weight=0.1),
    ])
    
    # Velocity thresholds
    velocity_acceleration_threshold: float = 1.5  # >1.5 = accelerating
    velocity_deceleration_threshold: float = 0.5  # <0.5 = decelerating
    
    # Freshness thresholds
    freshness_hot_threshold: float = 0.3  # >30% in 7d = hot
    freshness_cold_threshold: float = 0.05  # <5% in 7d = cold
    
    # Diversity thresholds
    diversity_mainstream_threshold: int = 5  # 5+ sources = mainstream
    diversity_niche_threshold: int = 2  # 1-2 sources = niche
    
    # Cohesion thresholds
    cohesion_well_defined_threshold: float = 0.7
    cohesion_heterogeneous_threshold: float = 0.4
    
    # Drift detection
    drift_detection_enabled: bool = True
    drift_threshold: float = 0.15  # cosine distance > 0.15 = drift
    
    # Scoring weights
    potential_score_weights: dict = field(default_factory=lambda: {
        "velocity": 0.25,
        "freshness": 0.25,
        "diversity": 0.20,
        "cohesion": 0.15,
        "size": 0.15,
    })

    # Potential score classification thresholds (calibrated based on real data)
    # These thresholds define how potential_score (0-1) maps to labels
    potential_very_high_threshold: float = 0.5  # "Très prometteur"
    potential_high_threshold: float = 0.35      # "Prometteur"
    potential_medium_threshold: float = 0.2     # "Modéré"
    # Below 0.2 = "Faible potentiel"

    # Differentiation score classification thresholds
    # These thresholds define how differentiation_score (0-1) maps to labels
    differentiation_very_high_threshold: float = 0.85  # "Très différenciant"
    differentiation_high_threshold: float = 0.75       # "Différenciant"
    differentiation_medium_threshold: float = 0.65     # "Moyennement différenciant"
    # Below 0.65 = "Peu différenciant"

    @classmethod
    def default(cls) -> "TemporalConfig":
        """Create default configuration."""
        return cls()

