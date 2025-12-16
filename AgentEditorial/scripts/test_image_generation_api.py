#!/usr/bin/env python3
"""Test de la route API de génération d'image."""

import asyncio
import json

import httpx


async def test_image_generation():
    """Teste la route de génération d'image."""
    api_url = "http://localhost:8000/api/v1"
    
    # Données de test
    request_data = {
        "prompt": "A modern cybersecurity shield protecting digital data, flat design style, corporate professional aesthetic",
        "negative_prompt": "text, words, letters, realistic photo",
        "width": 768,
        "height": 768,
        "steps": 12,
        "guidance_scale": 7.5,
        "style": "corporate_flat",
        "save_to_db": True,
    }
    
    print("=" * 80)
    print("🧪 TEST DE LA ROUTE DE GÉNÉRATION D'IMAGE")
    print("=" * 80)
    print(f"\n📋 Requête:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        print(f"\n🚀 Génération de l'image...")
        try:
            response = await client.post(
                f"{api_url}/images/generate",
                json=request_data,
            )
            
            if response.status_code != 200:
                print(f"❌ Erreur: {response.status_code}")
                print(response.text)
                return
            
            result = response.json()
            
            print(f"\n✅ Image générée avec succès!")
            print(f"\n{'=' * 80}")
            print("📊 RÉSULTATS")
            print("=" * 80)
            print(f"\n✅ Success: {result.get('success')}")
            print(f"📁 Image path: {result.get('image_path')}")
            print(f"📝 Prompt utilisé: {result.get('prompt_used')[:100]}...")
            print(f"⏱️  Temps de génération: {result.get('generation_time_seconds', 0):.2f} secondes")
            print(f"🔄 Retry count: {result.get('retry_count')}")
            print(f"📊 Statut final: {result.get('final_status')}")
            print(f"💬 Message: {result.get('message')}")
            
            if result.get('generation_params'):
                print(f"\n⚙️  Paramètres de génération:")
                print(json.dumps(result.get('generation_params'), indent=2, ensure_ascii=False))
            
        except httpx.ConnectError:
            print("❌ Erreur: Impossible de se connecter à l'API")
            print("   Assurez-vous que le serveur est démarré: make start")
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_image_generation())

