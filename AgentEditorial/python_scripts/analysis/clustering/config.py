"""Configuration for clustering module (ETAGE 1)."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HDBSCANConfig:
    """HDBSCAN clustering configuration."""
    
    min_cluster_size: int = 5
    min_samples: int = 3
    metric: str = "euclidean"
    cluster_selection_method: str = "eom"  # excess of mass
    cluster_selection_epsilon: float = 0.1
    prediction_data: bool = True


@dataclass
class UMAPConfig:
    """UMAP dimensionality reduction configuration."""
    
    n_neighbors: int = 20
    n_components: int = 10
    min_dist: float = 0.0
    metric: str = "cosine"
    random_state: int = 42


@dataclass
class BERTopicConfig:
    """BERTopic model configuration."""
    
    min_topic_size: int = 10
    nr_topics: str | int = "auto"
    calculate_probabilities: bool = True
    verbose: bool = True
    low_memory: bool = False


@dataclass
class ClusteringConfig:
    """Main clustering configuration."""
    
    # Sub-configurations
    hdbscan: HDBSCANConfig = field(default_factory=HDBSCANConfig)
    umap: UMAPConfig = field(default_factory=UMAPConfig)
    bertopic: BERTopicConfig = field(default_factory=BERTopicConfig)
    
    # Embedding settings
    use_qdrant_embeddings: bool = True
    embedding_collection: str = "competitor_articles"
    client_collection: str = "client_articles"
    normalize_embeddings: bool = True
    
    # Filtering
    min_articles: int = 50
    max_age_days: int = 365
    
    # Outlier handling
    save_outliers: bool = True
    analyze_outliers: bool = True
    max_outliers_to_analyze: int = 100
    
    # Output
    generate_visualizations: bool = True
    save_centroids_to_qdrant: bool = True
    centroid_collection: str = "topic_centroids"
    
    @classmethod
    def default(cls) -> "ClusteringConfig":
        """Create default configuration."""
        return cls()
    
    @classmethod
    def for_small_corpus(cls) -> "ClusteringConfig":
        """Configuration optimized for small corpus (<500 articles)."""
        return cls(
            hdbscan=HDBSCANConfig(
                min_cluster_size=3,
                min_samples=2,
            ),
            bertopic=BERTopicConfig(
                min_topic_size=5,
            ),
            min_articles=20,
        )
    
    @classmethod
    def for_large_corpus(cls) -> "ClusteringConfig":
        """Configuration optimized for large corpus (>5000 articles)."""
        return cls(
            hdbscan=HDBSCANConfig(
                min_cluster_size=10,
                min_samples=5,
            ),
            umap=UMAPConfig(
                n_neighbors=30,
                n_components=15,
            ),
            bertopic=BERTopicConfig(
                min_topic_size=20,
                low_memory=True,
            ),
        )

