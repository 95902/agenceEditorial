import pytest
from httpx import AsyncClient

from python_scripts.api.main import app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_article_generation_endpoint_starts(client_domain: str | None = None) -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "topic": "Comment structurer un article de blog SEO en 2025",
            "keywords": "SEO,contenu,blog",
            "tone": "professional",
            "target_words": 1200,
            "language": "fr",
            "site_profile_id": None,
            "generate_images": False,
        }
        response = await client.post("/api/v1/articles/generate", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert "plan_id" in data

















