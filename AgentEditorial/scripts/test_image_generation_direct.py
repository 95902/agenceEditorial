#!/usr/bin/env python3
"""Test direct de generate_article_image pour debug."""

import asyncio
from pathlib import Path

from python_scripts.agents.agent_image_generation import generate_article_image


async def test():
    """Test direct de la génération d'image."""
    print("🧪 Test direct de generate_article_image")
    print("=" * 80)
    
    site_profile = {
        "editorial_tone": "professional",
        "target_audience": {},
        "activity_domains": [],
    }
    
    try:
        print("\n📝 Génération de l'image...")
        result = await generate_article_image(
            site_profile=site_profile,
            article_topic="Test rapide",
            style="corporate_flat",
            max_retries=2,  # Réduire pour test rapide
        )
        
        print(f"\n✅ Résultat:")
        print(f"  image_path: {result.image_path}")
        print(f"  prompt_used: {result.prompt_used[:100] if result.prompt_used else 'None'}...")
        print(f"  quality_score: {result.quality_score}")
        print(f"  retry_count: {result.retry_count}")
        print(f"  final_status: {result.final_status}")
        print(f"  generation_params: {result.generation_params}")
        
        if result.image_path and result.image_path.exists():
            print(f"\n✅ Image trouvée à: {result.image_path}")
            print(f"   Taille: {result.image_path.stat().st_size / 1024:.2f} KB")
        else:
            print(f"\n⚠️  Image path invalide ou fichier non trouvé: {result.image_path}")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())








