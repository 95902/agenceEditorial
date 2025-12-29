import pytest
from httpx import AsyncClient

from python_scripts.api.main import app


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_article_generation_flow() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "topic": "Stratégie de contenu B2B en 2025",
            "keywords": "B2B,contenu,marketing",
            "tone": "professional",
            "target_words": 800,
            "language": "fr",
            "site_profile_id": None,
            "generate_images": False,
        }
        response = await client.post("/api/v1/articles/generate", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert "plan_id" in data











