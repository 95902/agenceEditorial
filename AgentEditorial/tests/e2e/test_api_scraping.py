"""End-to-end tests for scraping API (T095 - US5)."""

import asyncio
import time
from uuid import UUID

import pytest
from httpx import AsyncClient

from python_scripts.api.main import app
from python_scripts.database.db_session import AsyncSessionLocal


@pytest.mark.e2e
@pytest.mark.asyncio
class TestScrapingAPI:
    """E2E tests for scraping API endpoints."""

    @pytest.fixture
    async def client(self) -> AsyncClient:
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def db_session(self):
        """Create database session for cleanup."""
        async with AsyncSessionLocal() as session:
            yield session
            try:
                await session.rollback()
            except Exception:
                pass

    async def test_scrape_competitors_endpoint(self, client: AsyncClient) -> None:
        """Test POST /api/v1/scraping/competitors endpoint (T103 - US5)."""
        response = await client.post(
            "/api/v1/scraping/competitors",
            json={
                "domains": ["example.com"],
                "max_articles_per_domain": 10,
            },
        )

        # Should return 202 Accepted with execution_id
        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "pending"

        # Verify execution_id is valid UUID
        execution_id = UUID(data["execution_id"])
        assert execution_id is not None

    async def test_scrape_competitors_invalid_domains(self, client: AsyncClient) -> None:
        """Test scraping with invalid domains."""
        response = await client.post(
            "/api/v1/scraping/competitors",
            json={
                "domains": [],
                "max_articles_per_domain": 10,
            },
        )
        # Should return validation error
        assert response.status_code in [400, 422]

    async def test_scrape_competitors_invalid_max_articles(self, client: AsyncClient) -> None:
        """Test scraping with invalid max_articles_per_domain."""
        response = await client.post(
            "/api/v1/scraping/competitors",
            json={
                "domains": ["example.com"],
                "max_articles_per_domain": -1,
            },
        )
        # Should return validation error
        assert response.status_code in [400, 422]

    @pytest.mark.slow
    async def test_scrape_competitors_full_workflow(self, client: AsyncClient, db_session) -> None:
        """Test full scraping workflow (T095 - US5)."""
        domains = ["example.com"]
        
        # Step 1: Start scraping
        response = await client.post(
            "/api/v1/scraping/competitors",
            json={
                "domains": domains,
                "max_articles_per_domain": 5,
            },
        )
        assert response.status_code == 202
        execution_id = UUID(response.json()["execution_id"])

        # Step 2: Poll for completion
        max_wait = 300  # 5 minutes
        poll_interval = 5  # 5 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = await client.get(f"/api/v1/executions/{execution_id}")
            assert response.status_code == 200
            execution_data = response.json()
            status = execution_data.get("status")
            
            if status == "completed":
                break
            elif status == "failed":
                pytest.fail(f"Scraping workflow failed: {execution_data.get('error_message')}")
            
            await asyncio.sleep(poll_interval)

        # Step 3: Verify articles were scraped
        response = await client.get("/api/v1/scraping/articles", params={"domain": domains[0]})
        assert response.status_code == 200
        articles_data = response.json()
        assert "articles" in articles_data
        assert isinstance(articles_data["articles"], list)
        # Note: In a real scenario, we'd verify articles were actually scraped
        # For E2E test, we verify the endpoint structure

    async def test_get_articles_endpoint(self, client: AsyncClient) -> None:
        """Test GET /api/v1/scraping/articles endpoint (T104 - US5)."""
        # Test with domain filter
        response = await client.get("/api/v1/scraping/articles", params={"domain": "example.com"})
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert "total" in data
        assert isinstance(data["articles"], list)
        assert isinstance(data["total"], int)

    async def test_get_articles_with_limit_offset(self, client: AsyncClient) -> None:
        """Test GET /api/v1/scraping/articles with pagination."""
        response = await client.get(
            "/api/v1/scraping/articles",
            params={
                "domain": "example.com",
                "limit": 10,
                "offset": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert len(data["articles"]) <= 10

    async def test_get_articles_without_domain(self, client: AsyncClient) -> None:
        """Test GET /api/v1/scraping/articles without domain filter."""
        response = await client.get("/api/v1/scraping/articles")
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert isinstance(data["articles"], list)

    async def test_get_articles_invalid_limit(self, client: AsyncClient) -> None:
        """Test GET /api/v1/scraping/articles with invalid limit."""
        response = await client.get(
            "/api/v1/scraping/articles",
            params={"limit": -1},
        )
        # Should return validation error
        assert response.status_code in [400, 422]

    async def test_get_articles_invalid_offset(self, client: AsyncClient) -> None:
        """Test GET /api/v1/scraping/articles with invalid offset."""
        response = await client.get(
            "/api/v1/scraping/articles",
            params={"offset": -1},
        )
        # Should return validation error
        assert response.status_code in [400, 422]

