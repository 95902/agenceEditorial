"""Tests unitaires pour la génération d'images Z-Image."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from python_scripts.image_generation import (
    ZImageGenerator,
    ImageModel,
    ImagePromptBuilder,
    ImageCache,
    ImageGenerationError,
    VRAMError,
)


class TestZImageGenerator:
    """Tests pour ZImageGenerator."""

    def test_singleton_pattern(self):
        """Test que ZImageGenerator est un singleton."""
        instance1 = ZImageGenerator.get_instance()
        instance2 = ZImageGenerator.get_instance()
        assert instance1 is instance2

    def test_singleton_prevents_direct_instantiation(self):
        """Test qu'on ne peut pas instancier directement."""
        # Réinitialiser l'instance pour ce test
        ZImageGenerator._instance = None
        instance1 = ZImageGenerator.get_instance()
        
        with pytest.raises(RuntimeError, match="singleton"):
            ZImageGenerator(ImageModel.Z_IMAGE_TURBO)

    @patch("python_scripts.image_generation.z_image_generator.DiffusionPipeline")
    @patch("python_scripts.image_generation.z_image_generator.torch")
    def test_model_loading(self, mock_torch, mock_pipeline_class):
        """Test le chargement du modèle."""
        mock_torch.cuda.is_available.return_value = True
        mock_torch.bfloat16 = "bfloat16"
        
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        
        generator = ZImageGenerator.get_instance()
        generator._load_model()
        
        assert generator._is_loaded is True
        mock_pipeline_class.from_pretrained.assert_called_once()

    def test_prompt_validation(self):
        """Test la validation des prompts."""
        generator = ZImageGenerator.get_instance()
        
        with pytest.raises(ImageGenerationError):
            generator.generate("")  # Prompt vide
        
        with pytest.raises(ImageGenerationError):
            generator.generate("test", width=100, height=100)  # Dimensions non multiples de 8

    def test_get_model_info(self):
        """Test la récupération des infos du modèle."""
        generator = ZImageGenerator.get_instance()
        info = generator.get_model_info()
        
        assert "model_type" in info
        assert "model_id" in info
        assert "is_loaded" in info


class TestImagePromptBuilder:
    """Tests pour ImagePromptBuilder."""

    def test_build_hero_image_prompt(self):
        """Test la construction d'un prompt hero."""
        builder = ImagePromptBuilder()
        profile = {
            "editorial_tone": "professional",
            "activity_domains": ["tech", "innovation"],
        }
        
        prompt = builder.build_hero_image_prompt(profile, style="corporate")
        assert "Professional hero image" in prompt
        assert "professional" in prompt

    def test_build_article_illustration_prompt(self):
        """Test la construction d'un prompt d'illustration."""
        builder = ImagePromptBuilder()
        prompt = builder.build_article_illustration_prompt(
            article_topic="AI",
            editorial_tone="professional",
            keywords=["machine learning", "neural networks"],
        )
        assert "Editorial illustration" in prompt
        assert "AI" in prompt

    def test_build_negative_prompt(self):
        """Test la construction d'un negative prompt."""
        builder = ImagePromptBuilder()
        negative = builder.build_negative_prompt()
        
        assert "blurry" in negative
        assert "low quality" in negative


class TestImageCache:
    """Tests pour ImageCache."""

    def test_cache_key_generation(self):
        """Test la génération de clés de cache."""
        cache = ImageCache(enabled=True)
        key1 = cache.get_cache_key("test prompt", 1024, 1024, "z-image-turbo")
        key2 = cache.get_cache_key("test prompt", 1024, 1024, "z-image-turbo")
        
        assert key1 == key2  # Même prompt = même clé
        
        key3 = cache.get_cache_key("different prompt", 1024, 1024, "z-image-turbo")
        assert key1 != key3  # Prompt différent = clé différente

    def test_cache_disabled(self):
        """Test que le cache peut être désactivé."""
        cache = ImageCache(enabled=False)
        assert cache.get_cached("test_key") is None

    def test_cache_stats(self):
        """Test les statistiques du cache."""
        cache = ImageCache(enabled=True)
        stats = cache.get_cache_stats()
        
        assert "total_files" in stats
        assert "total_size_mb" in stats


@pytest.mark.asyncio
class TestIntegration:
    """Tests d'intégration (nécessitent GPU)."""

    @pytest.mark.skip(reason="Requires GPU and model download")
    async def test_full_generation_workflow(self):
        """Test complet du workflow de génération."""
        generator = ZImageGenerator.get_instance()
        builder = ImagePromptBuilder()
        
        prompt = builder.build_article_illustration_prompt(
            article_topic="Test",
            editorial_tone="professional",
        )
        
        # Note: Ce test nécessite un GPU et le téléchargement du modèle
        # image_path = generator.generate(prompt, width=512, height=512)
        # assert image_path.exists()






