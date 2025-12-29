"""Script de démonstration pour le pipeline de génération d'images avec validation."""

import asyncio
import argparse
from pathlib import Path

from python_scripts.agents.agent_image_generation import generate_article_image
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Fonction principale pour la démonstration."""
    parser = argparse.ArgumentParser(
        description="Démonstration du pipeline de génération d'images avec validation IA"
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="Sujet de l'article pour lequel générer l'image",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="corporate_flat",
        choices=[
            "corporate_flat",
            "corporate_3d",
            "tech_isometric",
            "tech_gradient",
            "modern_minimal",
        ],
        help="Style d'image à utiliser",
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Chemin vers un fichier JSON avec le profil éditorial (optionnel)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Nombre maximum de tentatives",
    )

    args = parser.parse_args()

    # Construire le profil éditorial
    if args.profile:
        import json

        profile_path = Path(args.profile)
        if not profile_path.exists():
            logger.error("Profile file not found", path=str(profile_path))
            return

        with open(profile_path) as f:
            site_profile = json.load(f)
    else:
        # Profil éditorial par défaut pour la démo
        site_profile = {
            "editorial_tone": "professional",
            "activity_domains": {
                "primary": "technology",
                "secondary": ["cybersecurity", "cloud computing"],
            },
            "style_features": {
                "colors": "blue, white, silver",
            },
            "keywords": {},
        }

    logger.info(
        "Starting image generation demo",
        topic=args.topic,
        style=args.style,
        max_retries=args.max_retries,
    )

    try:
        # Générer l'image
        result = await generate_article_image(
            site_profile=site_profile,
            article_topic=args.topic,
            style=args.style,
            max_retries=args.max_retries,
        )

        # Afficher les résultats
        print("\n" + "=" * 60)
        print("RÉSULTAT DE LA GÉNÉRATION")
        print("=" * 60)
        print(f"Image générée: {result.image_path}")
        print(f"Statut: {result.final_status}")
        print(f"Nombre de tentatives: {result.retry_count + 1}")

        if result.quality_score:
            print(f"Score de qualité: {result.quality_score}/50")

        if result.critique_details:
            scores = result.critique_details.get("scores", {})
            print("\nScores détaillés:")
            print(f"  - Netteté: {scores.get('sharpness', 'N/A')}/10")
            print(f"  - Composition: {scores.get('composition', 'N/A')}/10")
            print(f"  - Absence de texte: {scores.get('no_text', 'N/A')}/10")
            print(f"  - Cohérence: {scores.get('coherence', 'N/A')}/10")
            print(f"  - Professionnalisme: {scores.get('professionalism', 'N/A')}/10")

            if result.critique_details.get("problems"):
                print("\nProblèmes détectés:")
                for problem in result.critique_details["problems"]:
                    print(f"  - {problem}")

            if result.critique_details.get("suggestions"):
                print("\nSuggestions d'amélioration:")
                for suggestion in result.critique_details["suggestions"]:
                    print(f"  - {suggestion}")

        print("\n" + "=" * 60)

    except Exception as e:
        logger.error("Image generation demo failed", error=str(e))
        print(f"\nErreur: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())








