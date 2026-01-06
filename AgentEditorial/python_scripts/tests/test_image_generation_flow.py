"""Tests d'intégration pour le flow complet de génération d'images."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from python_scripts.agents.agent_image_generation import (
    ImageGenerationResult,
    generate_article_image,
)
from python_scripts.database.crud_images import (
    get_images_by_site,
    get_recent_generations,
    save_image_generation,
    update_quality_score,
)


@pytest.fixture
def sample_site_profile():
    """Profil éditorial de test."""
    return {
        "editorial_tone": "professional",
        "activity_domains": {
            "primary": "technology",
            "secondary": ["cybersecurity"],
        },
        "style_features": {
            "colors": "blue, white",
        },
        "keywords": {},
    }


@pytest.fixture
def sample_image_path(tmp_path):
    """Chemin d'image de test."""
    image_path = tmp_path / "test_image.png"
    image_path.write_bytes(b"fake_png_data")
    return image_path


class TestImageGenerationFlow:
    """Tests pour le flow complet de génération d'images."""

    @pytest.mark.asyncio
    async def test_full_flow_success(
        self, sample_site_profile, sample_image_path, tmp_path
    ):
        """Test du flow complet avec succès."""
        # Mock de la génération d'image
        with patch(
            "python_scripts.agents.agent_image_generation.ZImageGenerator"
        ) as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator.generate_with_profile.return_value = sample_image_path
            mock_generator_class.get_instance.return_value = mock_generator

            # Mock de la critique (score élevé = succès)
            with patch(
                "python_scripts.agents.agent_image_generation.ImageCritic"
            ) as mock_critic_class:
                mock_critic = MagicMock()
                mock_critic.should_retry.return_value = False

                from python_scripts.image_generation import CritiqueResult, CritiqueScores

                mock_critic.evaluate = AsyncMock(
                    return_value=CritiqueResult(
                        scores=CritiqueScores(9, 9, 10, 9, 9),
                        score_total=46,
                        verdict="VALIDE",
                        problems=[],
                        suggestions=[],
                        has_unwanted_text=False,
                    )
                )
                mock_critic_class.return_value = mock_critic

                # Exécuter la génération
                result = await generate_article_image(
                    site_profile=sample_site_profile,
                    article_topic="cybersécurité cloud",
                    style="corporate_flat",
                    max_retries=3,
                )

                assert result.final_status == "success"
                assert result.quality_score == 46.0
                assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_flow_with_retry(
        self, sample_site_profile, sample_image_path, tmp_path
    ):
        """Test du flow avec retry."""
        # Mock de la génération d'image
        with patch(
            "python_scripts.agents.agent_image_generation.ZImageGenerator"
        ) as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator.generate_with_profile.return_value = sample_image_path
            mock_generator_class.get_instance.return_value = mock_generator

            # Mock de la critique avec retry (première tentative faible, deuxième bonne)
            with patch(
                "python_scripts.agents.agent_image_generation.ImageCritic"
            ) as mock_critic_class:
                from python_scripts.image_generation import CritiqueResult, CritiqueScores

                # Première tentative : score faible
                low_score = CritiqueResult(
                    scores=CritiqueScores(5, 5, 5, 5, 5),
                    score_total=25,
                    verdict="REGENERER",
                    problems=["Poor quality"],
                    suggestions=["Improve"],
                    has_unwanted_text=False,
                )

                # Deuxième tentative : score bon
                high_score = CritiqueResult(
                    scores=CritiqueScores(9, 9, 10, 9, 9),
                    score_total=46,
                    verdict="VALIDE",
                    problems=[],
                    suggestions=[],
                    has_unwanted_text=False,
                )

                mock_critic = MagicMock()
                mock_critic.should_retry.side_effect = [
                    True,  # Première tentative : retry nécessaire
                    False,  # Deuxième tentative : pas de retry
                ]
                mock_critic.evaluate = AsyncMock(side_effect=[low_score, high_score])
                mock_critic_class.return_value = mock_critic

                # Exécuter la génération avec max_retries=2
                result = await generate_article_image(
                    site_profile=sample_site_profile,
                    article_topic="cloud security",
                    style="tech_isometric",
                    max_retries=2,
                )

                assert result.final_status == "success"
                assert result.quality_score == 46.0
                assert result.retry_count == 1  # Une tentative de retry

    @pytest.mark.asyncio
    async def test_database_persistence(self, sample_site_profile):
        """Test de la persistance en base de données."""
        # Note: Ce test nécessiterait une vraie session DB ou des mocks
        # Pour l'instant, on teste juste que les fonctions existent et ont la bonne signature
        from sqlalchemy.ext.asyncio import AsyncSession

        # Mock de la session DB
        mock_db = MagicMock(spec=AsyncSession)

        # Test save_image_generation
        result = await save_image_generation(
            db=mock_db,
            site_profile_id=1,
            article_topic="test topic",
            prompt_used="test prompt",
            output_path="/tmp/test.png",
            generation_params={"width": 768, "height": 768},
            quality_score=40.0,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_vram_transitions(self):
        """Test des transitions VRAM (mock)."""
        # Ce test vérifie que VRAMResourceManager est utilisé correctement
        from python_scripts.image_generation.vram_resource_manager import (
            VRAMResourceManager,
        )

        vram_manager = VRAMResourceManager.get_instance()

        # Test acquire_for_zimage
        result = await vram_manager.acquire_for_zimage()
        assert result is True

        # Vérifier le statut
        status = vram_manager.get_vram_status()
        assert status.current_owner == "zimage"

        # Release
        vram_manager.release_all()
        status = vram_manager.get_vram_status()
        assert status.current_owner == "none"














