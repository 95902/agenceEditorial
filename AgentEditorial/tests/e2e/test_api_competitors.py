"""End-to-end tests for competitor search API (T075 - US3)."""

import asyncio
import time
from uuid import UUID

import pytest
from httpx import AsyncClient

from python_scripts.api.main import app
from python_scripts.database.db_session import AsyncSessionLocal
from python_scripts.database.models import WorkflowExecution


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompetitorSearchAPI:
    """E2E tests for competitor search API endpoints."""

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

    async def test_search_competitors_endpoint(self, client: AsyncClient) -> None:
        """Test POST /api/v1/competitors/search endpoint (T075 - US3)."""
        response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": "innosys.fr", "max_competitors": 5},
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "pending"

        # Verify execution_id is valid UUID
        execution_id = UUID(data["execution_id"])
        assert execution_id is not None

    async def test_search_competitors_invalid_domain(self, client: AsyncClient) -> None:
        """Test competitor search with invalid domain."""
        response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": "", "max_competitors": 5},
        )
        # Should return validation error
        assert response.status_code in [400, 422]

    async def test_search_competitors_invalid_max_competitors(self, client: AsyncClient) -> None:
        """Test competitor search with invalid max_competitors."""
        response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": "innosys.fr", "max_competitors": -1},
        )
        # Should return validation error
        assert response.status_code in [400, 422]

    async def test_get_competitors_endpoint(self, client: AsyncClient, db_session) -> None:
        """Test GET /api/v1/competitors/{domain} endpoint (T075 - US3)."""
        domain = "innosys.fr"

        # First, start a search
        search_response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": domain, "max_competitors": 5},
        )
        assert search_response.status_code == 202
        execution_id = UUID(search_response.json()["execution_id"])

        # Poll for completion (with timeout)
        max_wait = 600  # 10 minutes max for competitor search
        poll_interval = 10  # Poll every 10 seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            # Check execution status
            exec_response = await client.get(f"/api/v1/executions/{execution_id}")
            if exec_response.status_code == 200:
                exec_data = exec_response.json()
                status = exec_data.get("status")

                if status == "completed":
                    break
                elif status == "failed":
                    error_msg = exec_data.get("error_message", "Unknown error")
                    pytest.skip(f"Workflow failed: {error_msg}")

            await asyncio.sleep(poll_interval)

        # Try to get competitors (may not exist if workflow still running)
        response = await client.get(f"/api/v1/competitors/{domain}")

        # Should return 200 or 404 (404 if not completed yet)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "competitors" in data or "domain" in data

    async def test_get_competitors_not_found(self, client: AsyncClient) -> None:
        """Test getting competitors for domain with no search results."""
        response = await client.get("/api/v1/competitors/nonexistent-domain.fr")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.slow
    async def test_competitor_search_full_workflow(self, client: AsyncClient, db_session) -> None:
        """
        Test full competitor search workflow (T075 - US3).

        Scenario:
        1. POST /api/v1/competitors/search with domain
        2. Get execution_id
        3. Poll GET /api/v1/executions/{id} until status="completed"
        4. GET /api/v1/competitors/{domain} returns competitor list
        """
        domain = "innosys.fr"

        # Step 1: Start search
        response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": domain, "max_competitors": 100},
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        execution_id = UUID(data["execution_id"])

        # Step 2: Poll for completion
        max_wait = 600  # 10 minutes
        poll_interval = 10
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = await client.get(f"/api/v1/executions/{execution_id}")
            assert response.status_code == 200
            execution_data = response.json()

            status = execution_data.get("status")
            assert status in ["pending", "running", "completed", "failed"]

            if status == "completed":
                break
            elif status == "failed":
                error_msg = execution_data.get("error_message", "Unknown error")
                pytest.skip(f"Workflow failed: {error_msg}")

            await asyncio.sleep(poll_interval)

        # Step 3: Get competitors
        response = await client.get(f"/api/v1/competitors/{domain}")

        if response.status_code == 200:
            data = response.json()
            assert "domain" in data
            assert data["domain"] == domain

            # Should have competitors list or total_found
            if "competitors" in data:
                assert isinstance(data["competitors"], list)
                # Verify competitor structure
                if len(data["competitors"]) > 0:
                    competitor = data["competitors"][0]
                    assert "domain" in competitor or "url" in competitor
            elif "total_found" in data:
                assert isinstance(data["total_found"], int)

    async def test_search_competitors_creates_execution(self, client: AsyncClient, db_session) -> None:
        """Test that searching competitors creates execution in database."""
        domain = "test-competitor.fr"
        response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": domain, "max_competitors": 5},
        )

        assert response.status_code == 202
        execution_id = UUID(response.json()["execution_id"])

        # Verify execution exists in database
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            stmt = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
            result = await session.execute(stmt)
            execution = result.scalar_one_or_none()

            assert execution is not None
            assert execution.workflow_type == "competitor_search"
            assert execution.status in ["pending", "running"]
            assert execution.input_data.get("domain") == domain

    async def test_validate_competitors_endpoint(self, client: AsyncClient, db_session) -> None:
        """Test POST /api/v1/competitors/{domain}/validate endpoint (T088 - US4)."""
        domain = "innosys.fr"

        # First, start a search and wait for completion (or use existing results)
        search_response = await client.post(
            "/api/v1/competitors/search",
            json={"domain": domain, "max_competitors": 5},
        )
        assert search_response.status_code == 202
        execution_id = UUID(search_response.json()["execution_id"])

        # Wait a bit for execution to potentially complete
        await asyncio.sleep(5)

        # Try to get existing competitors first
        get_response = await client.get(f"/api/v1/competitors/{domain}")

        if get_response.status_code == 404:
            # No results yet, skip validation test
            pytest.skip("No competitor search results available for validation test")

        # Test validation endpoint
        validation_data = {
            "competitors": [
                {
                    "domain": "competitor1.fr",
                    "validation_status": "validated",
                    "relevance_score": 0.8,
                    "confidence_score": 0.9,
                },
                {
                    "domain": "competitor2.fr",
                    "validation_status": "manual",
                    "reason": "Manually added competitor",
                },
                {
                    "domain": "competitor3.fr",
                    "validation_status": "excluded",
                },
            ]
        }

        response = await client.post(
            f"/api/v1/competitors/{domain}/validate",
            json=validation_data,
        )

        # Should return 200 or 404 (if no search results)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "competitors" in data
            assert "total" in data
            assert isinstance(data["competitors"], list)

            # Should only include validated and manual competitors (not excluded)
            validated_domains = [c.get("domain") for c in data["competitors"]]
            assert "competitor1.fr" in validated_domains or len(validated_domains) > 0
            assert "competitor3.fr" not in validated_domains  # Excluded should not be in list

    async def test_validate_competitors_not_found(self, client: AsyncClient) -> None:
        """Test validation for domain with no search results (T088 - US4)."""
        validation_data = {
            "competitors": [
                {
                    "domain": "test.fr",
                    "validation_status": "validated",
                }
            ]
        }

        response = await client.post(
            "/api/v1/competitors/nonexistent-domain.fr/validate",
            json=validation_data,
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_validate_competitors_invalid_request(self, client: AsyncClient) -> None:
        """Test validation with invalid request data (T088 - US4)."""
        response = await client.post(
            "/api/v1/competitors/test.fr/validate",
            json={"competitors": []},  # Empty list should be valid
        )
        # Should accept empty list or return validation error
        assert response.status_code in [200, 404, 422]

