#!/usr/bin/env python3
"""Script de test pour la génération d'article avec les nouveaux agents d'image."""

import asyncio
import json
import time
from uuid import UUID

import httpx


async def test_article_generation():
    """Teste la génération d'article avec les nouveaux agents d'image."""
    api_url = "http://localhost:8000/api/v1"
    
    # Données de test
    request_data = {
        "topic": "Sécurité cloud et protection des données",
        "keywords": "cloud, sécurité, données, protection",
        "tone": "professional",
        "target_words": 1500,
        "language": "fr",
        "generate_images": True,  # Activer la génération d'images
    }
    
    print("=" * 80)
    print("🧪 TEST DE GÉNÉRATION D'ARTICLE AVEC NOUVEAUX AGENTS")
    print("=" * 80)
    print(f"\n📋 Requête:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. Lancer la génération
        print(f"\n🚀 Lancement de la génération...")
        response = await client.post(
            f"{api_url}/articles/generate",
            json=request_data,
        )
        
        if response.status_code != 202:
            print(f"❌ Erreur: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        plan_id = result["plan_id"]
        print(f"✅ Génération lancée - Plan ID: {plan_id}")
        
        # 2. Surveiller le statut
        print(f"\n⏳ Surveillance du statut...")
        max_wait = 300  # 5 minutes max
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = await client.get(
                f"{api_url}/articles/{plan_id}/status"
            )
            
            if status_response.status_code != 200:
                print(f"❌ Erreur lors de la récupération du statut: {status_response.status_code}")
                break
            
            status_data = status_response.json()
            status = status_data["status"]
            progress = status_data.get("progress_percentage", 0)
            current_step = status_data.get("current_step", "")
            
            print(f"📊 Statut: {status} | Progression: {progress}% | Étape: {current_step}")
            
            if status == "validated":
                print(f"\n✅ Génération terminée avec succès!")
                break
            elif status == "failed":
                print(f"\n❌ Génération échouée")
                if "error_message" in status_data:
                    print(f"   Erreur: {status_data['error_message']}")
                break
            
            await asyncio.sleep(5)  # Attendre 5 secondes avant le prochain check
        
        # 3. Récupérer les détails complets
        print(f"\n📄 Récupération des détails...")
        detail_response = await client.get(f"{api_url}/articles/{plan_id}")
        
        if detail_response.status_code == 200:
            article_detail = detail_response.json()
            
            print(f"\n{'=' * 80}")
            print("📊 RÉSULTATS DE LA GÉNÉRATION")
            print("=" * 80)
            print(f"\n📋 Topic: {article_detail.get('topic')}")
            print(f"📊 Status: {article_detail.get('status')}")
            print(f"📈 Progression: {status_data.get('progress_percentage', 0)}%")
            
            # Afficher les images générées
            images = article_detail.get("images", [])
            print(f"\n🖼️  Images générées: {len(images)}")
            for idx, img in enumerate(images, 1):
                print(f"\n  Image #{idx}:")
                print(f"    ID: {img.get('id')}")
                print(f"    Type: {img.get('image_type')}")
                print(f"    Chemin: {img.get('local_path')}")
                print(f"    Alt text: {img.get('alt_text', 'N/A')}")
            
            # Vérifier les métadonnées d'image dans la base de données
            if images:
                print(f"\n📊 Vérification des métadonnées d'image...")
                # On pourrait faire une requête directe à la DB pour voir les détails
                print(f"   ℹ️  Utilisez le script analyze_image_generation.py pour voir les détails complets")
        
        print(f"\n{'=' * 80}")
        print("✅ TEST TERMINÉ")
        print("=" * 80)
        print(f"\n💡 Pour analyser l'image générée:")
        print(f"   python scripts/analyze_image_generation.py {plan_id}")


async def main():
    """Point d'entrée principal."""
    try:
        await test_article_generation()
    except httpx.ConnectError:
        print("❌ Erreur: Impossible de se connecter à l'API")
        print("   Assurez-vous que le serveur est démarré: make start")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

