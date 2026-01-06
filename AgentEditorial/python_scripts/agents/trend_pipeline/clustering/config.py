"""Configuration for clustering module (ETAGE 1)."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HDBSCANConfig:
    """HDBSCAN clustering configuration."""
    
    # Augmenté de 5 à 12 pour éviter les clusters géants
    # Recommandation: 10-15 pour un corpus de taille moyenne
    min_cluster_size: int = 12
    min_samples: int = 5  # Augmenté de 3 à 5 pour plus de stabilité
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
    
    # Augmenté de 10 à 15 pour éviter les micro-clusters
    min_topic_size: int = 15
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
    embedding_collection: Optional[str] = None  # Will be generated from client_domain if provided
    client_domain: Optional[str] = None  # Client domain for generating collection name
    client_collection: str = "client_articles"
    include_client_articles: bool = True  # Include client articles in clustering (unified clustering)
    normalize_embeddings: bool = True
    
    def __post_init__(self):
        """Generate collection name from client_domain if not explicitly set."""
        if self.embedding_collection is None:
            if self.client_domain:
                from python_scripts.vectorstore.qdrant_client import get_competitor_collection_name
                self.embedding_collection = get_competitor_collection_name(self.client_domain)
            else:
                # Fallback to default collection name
                from python_scripts.vectorstore.qdrant_client import COLLECTION_NAME
                self.embedding_collection = COLLECTION_NAME
    
    # Filtering
    min_articles: int = 50
    max_age_days: int = 1365
    
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
                min_cluster_size=5,
                min_samples=3,
            ),
            bertopic=BERTopicConfig(
                min_topic_size=8,
            ),
            min_articles=20,
        )
    
    @classmethod
    def for_medium_corpus(cls) -> "ClusteringConfig":
        """Configuration optimized for medium corpus (500-5000 articles)."""
        return cls(
            hdbscan=HDBSCANConfig(
                min_cluster_size=12,
                min_samples=5,
            ),
            bertopic=BERTopicConfig(
                min_topic_size=15,
            ),
        )
    
    @classmethod
    def for_large_corpus(cls) -> "ClusteringConfig":
        """Configuration optimized for large corpus (>5000 articles)."""
        return cls(
            hdbscan=HDBSCANConfig(
                min_cluster_size=20,
                min_samples=8,
            ),
            umap=UMAPConfig(
                n_neighbors=30,
                n_components=15,
            ),
            bertopic=BERTopicConfig(
                min_topic_size=30,
                low_memory=True,
            ),
        )

