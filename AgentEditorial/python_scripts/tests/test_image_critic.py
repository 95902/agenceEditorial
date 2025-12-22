"""Tests pour ImageCritic."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from python_scripts.image_generation.image_critic import (
    CritiqueResult,
    CritiqueScores,
    ImageCritic,
)


@pytest.fixture
def image_critic():
    """Fixture pour créer un ImageCritic."""
    return ImageCritic(model="qwen2.5vl:latest", ollama_url="http://localhost:11435")


@pytest.fixture
def sample_image_path(tmp_path):
    """Fixture pour créer une image de test."""
    image_path = tmp_path / "test_image.png"
    # Créer un fichier PNG minimal (juste un placeholder)
    image_path.write_bytes(b"fake_png_data")
    return image_path


@pytest.fixture
def good_critique_response():
    """Réponse JSON d'une bonne évaluation."""
    return {
        "response": json.dumps({
            "scores": {
                "sharpness": 9,
                "composition": 8,
                "no_text": 10,
                "coherence": 9,
                "professionalism": 9,
            },
            "score_total": 45,
            "verdict": "VALIDE",
            "has_unwanted_text": False,
            "problems": [],
            "suggestions": ["Excellent quality"],
        })
    }


@pytest.fixture
def bad_critique_response():
    """Réponse JSON d'une mauvaise évaluation."""
    return {
        "response": json.dumps({
            "scores": {
                "sharpness": 5,
                "composition": 4,
                "no_text": 3,
                "coherence": 5,
                "professionalism": 4,
            },
            "score_total": 21,
            "verdict": "REGENERER",
            "has_unwanted_text": True,
            "problems": ["Blurry", "Has text", "Poor composition"],
            "suggestions": ["Improve sharpness", "Remove text", "Better composition"],
        })
    }


class TestImageCritic:
    """Tests pour ImageCritic."""

    def test_parse_json_response_with_code_block(self, image_critic):
        """Test parsing JSON depuis un bloc de code."""
        response = '```json\n{"scores": {"sharpness": 8}, "verdict": "VALIDE"}\n```'
        result = image_critic._parse_json_response(response)
        assert result["verdict"] == "VALIDE"
        assert result["scores"]["sharpness"] == 8

    def test_parse_json_response_without_code_block(self, image_critic):
        """Test parsing JSON sans bloc de code."""
        response = '{"scores": {"sharpness": 8}, "verdict": "VALIDE"}'
        result = image_critic._parse_json_response(response)
        assert result["verdict"] == "VALIDE"

    def test_parse_json_response_fixes_trailing_comma(self, image_critic):
        """Test que les trailing commas sont corrigées."""
        response = '{"scores": {"sharpness": 8,}, "verdict": "VALIDE",}'
        result = image_critic._parse_json_response(response)
        assert result["verdict"] == "VALIDE"

    @pytest.mark.asyncio
    async def test_evaluate_good_image(
        self, image_critic, sample_image_path, good_critique_response
    ):
        """Test évaluation d'une bonne image."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = good_critique_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with patch(
                "python_scripts.image_generation.image_critic.get_vram_resource_manager"
            ) as mock_vram:
                mock_vram.return_value.acquire_for_vision = AsyncMock()

                result = await image_critic.evaluate(sample_image_path)

                assert result.verdict == "VALIDE"
                assert result.score_total == 45
                assert result.scores.sharpness == 9
                assert not result.has_unwanted_text

    @pytest.mark.asyncio
    async def test_evaluate_bad_image(
        self, image_critic, sample_image_path, bad_critique_response
    ):
        """Test évaluation d'une mauvaise image."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = bad_critique_response
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with patch(
                "python_scripts.image_generation.image_critic.get_vram_resource_manager"
            ) as mock_vram:
                mock_vram.return_value.acquire_for_vision = AsyncMock()

                result = await image_critic.evaluate(sample_image_path)

                assert result.verdict == "REGENERER"
                assert result.score_total == 21
                assert result.has_unwanted_text
                assert len(result.problems) > 0

    def test_should_retry_with_low_score(self, image_critic):
        """Test should_retry avec score faible."""
        result = CritiqueResult(
            scores=CritiqueScores(5, 5, 5, 5, 5),
            score_total=25,
            verdict="REGENERER",
            problems=["Poor quality"],
            suggestions=["Improve"],
            has_unwanted_text=False,
        )
        assert image_critic.should_retry(result) is True

    def test_should_retry_with_high_score(self, image_critic):
        """Test should_retry avec score élevé."""
        result = CritiqueResult(
            scores=CritiqueScores(9, 9, 10, 9, 9),
            score_total=46,
            verdict="VALIDE",
            problems=[],
            suggestions=[],
            has_unwanted_text=False,
        )
        assert image_critic.should_retry(result) is False

    def test_should_retry_with_threshold_score(self, image_critic):
        """Test should_retry avec score exactement au seuil."""
        # Score total = 35 (seuil)
        result = CritiqueResult(
            scores=CritiqueScores(7, 7, 7, 7, 7),
            score_total=35,
            verdict="VALIDE",
            problems=[],
            suggestions=[],
            has_unwanted_text=False,
        )
        assert image_critic.should_retry(result) is False

        # Score total = 34 (juste en dessous)
        result_below = CritiqueResult(
            scores=CritiqueScores(7, 7, 7, 6, 7),
            score_total=34,
            verdict="REGENERER",
            problems=["Minor issues"],
            suggestions=["Improve"],
            has_unwanted_text=False,
        )
        assert image_critic.should_retry(result_below) is True

    @pytest.mark.asyncio
    async def test_evaluate_detect_unwanted_text(
        self, image_critic, sample_image_path
    ):
        """Test détection de texte non désiré."""
        response_with_text = {
            "response": json.dumps({
                "scores": {
                    "sharpness": 8,
                    "composition": 7,
                    "no_text": 2,  # Score faible = texte présent
                    "coherence": 8,
                    "professionalism": 7,
                },
                "score_total": 32,
                "verdict": "REGENERER",
                "has_unwanted_text": True,
                "problems": ["Text visible in image"],
                "suggestions": ["Remove all text"],
            })
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = response_with_text
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with patch(
                "python_scripts.image_generation.image_critic.get_vram_resource_manager"
            ) as mock_vram:
                mock_vram.return_value.acquire_for_vision = AsyncMock()

                result = await image_critic.evaluate(sample_image_path)

                assert result.has_unwanted_text is True
                assert result.scores.no_text == 2




