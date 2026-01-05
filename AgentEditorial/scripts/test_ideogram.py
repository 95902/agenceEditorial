#!/usr/bin/env python3
"""Test de l'intégration Ideogram.

Usage: python scripts/test_ideogram.py
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.image_generation import (
    IdeogramClient,
    ImageGenerator,
)


async def test_ideogram_client():
    """Test 1: IdeogramClient direct."""
    print("=" * 60)
    print("Test 1: IdeogramClient direct")
    print("=" * 60)

    try:
        client = IdeogramClient.get_instance()

        result = await client.generate(
            prompt="cybersecurity shield icon, flat design, blue colors",
            style_type="DESIGN",
            aspect_ratio="ASPECT_1_1",
        )

        print(f"✓ Image générée avec succès")
        print(f"  URL: {result.url}")
        print(f"  Prompt amélioré: {result.prompt[:100]}...")
        print(f"  Résolution: {result.resolution}")
        print(f"  Temps: {result.generation_time:.2f}s")

        # Télécharger l'image
        output_path = Path("outputs/images/test_ideogram_direct.png")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        downloaded_path = await client.download_image(result.url, output_path)
        print(f"✓ Image téléchargée: {downloaded_path}")

        await client.close()
        return True

    except Exception as e:
        print(f"✗ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_image_generator():
    """Test 2: ImageGenerator."""
    print("\n" + "=" * 60)
    print("Test 2: ImageGenerator")
    print("=" * 60)

    try:
        generator = ImageGenerator.get_instance()

        result = await generator.generate(
            prompt="cloud computing security, padlock, shield",
            style="corporate_flat",
            aspect_ratio="1:1",
        )

        if result.success:
            print(f"✓ Image générée avec succès")
            print(f"  Chemin: {result.image_path}")
            print(f"  Provider: {result.provider}")
            print(f"  Prompt utilisé: {result.prompt_used[:100]}...")
            print(f"  Temps: {result.generation_time:.2f}s")
            print(f"  Métadonnées: {result.metadata}")
            return True
        else:
            print(f"✗ Échec: {result.error}")
            return False

    except Exception as e:
        print(f"✗ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_generate_from_profile():
    """Test 3: Generate from profile."""
    print("\n" + "=" * 60)
    print("Test 3: Generate from profile")
    print("=" * 60)

    try:
        generator = ImageGenerator.get_instance()

        site_profile = {
            "editorial_tone": "professional",
            "activity_domains": ["cybersecurity", "cloud"],
            "target_audience": "B2B tech",
        }

        result = await generator.generate_from_profile(
            site_profile=site_profile,
            article_topic="sécurité des données cloud",
        )

        if result.success:
            print(f"✓ Image générée depuis profil éditorial")
            print(f"  Chemin: {result.image_path}")
            print(f"  Prompt utilisé: {result.prompt_used[:150]}...")
            print(f"  Temps: {result.generation_time:.2f}s")
            return True
        else:
            print(f"✗ Échec: {result.error}")
            return False

    except Exception as e:
        print(f"✗ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Fonction principale."""
    print("\n🚀 Test de l'intégration Ideogram\n")

    results = []

    # Test 1: Client direct
    results.append(await test_ideogram_client())

    # Test 2: ImageGenerator
    results.append(await test_image_generator())

    # Test 3: Depuis profil
    results.append(await test_generate_from_profile())

    # Résumé
    print("\n" + "=" * 60)
    print("Résumé des tests")
    print("=" * 60)
    print(f"Tests réussis: {sum(results)}/{len(results)}")

    if all(results):
        print("✓ Tous les tests ont réussi!")
        return 0
    else:
        print("✗ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)













