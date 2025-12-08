"""Clustering module for BERTopic-based topic extraction (ETAGE 1)."""

from python_scripts.analysis.clustering.config import ClusteringConfig
from python_scripts.analysis.clustering.bertopic_clusterer import BertopicClusterer
from python_scripts.analysis.clustering.embedding_fetcher import EmbeddingFetcher
from python_scripts.analysis.clustering.outlier_handler import OutlierHandler
from python_scripts.analysis.clustering.topic_labeler import TopicLabeler

__all__ = [
    "ClusteringConfig",
    "BertopicClusterer",
    "EmbeddingFetcher",
    "OutlierHandler",
    "TopicLabeler",
]

