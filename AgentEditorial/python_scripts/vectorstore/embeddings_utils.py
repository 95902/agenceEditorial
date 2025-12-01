"""Embeddings utilities using Sentence-Transformers."""

from typing import List

from sentence_transformers import SentenceTransformer

from python_scripts.utils.exceptions import VectorStoreError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

# Model name: all-MiniLM-L6-v2 (384 dimensions)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Global model instance (lazy loaded)
_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            logger.info("Loading embedding model", model=EMBEDDING_MODEL_NAME)
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error("Failed to load embedding model", error=str(e))
            raise VectorStoreError(f"Failed to load embedding model: {e}") from e
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text."""
    try:
        model = get_embedding_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error("Failed to generate embedding", error=str(e))
        raise VectorStoreError(f"Failed to generate embedding: {e}") from e


def generate_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Generate embeddings for multiple texts in batch."""
    try:
        model = get_embedding_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()
    except Exception as e:
        logger.error("Failed to generate embeddings batch", error=str(e))
        raise VectorStoreError(f"Failed to generate embeddings batch: {e}") from e

