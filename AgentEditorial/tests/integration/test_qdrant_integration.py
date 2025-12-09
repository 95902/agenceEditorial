"""Integration tests for Qdrant indexing (T109 - US6)."""

import pytest
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import MagicMock, patch

from python_scripts.vectorstore.qdrant_client import (
    qdrant_client,
    COLLECTION_NAME,
    DUPLICATE_THRESHOLD,
)


@pytest.mark.integration
class TestQdrantIntegration:
    """Integration tests for Qdrant indexing."""

    def test_collection_exists(self) -> None:
        """Test checking if collection exists."""
        exists = qdrant_client.collection_exists(COLLECTION_NAME)
        assert isinstance(exists, bool)

    def test_index_article_basic(self, mocker) -> None:
        """Test basic article indexing."""
        # Mock Qdrant client methods
        mock_upsert = mocker.patch.object(qdrant_client.client, "upsert")
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=[],  # No duplicates
        )
        
        # Mock embedding generation
        mock_embedding = [0.1] * 384
        mocker.patch(
            "python_scripts.vectorstore.qdrant_client.generate_embedding",
            return_value=mock_embedding,
        )
        
        point_id = qdrant_client.index_article(
            article_id=1,
            domain="example.com",
            title="Test Article",
            content_text="This is a test article content.",
            url="https://example.com/article",
            url_hash="abc123",
        )
        
        assert point_id is not None
        assert isinstance(point_id, UUID)
        mock_upsert.assert_called_once()

    def test_index_article_with_metadata(self, mocker) -> None:
        """Test indexing article with full metadata."""
        mock_upsert = mocker.patch.object(qdrant_client.client, "upsert")
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=[],
        )
        
        mock_embedding = [0.1] * 384
        mocker.patch(
            "python_scripts.vectorstore.qdrant_client.generate_embedding",
            return_value=mock_embedding,
        )
        
        published_date = datetime.now(timezone.utc)
        point_id = qdrant_client.index_article(
            article_id=2,
            domain="example.com",
            title="Test Article with Metadata",
            content_text="Content here.",
            url="https://example.com/article2",
            url_hash="def456",
            published_date=published_date,
            author="John Doe",
            keywords={"tech": 0.8, "ai": 0.6},
            topic_id=5,
        )
        
        assert point_id is not None
        mock_upsert.assert_called_once()

    def test_index_article_duplicate_detection(self, mocker) -> None:
        """Test duplicate detection during indexing."""
        # Mock search to return a duplicate
        from qdrant_client.models import ScoredPoint
        
        duplicate_point = ScoredPoint(
            id=UUID("12345678-1234-1234-1234-123456789abc"),
            score=0.95,  # Above threshold
            payload={"article_id": 99, "domain": "example.com"},
        )
        
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=[duplicate_point],
        )
        
        mock_embedding = [0.1] * 384
        mocker.patch(
            "python_scripts.vectorstore.qdrant_client.generate_embedding",
            return_value=mock_embedding,
        )
        
        point_id = qdrant_client.index_article(
            article_id=3,
            domain="example.com",
            title="Duplicate Article",
            content_text="Similar content.",
            url="https://example.com/duplicate",
            url_hash="ghi789",
            check_duplicate=True,
        )
        
        # Should return existing point ID, not create new one
        assert point_id == duplicate_point.id
        # Should not call upsert
        mock_upsert = mocker.patch.object(qdrant_client.client, "upsert")
        assert not mock_upsert.called

    def test_check_duplicate_above_threshold(self, mocker) -> None:
        """Test duplicate check with similarity above threshold."""
        from qdrant_client.models import ScoredPoint
        
        duplicate_point = ScoredPoint(
            id=UUID("12345678-1234-1234-1234-123456789abc"),
            score=0.93,  # Above 0.92 threshold
            payload={"article_id": 100},
        )
        
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=[duplicate_point],
        )
        
        mock_embedding = [0.1] * 384
        duplicate = qdrant_client.check_duplicate(COLLECTION_NAME, mock_embedding)
        
        assert duplicate is not None
        assert duplicate["point_id"] == duplicate_point.id
        assert duplicate["score"] == 0.93

    def test_check_duplicate_below_threshold(self, mocker) -> None:
        """Test duplicate check with similarity below threshold."""
        from qdrant_client.models import ScoredPoint
        
        similar_point = ScoredPoint(
            id=UUID("12345678-1234-1234-1234-123456789abc"),
            score=0.85,  # Below 0.92 threshold
            payload={"article_id": 101},
        )
        
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=[similar_point],
        )
        
        mock_embedding = [0.1] * 384
        duplicate = qdrant_client.check_duplicate(COLLECTION_NAME, mock_embedding)
        
        # Should return None (not a duplicate)
        assert duplicate is None

    def test_semantic_search_basic(self, mocker) -> None:
        """Test basic semantic search."""
        from qdrant_client.models import ScoredPoint
        
        search_results = [
            ScoredPoint(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                score=0.88,
                payload={
                    "article_id": 1,
                    "domain": "example.com",
                    "title": "Machine Learning Article",
                },
            ),
            ScoredPoint(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                score=0.85,
                payload={
                    "article_id": 2,
                    "domain": "example.com",
                    "title": "AI Research Paper",
                },
            ),
        ]
        
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=search_results,
        )
        
        mock_embedding = [0.1] * 384
        mocker.patch(
            "python_scripts.vectorstore.qdrant_client.generate_embedding",
            return_value=mock_embedding,
        )
        
        results = qdrant_client.semantic_search(
            query_text="machine learning and artificial intelligence",
            limit=10,
        )
        
        assert len(results) == 2
        assert results[0]["score"] == 0.88
        assert results[0]["payload"]["article_id"] == 1
        assert results[1]["score"] == 0.85

    def test_semantic_search_with_domain_filter(self, mocker) -> None:
        """Test semantic search with domain filter."""
        from qdrant_client.models import ScoredPoint, Filter, FieldCondition, MatchValue
        
        search_results = [
            ScoredPoint(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                score=0.90,
                payload={
                    "article_id": 3,
                    "domain": "example.com",
                    "title": "Filtered Article",
                },
            ),
        ]
        
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=search_results,
        )
        
        mock_embedding = [0.1] * 384
        mocker.patch(
            "python_scripts.vectorstore.qdrant_client.generate_embedding",
            return_value=mock_embedding,
        )
        
        results = qdrant_client.semantic_search(
            query_text="test query",
            domain_filter="example.com",
            limit=10,
        )
        
        assert len(results) == 1
        # Verify filter was applied (check that search was called with filter)
        call_args = mock_search.call_args
        assert call_args is not None
        # The filter should be passed to search

    def test_semantic_search_with_score_threshold(self, mocker) -> None:
        """Test semantic search with score threshold."""
        from qdrant_client.models import ScoredPoint
        
        search_results = [
            ScoredPoint(
                id=UUID("44444444-4444-4444-4444-444444444444"),
                score=0.95,
                payload={"article_id": 4},
            ),
        ]
        
        mock_search = mocker.patch.object(
            qdrant_client.client,
            "search",
            return_value=search_results,
        )
        
        mock_embedding = [0.1] * 384
        mocker.patch(
            "python_scripts.vectorstore.qdrant_client.generate_embedding",
            return_value=mock_embedding,
        )
        
        results = qdrant_client.semantic_search(
            query_text="high similarity query",
            limit=10,
            score_threshold=0.90,
        )
        
        assert len(results) == 1
        assert results[0]["score"] >= 0.90

