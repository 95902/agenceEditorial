"""Clustering module for BERTopic-based topic extraction (ETAGE 1)."""

from python_scripts.agents.trend_pipeline.clustering.config import ClusteringConfig
from python_scripts.agents.trend_pipeline.clustering.bertopic_clusterer import BertopicClusterer
from python_scripts.agents.trend_pipeline.clustering.embedding_fetcher import EmbeddingFetcher
from python_scripts.agents.trend_pipeline.clustering.outlier_handler import OutlierHandler
from python_scripts.agents.trend_pipeline.clustering.topic_labeler import TopicLabeler

__all__ = [
    "ClusteringConfig",
    "BertopicClusterer",
    "EmbeddingFetcher",
    "OutlierHandler",
    "TopicLabeler",
]

