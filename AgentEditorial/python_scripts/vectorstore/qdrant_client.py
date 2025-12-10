"""Qdrant client wrapper."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from python_scripts.config.settings import settings
from python_scripts.utils.exceptions import VectorStoreError
from python_scripts.utils.logging import get_logger
from python_scripts.vectorstore.embeddings_utils import generate_embedding

logger = get_logger(__name__)

# Collection name for competitor articles
COLLECTION_NAME = "competitor_articles"
# Collection name for client articles (legacy, use get_client_collection_name instead)
CLIENT_COLLECTION_NAME = "client_articles"
# Similarity threshold for duplicate detection (0.92 = 92% similarity)
DUPLICATE_THRESHOLD = 0.92


def get_client_collection_name(domain: str) -> str:
    """
    Generate Qdrant collection name for client articles based on domain.
    
    Format: {domain}_client_articles
    
    Args:
        domain: Domain name (e.g., "example.com")
        
    Returns:
        Collection name (e.g., "example_com_client_articles")
    """
    # Normalize domain: replace dots with underscores, lowercase, remove invalid chars
    normalized_domain = domain.lower().replace(".", "_").replace("-", "_")
    # Remove any other invalid characters for collection names
    normalized_domain = "".join(c for c in normalized_domain if c.isalnum() or c == "_")
    return f"{normalized_domain}_client_articles"


def get_competitor_collection_name(client_domain: str) -> str:
    """
    Generate Qdrant collection name for competitor articles based on client domain.
    
    Format: {client_domain}_competitor_articles
    
    Args:
        client_domain: Client domain name (e.g., "innosys.fr")
        
    Returns:
        Collection name (e.g., "innosys_fr_competitor_articles")
    """
    # Normalize domain: replace dots with underscores, lowercase, remove invalid chars
    normalized_domain = client_domain.lower().replace(".", "_").replace("-", "_")
    # Remove any other invalid characters for collection names
    normalized_domain = "".join(c for c in normalized_domain if c.isalnum() or c == "_")
    return f"{normalized_domain}_competitor_articles"


class QdrantClientWrapper:
    """Wrapper for Qdrant client operations."""

    def __init__(self) -> None:
        """Initialize Qdrant client."""
        try:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            )
            logger.info("Qdrant client initialized", url=settings.qdrant_url)
        except Exception as e:
            logger.error("Failed to initialize Qdrant client", error=str(e))
            raise VectorStoreError(f"Failed to initialize Qdrant client: {e}") from e

    def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1024,  # mxbai-embed-large-v1 dimension
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create a Qdrant collection."""
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance,
                ),
            )
            logger.info(
                "Collection created",
                collection=collection_name,
                vector_size=vector_size,
            )
        except Exception as e:
            logger.error(
                "Failed to create collection",
                collection=collection_name,
                error=str(e),
            )
            raise VectorStoreError(f"Failed to create collection: {e}") from e

    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            collections = self.client.get_collections().collections
            return any(c.name == collection_name for c in collections)
        except Exception as e:
            logger.error("Failed to check collection existence", error=str(e))
            return False

    def ensure_collection_exists(
        self,
        collection_name: str,
        vector_size: int = 1024,  # mxbai-embed-large-v1 dimension
        distance: Distance = Distance.COSINE,
    ) -> None:
        """
        Ensure collection exists, create it if it doesn't.
        
        Args:
            collection_name: Name of the collection
            vector_size: Vector dimension size (default: 1024 for mxbai-embed-large-v1)
            distance: Distance metric (default: COSINE)
        """
        if not self.collection_exists(collection_name):
            logger.info(
                "Collection does not exist, creating it",
                collection=collection_name,
                vector_size=vector_size,
            )
            self.create_collection(
                collection_name=collection_name,
                vector_size=vector_size,
                distance=distance,
            )
            logger.info(
                "Collection created automatically",
                collection=collection_name,
            )

    def upsert_points(
        self,
        collection_name: str,
        points: list[PointStruct],
    ) -> None:
        """Upsert points into collection."""
        # Ensure collection exists before upserting
        self.ensure_collection_exists(collection_name)
        
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(
                "Points upserted",
                collection=collection_name,
                count=len(points),
            )
        except Exception as e:
            logger.error(
                "Failed to upsert points",
                collection=collection_name,
                error=str(e),
            )
            raise VectorStoreError(f"Failed to upsert points: {e}") from e

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter: Optional[Any] = None,
    ) -> list[Any]:
        """Search for similar vectors using query_points (qdrant-client >= 1.10)."""
        # Ensure collection exists before searching
        self.ensure_collection_exists(collection_name)
        
        try:
            # Use query_points instead of deprecated search method
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filter,
            )
            # query_points returns QueryResponse with .points attribute
            return results.points if hasattr(results, 'points') else []
        except Exception as e:
            logger.error(
                "Failed to search vectors",
                collection=collection_name,
                error=str(e),
            )
            raise VectorStoreError(f"Failed to search vectors: {e}") from e

    def delete_points(
        self,
        collection_name: str,
        point_ids: list[UUID],
    ) -> None:
        """Delete points from collection."""
        try:
            from qdrant_client.models import PointIdsList

            self.client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids),
            )
            logger.info(
                "Points deleted",
                collection=collection_name,
                count=len(point_ids),
            )
        except Exception as e:
            logger.error(
                "Failed to delete points",
                collection=collection_name,
                error=str(e),
            )
            raise VectorStoreError(f"Failed to delete points: {e}") from e

    def check_duplicate(
        self,
        collection_name: str,
        query_vector: list[float],
        threshold: float = DUPLICATE_THRESHOLD,
    ) -> Optional[dict[str, Any]]:
        """
        Check for duplicate content via cosine similarity.
        
        Args:
            collection_name: Collection name
            query_vector: Embedding vector to check
            threshold: Similarity threshold (default: 0.92)
            
        Returns:
            Duplicate point info if found (with id and score), None otherwise
        """
        try:
            # Ensure collection exists (will create if needed, but empty collection = no duplicates)
            self.ensure_collection_exists(collection_name)
            
            # If collection is empty, no duplicates
            try:
                collection_info = self.client.get_collection(collection_name)
                # Check if collection has any points
                points_count = getattr(collection_info, 'points_count', 0)
                if points_count == 0:
                    return None
            except Exception:
                # If we can't get collection info, proceed with search anyway
                pass
            
            results = self.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=1,
                score_threshold=threshold,
            )
            
            if results and len(results) > 0:
                result = results[0]
                if result.score >= threshold:
                    logger.debug(
                        "Duplicate found",
                        collection=collection_name,
                        point_id=str(result.id),
                        score=result.score,
                    )
                    return {
                        "point_id": result.id,
                        "score": result.score,
                        "payload": result.payload,
                    }
            
            return None
        except Exception as e:
            logger.error(
                "Failed to check duplicate",
                collection=collection_name,
                error=str(e),
            )
            # Don't raise, just log - indexing should continue
            return None

    def index_article(
        self,
        article_id: int,
        domain: str,
        title: str,
        content_text: str,
        url: str,
        url_hash: str,
        published_date: Optional[datetime] = None,
        author: Optional[str] = None,
        keywords: Optional[dict] = None,
        topic_id: Optional[int] = None,
        check_duplicate: bool = True,
        collection_name: Optional[str] = None,
    ) -> Optional[UUID]:
        """
        Index an article in Qdrant with embedding generation and duplicate detection.
        
        Args:
            article_id: Database article ID
            domain: Domain name
            title: Article title
            content_text: Article text content
            url: Article URL
            url_hash: URL hash for deduplication
            published_date: Publication date (optional)
            author: Author name (optional)
            keywords: Keywords dict (optional)
            topic_id: Topic ID (optional)
            check_duplicate: Whether to check for duplicates before indexing
            collection_name: Collection name (default: COLLECTION_NAME for competitors, CLIENT_COLLECTION_NAME for client)
            
        Returns:
            Qdrant point ID if indexed, None if duplicate found or error
        """
        # Use default collection if not specified
        target_collection = collection_name or COLLECTION_NAME
        
        try:
            # Generate embedding from title + content
            text_for_embedding = f"{title}\n{content_text[:2000]}"  # Limit content for embedding
            embedding = generate_embedding(text_for_embedding)
            
            # Check for duplicates if enabled
            if check_duplicate:
                duplicate = self.check_duplicate(target_collection, embedding)
                if duplicate:
                    logger.info(
                        "Article is duplicate, skipping indexing",
                        article_id=article_id,
                        domain=domain,
                        url=url,
                        collection=target_collection,
                        duplicate_point_id=str(duplicate["point_id"]),
                        similarity_score=duplicate["score"],
                    )
                    return duplicate["point_id"]  # Return existing point ID
            
            # Generate point ID (use article_id as UUID seed for consistency)
            point_id = uuid4()
            
            # Prepare payload
            payload = {
                "article_id": article_id,
                "domain": domain,
                "title": title,
                "url": url,
                "url_hash": url_hash,
                "author": author,
                "topic_id": topic_id,
            }
            
            if published_date:
                payload["published_date"] = published_date.isoformat()
            
            if keywords:
                payload["keywords"] = keywords
            
            # Create point
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )
            
            # Upsert to Qdrant
            self.upsert_points(target_collection, [point])
            
            logger.info(
                "Article indexed in Qdrant",
                article_id=article_id,
                domain=domain,
                collection=target_collection,
                point_id=str(point_id),
            )
            
            return point_id
            
        except Exception as e:
            logger.error(
                "Failed to index article",
                article_id=article_id,
                domain=domain,
                collection=target_collection,
                error=str(e),
            )
            # Don't raise - allow scraping to continue even if indexing fails
            return None

    def get_embeddings_by_article_ids(
        self,
        article_ids: List[int],
        collection_name: str = COLLECTION_NAME,
        batch_size: int = 100,
    ) -> Dict[int, List[float]]:
        """
        Retrieve embeddings from Qdrant by article IDs.
        
        Args:
            article_ids: List of article IDs to retrieve embeddings for
            collection_name: Collection name (default: competitor_articles)
            batch_size: Batch size for scrolling (default: 100)
            
        Returns:
            Dictionary mapping article_id to embedding vector
        """
        # Ensure collection exists before querying
        self.ensure_collection_exists(collection_name)
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchAny
            
            embeddings_dict = {}
            
            # Process in batches to avoid timeouts
            for i in range(0, len(article_ids), batch_size):
                batch_ids = article_ids[i:i + batch_size]
                
                # Create filter for this batch
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="article_id",
                            match=MatchAny(any=batch_ids),
                        )
                    ]
                )
                
                # Scroll through points matching the filter
                scroll_result = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=query_filter,
                    limit=batch_size,
                    with_payload=True,
                    with_vectors=True,
                )
                
                # Extract embeddings
                for point in scroll_result[0]:
                    if point.payload and "article_id" in point.payload:
                        article_id = point.payload["article_id"]
                        if point.vector:
                            embeddings_dict[article_id] = point.vector
                
                logger.debug(
                    "Retrieved embeddings batch",
                    batch_size=len(batch_ids),
                    retrieved=len(embeddings_dict),
                )
            
            logger.info(
                "Embeddings retrieved from Qdrant",
                total_requested=len(article_ids),
                total_found=len(embeddings_dict),
            )
            
            return embeddings_dict
            
        except Exception as e:
            logger.error(
                "Failed to retrieve embeddings by article IDs",
                error=str(e),
                article_ids_count=len(article_ids),
            )
            # Don't raise - return empty dict to allow fallback to generation
            return {}

    def semantic_search(
        self,
        query_text: str,
        limit: int = 10,
        score_threshold: Optional[float] = None,
        domain_filter: Optional[str] = None,
        collection_name: str = COLLECTION_NAME,
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search on articles.
        
        Args:
            query_text: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score (optional)
            domain_filter: Filter by domain (optional)
            collection_name: Collection name (default: competitor_articles)
            
        Returns:
            List of search results with score, point_id, and payload
        """
        # Ensure collection exists before searching
        self.ensure_collection_exists(collection_name)
        
        try:
            # Generate embedding for query
            query_embedding = generate_embedding(query_text)
            
            # Build filter if domain specified
            query_filter = None
            if domain_filter:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="domain",
                            match=MatchValue(value=domain_filter),
                        )
                    ]
                )
            
            # Search
            results = self.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                filter=query_filter,
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "point_id": str(result.id),
                    "score": result.score,
                    "payload": result.payload,
                })
            
            logger.info(
                "Semantic search completed",
                query=query_text[:100],  # Truncate for logging
                results_count=len(formatted_results),
            )
            
            return formatted_results
            
        except Exception as e:
            logger.error(
                "Failed to perform semantic search",
                query=query_text[:100],
                error=str(e),
            )
            raise VectorStoreError(f"Failed to perform semantic search: {e}") from e


# Global instance
qdrant_client = QdrantClientWrapper()

