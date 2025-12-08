"""Unit tests for competitor search sources (T073 - US3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from python_scripts.agents.agent_competitor import CompetitorSearchAgent


@pytest.mark.unit
@pytest.mark.asyncio
class TestCompetitorSearchSources:
    """Test competitor search sources (Tavily and DuckDuckGo) with mocks."""

    @pytest.fixture
    def agent(self) -> CompetitorSearchAgent:
        """Create competitor search agent instance."""
        return CompetitorSearchAgent()

    async def test_search_tavily_success(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test successful Tavily search."""
        # Mock Tavily API response
        mock_response = {
            "results": [
                {
                    "url": "https://example.fr",
                    "title": "Example ESN",
                    "content": "ESN spécialisée en développement",
                    "score": 0.95,
                },
                {
                    "url": "https://test.fr",
                    "title": "Test SSII",
                    "content": "SSII Paris",
                    "score": 0.85,
                },
            ]
        }

        # Mock httpx.AsyncClient
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await agent._search_tavily("ESN Paris")

        assert len(results) == 2
        assert results[0]["url"] == "https://example.fr"
        assert results[0]["domain"] == "example.fr"
        assert results[0]["source"] == "tavily"
        assert results[1]["url"] == "https://test.fr"
        assert results[1]["domain"] == "test.fr"

    async def test_search_tavily_api_error(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test Tavily search with API error."""
        # Mock httpx error
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("API Error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await agent._search_tavily("ESN Paris")

        # Should return empty list on error
        assert results == []

    async def test_search_tavily_empty_results(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test Tavily search with empty results."""
        mock_response = {"results": []}

        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await agent._search_tavily("ESN Paris")

        assert results == []

    async def test_search_tavily_filters_fr_domains(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test that Tavily search filters only .fr domains."""
        mock_response = {
            "results": [
                {
                    "url": "https://example.fr",
                    "title": "Example FR",
                    "content": "ESN française",
                    "score": 0.95,
                },
                {
                    "url": "https://example.com",
                    "title": "Example COM",
                    "content": "ESN internationale",
                    "score": 0.85,
                },
                {
                    "url": "https://test.fr",
                    "title": "Test FR",
                    "content": "SSII",
                    "score": 0.80,
                },
            ]
        }

        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await agent._search_tavily("ESN")

        # Should only include .fr domains
        assert len(results) == 2
        assert all(".fr" in r["url"] for r in results)
        assert not any(".com" in r["url"] for r in results)

    async def test_search_duckduckgo_success(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test successful DuckDuckGo search."""
        # Mock DDGS results
        mock_ddgs_results = [
            {
                "href": "https://example.fr",
                "title": "Example ESN",
                "body": "ESN spécialisée en développement",
            },
            {
                "href": "https://test.fr",
                "title": "Test SSII",
                "body": "SSII Paris",
            },
        ]

        # Mock DDGS context manager
        mock_ddgs = MagicMock()
        mock_ddgs.text = MagicMock(return_value=iter(mock_ddgs_results))
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=None)

        with patch("python_scripts.agents.agent_competitor.DDGS", return_value=mock_ddgs):
            results = await agent._search_duckduckgo("ESN Paris")

        assert len(results) >= 2
        assert any(r["url"] == "https://example.fr" for r in results)
        assert any(r["domain"] == "example.fr" for r in results)
        assert any(r["source"] == "duckduckgo" for r in results)

    async def test_search_duckduckgo_filters_fr_domains(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test that DuckDuckGo search filters only .fr domains."""
        mock_ddgs_results = [
            {
                "href": "https://example.fr",
                "title": "Example FR",
                "body": "ESN française",
            },
            {
                "href": "https://example.com",
                "title": "Example COM",
                "body": "ESN internationale",
            },
            {
                "href": "https://test.fr",
                "title": "Test FR",
                "body": "SSII",
            },
        ]

        mock_ddgs = MagicMock()
        mock_ddgs.text = MagicMock(return_value=iter(mock_ddgs_results))
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=None)

        with patch("python_scripts.agents.agent_competitor.DDGS", return_value=mock_ddgs):
            results = await agent._search_duckduckgo("ESN")

        # Should only include .fr domains
        assert len(results) == 2
        assert all(".fr" in r["url"] for r in results)
        assert not any(".com" in r["url"] for r in results)

    async def test_search_duckduckgo_empty_results(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test DuckDuckGo search with empty results."""
        mock_ddgs = MagicMock()
        mock_ddgs.text = MagicMock(return_value=iter([]))
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=None)

        with patch("python_scripts.agents.agent_competitor.DDGS", return_value=mock_ddgs):
            results = await agent._search_duckduckgo("ESN Paris")

        assert results == []

    async def test_search_duckduckgo_error_handling(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test DuckDuckGo search error handling."""
        mock_ddgs = MagicMock()
        mock_ddgs.text = MagicMock(side_effect=Exception("Search error"))
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=None)

        with patch("python_scripts.agents.agent_competitor.DDGS", return_value=mock_ddgs):
            results = await agent._search_duckduckgo("ESN Paris")

        # Should return empty list on error
        assert results == []

    async def test_extract_domain_from_url(self, agent: CompetitorSearchAgent) -> None:
        """Test domain extraction from URL."""
        # Test various URL formats
        assert agent._extract_domain_from_url("https://example.fr") == "example.fr"
        assert agent._extract_domain_from_url("https://www.example.fr") == "example.fr"
        assert agent._extract_domain_from_url("https://example.fr/page") == "example.fr"
        assert agent._extract_domain_from_url("http://test.fr/path/to/page") == "test.fr"
        assert agent._extract_domain_from_url("https://example.com") == ""  # Not .fr
        assert agent._extract_domain_from_url("invalid-url") == ""
        assert agent._extract_domain_from_url("") == ""

    async def test_search_tavily_invalid_response(self, agent: CompetitorSearchAgent, mocker) -> None:
        """Test Tavily search with invalid response format."""
        mock_response = {"invalid": "format"}

        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await agent._search_tavily("ESN Paris")

        # Should handle gracefully and return empty list
        assert isinstance(results, list)

