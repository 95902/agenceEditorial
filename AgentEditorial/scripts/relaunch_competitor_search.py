#!/usr/bin/env python3
"""Relance une recherche de concurrents avec le nouveau max_competitors=35"""

import asyncio
import httpx
import time
import sys

API_BASE_URL = "http://localhost:8000/api/v1"


async def relaunch_and_analyze(domain: str = "innosys.fr", max_competitors: int = 35):
    """Relance la recherche et attend les résultats."""
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 1. Lancer la recherche
        print(f"🚀 Lancement de la recherche de concurrents pour {domain}")
        print(f"   max_competitors: {max_competitors}\n")
        
        response = await client.post(
            f"{API_BASE_URL}/competitors/search",
            json={"domain": domain, "max_competitors": max_competitors}
        )
        
        if response.status_code != 202:
            print(f"❌ Erreur: {response.status_code}")
            print(response.text)
            return
        
        data = response.json()
        execution_id = data.get("execution_id")
        
        print(f"✅ Recherche lancée")
        print(f"   Execution ID: {execution_id}\n")
        print("⏳ Attente de la complétion...")
        
        # 2. Poller le statut
        max_wait = 600  # 10 minutes max
        start_time = time.time()
        check_interval = 5  # Vérifier toutes les 5 secondes
        
        while time.time() - start_time < max_wait:
            await asyncio.sleep(check_interval)
            
            status_response = await client.get(
                f"{API_BASE_URL}/executions/{execution_id}"
            )
            
            if status_response.status_code != 200:
                print(f"⚠️ Erreur lors de la vérification du statut: {status_response.status_code}")
                continue
            
            status_data = status_response.json()
            status = status_data.get("status")
            
            if status == "completed":
                print(f"\n✅ Recherche terminée !\n")
                break
            elif status == "failed":
                print(f"\n❌ Recherche échouée")
                print(status_data.get("error", "Erreur inconnue"))
                return
            else:
                progress = status_data.get("progress", 0)
                print(f"   Statut: {status} ({progress}%)", end="\r")
        
        # 3. Récupérer les résultats
        print("\n📊 Récupération des résultats...\n")
        
        competitors_response = await client.get(
            f"{API_BASE_URL}/competitors/{domain}"
        )
        
        if competitors_response.status_code == 200:
            competitors_data = competitors_response.json()
            competitors = competitors_data.get("competitors", [])
            
            print("="*80)
            print("RÉSULTATS DE LA RECHERCHE")
            print("="*80)
            print(f"Nombre de concurrents trouvés: {len(competitors)}")
            print(f"Limite demandée: {max_competitors}\n")
            
            if competitors:
                print("Liste des concurrents:")
                for i, comp in enumerate(competitors, 1):
                    similarity = comp.get("similarity", 0)
                    validated = "✓" if comp.get("validated", False) else " "
                    print(f"{i:2d}. {comp.get('name', 'N/A'):<40} Similarité: {similarity:3d}% {validated}")
        else:
            print(f"⚠️ Impossible de récupérer les concurrents: {competitors_response.status_code}")


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "innosys.fr"
    max_comp = int(sys.argv[2]) if len(sys.argv) > 2 else 35
    
    asyncio.run(relaunch_and_analyze(domain, max_comp))


