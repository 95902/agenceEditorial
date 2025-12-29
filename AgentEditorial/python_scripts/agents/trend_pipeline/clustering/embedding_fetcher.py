"""Embedding fetcher from Qdrant (ETAGE 1)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from python_scripts.agents.trend_pipeline.clustering.config import ClusteringConfig
from python_scripts.config.settings import settings
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingFetcher:
    """Fetch embeddings and metadata from Qdrant."""
    
    def __init__(self, config: Optional[ClusteringConfig] = None):
        """
        Initialize the embedding fetcher.
        
        Args:
            config: Clustering configuration
        """
        self.config = config or ClusteringConfig.default()
        self._client: Optional[QdrantClient] = None
    
    @property
    def client(self) -> QdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            )
        return self._client
    
    def fetch_embeddings(
        self,
        domains: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]], List[str]]:
        """
        Fetch embeddings from Qdrant collection.

        Args:
            domains: Filter by domains (optional)
            max_age_days: Maximum article age in days (optional)
            limit: Maximum number of embeddings to fetch (optional)

        Returns:
            Tuple of (embeddings array, metadata list, document IDs list)
        """
        collection_name = self.config.embedding_collection
        max_age = max_age_days or self.config.max_age_days

        logger.info(
            "Fetching embeddings from Qdrant",
            collection=collection_name,
            domains=domains,
            max_age_days=max_age,
        )

        # Check if collection exists first
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if collection_name not in collection_names:
                logger.error(
                    "Collection does not exist in Qdrant",
                    collection=collection_name,
                    available_collections=collection_names,
                    error_type="collection_not_found",
                )
                logger.info(
                    "This error typically occurs when articles have not been scraped yet. "
                    "Run the scraping pipeline first to index competitor articles before running trend analysis.",
                )
                # Return empty arrays to allow pipeline to handle gracefully
                return np.array([], dtype=np.float32), [], []
        except Exception as e:
            logger.error(
                "Failed to check collection existence",
                collection=collection_name,
                error=str(e),
                error_type="connection_error",
            )
            # Return empty arrays on connection error
            return np.array([], dtype=np.float32), [], []

        # Check collection info
        try:
            collection_info = self.get_collection_info()
            points_count = collection_info.get("points_count", 0)
            vectors_count = collection_info.get("vectors_count", 0)

            logger.info(
                "Collection info",
                collection=collection_name,
                points_count=points_count,
                vectors_count=vectors_count,
            )

            # Warn if collection is empty
            if points_count == 0:
                logger.warning(
                    "Collection exists but contains no articles",
                    collection=collection_name,
                    message="Run the scraping pipeline to index competitor articles before running trend analysis.",
                )
                # Return empty arrays
                return np.array([], dtype=np.float32), [], []
        except Exception as e:
            logger.warning("Could not get collection info", error=str(e))
        
        # Build filter
        must_conditions = []
        
        # Domain filter
        if domains:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="domain",
                    match=qdrant_models.MatchAny(any=domains),
                )
            )
        
        # Note: Date filtering is done after retrieval since dates are stored as ISO strings
        # Calculate cutoff date for post-filtering
        cutoff_date = None
        if max_age > 0:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age)
        
        # Build scroll filter
        scroll_filter = None
        if must_conditions:
            scroll_filter = qdrant_models.Filter(must=must_conditions)
        
        # Scroll through all points
        embeddings = []
        metadata_list = []
        document_ids = []
        
        offset = None
        batch_size = 1000
        total_fetched = 0
        total_scanned = 0
        filtered_by_date = 0
        
        while True:
            try:
                result = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=scroll_filter,
                    limit=batch_size,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True,
                )
                
                points, next_offset = result
                
                if not points:
                    break
                
                total_scanned += len(points)
                
                for point in points:
                    if point.vector is not None:
                        payload = point.payload or {}
                        
                        # Filter by date if needed (dates are stored as ISO strings)
                        if cutoff_date:
                            published_date_str = payload.get("published_date")
                            if published_date_str:
                                try:
                                    # Parse ISO string to datetime
                                    if published_date_str.endswith('Z'):
                                        published_date_str = published_date_str[:-1] + '+00:00'
                                    pub_date = datetime.fromisoformat(published_date_str)
                                    
                                    # Ensure both dates are timezone-aware for comparison
                                    if pub_date.tzinfo is None:
                                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                                    cutoff = cutoff_date
                                    if cutoff.tzinfo is None:
                                        cutoff = cutoff.replace(tzinfo=timezone.utc)
                                    
                                    # Compare dates
                                    if pub_date < cutoff:
                                        filtered_by_date += 1
                                        continue  # Skip articles older than cutoff
                                except (ValueError, AttributeError, TypeError) as e:
                                    # If date parsing fails, include the article
                                    logger.debug("Date parsing failed", date_str=published_date_str, error=str(e))
                                    pass
                            # If no published_date, include the article
                        
                        embeddings.append(point.vector)
                        metadata_list.append(payload)
                        document_ids.append(str(point.id))
                        total_fetched += 1
                        
                        if limit and total_fetched >= limit:
                            break
                
                if limit and total_fetched >= limit:
                    break
                
                if next_offset is None:
                    break
                    
                offset = next_offset
                
            except Exception as e:
                error_msg = str(e)
                # Categorize error type
                if "Not found" in error_msg or "doesn't exist" in error_msg:
                    logger.error(
                        "Collection not found during scroll - this should not happen after initial check",
                        collection=collection_name,
                        error=error_msg,
                        error_type="collection_not_found",
                    )
                elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    logger.error(
                        "Connection error while fetching embeddings",
                        collection=collection_name,
                        error=error_msg,
                        error_type="connection_error",
                    )
                else:
                    logger.error(
                        "Unexpected error fetching embeddings",
                        collection=collection_name,
                        error=error_msg,
                        error_type="unknown_error",
                    )
                break
        
        # Convert to numpy array
        if embeddings:
            embeddings_array = np.array(embeddings, dtype=np.float32)
            
            # Normalize if configured
            if self.config.normalize_embeddings:
                norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
                norms[norms == 0] = 1  # Avoid division by zero
                embeddings_array = embeddings_array / norms
        else:
            embeddings_array = np.array([], dtype=np.float32)
        
        # If no results with domain filter, try without filter to see what domains exist
        if total_scanned == 0 and domains:
            logger.warning(
                "No articles found matching domain filter",
                requested_domains=domains,
                collection=collection_name,
            )
            # Try a small sample without domain filter to see available domains
            try:
                sample_result = self.client.scroll(
                    collection_name=collection_name,
                    limit=10,
                    with_vectors=False,
                    with_payload=True,
                )
                sample_points, _ = sample_result
                if sample_points:
                    available_domains = set()
                    for point in sample_points:
                        if point.payload and "domain" in point.payload:
                            available_domains.add(point.payload["domain"])
                    logger.info(
                        "Diagnosis: Collection contains articles from different domains",
                        available_domains=list(available_domains),
                        requested_domains=domains,
                        message="The requested domains do not match the domains in the collection. "
                                "This may indicate that articles were scraped with a different configuration.",
                    )
                else:
                    logger.warning(
                        "Collection appears to be empty",
                        collection=collection_name,
                        message="No articles found in collection even without domain filter.",
                    )
            except Exception as e:
                logger.debug("Could not sample collection", error=str(e))
        
        logger.info(
            "Fetched embeddings",
            count=len(embeddings_array),
            total_scanned=total_scanned,
            filtered_by_date=filtered_by_date,
            domains=domains,
        )
        
        return embeddings_array, metadata_list, document_ids
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the Qdrant collection.
        
        Returns:
            Collection information
        """
        try:
            collection = self.client.get_collection(self.config.embedding_collection)
            # Qdrant CollectionInfo structure may vary by version
            info = {
                "name": self.config.embedding_collection,
                "points_count": getattr(collection, "points_count", 0),
                "status": getattr(collection.status, "value", str(collection.status)) if hasattr(collection, "status") else "unknown",
            }
            # Try to get vectors_count if available
            if hasattr(collection, "vectors_count"):
                info["vectors_count"] = collection.vectors_count
            else:
                # Fallback: assume 1 vector per point (most common case)
                info["vectors_count"] = info["points_count"]
            return info
        except Exception as e:
            logger.error("Error getting collection info", error=str(e))
            return {"error": str(e)}
    
    def save_centroids(
        self,
        centroids: np.ndarray,
        topic_ids: List[int],
        topic_labels: List[str],
    ) -> bool:
        """
        Save topic centroids to Qdrant.
        
        Args:
            centroids: Centroid vectors
            topic_ids: Topic IDs
            topic_labels: Topic labels
            
        Returns:
            Success status
        """
        if not self.config.save_centroids_to_qdrant:
            return True
        
        collection_name = self.config.centroid_collection
        
        try:
            # Check if collection exists, create if not
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if collection_name not in collection_names:
                # Get vector dimension from first centroid
                vector_size = centroids.shape[1] if len(centroids) > 0 else 1024
                
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=vector_size,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                logger.info("Created centroid collection", collection=collection_name)
            
            # Prepare points
            points = [
                qdrant_models.PointStruct(
                    id=topic_id,
                    vector=centroid.tolist(),
                    payload={
                        "topic_id": topic_id,
                        "label": label,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                for topic_id, centroid, label in zip(topic_ids, centroids, topic_labels)
                if topic_id >= 0  # Skip outlier topic
            ]
            
            if points:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points,
                )
                logger.info("Saved centroids", count=len(points))
            
            return True
            
        except Exception as e:
            logger.error("Error saving centroids", error=str(e))
            return False

