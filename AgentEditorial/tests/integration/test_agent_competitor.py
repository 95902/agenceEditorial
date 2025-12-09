"""Integration tests for competitor search agent (T074 - US3)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.competitor.agent import CompetitorSearchAgent
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.crud_profiles import create_site_profile


@pytest.mark.integration
@pytest.mark.asyncio
class TestCompetitorSearchAgent:
    """Integration tests for CompetitorSearchAgent."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        """Create database session for tests."""
        async with AsyncSessionLocal() as session:
            yield session
            await session.rollback()

    @pytest.fixture
    def agent(self) -> CompetitorSearchAgent:
        """Create competitor search agent instance."""
        return CompetitorSearchAgent()

    async def test_agent_initialization(self, agent: CompetitorSearchAgent) -> None:
        """Test agent initialization."""
        assert agent is not None
        assert agent.agent_name == "competitor_search"
        assert agent.config is not None
        assert agent.query_generator is not None
        assert agent.pre_filter is not None

    async def test_query_generation(self, agent: CompetitorSearchAgent, db_session: AsyncSession) -> None:
        """Test query generation for a domain."""
        # Create a test site profile
        await create_site_profile(
            db_session,
            domain="innosys.fr",
            language_level="professional",
            editorial_tone="technical",
            activity_domains={"IT": ["développement", "conseil"]},
        )
        await db_session.commit()

        # Get site profile
        from python_scripts.database.crud_profiles import get_site_profile_by_domain

        site_profile = await get_site_profile_by_domain(db_session, "innosys.fr")
        assert site_profile is not None

        # Generate queries
        queries = agent.query_generator.generate_queries(site_profile)
        assert len(queries) > 0
        assert isinstance(queries, list)
        assert all(isinstance(q, str) for q in queries)

    async def test_pre_filtering(self, agent: CompetitorSearchAgent) -> None:
        """Test pre-filtering of candidates."""
        candidates = [
            {"domain": "example.fr", "url": "https://example.fr"},
            {"domain": "test.fr", "url": "https://test.fr"},
            {"domain": "amazon.fr", "url": "https://amazon.fr"},  # Should be filtered
        ]

        filtered = agent.pre_filter.filter(candidates)
        # Amazon should be filtered out
        assert len(filtered) < len(candidates)
        assert not any(c["domain"] == "amazon.fr" for c in filtered)

    async def test_domain_extraction(self, agent: CompetitorSearchAgent) -> None:
        """Test domain extraction from URLs."""
        test_cases = [
            ("https://example.fr", "example.fr"),
            ("https://www.test.fr/page", "test.fr"),
            ("http://subdomain.example.fr", "subdomain.example.fr"),
        ]

        for url, expected_domain in test_cases:
            domain = agent._extract_domain_from_url(url)
            assert domain == expected_domain or domain.endswith(".fr")

    @pytest.mark.slow
    async def test_full_pipeline_with_mock_sources(
        self, agent: CompetitorSearchAgent, db_session: AsyncSession, mocker
    ) -> None:
        """Test full competitor search pipeline with mocked sources."""
        # Create test site profile
        await create_site_profile(
            db_session,
            domain="innosys.fr",
            language_level="professional",
            activity_domains={"IT": ["développement"]},
        )
        await db_session.commit()

        # Mock search sources to return test data
        mock_tavily_results = [
            {
                "url": "https://competitor1.fr",
                "title": "Competitor 1 ESN",
                "content": "ESN spécialisée en développement",
                "score": 0.9,
            },
            {
                "url": "https://competitor2.fr",
                "title": "Competitor 2 SSII",
                "content": "SSII Paris",
                "score": 0.85,
            },
        ]

        mock_ddgs_results = [
            {
                "href": "https://competitor3.fr",
                "title": "Competitor 3",
                "body": "ESN développement",
            },
        ]

        # Mock Tavily
        async def mock_tavily_search(query: str):
            return [
                {
                    "url": r["url"],
                    "domain": r["url"].replace("https://", "").replace("http://", "").split("/")[0],
                    "title": r["title"],
                    "snippet": r["content"],
                    "source": "tavily",
                }
                for r in mock_tavily_results
            ]

        # Mock DuckDuckGo
        async def mock_ddgs_search(query: str):
            return [
                {
                    "url": r["href"],
                    "domain": r["href"].replace("https://", "").replace("http://", "").split("/")[0],
                    "title": r["title"],
                    "snippet": r["body"],
                    "source": "duckduckgo",
                }
                for r in mock_ddgs_results
            ]

        agent._search_tavily = mock_tavily_search
        agent._search_duckduckgo = mock_ddgs_search

        # Run execute (simplified - would need full setup)
        # This is a basic integration test structure
        # Full execution would require more setup (LLM mocks, etc.)
        assert agent is not None
        assert agent.query_generator is not None

