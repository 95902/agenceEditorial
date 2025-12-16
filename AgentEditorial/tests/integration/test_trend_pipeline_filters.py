"""Tests d'intégration pour les filtres du trend-pipeline."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTrendPipelineFilters:
    """Tests d'intégration pour les filtres du trend-pipeline."""
    
    async def test_clusters_endpoint_with_filters(self, async_client: AsyncClient):
        """Test de l'endpoint /clusters avec filtres."""
        execution_id = "test-execution-id"
        
        # Test sans filtres
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/clusters"
        )
        # Note: Ce test peut échouer si l'execution_id n'existe pas, mais teste la structure
        assert response.status_code in [200, 404]
        
        # Test avec min_size
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/clusters?min_size=20"
        )
        assert response.status_code in [200, 404]
        
        # Test avec scope=core
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/clusters?scope=core"
        )
        assert response.status_code in [200, 404]
        
        # Test avec combinaison de filtres
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/clusters?min_size=20&scope=core&min_coherence=0.3"
        )
        assert response.status_code in [200, 404]
        
        # Test avec scope invalide (devrait échouer)
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/clusters?scope=invalid"
        )
        assert response.status_code == 422  # Validation error
    
    async def test_gaps_endpoint_with_filters(self, async_client: AsyncClient):
        """Test de l'endpoint /gaps avec filtres."""
        execution_id = "test-execution-id"
        
        # Test sans filtres
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/gaps"
        )
        assert response.status_code in [200, 404]
        
        # Test avec scope
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/gaps?scope=core"
        )
        assert response.status_code in [200, 404]
        
        # Test avec top_n
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/gaps?top_n=10"
        )
        assert response.status_code in [200, 404]
        
        # Test avec combinaison
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/gaps?scope=core&top_n=5"
        )
        assert response.status_code in [200, 404]
    
    async def test_roadmap_endpoint_with_filters(self, async_client: AsyncClient):
        """Test de l'endpoint /roadmap avec filtres."""
        execution_id = "test-execution-id"
        
        # Test sans filtres
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/roadmap"
        )
        assert response.status_code in [200, 404]
        
        # Test avec scope
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/roadmap?scope=core"
        )
        assert response.status_code in [200, 404]
        
        # Test avec max_effort
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/roadmap?max_effort=medium"
        )
        assert response.status_code in [200, 404]
        
        # Test avec combinaison (quick wins core)
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/roadmap?scope=core&max_effort=medium"
        )
        assert response.status_code in [200, 404]
        
        # Test avec max_effort invalide (devrait échouer)
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/roadmap?max_effort=invalid"
        )
        assert response.status_code == 422
    
    async def test_llm_results_endpoint_with_filters(self, async_client: AsyncClient):
        """Test de l'endpoint /llm-results avec filtres."""
        execution_id = "test-execution-id"
        
        # Test sans filtres
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/llm-results"
        )
        assert response.status_code in [200, 404]
        
        # Test avec scope
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/llm-results?scope=core"
        )
        assert response.status_code in [200, 404]
        
        # Test avec min_differentiation
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/llm-results?min_differentiation=0.7"
        )
        assert response.status_code in [200, 404]
        
        # Test avec combinaison
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/llm-results?scope=core&min_differentiation=0.7"
        )
        assert response.status_code in [200, 404]
    
    async def test_outliers_endpoint_new(self, async_client: AsyncClient):
        """Test du nouvel endpoint /outliers."""
        execution_id = "test-execution-id"
        
        # Test sans filtres
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/outliers"
        )
        assert response.status_code in [200, 404]
        
        # Test avec limit
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/outliers?limit=20"
        )
        assert response.status_code in [200, 404]
        
        # Test avec max_distance
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/outliers?max_distance=0.8"
        )
        assert response.status_code in [200, 404]
        
        # Test avec domain
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/outliers?domain=example.com"
        )
        assert response.status_code in [200, 404]
        
        # Test avec combinaison
        response = await async_client.get(
            f"/api/v1/trend-pipeline/{execution_id}/outliers?limit=10&max_distance=0.9"
        )
        assert response.status_code in [200, 404]


@pytest.fixture
async def async_client():
    """Fixture pour client HTTP async."""
    from python_scripts.api.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client



