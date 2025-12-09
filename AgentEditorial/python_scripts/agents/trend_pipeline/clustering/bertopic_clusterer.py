"""BERTopic clustering implementation (ETAGE 1)."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from bertopic import BERTopic
from hdbscan import HDBSCAN
from umap import UMAP

from python_scripts.agents.trend_pipeline.clustering.config import ClusteringConfig
from python_scripts.agents.trend_pipeline.clustering.embedding_fetcher import EmbeddingFetcher
from python_scripts.config.settings import settings
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.embeddings_utils import get_embedding_model

logger = get_logger(__name__)


class BertopicClusterer:
    """BERTopic-based document clustering."""
    
    def __init__(self, config: Optional[ClusteringConfig] = None):
        """
        Initialize the clusterer.
        
        Args:
            config: Clustering configuration
        """
        self.config = config or ClusteringConfig.default()
        self._model: Optional[BERTopic] = None
        self._embedding_fetcher = EmbeddingFetcher(self.config)
    
    def _create_model(self) -> BERTopic:
        """Create and configure BERTopic model."""
        cfg = self.config
        
        # Configure UMAP
        umap_model = UMAP(
            n_neighbors=cfg.umap.n_neighbors,
            n_components=cfg.umap.n_components,
            min_dist=cfg.umap.min_dist,
            metric=cfg.umap.metric,
            random_state=cfg.umap.random_state,
        )
        
        # Configure HDBSCAN
        hdbscan_model = HDBSCAN(
            min_cluster_size=cfg.hdbscan.min_cluster_size,
            min_samples=cfg.hdbscan.min_samples,
            metric=cfg.hdbscan.metric,
            cluster_selection_method=cfg.hdbscan.cluster_selection_method,
            cluster_selection_epsilon=cfg.hdbscan.cluster_selection_epsilon,
            prediction_data=cfg.hdbscan.prediction_data,
        )
        
        # Get embedding model
        embedding_model = get_embedding_model()
        
        # Create BERTopic model
        model = BERTopic(
            embedding_model=embedding_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            min_topic_size=cfg.bertopic.min_topic_size,
            nr_topics=cfg.bertopic.nr_topics,
            calculate_probabilities=cfg.bertopic.calculate_probabilities,
            verbose=cfg.bertopic.verbose,
            low_memory=cfg.bertopic.low_memory,
        )
        
        logger.info(
            "BERTopic model created",
            min_topic_size=cfg.bertopic.min_topic_size,
            nr_topics=cfg.bertopic.nr_topics,
        )
        
        return model
    
    def cluster(
        self,
        texts: List[str],
        embeddings: Optional[np.ndarray] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Cluster documents using BERTopic.
        
        Args:
            texts: List of document texts
            embeddings: Pre-computed embeddings (optional)
            metadata: Document metadata (optional)
            
        Returns:
            Clustering results
        """
        if len(texts) < self.config.min_articles:
            logger.warning(
                "Not enough documents for clustering",
                count=len(texts),
                min_required=self.config.min_articles,
            )
            return {
                "success": False,
                "error": f"Not enough documents ({len(texts)}). Minimum required: {self.config.min_articles}",
                "topics": [],
                "outliers": [],
            }
        
        logger.info("Starting clustering", documents=len(texts))
        
        # Create model
        self._model = self._create_model()
        
        try:
            # Fit model
            if embeddings is not None and len(embeddings) > 0:
                topics, probs = self._model.fit_transform(texts, embeddings)
            else:
                topics, probs = self._model.fit_transform(texts)
            
            # Get topic info
            topic_info = self._model.get_topic_info()
            
            # Process results
            clusters = []
            outlier_indices = []
            
            for idx, row in topic_info.iterrows():
                topic_id = row["Topic"]
                
                if topic_id == -1:
                    # Outlier topic
                    outlier_count = row["Count"]
                    continue
                
                # Get topic representation
                topic_words = self._model.get_topic(topic_id)
                top_terms = [
                    {"word": word, "score": float(score)}
                    for word, score in topic_words[:10]
                ] if topic_words else []
                
                # Find documents in this topic
                doc_indices = [i for i, t in enumerate(topics) if t == topic_id]
                
                clusters.append({
                    "topic_id": int(topic_id),
                    "label": row.get("Name", f"Topic_{topic_id}"),
                    "size": int(row["Count"]),
                    "top_terms": top_terms,
                    "document_indices": doc_indices,
                    "representative_docs": row.get("Representative_Docs", []),
                })
            
            # Get outlier indices
            outlier_indices = [i for i, t in enumerate(topics) if t == -1]
            
            # Calculate centroids
            centroids = self._calculate_centroids(embeddings, topics) if embeddings is not None else None
            
            logger.info(
                "Clustering complete",
                num_topics=len(clusters),
                num_outliers=len(outlier_indices),
            )
            
            return {
                "success": True,
                "topics": topics,
                "probabilities": probs.tolist() if probs is not None else None,
                "clusters": clusters,
                "outlier_indices": outlier_indices,
                "centroids": centroids,
                "model": self._model,
            }
            
        except Exception as e:
            logger.error("Clustering failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "topics": [],
                "outliers": [],
            }
    
    def _calculate_centroids(
        self,
        embeddings: np.ndarray,
        topics: List[int],
    ) -> Dict[int, np.ndarray]:
        """
        Calculate centroid for each topic.
        
        Args:
            embeddings: Document embeddings
            topics: Topic assignments
            
        Returns:
            Dictionary mapping topic_id to centroid vector
        """
        centroids = {}
        unique_topics = set(topics)
        
        for topic_id in unique_topics:
            if topic_id == -1:
                continue
            
            # Get embeddings for this topic
            topic_embeddings = embeddings[[i for i, t in enumerate(topics) if t == topic_id]]
            
            if len(topic_embeddings) > 0:
                centroid = np.mean(topic_embeddings, axis=0)
                centroids[topic_id] = centroid
        
        return centroids
    
    def get_topic_hierarchy(self) -> Optional[Dict[str, Any]]:
        """
        Get hierarchical topic structure.
        
        Returns:
            Topic hierarchy or None if not available
        """
        if self._model is None:
            return None
        
        try:
            hierarchy = self._model.hierarchical_topics(
                self._model._texts if hasattr(self._model, "_texts") else []
            )
            return hierarchy.to_dict() if hasattr(hierarchy, "to_dict") else None
        except Exception as e:
            logger.warning("Could not generate hierarchy", error=str(e))
            return None
    
    def generate_visualizations(
        self,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Generate topic visualizations.
        
        Args:
            output_dir: Output directory for visualizations
            
        Returns:
            Dictionary mapping visualization name to file path
        """
        if self._model is None or not self.config.generate_visualizations:
            return {}
        
        output_dir = output_dir or Path(settings.OUTPUTS_PATH) / "visualizations"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        visualizations = {}
        
        try:
            # 2D topic visualization
            fig = self._model.visualize_topics()
            path = output_dir / f"topics_2d_{timestamp}.html"
            fig.write_html(str(path))
            visualizations["topics_2d"] = str(path)
        except Exception as e:
            logger.warning("Could not generate 2D visualization", error=str(e))
        
        try:
            # Topic barchart
            fig = self._model.visualize_barchart()
            path = output_dir / f"topics_barchart_{timestamp}.html"
            fig.write_html(str(path))
            visualizations["topics_barchart"] = str(path)
        except Exception as e:
            logger.warning("Could not generate barchart", error=str(e))
        
        try:
            # Topic heatmap
            fig = self._model.visualize_heatmap()
            path = output_dir / f"topics_heatmap_{timestamp}.html"
            fig.write_html(str(path))
            visualizations["topics_heatmap"] = str(path)
        except Exception as e:
            logger.warning("Could not generate heatmap", error=str(e))
        
        logger.info("Generated visualizations", count=len(visualizations))
        
        return visualizations
    
    def reduce_topics(self, nr_topics: int) -> bool:
        """
        Reduce number of topics after fitting.
        
        Args:
            nr_topics: Target number of topics
            
        Returns:
            Success status
        """
        if self._model is None:
            return False
        
        try:
            self._model.reduce_topics(self._model._texts, nr_topics=nr_topics)
            logger.info("Reduced topics", nr_topics=nr_topics)
            return True
        except Exception as e:
            logger.error("Could not reduce topics", error=str(e))
            return False

