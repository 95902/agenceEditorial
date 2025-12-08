"""Outlier handling for clustering (ETAGE 1)."""

from typing import Any, Dict, List, Optional

import numpy as np

from python_scripts.analysis.clustering.config import ClusteringConfig
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class OutlierHandler:
    """Handle outlier documents from clustering."""
    
    def __init__(self, config: Optional[ClusteringConfig] = None):
        """
        Initialize the outlier handler.
        
        Args:
            config: Clustering configuration
        """
        self.config = config or ClusteringConfig.default()
    
    def extract_outliers(
        self,
        topics: List[int],
        metadata: List[Dict[str, Any]],
        document_ids: List[str],
        embeddings: Optional[np.ndarray] = None,
        centroids: Optional[Dict[int, np.ndarray]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract and process outlier documents.
        
        Args:
            topics: Topic assignments
            metadata: Document metadata
            document_ids: Document IDs
            embeddings: Document embeddings (optional)
            centroids: Topic centroids (optional)
            
        Returns:
            List of outlier documents with analysis
        """
        outliers = []
        
        for i, topic in enumerate(topics):
            if topic != -1:
                continue
            
            outlier = {
                "index": i,
                "document_id": document_ids[i] if i < len(document_ids) else str(i),
                "metadata": metadata[i] if i < len(metadata) else {},
            }
            
            # Calculate distance to nearest centroid if available
            if embeddings is not None and centroids and len(centroids) > 0:
                embedding = embeddings[i]
                min_distance = float("inf")
                nearest_topic = None
                
                for topic_id, centroid in centroids.items():
                    distance = np.linalg.norm(embedding - centroid)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_topic = topic_id
                
                outlier["nearest_topic_id"] = nearest_topic
                outlier["distance_to_nearest"] = float(min_distance)
            
            outliers.append(outlier)
        
        logger.info(
            "Extracted outliers",
            count=len(outliers),
            max_to_analyze=self.config.max_outliers_to_analyze,
        )
        
        return outliers[:self.config.max_outliers_to_analyze]
    
    def categorize_outliers(
        self,
        outliers: List[Dict[str, Any]],
        texts: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize outliers by potential reason.
        
        Args:
            outliers: List of outlier documents
            texts: Document texts (optional)
            
        Returns:
            Categorized outliers
        """
        categories = {
            "too_short": [],       # Documents too short
            "too_unique": [],      # Very unique content
            "mixed_topics": [],    # Content spanning multiple topics
            "low_quality": [],     # Low quality content
            "emerging": [],        # Potentially emerging topics
            "uncategorized": [],   # Cannot determine
        }
        
        for outlier in outliers:
            idx = outlier["index"]
            metadata = outlier.get("metadata", {})
            
            # Check text length
            word_count = metadata.get("word_count", 0)
            if texts and idx < len(texts):
                word_count = len(texts[idx].split())
            
            if word_count < 100:
                categories["too_short"].append(outlier)
                outlier["potential_category"] = "too_short"
                continue
            
            # Check distance to nearest topic
            distance = outlier.get("distance_to_nearest")
            if distance is not None:
                if distance > 1.5:  # Very far from all topics
                    categories["too_unique"].append(outlier)
                    outlier["potential_category"] = "too_unique"
                elif distance < 0.5:  # Close to a topic but not assigned
                    categories["mixed_topics"].append(outlier)
                    outlier["potential_category"] = "mixed_topics"
                else:
                    # Medium distance - could be emerging
                    categories["emerging"].append(outlier)
                    outlier["potential_category"] = "emerging"
            else:
                categories["uncategorized"].append(outlier)
                outlier["potential_category"] = "uncategorized"
        
        # Log summary
        summary = {k: len(v) for k, v in categories.items() if v}
        logger.info("Categorized outliers", categories=summary)
        
        return categories
    
    def find_potential_clusters(
        self,
        outliers: List[Dict[str, Any]],
        embeddings: np.ndarray,
        min_cluster_size: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Find potential sub-clusters among outliers.
        
        This can identify emerging topics that didn't meet the
        minimum cluster size threshold.
        
        Args:
            outliers: List of outlier documents
            embeddings: Document embeddings
            min_cluster_size: Minimum cluster size
            
        Returns:
            List of potential clusters
        """
        if len(outliers) < min_cluster_size:
            return []
        
        try:
            from sklearn.cluster import AgglomerativeClustering
            
            # Get outlier indices
            indices = [o["index"] for o in outliers]
            outlier_embeddings = embeddings[indices]
            
            # Try hierarchical clustering with loose parameters
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=0.5,
                metric="cosine",
                linkage="average",
            )
            
            labels = clustering.fit_predict(outlier_embeddings)
            
            # Find clusters with at least min_cluster_size members
            potential_clusters = []
            unique_labels = set(labels)
            
            for label in unique_labels:
                cluster_indices = [i for i, l in enumerate(labels) if l == label]
                
                if len(cluster_indices) >= min_cluster_size:
                    cluster_outliers = [outliers[i] for i in cluster_indices]
                    
                    # Calculate centroid
                    cluster_embeddings = outlier_embeddings[cluster_indices]
                    centroid = np.mean(cluster_embeddings, axis=0)
                    
                    potential_clusters.append({
                        "label": f"potential_topic_{label}",
                        "size": len(cluster_indices),
                        "outliers": cluster_outliers,
                        "centroid": centroid.tolist(),
                    })
            
            logger.info(
                "Found potential clusters in outliers",
                count=len(potential_clusters),
            )
            
            return potential_clusters
            
        except Exception as e:
            logger.warning("Could not find potential clusters", error=str(e))
            return []

