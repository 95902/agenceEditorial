"""End-to-end tests for all API endpoints."""

import pytest
from httpx import AsyncClient

from python_scripts.api.main import app


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteAPI:
    """E2E tests for all API endpoints."""

    @pytest.fixture
    async def client(self) -> AsyncClient:
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    async def test_health_endpoint(self, client: AsyncClient) -> None:
        """Test health check endpoint."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    async def test_sites_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that sites endpoints are accessible."""
        # Test GET /api/v1/sites (list)
        response = await client.get("/api/v1/sites")
        assert response.status_code in [200, 404]  # 404 if no sites yet
        
        # Test GET /api/v1/sites/{domain} (should return 404 for non-existent domain)
        response = await client.get("/api/v1/sites/nonexistent.com")
        assert response.status_code == 404

    async def test_competitors_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that competitors endpoints are accessible."""
        # Test GET /api/v1/competitors/{domain} (should return 404 for non-existent domain)
        response = await client.get("/api/v1/competitors/nonexistent.com")
        assert response.status_code == 404

    async def test_discovery_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that discovery endpoints are accessible."""
        # Test GET /api/v1/discovery/profile/{domain} (should return 404 for non-existent domain)
        response = await client.get("/api/v1/discovery/profile/nonexistent.com")
        assert response.status_code == 404

    async def test_trend_pipeline_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that trend pipeline endpoints are accessible."""
        from uuid import uuid4
        
        # Test GET /api/v1/trend-pipeline/{execution_id}/status (should return 404 for non-existent execution)
        fake_id = uuid4()
        response = await client.get(f"/api/v1/trend-pipeline/{fake_id}/status")
        assert response.status_code == 404

    async def test_executions_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that executions endpoints are accessible."""
        from uuid import uuid4
        
        # Test GET /api/v1/executions/{execution_id} (should return 404 for non-existent execution)
        fake_id = uuid4()
        response = await client.get(f"/api/v1/executions/{fake_id}")
        assert response.status_code == 404

    async def test_errors_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that errors endpoints are accessible."""
        # Test GET /api/v1/errors
        response = await client.get("/api/v1/errors")
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data or "total" in data

    async def test_articles_endpoints_exist(self, client: AsyncClient) -> None:
        """Test that articles endpoints are accessible."""
        # Test GET /api/v1/articles/{article_id}/enriched (should return 404 for non-existent article)
        response = await client.get("/api/v1/articles/99999/enriched")
        assert response.status_code == 404

    async def test_openapi_docs_accessible(self, client: AsyncClient) -> None:
        """Test that OpenAPI documentation is accessible."""
        response = await client.get("/docs")
        assert response.status_code == 200
        
        response = await client.get("/redoc")
        assert response.status_code == 200
        
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema









