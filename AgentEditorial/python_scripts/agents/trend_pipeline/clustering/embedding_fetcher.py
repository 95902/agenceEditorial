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
    
    def _fetch_from_collection(
        self,
        collection_name: str,
        domains: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
        limit: Optional[int] = None,
        article_type: Optional[str] = None,
    ) -> Tuple[List[List[float]], List[Dict[str, Any]], List[str]]:
        """
        Fetch embeddings from a specific Qdrant collection (internal helper method).
        
        Args:
            collection_name: Name of the Qdrant collection
            domains: Filter by domains (optional)
            max_age_days: Maximum article age in days (optional)
            limit: Maximum number of embeddings to fetch (optional)
            article_type: Type of article ("client" or "competitor") to mark in metadata
            
        Returns:
            Tuple of (embeddings list, metadata list, document IDs list)
        """
        max_age = max_age_days or self.config.max_age_days
        
        # Check if collection exists
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if collection_name not in collection_names:
                logger.debug(
                    "Collection does not exist, skipping",
                    collection=collection_name,
                )
                return [], [], []
        except Exception as e:
            logger.warning(
                "Failed to check collection existence",
                collection=collection_name,
                error=str(e),
            )
            return [], [], []
        
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
                        payload = dict(point.payload or {})
                        
                        # Mark article type
                        if article_type:
                            payload["article_type"] = article_type
                        
                        # Filter by date if needed (skip date filter for client articles to include all historical content)
                        if cutoff_date and article_type != "client":
                            published_date_str = payload.get("published_date")
                            if published_date_str:
                                try:
                                    if published_date_str.endswith('Z'):
                                        published_date_str = published_date_str[:-1] + '+00:00'
                                    pub_date = datetime.fromisoformat(published_date_str)
                                    
                                    if pub_date.tzinfo is None:
                                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                                    cutoff = cutoff_date
                                    if cutoff.tzinfo is None:
                                        cutoff = cutoff.replace(tzinfo=timezone.utc)
                                    
                                    if pub_date < cutoff:
                                        filtered_by_date += 1
                                        continue
                                except (ValueError, AttributeError, TypeError) as e:
                                    logger.debug("Date parsing failed", date_str=published_date_str, error=str(e))
                        
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
                logger.warning(
                    "Error fetching from collection",
                    collection=collection_name,
                    error=str(e),
                )
                break
        
        logger.debug(
            "Fetched from collection",
            collection=collection_name,
            count=len(embeddings),
            total_scanned=total_scanned,
            filtered_by_date=filtered_by_date,
            article_type=article_type,
        )
        
        return embeddings, metadata_list, document_ids

    def fetch_embeddings(
        self,
        domains: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]], List[str]]:
        """
        Fetch embeddings from Qdrant collections (competitor and optionally client).

        Args:
            domains: Filter by domains (optional)
            max_age_days: Maximum article age in days (optional)
            limit: Maximum number of embeddings to fetch (optional)

        Returns:
            Tuple of (embeddings array, metadata list, document IDs list)
        """
        max_age = max_age_days or self.config.max_age_days
        competitor_collection = self.config.embedding_collection

        logger.info(
            "Fetching embeddings from Qdrant",
            competitor_collection=competitor_collection,
            include_client_articles=self.config.include_client_articles,
            domains=domains,
            max_age_days=max_age,
        )

        # 1. Fetch from competitor collection
        competitor_embeddings, competitor_metadata, competitor_ids = self._fetch_from_collection(
            collection_name=competitor_collection,
            domains=domains,
            max_age_days=max_age,
            limit=limit,
            article_type="competitor",
        )

        # 2. Fetch from client collection if enabled
        client_embeddings, client_metadata, client_ids = [], [], []
        if self.config.include_client_articles and self.config.client_domain:
            from python_scripts.vectorstore.qdrant_client import get_client_collection_name
            client_collection = get_client_collection_name(self.config.client_domain)
            
            logger.info(
                "Including client articles in clustering",
                client_collection=client_collection,
                client_domain=self.config.client_domain,
            )
            
            # For client articles, only fetch articles from the client domain
            client_domains = [self.config.client_domain] if domains is None else [d for d in domains if d == self.config.client_domain]
            if not client_domains and self.config.client_domain:
                # If client domain not in domains filter, add it anyway for client collection
                client_domains = [self.config.client_domain]
            
            client_embeddings, client_metadata, client_ids = self._fetch_from_collection(
                collection_name=client_collection,
                domains=client_domains,
                max_age_days=max_age,
                limit=None,  # No limit for client articles (usually small number)
                article_type="client",
            )
            
            logger.info(
                "Fetched client articles",
                count=len(client_embeddings),
                collection=client_collection,
            )

        # 3. Merge results
        all_embeddings = competitor_embeddings + client_embeddings
        all_metadata = competitor_metadata + client_metadata
        all_ids = competitor_ids + client_ids

        # Convert to numpy array
        if all_embeddings:
            embeddings_array = np.array(all_embeddings, dtype=np.float32)
            
            # Normalize if configured
            if self.config.normalize_embeddings:
                norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
                norms[norms == 0] = 1  # Avoid division by zero
                embeddings_array = embeddings_array / norms
        else:
            embeddings_array = np.array([], dtype=np.float32)

        # Log summary
        logger.info(
            "Fetched embeddings (unified)",
            total_count=len(embeddings_array),
            competitor_count=len(competitor_embeddings),
            client_count=len(client_embeddings),
            domains=domains,
        )

        # If no results, provide helpful diagnostics
        if len(embeddings_array) == 0:
            if competitor_collection:
                try:
                    sample_result = self.client.scroll(
                        collection_name=competitor_collection,
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
                        logger.warning(
                            "No articles found matching filters",
                            requested_domains=domains,
                            available_domains=list(available_domains),
                            collection=competitor_collection,
                            message="The requested domains may not match the domains in the collection.",
                        )
                except Exception as e:
                    logger.debug("Could not sample collection", error=str(e))

        return embeddings_array, all_metadata, all_ids
    
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

