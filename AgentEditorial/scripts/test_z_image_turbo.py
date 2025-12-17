#!/usr/bin/env python3
"""Script de test pour Z-Image Turbo avec vérification VRAM."""

import sys
import time
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.image_generation import (
    ImageModel,
    ImagePromptBuilder,
    ZImageGenerator,
)
from python_scripts.image_generation.vram_manager import get_vram_manager


def test_vram_manager():
    """Test du gestionnaire VRAM."""
    print("=" * 60)
    print("Test 1 : Gestionnaire VRAM")
    print("=" * 60)

    vram_manager = get_vram_manager()
    vram_info = vram_manager.check_available_vram()

    if vram_info:
        print(f"✓ VRAM totale : {vram_info.total_gb:.2f} GB")
        print(f"✓ VRAM utilisée : {vram_info.used_gb:.2f} GB ({vram_info.used_percent:.1f}%)")
        print(f"✓ VRAM libre : {vram_info.free_gb:.2f} GB")
    else:
        print("✗ Impossible de vérifier la VRAM (nvidia-smi non disponible)")

    processes = vram_manager.get_gpu_processes()
    if processes:
        print(f"\nProcessus utilisant la GPU ({len(processes)}):")
        for proc in processes:
            print(f"  - PID {proc.pid}: {proc.name} - {proc.memory_gb:.2f} GB")
    else:
        print("\nAucun processus n'utilise actuellement la GPU")

    # Test estimation mémoire
    print("\nEstimation mémoire pour différents modèles (1024x1024):")
    for model_type in [ImageModel.Z_IMAGE_TURBO, ImageModel.FLUX_SCHNELL]:
        estimated = vram_manager.estimate_model_memory(model_type, 1024, 1024)
        print(f"  - {model_type.value}: ~{estimated:.2f} GB")

    # Test résolution recommandée
    print("\nRésolution recommandée selon VRAM disponible:")
    recommended = vram_manager.get_recommended_resolution(
        ImageModel.Z_IMAGE_TURBO, (768, 768)
    )
    print(f"  - Recommandée : {recommended[0]}x{recommended[1]}")


def test_model_loading():
    """Test du chargement du modèle Z-Image Turbo."""
    print("\n" + "=" * 60)
    print("Test 2 : Chargement du modèle Z-Image Turbo")
    print("=" * 60)

    try:
        generator = ZImageGenerator.get_instance(ImageModel.Z_IMAGE_TURBO)
        print(f"✓ Générateur initialisé : {generator.model_type.value}")

        model_info = generator.get_model_info()
        print(f"✓ Modèle ID : {model_info['model_id']}")
        print(f"✓ Modèle chargé : {model_info['is_loaded']}")
        print(f"✓ CUDA disponible : {model_info['cuda_available']}")
        if model_info.get("cuda_device"):
            print(f"✓ Device CUDA : {model_info['cuda_device']}")

        # Tenter de charger le modèle
        if not generator.is_loaded:
            print("\nChargement du modèle...")
            start_time = time.time()
            generator._load_model()
            load_time = time.time() - start_time
            print(f"✓ Modèle chargé en {load_time:.2f} secondes")
        else:
            print("✓ Modèle déjà chargé")

        return generator

    except Exception as e:
        print(f"✗ Erreur lors du chargement : {e}")
        return None


def test_image_generation(generator):
    """Test de génération d'image avec différentes résolutions."""
    print("\n" + "=" * 60)
    print("Test 3 : Génération d'images")
    print("=" * 60)

    if generator is None:
        print("✗ Générateur non disponible - test annulé")
        return

    prompt_builder = ImagePromptBuilder()
    prompt = prompt_builder.build_article_illustration_prompt(
        article_topic="Test Z-Image Turbo",
        editorial_tone="professional",
        keywords=["test", "validation"],
    )

    print(f"Prompt : {prompt[:80]}...")

    # Test avec résolution recommandée
    vram_manager = get_vram_manager()
    recommended = vram_manager.get_recommended_resolution(
        ImageModel.Z_IMAGE_TURBO, (512, 512)
    )

    resolutions = [
        recommended,
        (512, 512),
        (384, 384),
    ]

    for width, height in resolutions:
        print(f"\nTest génération {width}x{height}...")
        try:
            start_time = time.time()
            image_path = generator.generate(
                prompt=prompt,
                width=width,
                height=height,
                filename=f"test_z_image_turbo_{width}x{height}.png",
            )
            generation_time = time.time() - start_time

            print(f"✓ Image générée : {image_path}")
            print(f"✓ Temps de génération : {generation_time:.2f} secondes")

            # Vérifier la VRAM après génération
            vram_info = vram_manager.check_available_vram()
            if vram_info:
                print(f"✓ VRAM libre après génération : {vram_info.free_gb:.2f} GB")

            # Arrêter après le premier succès
            break

        except Exception as e:
            print(f"✗ Erreur : {e}")
            if "out of memory" in str(e).lower():
                print("  → VRAM insuffisante, test avec résolution plus basse...")
                continue
            else:
                print("  → Erreur non liée à la VRAM")
                break


def test_retry_mechanism(generator):
    """Test du mécanisme de retry avec réduction de résolution."""
    print("\n" + "=" * 60)
    print("Test 4 : Mécanisme de retry")
    print("=" * 60)

    if generator is None:
        print("✗ Générateur non disponible - test annulé")
        return

    prompt = "A beautiful landscape with mountains and a lake, professional photography"

    print("Test avec generate_with_retry()...")
    try:
        start_time = time.time()
        image_path = generator.generate_with_retry(
            prompt=prompt,
            width=768,  # Résolution initiale
            height=768,
            max_retries=4,
            filename="test_retry_mechanism.png",
        )
        generation_time = time.time() - start_time

        print(f"✓ Image générée avec retry : {image_path}")
        print(f"✓ Temps total : {generation_time:.2f} secondes")

    except Exception as e:
        print(f"✗ Erreur lors du retry : {e}")


def compare_models():
    """Compare Z-Image Turbo avec FLUX Schnell."""
    print("\n" + "=" * 60)
    print("Test 5 : Comparaison des modèles")
    print("=" * 60)

    vram_manager = get_vram_manager()

    print("Comparaison de la consommation VRAM estimée :")
    for model_type in [ImageModel.Z_IMAGE_TURBO, ImageModel.FLUX_SCHNELL]:
        estimated_512 = vram_manager.estimate_model_memory(model_type, 512, 512)
        estimated_1024 = vram_manager.estimate_model_memory(model_type, 1024, 1024)
        print(f"\n{model_type.value}:")
        print(f"  - 512x512 : ~{estimated_512:.2f} GB")
        print(f"  - 1024x1024 : ~{estimated_1024:.2f} GB")

    # Calculer l'économie
    turbo_512 = vram_manager.estimate_model_memory(ImageModel.Z_IMAGE_TURBO, 512, 512)
    flux_512 = vram_manager.estimate_model_memory(ImageModel.FLUX_SCHNELL, 512, 512)
    economy = flux_512 - turbo_512
    economy_percent = (economy / flux_512) * 100 if flux_512 > 0 else 0

    print(f"\n✓ Économie VRAM avec Z-Image Turbo (512x512) : {economy:.2f} GB ({economy_percent:.1f}%)")


def main():
    """Fonction principale."""
    print("=" * 60)
    print("Tests Z-Image Turbo avec gestion VRAM hybride")
    print("=" * 60)

    # Test 1 : Gestionnaire VRAM
    test_vram_manager()

    # Test 2 : Chargement du modèle
    generator = test_model_loading()

    # Test 3 : Génération d'images
    if generator:
        test_image_generation(generator)

        # Test 4 : Mécanisme de retry
        test_retry_mechanism(generator)

    # Test 5 : Comparaison
    compare_models()

    print("\n" + "=" * 60)
    print("Tests terminés")
    print("=" * 60)
    print("\nRésumé :")
    print("  - Z-Image Turbo est plus léger que FLUX Schnell")
    print("  - La gestion VRAM hybride adapte automatiquement la résolution")
    print("  - Le mécanisme de retry réduit la résolution en cas d'erreur VRAM")
    print("\nPour utiliser dans votre code :")
    print("  from python_scripts.image_generation import ZImageGenerator, ImageModel")
    print("  generator = ZImageGenerator.get_instance(ImageModel.Z_IMAGE_TURBO)")
    print("  image_path = generator.generate_with_retry('your prompt')")


if __name__ == "__main__":
    main()



