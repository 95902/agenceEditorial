"""Embeddings utilities using Sentence-Transformers."""

from typing import List

from sentence_transformers import SentenceTransformer

from python_scripts.utils.exceptions import VectorStoreError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

# Model name: mxbai-embed-large-v1 (1024 dimensions)
# mixedbread-ai/mxbai-embed-large-v1 is a high-quality multilingual embedding model
EMBEDDING_MODEL_NAME = "mixedbread-ai/mxbai-embed-large-v1"
EMBEDDING_DIMENSION = 1024

# Global model instance (lazy loaded)
_embedding_model: SentenceTransformer | None = None


def _get_device() -> str:
    """
    Detect and return the best device for model inference.
    
    Returns:
        Device string: "cuda" if GPU available, "cpu" otherwise
    """
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info("GPU detected", device=device_name, device_id=0)
            return "cuda"
        else:
            logger.info("No GPU detected, using CPU")
            return "cpu"
    except ImportError:
        logger.warning("PyTorch not available, using default device")
        return "cpu"
    except Exception as e:
        logger.warning("Error detecting GPU", error=str(e))
        return "cpu"


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            device = _get_device()
            logger.info(
                "Loading embedding model",
                model=EMBEDDING_MODEL_NAME,
                device=device,
            )
            _embedding_model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                device=device,
            )
            logger.info(
                "Embedding model loaded successfully",
                model=EMBEDDING_MODEL_NAME,
                device=device,
            )
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

