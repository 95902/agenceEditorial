"""Unit tests for embeddings utilities (T110 - US6)."""

import pytest

from python_scripts.vectorstore.embeddings_utils import (
    generate_embedding,
    generate_embeddings_batch,
    get_embedding_model,
    EMBEDDING_MODEL_NAME,
)


@pytest.mark.unit
class TestEmbeddingsUtils:
    """Test embeddings utilities."""

    def test_get_embedding_model(self) -> None:
        """Test getting embedding model."""
        model = get_embedding_model()
        assert model is not None
        assert model.get_sentence_embedding_dimension() == 384  # all-MiniLM-L6-v2 dimension

    def test_generate_embedding_single(self) -> None:
        """Test generating embedding for a single text."""
        text = "This is a test article about machine learning and artificial intelligence."
        embedding = generate_embedding(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_generate_embedding_empty_text(self) -> None:
        """Test generating embedding for empty text."""
        embedding = generate_embedding("")
        assert isinstance(embedding, list)
        assert len(embedding) == 384

    def test_generate_embedding_long_text(self) -> None:
        """Test generating embedding for long text."""
        long_text = " ".join(["This is a test sentence."] * 100)
        embedding = generate_embedding(long_text)
        assert isinstance(embedding, list)
        assert len(embedding) == 384

    def test_generate_embeddings_batch(self) -> None:
        """Test generating embeddings for multiple texts."""
        texts = [
            "First article about technology.",
            "Second article about science.",
            "Third article about business.",
        ]
        embeddings = generate_embeddings_batch(texts)
        
        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(len(emb) == 384 for emb in embeddings)

    def test_generate_embeddings_batch_empty(self) -> None:
        """Test generating embeddings for empty batch."""
        embeddings = generate_embeddings_batch([])
        assert isinstance(embeddings, list)
        assert len(embeddings) == 0

    def test_generate_embeddings_batch_single(self) -> None:
        """Test generating embeddings for single text in batch."""
        texts = ["Single article text."]
        embeddings = generate_embeddings_batch(texts)
        
        assert isinstance(embeddings, list)
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384

    def test_generate_embeddings_batch_large(self) -> None:
        """Test generating embeddings for large batch."""
        texts = [f"Article {i} about topic {i}." for i in range(50)]
        embeddings = generate_embeddings_batch(texts, batch_size=10)
        
        assert isinstance(embeddings, list)
        assert len(embeddings) == 50
        assert all(len(emb) == 384 for emb in embeddings)

    def test_embedding_consistency(self) -> None:
        """Test that same text produces same embedding."""
        text = "Consistent test text for embedding."
        embedding1 = generate_embedding(text)
        embedding2 = generate_embedding(text)
        
        # Embeddings should be identical (normalized)
        assert embedding1 == embedding2

    def test_embedding_different_texts(self) -> None:
        """Test that different texts produce different embeddings."""
        text1 = "First article about machine learning."
        text2 = "Second article about deep learning."
        
        embedding1 = generate_embedding(text1)
        embedding2 = generate_embedding(text2)
        
        # Embeddings should be different
        assert embedding1 != embedding2

    def test_embedding_normalization(self) -> None:
        """Test that embeddings are normalized (unit vectors)."""
        text = "Test text for normalization check."
        embedding = generate_embedding(text)
        
        # Check that embedding is normalized (magnitude should be ~1.0)
        magnitude = sum(x * x for x in embedding) ** 0.5
        assert abs(magnitude - 1.0) < 0.01  # Allow small floating point errors

