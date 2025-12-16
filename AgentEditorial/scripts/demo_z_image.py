"""Script de démonstration de Z-Image."""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.image_generation import (
    ZImageGenerator,
    ImageModel,
    ImagePromptBuilder,
)
from python_scripts.config.settings import settings


def main():
    """Fonction principale de démonstration."""
    print("=" * 60)
    print("Démonstration Z-Image Generator")
    print("=" * 60)

    # Initialiser le générateur
    print("\n1. Initialisation du générateur...")
    try:
        # Utiliser Z-Image Turbo par défaut (plus léger que FLUX)
        # Nécessite transformers >= 4.47.0 avec Qwen3Model support
        generator = ZImageGenerator.get_instance(ImageModel.Z_IMAGE_TURBO)
        print(f"✓ Générateur initialisé: {generator.model_type.value}")
    except Exception as e:
        print(f"✗ Erreur d'initialisation: {e}")
        print("\nNote: Assurez-vous que:")
        print("  - CUDA est disponible")
        print("  - Le modèle Z-Image est téléchargé")
        print("  - Les dépendances sont installées (diffusers, torch, etc.)")
        return

    # Afficher les infos du modèle
    print("\n2. Informations du modèle:")
    model_info = generator.get_model_info()
    for key, value in model_info.items():
        print(f"  {key}: {value}")

    # Initialiser le prompt builder
    print("\n3. Initialisation du prompt builder...")
    prompt_builder = ImagePromptBuilder()
    print("✓ Prompt builder initialisé")

    # Test 1 : Génération simple
    print("\n4. Test 1 : Génération simple")
    print("-" * 60)
    simple_prompt = "A modern tech startup office, natural lighting, minimalist design"
    print(f"Prompt: {simple_prompt}")
    
    try:
        image_path = generator.generate(
            prompt=simple_prompt,
            width=1024,
            height=1024,
        )
        print(f"✓ Image générée: {image_path}")
    except Exception as e:
        print(f"✗ Erreur de génération: {e}")
        print("  Note: Ce test nécessite un GPU et le modèle chargé")

    # Test 2 : Avec prompt builder
    print("\n5. Test 2 : Prompt builder")
    print("-" * 60)
    profile = {
        "editorial_tone": "professional",
        "activity_domains": ["fintech", "technology"],
        "target_audience": "B2B decision makers",
    }
    
    hero_prompt = prompt_builder.build_hero_image_prompt(profile, style="cinematic")
    print(f"Prompt généré: {hero_prompt}")
    
    try:
        image_path = generator.generate(
            prompt=hero_prompt,
            width=1024,
            height=1024,
        )
        print(f"✓ Image générée: {image_path}")
    except Exception as e:
        print(f"✗ Erreur de génération: {e}")

    # Test 3 : Prompt d'article
    print("\n6. Test 3 : Illustration d'article")
    print("-" * 60)
    article_prompt = prompt_builder.build_article_illustration_prompt(
        article_topic="Intelligence Artificielle",
        editorial_tone="professional",
        keywords=["machine learning", "deep learning", "neural networks"],
    )
    print(f"Prompt: {article_prompt}")
    
    try:
        image_path = generator.generate(
            prompt=article_prompt,
            width=1024,
            height=1024,
        )
        print(f"✓ Image générée: {image_path}")
    except Exception as e:
        print(f"✗ Erreur de génération: {e}")

    # Test 4 : Negative prompt
    print("\n7. Test 4 : Negative prompt")
    print("-" * 60)
    negative_prompt = prompt_builder.build_negative_prompt()
    print(f"Negative prompt: {negative_prompt}")
    
    try:
        image_path = generator.generate(
            prompt="A beautiful landscape",
            negative_prompt=negative_prompt,
            width=512,
            height=512,
        )
        print(f"✓ Image générée avec negative prompt: {image_path}")
    except Exception as e:
        print(f"✗ Erreur de génération: {e}")

    # Résumé
    print("\n" + "=" * 60)
    print("Démonstration terminée")
    print("=" * 60)
    print("\nLes images générées sont sauvegardées dans:")
    print(f"  {settings.article_images_dir}")
    print("\nPour utiliser le générateur dans votre code:")
    print("  from python_scripts.image_generation import ZImageGenerator, ImagePromptBuilder")
    print("  generator = ZImageGenerator.get_instance()")
    print("  image_path = generator.generate('your prompt here')")


if __name__ == "__main__":
    main()

