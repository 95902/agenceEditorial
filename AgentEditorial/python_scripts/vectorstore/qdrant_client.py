"""Qdrant client wrapper."""

from typing import Any, Optional
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from python_scripts.config.settings import settings
from python_scripts.utils.exceptions import VectorStoreError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


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
        vector_size: int = 384,
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

    def upsert_points(
        self,
        collection_name: str,
        points: list[PointStruct],
    ) -> None:
        """Upsert points into collection."""
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
        """Search for similar vectors."""
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filter,
            )
            return results
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


# Global instance
qdrant_client = QdrantClientWrapper()

